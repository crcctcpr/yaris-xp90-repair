"""Readiness-monitor tracker.

Polls mode 01 PID 01 over time, reports when each non-continuous monitor
completes. Essential after a code-clear or after a repair: the ECM needs
to run each emissions monitor at least once before permanent codes are
dropped, and before an emissions test will pass.

Usage:
  python3 -m yaris.readiness [--interval 15] [--once]
  python3 -m yaris.readiness --drive   # live display, exit on Ctrl-C
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, decode_readiness
from .vehicle import DEFAULT_PORT, REPORT_DIR

NON_CONTINUOUS = [
    ("cat_sup", "cat_incomplete", "Catalyst"),
    ("htd_cat_sup", "htd_cat_incomplete", "Heated catalyst"),
    ("evap_sup", "evap_incomplete", "EVAP"),
    ("sec_air_sup", "sec_air_incomplete", "Secondary air"),
    ("ac_sup", "ac_incomplete", "A/C refrigerant"),
    ("o2_sup", "o2_incomplete", "O2 sensor"),
    ("o2htr_sup", "o2htr_incomplete", "O2 heater"),
    ("egr_sup", "egr_incomplete", "EGR"),
]
CONTINUOUS = [
    ("misfire_sup", "misfire_incomplete", "Misfire"),
    ("fuel_sup", "fuel_incomplete", "Fuel system"),
    ("comp_sup", "comp_incomplete", "Comprehensive components"),
]


def state_of(supported: bool, incomplete: bool) -> str:
    if not supported:
        return "n/a"
    return "incomplete" if incomplete else "complete"


def snapshot(elm: Elm) -> dict | None:
    payload = read_pid(elm, "0101", 1.5)
    if not payload:
        return None
    return decode_readiness(payload)


def format_snapshot(r: dict) -> str:
    lines = []
    lines.append(f"  MIL: {'ON' if r['MIL'] else 'OFF'}   DTC count: {r['DTC_count']}")
    lines.append(f"  -- Continuous monitors --")
    for sup_k, inc_k, name in CONTINUOUS:
        lines.append(f"     {name:32}: {state_of(r[sup_k], r[inc_k])}")
    lines.append(f"  -- Non-continuous monitors (need drive cycle to complete) --")
    for sup_k, inc_k, name in NON_CONTINUOUS:
        lines.append(f"     {name:32}: {state_of(r[sup_k], r[inc_k])}")
    return "\n".join(lines)


def run_once(port: str) -> dict:
    with Elm(port) as e:
        e.init_can()
        r = snapshot(e)
        return r or {}


def run_watch(port: str, interval: float, log_path: str | None) -> None:
    """Loop forever, report on any state change. Ctrl-C to exit."""
    print(f"[*] Readiness watch — polling every {interval}s. Ctrl-C to exit.")
    prev = {}
    start = time.time()
    f = open(log_path, "w") if log_path else None
    if f:
        f.write("timestamp,elapsed_s,mil,dtc_count,cat,htd_cat,evap,sec_air,ac,o2,o2htr,egr,misfire,fuel,comp\n")

    try:
        with Elm(port) as e:
            e.init_can()
            while True:
                r = snapshot(e)
                if not r:
                    print(f"[{int(time.time()-start):4d}s] (no data)")
                    time.sleep(interval)
                    continue
                now = datetime.now().strftime("%H:%M:%S")
                elapsed = int(time.time() - start)
                if f:
                    row = [datetime.now().isoformat(timespec="seconds"), str(elapsed),
                           "1" if r["MIL"] else "0", str(r["DTC_count"])]
                    for sup_k, inc_k, _ in NON_CONTINUOUS + CONTINUOUS:
                        row.append(state_of(r[sup_k], r[inc_k]))
                    f.write(",".join(row) + "\n")
                    f.flush()
                # Changes since last
                changes = []
                for sup_k, inc_k, name in NON_CONTINUOUS + CONTINUOUS:
                    new = state_of(r[sup_k], r[inc_k])
                    old = prev.get(name)
                    if old and old != new:
                        arrow = "✓ COMPLETED" if new == "complete" else f"{old} → {new}"
                        changes.append(f"{name} {arrow}")
                    prev[name] = new
                if r["MIL"] != prev.get("_mil"):
                    changes.append(f"MIL {'→ ON !!!' if r['MIL'] else '→ OFF ✓'}")
                    prev["_mil"] = r["MIL"]
                if r["DTC_count"] != prev.get("_dtc_count"):
                    if "_dtc_count" in prev:
                        changes.append(f"DTC count {prev['_dtc_count']} → {r['DTC_count']}")
                    prev["_dtc_count"] = r["DTC_count"]

                # Progress line
                incomp = sum(1 for sup_k, inc_k, _ in NON_CONTINUOUS if r[sup_k] and r[inc_k])
                total = sum(1 for sup_k, _, _ in NON_CONTINUOUS if r[sup_k])
                mil = "MIL-ON" if r["MIL"] else "MIL-off"
                prog = f"{total - incomp}/{total} monitors complete"
                if changes:
                    print(f"[{elapsed:4d}s {now}] {mil}  {prog}  | " + "  ".join(changes))
                else:
                    print(f"[{elapsed:4d}s {now}] {mil}  {prog}")
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
    finally:
        if f:
            f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--once", action="store_true", help="Single snapshot then exit")
    ap.add_argument("--log", default=None)
    ap.add_argument("--nolog", action="store_true")
    args = ap.parse_args()

    if args.once:
        r = run_once(args.port)
        if not r:
            print("[!] No response from ECM (key on? Adapter bound?)")
            sys.exit(1)
        print(f"══ Readiness snapshot — {datetime.now().isoformat(timespec='seconds')} ══")
        print(format_snapshot(r))
        return

    log_path = None
    if not args.nolog:
        log_path = args.log or f"{REPORT_DIR}/readiness_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        print(f"[+] Logging to {log_path}")
    run_watch(args.port, args.interval, log_path)


if __name__ == "__main__":
    main()
