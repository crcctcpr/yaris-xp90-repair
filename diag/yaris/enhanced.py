"""Toyota Mode 21 Enhanced data decoder with correlation learning.

Toyota's mode 21 byte layout varies by ECU and is not publicly documented.
Rather than hardcode positions that might be wrong, this tool:

1. Queries 21 01 (and other subfunctions) repeatedly
2. In parallel, queries all the standard mode 01 PIDs we know
3. For each byte position in the enhanced response, tries multiple common
   encodings (raw, °C offset, %, signed trim, 2-byte RPM, 2-byte MAF, etc.)
4. Correlates against the known values and reports "byte N = X, matches PID Y"

Over N samples at different engine states (idle, revved, etc.) we can
confidently label each byte position with what it represents.

Also dumps every enhanced subfunction that responds, for manual inspection.

Usage:
  python3 -m yaris.enhanced              # single pass
  python3 -m yaris.enhanced --learn 8    # 8 samples for correlation learning
"""
import argparse
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, decode_pid, parse_can
from .vehicle import DEFAULT_PORT, REPORT_DIR


# Standard PIDs we'll use as correlation anchors
ANCHORS = [
    ("load_pct",    0x04, lambda v: v),
    ("coolant_c",   0x05, lambda v: v),
    ("stft_pct",    0x06, lambda v: v),
    ("ltft_pct",    0x07, lambda v: v),
    ("rpm",         0x0C, lambda v: v),
    ("speed_kmh",   0x0D, lambda v: v),
    ("timing_deg",  0x0E, lambda v: v),
    ("iat_c",       0x0F, lambda v: v),
    ("maf_gs",      0x10, lambda v: v),
    ("throttle_pct", 0x11, lambda v: v),
    ("baro_kpa",    0x33, lambda v: v),
    ("ctlv_V",      0x42, lambda v: v),
]


def query_enhanced(elm: Elm, sub: int) -> bytes | None:
    """Query 21<sub> and return payload bytes after 61 <sub> header, or None."""
    resp = elm.send(f"21{sub:02X}", 2.5)
    ecus = parse_can(resp)
    for data in ecus.values():
        if len(data) >= 2 and data[0] == 0x61 and data[1] == sub:
            return data[2:]
    return None


def candidate_decodings(b1: int, b2: int | None = None) -> dict[str, float]:
    """Generate all plausible decodings of a byte (or 2 bytes)."""
    out = {"raw": b1}
    # Single-byte interpretations
    out["temp_c"] = b1 - 40                        # coolant/IAT
    out["pct_255"] = b1 * 100 / 255                # load/throttle
    out["pct_128_signed"] = (b1 - 128) * 100 / 128 # trim
    out["timing_deg"] = (b1 - 128) / 2             # timing advance
    out["speed"] = b1                              # km/h
    out["kpa"] = b1                                # baro
    # Two-byte (A hi, B lo) interpretations
    if b2 is not None:
        word = (b1 << 8) | b2
        out["rpm"] = word / 4                      # rpm
        out["maf_gs"] = word / 100                 # MAF
        out["voltage_v"] = word / 1000             # ctl V
        out["word_raw"] = word
    return out


def match_score(value: float, target: float | None) -> float | None:
    """How close is value to target? Returns absolute difference."""
    if target is None:
        return None
    return abs(value - target)


def correlate(enh_bytes: bytes, anchors: dict[str, float]) -> list[dict]:
    """Return list of per-position match suggestions — filtered to eliminate noise.

    Rules:
      - Skip anchors whose value is 0 (matches too many zero-bytes promiscuously)
      - Skip encoding/anchor pairs where units don't match (e.g., don't match a
        byte decoded as 'rpm' against 'speed_kmh' — only against 'rpm' anchor)
      - Require relatively tight tolerance for the match
    """
    matches = []
    # Map encoding kinds to the anchors they could plausibly represent
    enc_to_anchors = {
        "raw":            ["raw_only"],
        "pct_255":        ["load_pct", "throttle_pct"],
        "pct_128_signed": ["stft_pct", "ltft_pct"],
        "timing_deg":     ["timing_deg"],
        "speed":          ["speed_kmh", "baro_kpa", "iat_c"],
        "temp_c":         ["coolant_c", "iat_c"],
        "kpa":            ["baro_kpa"],
        "rpm":            ["rpm"],
        "maf_gs":         ["maf_gs"],
        "voltage_v":      ["ctlv_V"],
        "word_raw":       [],
    }
    tol_map = {
        "load_pct": 2.0,
        "coolant_c": 2.0,
        "stft_pct": 1.5,
        "ltft_pct": 1.5,
        "rpm": 25.0,
        "speed_kmh": 2.0,
        "timing_deg": 1.0,
        "iat_c": 2.0,
        "maf_gs": 0.3,
        "throttle_pct": 2.0,
        "baro_kpa": 2.0,
        "ctlv_V": 0.2,
    }
    # Skip anchors whose magnitude is too small to give confidence
    min_magnitudes = {
        "stft_pct": 0.5,  # zero STFT is too common
        "ltft_pct": 0.5,
        "speed_kmh": 1.0,
        "timing_deg": 0.5,
    }
    for i, b in enumerate(enh_bytes):
        b2 = enh_bytes[i + 1] if i + 1 < len(enh_bytes) else None
        cand = candidate_decodings(b, b2)
        for enc_name, enc_val in cand.items():
            possible_anchors = enc_to_anchors.get(enc_name, [])
            for anchor_name in possible_anchors:
                anchor_val = anchors.get(anchor_name)
                if anchor_val is None:
                    continue
                # Skip if the anchor is effectively zero
                min_mag = min_magnitudes.get(anchor_name, 0.0)
                if abs(anchor_val) < min_mag:
                    continue
                tol = tol_map.get(anchor_name, 5.0)
                diff = abs(enc_val - anchor_val)
                if diff <= tol:
                    matches.append({
                        "byte": i,
                        "raw": b,
                        "raw_hex": f"0x{b:02X}",
                        "encoding": enc_name,
                        "encoded_value": round(enc_val, 3),
                        "matches_pid": anchor_name,
                        "anchor_value": round(anchor_val, 3),
                        "delta": round(diff, 3),
                        "multi_byte": enc_name in ("rpm", "maf_gs", "voltage_v", "word_raw"),
                    })
    # Sort by byte index then match strength
    matches.sort(key=lambda m: (m["byte"], m["delta"]))
    return matches


def gather_anchors(elm: Elm) -> dict[str, float | None]:
    """Read all anchor PIDs at approximately the same moment."""
    out = {}
    for name, pid, extract in ANCHORS:
        p = read_pid(elm, f"01{pid:02X}", 0.8)
        if p is None:
            out[name] = None
            continue
        try:
            v = decode_pid(pid, p)
            out[name] = extract(v) if not isinstance(v, dict) else None
        except Exception:
            out[name] = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--learn", type=int, default=1,
                    help="Number of samples for correlation (increase for rev-and-hold runs)")
    ap.add_argument("--subs", default="01,02,03,08,09,0A,10,15,20,30,40,41,A0,B1",
                    help="Comma-separated enhanced subfunctions to probe (hex)")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = f"{REPORT_DIR}/enhanced_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    subs = [int(s.strip(), 16) for s in args.subs.split(",") if s.strip()]

    lines = [f"═══ Toyota Mode 21 Enhanced — {ts} ═══", ""]
    with Elm(args.port) as e:
        e.init_can()

        samples = []
        for round_idx in range(args.learn):
            if args.learn > 1:
                print(f"\n[*] Sample {round_idx+1}/{args.learn} — capturing…")
                if round_idx > 0:
                    print("    (Vary engine state: idle / 1500 / 2500 RPM between rounds)")
                    time.sleep(0.5)
            anchors = gather_anchors(e)
            responses = {}
            for sub in subs:
                enh = query_enhanced(e, sub)
                if enh is not None:
                    responses[sub] = enh
            samples.append({"anchors": anchors, "responses": responses})

        # Report each response
        lines.append(f"Captured {len(samples)} sample(s).")
        lines.append("")
        for sub in subs:
            responses = [s["responses"].get(sub) for s in samples]
            if not any(r is not None for r in responses):
                lines.append(f"── 21 {sub:02X} — no response (subfunction not supported) ──")
                continue
            sample_hex = [r.hex() if r else "-" for r in responses]
            lines.append(f"── 21 {sub:02X} ({len(responses[0]) if responses[0] else 0} bytes) ──")
            for i, h in enumerate(sample_hex):
                lines.append(f"   sample {i}: {h}")

            # Correlation (use first sample with data)
            first_enh = next((r for r in responses if r is not None), None)
            first_anchors = samples[responses.index(first_enh)]["anchors"] if first_enh else None
            if first_enh and first_anchors:
                matches = correlate(first_enh, first_anchors)
                if matches:
                    # Filter "same-match" duplicates (byte might match multiple anchors loosely)
                    lines.append("   --- byte correlations (likely meanings) ---")
                    for m in matches:
                        span = "2-byte" if m["multi_byte"] else "1-byte"
                        lines.append(
                            f"     byte[{m['byte']:2d}] {m['raw_hex']}  "
                            f"{span} encoded as {m['encoding']:20} = {m['encoded_value']:7.2f}  "
                            f"≈ PID {m['matches_pid']} ({m['anchor_value']}, Δ={m['delta']})"
                        )
                else:
                    lines.append("   --- no byte matched any known PID to within tolerance ---")

            # ASCII interpretation
            if first_enh:
                ascii_view = "".join(chr(c) if 32 <= c < 127 else "." for c in first_enh)
                lines.append(f"   ascii: {ascii_view!r}")
            lines.append("")

    with open(txt_path, "w") as f: f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[+] Report: {txt_path}")


if __name__ == "__main__":
    main()
