"""Fuel economy estimator from MAF + speed.

Fuel flow (g/s)  = MAF (g/s) / AFR
Fuel flow (L/hr) = fuel_flow_g_s × 3600 / density_g_per_L
L/100km          = fuel_L_hr / speed_kmh × 100   (at speed > 0)
mpg (US)         = 235.214 / L_per_100km

AFR (air-to-fuel mass ratio) = 14.7 at stoichiometric for gasoline. Since the
ECM holds λ≈1.0 in closed-loop, stoich AFR is accurate most of the time. Under
enrichment (decel-cut, WOT), real AFR drifts, but for average efficiency the
stoich assumption is good enough (< 5% error under typical driving).

NOTE: if MAF is under-reading (like our P0101 car), fuel flow *appears* low,
so computed economy looks better than reality. After the MAF fix, computed
economy should match what the trip computer / fill-up math shows.

Usage:
  python3 -m yaris.economy --csv <dash.csv>
  python3 -m yaris.economy --history 30          # per-session trend
"""
import argparse
import csv
import os
from datetime import datetime

from .vehicle import REPORT_DIR, VIN


STOICH_AFR = 14.7           # gasoline
GASOLINE_DENSITY_G_L = 745  # average pump gasoline (varies 720–775)


def load_rows(csv_path: str) -> list[dict]:
    rows = []
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path) as f:
        last_t = None
        for r in csv.DictReader(f):
            try:
                row = {
                    "timestamp": r.get("timestamp", ""),
                    "rpm":    float(r.get("rpm") or 0),
                    "speed":  float(r.get("speed_kmh") or 0),
                    "maf":    float(r.get("maf_gs") or 0),
                    "stft":   float(r.get("stft_b1_pct") or 0),
                    "ltft":   float(r.get("ltft_b1_pct") or 0),
                }
                rows.append(row)
            except (ValueError, TypeError):
                continue
    return rows


def integrate_economy(rows: list[dict],
                       sample_interval_s: float = 1.3) -> dict:
    """Compute fuel-economy metrics over a sequence of samples.

    Args:
      rows: list of {rpm, speed, maf, stft, ltft, ...}
      sample_interval_s: approximate time between samples (used for
                         integration; Bluetooth ELM typically 1.2-1.5s).
    Returns:
      dict with total_fuel_g, total_fuel_L, total_distance_km,
      avg_L_per_100km, avg_mpg, running_L_per_100km, running_mpg,
      ratio_running_vs_idle (fraction of fuel burned while stationary).
    """
    if not rows:
        return {}

    total_fuel_g = 0.0
    total_distance_km = 0.0
    running_fuel_g = 0.0     # fuel while car is actually moving
    running_distance_km = 0.0
    idle_fuel_g = 0.0

    for r in rows:
        if r["maf"] <= 0 or r["rpm"] < 200:
            continue
        # AFR compensated for trims — STFT+LTFT tell us actual AFR drift.
        # Sum trim % >0 means ECU is *adding* fuel, so actual AFR is *richer*
        # (lower numeric AFR) than stoich. richer = more fuel per unit air.
        trim_sum_pct = r["stft"] + r["ltft"]
        afr = STOICH_AFR * (1 - trim_sum_pct / 100.0)
        if afr <= 0:  # sanity
            afr = STOICH_AFR

        fuel_g_s = r["maf"] / afr
        fuel_g = fuel_g_s * sample_interval_s
        total_fuel_g += fuel_g

        dist_km = r["speed"] * sample_interval_s / 3600.0
        total_distance_km += dist_km

        if r["speed"] > 5:
            running_fuel_g += fuel_g
            running_distance_km += dist_km
        else:
            idle_fuel_g += fuel_g

    total_fuel_L = total_fuel_g / GASOLINE_DENSITY_G_L
    running_fuel_L = running_fuel_g / GASOLINE_DENSITY_G_L

    out = {
        "n_samples": len(rows),
        "total_fuel_g": total_fuel_g,
        "total_fuel_L": total_fuel_L,
        "total_distance_km": total_distance_km,
        "idle_fuel_L": idle_fuel_g / GASOLINE_DENSITY_G_L,
        "running_distance_km": running_distance_km,
        "running_fuel_L": running_fuel_L,
    }
    if total_distance_km > 0:
        l100 = total_fuel_L / total_distance_km * 100
        out["avg_L_per_100km"] = l100
        out["avg_mpg"] = 235.214 / l100 if l100 > 0 else None
    if running_distance_km > 0:
        l100r = running_fuel_L / running_distance_km * 100
        out["running_L_per_100km"] = l100r
        out["running_mpg"] = 235.214 / l100r if l100r > 0 else None
    if total_fuel_g > 0:
        out["idle_fuel_fraction"] = idle_fuel_g / total_fuel_g
    return out


def format_report(stats: dict, label: str = "") -> str:
    if not stats:
        return "(no data)"
    def f(k, prec=2, unit=""):
        v = stats.get(k)
        return f"{v:.{prec}f}{unit}" if v is not None else "—"
    lines = []
    if label:
        lines.append(f"── {label} ──")
    lines.append(f"  Samples               : {stats.get('n_samples', 0)}")
    lines.append(f"  Total distance        : {f('total_distance_km', 2, ' km')}")
    lines.append(f"    of which moving     : {f('running_distance_km', 2, ' km')}")
    lines.append(f"  Total fuel burned     : {f('total_fuel_L', 3, ' L')}")
    lines.append(f"    idle portion        : {f('idle_fuel_L', 3, ' L')}")
    if stats.get("idle_fuel_fraction") is not None:
        lines.append(f"    idle fraction       : {100*stats['idle_fuel_fraction']:.1f}%")
    lines.append(f"  Average consumption   : {f('avg_L_per_100km', 2, ' L/100km')}   "
                 f"({f('avg_mpg', 1, ' mpg')})")
    lines.append(f"  While moving only     : {f('running_L_per_100km', 2, ' L/100km')}   "
                 f"({f('running_mpg', 1, ' mpg')})")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="Dash CSV to analyze")
    ap.add_argument("--history", type=int, metavar="DAYS",
                    help="Per-session economy trend from SQLite store")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="Compare two CSVs")
    ap.add_argument("--interval", type=float, default=1.3,
                    help="Sample interval in seconds (default 1.3)")
    args = ap.parse_args()

    if args.csv:
        stats = integrate_economy(load_rows(args.csv), args.interval)
        print(format_report(stats, label=os.path.basename(args.csv)))
        return

    if args.compare:
        before = integrate_economy(load_rows(args.compare[0]), args.interval)
        after = integrate_economy(load_rows(args.compare[1]), args.interval)
        print(format_report(before, label=f"BEFORE: {os.path.basename(args.compare[0])}"))
        print()
        print(format_report(after, label=f"AFTER:  {os.path.basename(args.compare[1])}"))
        print()
        if before.get("avg_L_per_100km") and after.get("avg_L_per_100km"):
            delta = after["avg_L_per_100km"] - before["avg_L_per_100km"]
            pct = 100 * delta / before["avg_L_per_100km"]
            mark = "↓" if delta < 0 else "↑"
            print(f"Δ consumption: {mark} {abs(delta):.2f} L/100km ({pct:+.1f}%)")
            if before.get("avg_mpg") and after.get("avg_mpg"):
                dmpg = after["avg_mpg"] - before["avg_mpg"]
                print(f"Δ MPG        : {dmpg:+.1f}")
        return

    if args.history:
        from .store import Store
        with Store() as s:
            sessions = s.sessions(vin=VIN, days=args.history)
        print(f"Fuel economy trend — last {args.history} days — {VIN}\n")
        print(f"{'ID':>4}  {'started':19}  {'n':>5}  {'dist':>8}  {'L/100km':>9}  {'mpg':>5}   note")
        print("-" * 80)
        with Store() as s:
            for sess in sessions:
                rows = []
                for sr in s.conn.execute(
                    "SELECT ts as timestamp, rpm, speed_kmh, maf_gs, stft_pct as stft, "
                    "ltft_pct as ltft FROM samples WHERE session_id=?",
                    (sess["id"],),
                ):
                    rows.append({
                        "timestamp": sr["timestamp"],
                        "rpm": sr["rpm"] or 0, "speed": sr["speed_kmh"] or 0,
                        "maf": sr["maf_gs"] or 0,
                        "stft": sr["stft"] or 0, "ltft": sr["ltft"] or 0,
                    })
                stats = integrate_economy(rows, args.interval)
                dist = stats.get("total_distance_km", 0)
                l100 = stats.get("avg_L_per_100km") or 0
                mpg = stats.get("avg_mpg") or 0
                print(f"{sess['id']:>4}  {sess['started_ts']:19}  {stats.get('n_samples',0):>5}  "
                      f"{dist:>6.2f}km  {l100:>7.2f}  {mpg:>5.1f}   {sess['note'] or ''}")
        return

    print("Pass --csv, --history, or --compare.  --help for details.")


if __name__ == "__main__":
    main()
