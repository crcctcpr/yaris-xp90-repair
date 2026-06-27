"""Query & summarise the longitudinal history store.

Usage:
  yaris-diag history                      # overview (sessions + trend summary)
  yaris-diag history --sessions 20        # list last 20 sessions
  yaris-diag history --ltft 30            # LTFT trend over last 30 days
  yaris-diag history --maf 30             # MAF-ratio trend
  yaris-diag history --dtcs               # DTC occurrences
  yaris-diag history --session <ID>       # single session detail
  yaris-diag history --import <CSV>       # ingest an existing CSV
"""
import argparse
import os
from datetime import datetime

from .store import Store, DEFAULT_DB
from .vehicle import VIN


def fmt_row(row: dict, cols: list[tuple[str, str, int]]) -> str:
    """cols: (key, fmt, width)."""
    parts = []
    for key, fmt, w in cols:
        v = row.get(key)
        if v is None:
            parts.append(" " * w)
            continue
        if fmt == "s":
            s = str(v)[:w]
        else:
            try:
                s = f"{v:{fmt}}"
            except Exception:
                s = str(v)
        parts.append(s.ljust(w))
    return "  ".join(parts)


def cmd_overview(store: Store):
    sessions = store.sessions(vin=VIN, days=365)
    print(f"═══ History for {VIN} ═══")
    print(f"Total sessions: {len(sessions)}")
    if not sessions:
        print("(no sessions — run yaris-diag dash to start logging)")
        return
    print("\nLatest 5 sessions:")
    for s in sessions[:5]:
        print(f"  #{s['id']:3d}  {s['started_ts']}  "
              f"{s['source']:12}  {s['note'] or '-':40}")
    print("\nLTFT trend (last 30 days):")
    for row in store.ltft_history(vin=VIN, days=30):
        print(f"  #{row['id']:3d}  {row['started_ts']}  n={row['n']:5d}  "
              f"LTFT avg {row['ltft_avg']:+6.2f}%  max {row['ltft_max']:+6.2f}%")
    print("\nMAF-ratio trend (last 30 days):")
    for row in store.maf_ratio_trend(vin=VIN, days=30):
        marker = "✓" if row["ratio_mean"] >= 0.85 else ("~" if row["ratio_mean"] >= 0.70 else "✗")
        print(f"  {marker} #{row['session_id']:3d}  {row['started_ts']}  "
              f"ratio {row['ratio_mean']:.2f}×  (range {row['ratio_min']:.2f}..{row['ratio_max']:.2f}, "
              f"n={row['n_samples']})")
    print("\nDTC occurrences (last 90 days):")
    for row in store.dtc_occurrences(vin=VIN, days=90):
        print(f"  {row['code']:6}  {row['bucket']:10}  seen×{row['occurrences']:3d}  "
              f"first {row['first_ts'][:10]}  last {row['last_ts'][:10]}")


def cmd_sessions(store: Store, n: int):
    sessions = store.sessions(vin=VIN, days=365)[:n]
    for s in sessions:
        print(f"#{s['id']:3d}  {s['started_ts']}  ended {s['ended_ts'] or '(open)'}  "
              f"source={s['source']}  {s['note'] or ''}")


def cmd_session_detail(store: Store, session_id: int):
    summ = store.session_summary(session_id)
    if not summ:
        print(f"No session #{session_id}")
        return
    s = summ["session"]
    print(f"═══ Session #{session_id} ═══")
    print(f"  VIN       : {s['vin']}")
    print(f"  Started   : {s['started_ts']}")
    print(f"  Ended     : {s['ended_ts'] or '(open)'}")
    print(f"  Source    : {s['source']}")
    print(f"  Note      : {s['note']}")
    print()
    st = summ.get("stats", {})
    if st.get("n"):
        print(f"  Samples        : {st['n']}")
        print(f"  RPM range      : {st['rpm_min']:.0f} .. {st['rpm_max']:.0f}")
        print(f"  LTFT range     : {st['ltft_min']:+.1f} .. {st['ltft_max']:+.1f}  "
              f"(avg {st['ltft_avg']:+.1f}%)")
        print(f"  Coolant range  : {st['cool_min']:.0f} .. {st['cool_max']:.0f}°C")
        print(f"  MIL ever       : {'yes' if st['mil_ever'] else 'no'}")
        print(f"  Max DTC count  : {st['dtc_max']}")
    if summ["dtcs"]:
        print(f"\n  DTCs seen:")
        for d in summ["dtcs"]:
            print(f"    {d['code']:6}  {d['bucket']}")
    if summ["events"]:
        print(f"\n  Events:")
        for e in summ["events"]:
            print(f"    [{e['ts']}] {e['type']:8}  {e['text']}")


def cmd_ltft(store: Store, days: int):
    rows = store.ltft_history(vin=VIN, days=days)
    print(f"LTFT history (last {days} days):")
    for r in rows:
        bar = "▮" * min(40, max(0, int(abs(r["ltft_avg"]) * 1.5)))
        side = " " if r["ltft_avg"] < 0 else ""
        print(f"  #{r['id']:3d}  {r['started_ts'][:16]}  n={r['n']:5d}  "
              f"avg {r['ltft_avg']:+6.2f}%  |{bar}")


def cmd_maf(store: Store, days: int):
    rows = store.maf_ratio_trend(vin=VIN, days=days)
    print(f"MAF ratio trend (last {days} days):")
    for r in rows:
        marker = "✓" if r["ratio_mean"] >= 0.85 else ("~" if r["ratio_mean"] >= 0.70 else "✗")
        print(f"  {marker} #{r['session_id']:3d}  {r['started_ts'][:16]}  "
              f"ratio {r['ratio_mean']:.2f}×  min {r['ratio_min']:.2f}  "
              f"max {r['ratio_max']:.2f}  n={r['n_samples']}")


def cmd_dtcs(store: Store):
    rows = store.dtc_occurrences(vin=VIN, days=365)
    print(f"DTC occurrences (all time):")
    for r in rows:
        print(f"  {r['code']:6}  {r['bucket']:10}  ×{r['occurrences']:3d}  "
              f"first {r['first_ts'][:10]}  last {r['last_ts'][:10]}")


def cmd_import(store: Store, csv_path: str):
    if not os.path.exists(csv_path):
        print(f"[!] File not found: {csv_path}")
        return
    sid = store.import_csv(csv_path, source="imported",
                            note=os.path.basename(csv_path))
    print(f"[+] Imported as session #{sid}")
    cmd_session_detail(store, sid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--sessions", type=int, help="List last N sessions")
    ap.add_argument("--session", type=int, help="Detail for a specific session ID")
    ap.add_argument("--ltft", type=int, metavar="DAYS", help="LTFT trend")
    ap.add_argument("--maf", type=int, metavar="DAYS", help="MAF ratio trend")
    ap.add_argument("--dtcs", action="store_true", help="DTC occurrences")
    ap.add_argument("--import", dest="import_csv", help="Import a CSV")
    args = ap.parse_args()

    with Store(args.db) as store:
        if args.sessions is not None:
            cmd_sessions(store, args.sessions)
        elif args.session is not None:
            cmd_session_detail(store, args.session)
        elif args.ltft is not None:
            cmd_ltft(store, args.ltft)
        elif args.maf is not None:
            cmd_maf(store, args.maf)
        elif args.dtcs:
            cmd_dtcs(store)
        elif args.import_csv:
            cmd_import(store, args.import_csv)
        else:
            cmd_overview(store)


if __name__ == "__main__":
    main()
