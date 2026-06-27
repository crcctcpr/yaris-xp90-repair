"""Full-sweep scanner for Toyota service 0x21 enhanced subfunctions.

Unlike yaris/enhanced.py which probes ~14 common subfunctions, this walks
all 256 and catalogs which the ECU actually supports + response size. Useful
for first-time discovery of a new ECU.

Typical output on the 2011 Yaris 1NR-FE ECM: ~5-10 subfunctions respond with
valid data, the rest return NRC 0x12 (sub-function not supported) or timeout.
"""
import argparse
import json
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import parse_can
from .vehicle import DEFAULT_PORT, REPORT_DIR


def sweep_mode21(elm: Elm, start: int = 0x00, end: int = 0xFF,
                  pause_s: float = 0.05) -> list[dict]:
    """Query every 21<sub> from start to end, return list of results."""
    results = []
    for sub in range(start, end + 1):
        cmd = f"21{sub:02X}"
        resp = elm.send(cmd, 1.5)
        ecus = parse_can(resp)
        entry = {"sub": sub, "cmd": cmd, "response_type": "none",
                 "ecus": {}, "hex_len": 0}
        for hdr, data in ecus.items():
            if not data:
                continue
            if data[0] == 0x61:  # positive response
                if len(data) >= 2 and data[1] == sub:
                    entry["response_type"] = "positive"
                    entry["ecus"][hdr] = {"hex": data[2:].hex(),
                                           "len": len(data) - 2}
                    entry["hex_len"] = max(entry["hex_len"], len(data) - 2)
            elif data[0] == 0x7F:  # negative response
                if len(data) >= 3 and data[1] == 0x21:
                    nrc = data[2]
                    entry["response_type"] = f"neg_{nrc:02X}"
                    entry["ecus"][hdr] = {"nrc": nrc,
                                           "nrc_name": _nrc_name(nrc)}
        results.append(entry)
        if pause_s > 0:
            time.sleep(pause_s)
    return results


def _nrc_name(nrc: int) -> str:
    return {
        0x10: "general reject", 0x11: "service not supported",
        0x12: "subfunction not supported", 0x13: "invalid length",
        0x22: "conditions not correct", 0x31: "request out of range",
        0x33: "security access denied", 0x7E: "subfunc not in active session",
        0x7F: "service not in active session",
    }.get(nrc, f"NRC 0x{nrc:02X}")


def summarize(results: list[dict]) -> dict:
    responding = [r for r in results if r["response_type"] == "positive"]
    rejected = [r for r in results if r["response_type"].startswith("neg_")]
    silent = [r for r in results if r["response_type"] == "none"]
    # Group neg responses by NRC
    by_nrc = {}
    for r in rejected:
        for hdr, info in r["ecus"].items():
            nrc = info.get("nrc", 0)
            by_nrc[f"0x{nrc:02X}"] = by_nrc.get(f"0x{nrc:02X}", 0) + 1
    return {
        "total": len(results),
        "positive": len(responding),
        "negative": len(rejected),
        "silent": len(silent),
        "nrc_distribution": by_nrc,
        "supported_subs": [r["sub"] for r in responding],
        "positive_entries": responding,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--start", type=lambda s: int(s, 16), default=0x00)
    ap.add_argument("--end", type=lambda s: int(s, 16), default=0xFF)
    ap.add_argument("--pause", type=float, default=0.05)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = f"{REPORT_DIR}/mode21_sweep_{ts}.json"
    out_txt = f"{REPORT_DIR}/mode21_sweep_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"═══ Mode 21 full sweep 0x{args.start:02X}–0x{args.end:02X} — {ts} ═══")
    print(f"[*] Will probe {args.end - args.start + 1} subfunctions, "
          f"estimated ~{(args.end - args.start + 1) * (1.5 + args.pause):.0f}s")

    with Elm(args.port) as e:
        e.init_can()
        results = sweep_mode21(e, args.start, args.end, args.pause)

    summary = summarize(results)

    # Write JSON
    with open(out_json, "w") as f:
        json.dump({"sweep": results, "summary": summary,
                    "start": args.start, "end": args.end, "ts": ts}, f, indent=2)

    # Write text report
    lines = [f"═══ Mode 21 sweep — {ts} ═══", ""]
    lines.append(f"Total queried: {summary['total']}")
    lines.append(f"Positive responses: {summary['positive']}")
    lines.append(f"Negative responses (NRC): {summary['negative']}")
    lines.append(f"Silent / timeout: {summary['silent']}")
    lines.append("")
    lines.append(f"NRC distribution: {summary['nrc_distribution']}")
    lines.append("")
    lines.append("── Supported subfunctions ──")
    for r in summary["positive_entries"]:
        for hdr, info in r["ecus"].items():
            lines.append(f"  21 {r['sub']:02X}  [{hdr}]  {info['len']} bytes  "
                          f"hex={info['hex']}")
    lines.append("")
    lines.append("── NRC summary (first 30 rejects) ──")
    rej = [r for r in results if r["response_type"].startswith("neg_")][:30]
    for r in rej:
        for hdr, info in r["ecus"].items():
            lines.append(f"  21 {r['sub']:02X}  → NRC 0x{info['nrc']:02X}  "
                          f"({info['nrc_name']})")

    with open(out_txt, "w") as f:
        f.write("\n".join(lines))

    print()
    print(f"[+] {summary['positive']} subs respond positively, "
          f"{summary['negative']} rejected, {summary['silent']} silent.")
    print(f"[+] Text: {out_txt}")
    print(f"[+] JSON: {out_json}")


if __name__ == "__main__":
    main()
