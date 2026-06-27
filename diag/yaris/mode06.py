"""Mode 06 — On-Board Monitor Test Results.

Walks all supported MIDs, queries each, decodes per-TID test values using
the SAE J1979 Unit-and-Scaling-ID (UAS_ID) table. Produces a ranked report
with pass/fail against min/max limits.

This is the GOLD-STANDARD emissions diagnostic: instead of "Catalyst monitor
complete ✓" it tells you *actual* cat efficiency ratio, O2 sensor response
time in ms, EGR flow %, etc.

Usage:
  python3 -m yaris.mode06
"""
import argparse
import os
from datetime import datetime

from .elm import Elm
from .obd import read_pid, parse_can
from .vehicle import DEFAULT_PORT, REPORT_DIR


# Toyota / SAE J1979 monitor IDs we might encounter on 1NR-FE
MID_NAMES = {
    0x01: "Misfire counts (general)",
    0x02: "Misfire cylinder 1",
    0x03: "Misfire cylinder 2",
    0x04: "Misfire cylinder 3",
    0x05: "Misfire cylinder 4",
    0x21: "Catalyst Bank 1 Monitor",
    0x31: "EGR Monitor",
    0x39: "EVAP Monitor (0.040 leak)",
    0x3A: "EVAP Monitor (0.020 leak)",
    0x3B: "EVAP Monitor — purge flow",
    0x3C: "EVAP Monitor — vent",
    0x41: "O2 B1S1 Rich→Lean sensor",
    0x42: "O2 B1S1 Lean→Rich sensor",
    0x43: "O2 B1S1 Low-to-switch voltage",
    0x44: "O2 B1S1 High-to-switch voltage",
    0x45: "O2 B1S1 Low-to-high time",
    0x46: "O2 B1S1 High-to-low time",
    0x47: "O2 B1S1 Min voltage",
    0x48: "O2 B1S1 Max voltage",
    0x49: "O2 B1S1 Transition time",
    0x4A: "O2 B1S1 Sensor period",
    0x81: "O2 B1S2 Rich→Lean",
    0x82: "O2 B1S2 Lean→Rich",
    0xA1: "O2 B1S2 Low-to-high time",
    0xA2: "O2 B1S2 High-to-low time",
}

# TIDs (Test IDs) — specific tests within a monitor
TID_NAMES = {
    0x01: "Test 1",
    0x05: "Test 5",
    0x07: "Test 7",
    0x0B: "Test 0x0B",
    0x80: "Test 0x80",
    0x81: "Test 0x81",
    0x82: "Test 0x82",
    0x83: "Test 0x83",
    0x84: "Test 0x84",
    0x85: "Test 0x85",
    0x86: "Test 0x86",
    0x87: "Test 0x87",
    0x88: "Test 0x88",
    0x8B: "Test 0x8B",
    0x90: "Cat switch ratio B1S1/B1S2",
}

# UAS_ID → (unit, scale, signed)
# Per SAE J1979, TABLE A3 (expanded subset)
UAS = {
    0x01: ("Raw",           1.0,     False),
    0x02: ("Raw",           0.1,     False),
    0x03: ("Raw",           0.01,    False),
    0x04: ("Raw",           0.001,   False),
    0x05: ("Raw",           0.0000305, False),  # 1/32768
    0x06: ("Raw",           0.000122, False),
    0x07: ("%",             0.05,    False),
    0x08: ("%",             0.005,   False),
    0x09: ("ppm",           1.0,     False),
    0x0A: ("V",             0.122,   False),    # volts, 0.122 mV/bit
    0x0B: ("V",             0.001,   False),
    0x0C: ("V",             0.01,    False),
    0x0D: ("mA",            0.00391, False),
    0x0E: ("mA",            0.001,   False),
    0x0F: ("mA",            0.01,    False),
    0x10: ("s",             1.0,     False),
    0x11: ("s",             0.1,     False),
    0x12: ("s",             1.0,     False),
    0x13: ("ms",            1.0,     False),
    0x14: ("ms",            10.0,    False),
    0x15: ("ms",            0.01,    False),
    0x16: ("kPa",           0.0039,  False),
    0x17: ("kPa",           0.01,    False),
    0x18: ("kPa",           0.0117,  False),
    0x19: ("kPa",           0.079,   False),
    0x1A: ("kPa",           1.0,     False),
    0x1B: ("kPa",           10.0,    False),
    0x1C: ("°C",            1.0,     False),    # offset -40 often handled elsewhere
    0x1D: ("°C",            0.1,     False),
    0x1E: ("°",             0.01,    True),
    0x1F: ("°",             0.5,     True),
    0x20: ("equiv ratio",   0.0000305, False),
    0x21: ("equiv ratio",   0.0039,  False),
    0x22: ("Hz",            0.25,    False),
    0x23: ("Hz",            1.0,     False),
    0x24: ("Hz",            1000,    False),
    0x25: ("counts",        1.0,     False),
    0x26: ("counts",        1.0,     False),
    0x27: ("km",            1.0,     False),
    0x28: ("mV/ms",         0.1,     True),
    0x29: ("g/s",           0.01,    False),
    0x2A: ("g/s",           0.001,   False),
    0x2B: ("Pa/s",          0.25,    False),
    0x2C: ("kg/h",          0.05,    False),
    0x2D: ("switch",        1.0,     False),
    0x2E: ("g/cyl",         0.01,    False),
    0x2F: ("mg/stroke",     0.01,    False),
    0x30: ("ratio",         0.03125, False),
    0x31: ("μs",            1.0,     False),
    0x32: ("mm",            0.25,    False),
    0x33: ("kOhm",          1.0,     False),
    0x34: ("Ohm",           1.0,     False),
    0x35: ("mOhm",          1.0,     False),
    0x36: ("bit string",    1.0,     False),
    0x37: ("UInt",          1.0,     False),
    0x38: ("SInt",          1.0,     True),
    # 0x80-0xFF reserved for manufacturer-specific scalings
}


def decode_value(raw: int, uas_id: int, signed_hint: bool = False) -> tuple[float, str]:
    """Decode a 16-bit raw value via UAS_ID. Returns (value, unit_str)."""
    unit, scale, signed = UAS.get(uas_id, ("raw", 1.0, False))
    if signed or signed_hint:
        if raw >= 0x8000:
            raw = raw - 0x10000
    return raw * scale, unit


def walk_supported_mids(elm: Elm) -> list[int]:
    """Walk 0600, 0620, 0640, ..., 06E0 for supported-MID bitmasks."""
    supported = []
    for base in range(0x00, 0xE0, 0x20):
        payload = read_pid(elm, f"06{base:02X}", 2.0)
        if not payload or len(payload) < 4:
            break
        mask = int.from_bytes(payload[:4], "big")
        any_next = False
        for i in range(32):
            if mask & (1 << (31 - i)):
                mid = base + 1 + i
                if mid == base + 0x20:
                    any_next = True
                supported.append(mid)
        if not any_next:
            break
    return sorted(set(supported))


def query_mid(elm: Elm, mid: int) -> list[dict]:
    """Query one MID, parse all TID entries in response.

    Response format (CAN, per frame):
      46 <MID> <TID> <UAS> <Value_hi> <Value_lo> <Min_hi> <Min_lo> <Max_hi> <Max_lo>
      ...possibly more TIDs...
    """
    resp = elm.send(f"06{mid:02X}", 2.5)
    ecus = parse_can(resp)
    tids = []
    for hdr, data in ecus.items():
        if not data or data[0] != 0x46:
            continue
        # Skip the 0x46 echo; payload is MID,TID,UAS,Val_hi,Val_lo,Min_hi,Min_lo,Max_hi,Max_lo
        i = 1
        while i + 8 < len(data):
            if data[i] != mid:
                # Some responders put the MID every time, some don't. If it doesn't match, slide.
                i += 1
                continue
            tid = data[i + 1]
            uas = data[i + 2]
            val = (data[i + 3] << 8) | data[i + 4]
            mn = (data[i + 5] << 8) | data[i + 6]
            mx = (data[i + 7] << 8) | data[i + 8]
            v_val, unit = decode_value(val, uas)
            v_min, _ = decode_value(mn, uas)
            v_max, _ = decode_value(mx, uas)
            within = v_min <= v_val <= v_max
            tids.append({
                "mid": mid, "tid": tid, "uas": uas,
                "value": v_val, "min": v_min, "max": v_max,
                "unit": unit, "within_limits": within,
                "raw": {"val": val, "min": mn, "max": mx},
            })
            i += 9
    return tids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = f"{REPORT_DIR}/mode06_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    lines = [f"═══ Mode 06 On-Board Monitor Results — {ts} ═══\n"]
    with Elm(args.port) as e:
        e.init_can()
        mids = walk_supported_mids(e)
        lines.append(f"Supported MIDs ({len(mids)}): " + ", ".join(f"{m:02X}" for m in mids))
        lines.append("")
        if not mids:
            lines.append("No MIDs reported supported. Engine may not be fully warmed up")
            lines.append("or ECM may limit Mode 06 to specific session states.")
            with open(txt_path, "w") as f: f.write("\n".join(lines))
            print("\n".join(lines))
            return
        all_tests = []
        for mid in mids:
            name = MID_NAMES.get(mid, f"(unknown MID 0x{mid:02X})")
            tids = query_mid(e, mid)
            lines.append(f"── MID 0x{mid:02X}  {name} ──")
            if not tids:
                lines.append("   (no data — monitor may not have run yet)")
                lines.append("")
                continue
            for t in tids:
                mark = "✓" if t["within_limits"] else "✗"
                tid_name = TID_NAMES.get(t["tid"], f"TID 0x{t['tid']:02X}")
                lines.append(
                    f"   {mark} {tid_name:35}  value={t['value']:10.4f} {t['unit']:<6}  "
                    f"[{t['min']:10.4f} .. {t['max']:10.4f}]  UAS=0x{t['uas']:02X}"
                )
                all_tests.append((mid, t))
            lines.append("")

        # Summary of fails
        fails = [(m, t) for m, t in all_tests if not t["within_limits"]]
        lines.append(f"── Summary ──")
        lines.append(f"  Tests total   : {len(all_tests)}")
        lines.append(f"  Within limits : {len(all_tests) - len(fails)}")
        lines.append(f"  Out of limits : {len(fails)}")
        if fails:
            lines.append("")
            lines.append("  Failing tests (may indicate future DTC):")
            for m, t in fails:
                name = MID_NAMES.get(m, f"MID 0x{m:02X}")
                tname = TID_NAMES.get(t["tid"], f"TID 0x{t['tid']:02X}")
                lines.append(f"    - {name}  {tname}  {t['value']:.4f} {t['unit']}  "
                             f"(limit {t['min']:.4f}..{t['max']:.4f})")
        else:
            lines.append("  All monitored tests are within manufacturer limits.")

    with open(txt_path, "w") as f: f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[+] Report: {txt_path}")


if __name__ == "__main__":
    main()
