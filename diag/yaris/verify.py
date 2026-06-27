"""Before/after repair verification.

Compares two yaris_live_dash CSVs. Reports per-RPM-band deltas for MAF,
LTFT, STFT, and produces a pass/fail verdict against sensible thresholds.

Usage:
  python3 -m yaris.verify --before path/before.csv --after path/after.csv
"""
import argparse
import csv
import os
import sys
from datetime import datetime
from math import sqrt

from .vehicle import expected_maf, REPORT_DIR, EXPECTED_LTFT_PCT, EXPECTED_STFT_PCT


def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append({
                    "t": row.get("timestamp", ""),
                    "rpm": float(row["rpm"]),
                    "speed": float(row["speed_kmh"]),
                    "maf": float(row["maf_gs"]),
                    "stft": float(row["stft_b1_pct"]),
                    "ltft": float(row["ltft_b1_pct"]),
                    "load": float(row["load_pct"]),
                    "throttle": float(row["throttle_pct"]),
                    "coolant": float(row["coolant_c"]),
                })
            except (ValueError, KeyError):
                continue
    return rows


def stats(vals):
    if not vals:
        return None
    n = len(vals)
    m = sum(vals) / n
    v = sum((x - m) ** 2 for x in vals) / n
    return {"n": n, "mean": m, "min": min(vals), "max": max(vals), "std": sqrt(v)}


BANDS = [
    ("Idle",       400,  800),
    ("Low",        800, 1500),
    ("Low-mid",   1500, 2100),
    ("Mid",       2100, 2700),
    ("Mid-high",  2700, 3500),
    ("High",      3500, 6500),
]


def analyze(rows: list[dict]) -> dict:
    live = [r for r in rows if r["rpm"] > 400]
    for r in live:
        # Use throttle-based VE (independent of MAF) for diagnosis
        r["expected"] = expected_maf(r["rpm"], throttle_pct=r.get("throttle"), mode="throttle")
        r["ratio"] = r["maf"] / r["expected"] if r["expected"] > 0 else 0
    out = {"n_total": len(rows), "n_live": len(live), "bands": {}}
    for name, lo, hi in BANDS:
        inband = [r for r in live if lo <= r["rpm"] < hi]
        if not inband:
            out["bands"][name] = None
            continue
        out["bands"][name] = {
            "n": len(inband),
            "maf": stats([r["maf"] for r in inband]),
            "expected": stats([r["expected"] for r in inband]),
            "ratio": stats([r["ratio"] for r in inband]),
            "stft": stats([r["stft"] for r in inband]),
            "ltft": stats([r["ltft"] for r in inband]),
            "coolant": stats([r["coolant"] for r in inband]),
        }
    if live:
        out["overall"] = {
            "ratio": stats([r["ratio"] for r in live]),
            "ltft": stats([r["ltft"] for r in live]),
            "stft": stats([r["stft"] for r in live]),
        }
    return out


def verdict(after: dict) -> list[tuple[str, str, str]]:
    """Return list of (metric, status, notes) tuples."""
    out = []
    ov = after.get("overall")
    if not ov:
        return [("overall", "FAIL", "No engine-on samples in after-CSV.")]
    r_mean = ov["ratio"]["mean"]
    if r_mean >= 0.85:
        out.append(("MAF ratio", "PASS", f"{r_mean:.2f}× expected (target ≥0.85×)"))
    elif r_mean >= 0.70:
        out.append(("MAF ratio", "WARN", f"{r_mean:.2f}× — improved but not healthy"))
    else:
        out.append(("MAF ratio", "FAIL", f"{r_mean:.2f}× — sensor still under-reading"))

    ltft_mean = ov["ltft"]["mean"]
    lo, hi = EXPECTED_LTFT_PCT
    if lo <= ltft_mean <= hi:
        out.append(("LTFT", "PASS", f"{ltft_mean:+.1f}% within healthy range {lo:+}..{hi:+}%"))
    elif abs(ltft_mean) < 12:
        out.append(("LTFT", "WARN", f"{ltft_mean:+.1f}% drifting, give more drive time"))
    else:
        out.append(("LTFT", "FAIL", f"{ltft_mean:+.1f}% still saturated"))

    stft_mean = ov["stft"]["mean"]
    if abs(stft_mean) < 5:
        out.append(("STFT", "PASS", f"{stft_mean:+.1f}% centered"))
    else:
        out.append(("STFT", "WARN", f"{stft_mean:+.1f}% offset"))
    return out


def fmt_stats(s, unit=""):
    if not s:
        return "—"
    return f"{s['mean']:+7.2f}{unit}  [{s['min']:+6.2f}, {s['max']:+6.2f}]  σ={s['std']:.2f}  n={s['n']}"


def compare(before: dict, after: dict) -> list[str]:
    lines = []
    lines.append("═══ Before → After ═══\n")
    for name, _, _ in BANDS:
        b = before["bands"].get(name)
        a = after["bands"].get(name)
        if not b and not a:
            continue
        lines.append(f"── {name} band ──")
        for metric, unit, path in [
            ("MAF ratio", "×", "ratio"),
            ("MAF g/s", " g/s", "maf"),
            ("LTFT", "%", "ltft"),
            ("STFT", "%", "stft"),
        ]:
            b_s = b[path] if b else None
            a_s = a[path] if a else None
            bm = f"{b_s['mean']:+7.2f}" if b_s else "     —"
            am = f"{a_s['mean']:+7.2f}" if a_s else "     —"
            delta = ""
            if b_s and a_s:
                d = a_s["mean"] - b_s["mean"]
                delta = f"  Δ {d:+7.2f}"
            lines.append(f"    {metric:10} before {bm}{unit}   after {am}{unit}{delta}")
        lines.append("")

    lines.append("── Overall verdict ──")
    v = verdict(after)
    for metric, status, note in v:
        icon = {"PASS": "✓", "WARN": "~", "FAIL": "✗"}.get(status, "?")
        lines.append(f"  {icon} {metric:12} {status:5}  {note}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--label", default="verify")
    args = ap.parse_args()

    for p in [args.before, args.after]:
        if not os.path.exists(p):
            print(f"[!] Missing: {p}"); sys.exit(1)

    before = analyze(load_csv(args.before))
    after = analyze(load_csv(args.after))
    lines = compare(before, after)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"{REPORT_DIR}/verify_{args.label}_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[+] Written: {out_path}")


if __name__ == "__main__":
    main()
