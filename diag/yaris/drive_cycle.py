"""Guided drive-cycle runner.

Toyota's OBD-II drive cycle for dropping permanent codes and completing all
non-continuous monitors. This tool walks the user through each phase with
realtime monitor-completion feedback — so instead of driving randomly and
hoping, you know when each monitor actually runs.

Toyota 1NR-FE drive cycle (approximate, works for most 2006-2012 Yaris):

  1. Start cold (coolant < 40°C). Idle 2-3 min (O2 heater warm-up).
  2. Accelerate gently to 80 km/h (50 mph). Hold steady 3+ min (cat monitor).
  3. Decelerate to 0 km/h with foot off gas, no brake until necessary (EGR).
  4. Idle for 1 min.
  5. Accelerate to 90 km/h, hold 5 min (O2 sensor monitor).
  6. Decel coasting, 4 min (EVAP small-leak).
  7. Back to idle, stay 2 min.

Tool announces when each non-continuous monitor COMPLETES; you know what's
left. Ctrl-C to abort at any time; all completed monitors remain completed.

Usage:
  python3 -m yaris.drive_cycle
"""
import argparse
import os
import sys
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, decode_pid, decode_readiness
from .vehicle import DEFAULT_PORT, REPORT_DIR


MONITORS = [
    ("cat_sup",    "cat_incomplete",    "Catalyst"),
    ("htd_cat_sup","htd_cat_incomplete","Heated Catalyst"),
    ("evap_sup",   "evap_incomplete",   "EVAP"),
    ("sec_air_sup","sec_air_incomplete","Secondary air"),
    ("ac_sup",     "ac_incomplete",     "A/C"),
    ("o2_sup",     "o2_incomplete",     "O2 sensor"),
    ("o2htr_sup",  "o2htr_incomplete",  "O2 heater"),
    ("egr_sup",    "egr_incomplete",    "EGR"),
]


PHASES = [
    {
        "title": "Cold-start warm-up",
        "instructions": [
            "Start the engine if it's not running.",
            "Leave it at idle. Do not touch the gas pedal.",
            "Target: let coolant climb to 80-90°C.",
        ],
        "complete_when": "coolant >= 80",
        "target_monitors": ["O2 heater"],
        "min_seconds": 120,
        "max_seconds": 400,
    },
    {
        "title": "Steady 80 km/h cruise",
        "instructions": [
            "Drive onto a clear stretch of road (highway, quiet 2-lane, etc.)",
            "Accelerate gently, reach about 80 km/h (50 mph).",
            "Hold STEADY — no throttle changes — for at least 3 minutes.",
            "If traffic forces deviation, resume steady speed as soon as safe.",
        ],
        "complete_when": "avg_speed > 70 for 3min",
        "target_monitors": ["Catalyst", "O2 sensor"],
        "min_seconds": 180,
        "max_seconds": 600,
    },
    {
        "title": "Deceleration (decel-cut)",
        "instructions": [
            "Lift foot completely off throttle.",
            "Let the car coast down to below 30 km/h WITHOUT braking if possible.",
            "Don't shift or touch pedals — pure engine-braking.",
        ],
        "complete_when": "speed < 30 and throttle < 5",
        "target_monitors": ["EGR"],
        "min_seconds": 20,
        "max_seconds": 60,
    },
    {
        "title": "Idle (after decel)",
        "instructions": [
            "Come to a stop somewhere safe.",
            "Keep engine running at idle for 1 minute.",
            "AC off, accessories off if possible.",
        ],
        "complete_when": "rpm stable at idle for 60s",
        "target_monitors": [],
        "min_seconds": 60,
        "max_seconds": 120,
    },
    {
        "title": "Steady 90 km/h cruise (long)",
        "instructions": [
            "Accelerate back up to ~90 km/h (55 mph).",
            "Hold steady for at least 5 minutes.",
            "This is where the EVAP and full O2 monitors run.",
        ],
        "complete_when": "avg_speed > 80 for 5min",
        "target_monitors": ["EVAP", "O2 sensor"],
        "min_seconds": 300,
        "max_seconds": 900,
    },
    {
        "title": "Final coast / idle",
        "instructions": [
            "Decelerate coasting to a stop.",
            "Idle 2 minutes.",
            "This completes the cycle.",
        ],
        "complete_when": "idle stable 2min",
        "target_monitors": [],
        "min_seconds": 120,
        "max_seconds": 180,
    },
]


def get_monitor_states(elm: Elm) -> dict | None:
    p = read_pid(elm, "0101", 1.0)
    if not p:
        return None
    return decode_readiness(p)


def get_live(elm: Elm) -> dict:
    """Lightweight sample for phase-completion logic."""
    out = {}
    for name, pid in [("rpm", 0x0C), ("speed", 0x0D), ("coolant", 0x05),
                      ("throttle", 0x11)]:
        p = read_pid(elm, f"01{pid:02X}", 0.5)
        if p:
            out[name] = decode_pid(pid, p)
    return out


def check_phase_complete(phase: dict, samples: list[dict], elapsed: float) -> tuple[bool, str]:
    if elapsed < phase["min_seconds"]:
        return False, f"min {phase['min_seconds']}s not yet elapsed"
    rule = phase["complete_when"]
    last = samples[-1] if samples else {}
    if "coolant >=" in rule:
        thresh = float(rule.split(">=")[1].strip().split()[0])
        if (last.get("coolant") or 0) >= thresh:
            return True, f"coolant {last.get('coolant')}°C reached threshold"
    if "avg_speed >" in rule and "for 3min" in rule:
        recent = [s for s in samples if s.get("t_elapsed", 0) > elapsed - 180]
        speeds = [s["speed"] for s in recent if s.get("speed") is not None]
        if speeds and sum(speeds)/len(speeds) > 70:
            return True, f"avg speed {sum(speeds)/len(speeds):.0f} km/h sustained 3 min"
    if "avg_speed >" in rule and "for 5min" in rule:
        recent = [s for s in samples if s.get("t_elapsed", 0) > elapsed - 300]
        speeds = [s["speed"] for s in recent if s.get("speed") is not None]
        if speeds and sum(speeds)/len(speeds) > 80:
            return True, f"avg speed {sum(speeds)/len(speeds):.0f} km/h sustained 5 min"
    if "speed < 30 and throttle < 5" in rule:
        if (last.get("speed") or 99) < 30 and (last.get("throttle") or 99) < 5:
            return True, "decel criteria met"
    if "rpm stable at idle for 60s" in rule or "idle stable 2min" in rule:
        window = 60 if "60s" in rule else 120
        recent = [s for s in samples if s.get("t_elapsed", 0) > elapsed - window]
        rpms = [s["rpm"] for s in recent if s.get("rpm") is not None]
        if rpms and all(r < 1100 for r in rpms) and len(recent) > 5:
            return True, f"idle stable {window}s"
    if elapsed > phase["max_seconds"]:
        return True, "max time reached — moving on"
    return False, "in progress"


def diff_monitors(old: dict, new: dict) -> list[str]:
    """Return list of monitor state-change descriptions."""
    events = []
    for sup_k, inc_k, name in MONITORS:
        if old.get(sup_k) != new.get(sup_k):
            continue
        if not new.get(sup_k):
            continue
        if old.get(inc_k, True) and not new.get(inc_k, True):
            events.append(f"✓ {name} monitor COMPLETED")
        elif not old.get(inc_k, True) and new.get(inc_k, True):
            events.append(f"⚠ {name} monitor reverted to incomplete (unexpected)")
    if old.get("MIL", False) and not new.get("MIL", False):
        events.append("✓ MIL went OFF")
    elif not old.get("MIL", False) and new.get("MIL", False):
        events.append(f"✗ MIL TURNED ON — new DTC logged!")
    if old.get("DTC_count", 0) != new.get("DTC_count", 0):
        events.append(f"⚠ DTC count {old.get('DTC_count')} → {new.get('DTC_count')}")
    return events


def summary_status(r: dict) -> str:
    done = sum(1 for sup, inc, _ in MONITORS if r.get(sup) and not r.get(inc))
    total = sum(1 for sup, _, _ in MONITORS if r.get(sup))
    return f"{done}/{total} monitors complete"


def run(port: str, csv_path: str, auto_advance: bool = True) -> None:
    print("═══ Guided Drive Cycle — 2011 Yaris 1NR-FE ═══")
    if auto_advance:
        print("AUTO-ADVANCE mode: phases transition automatically from live data.")
        print("Just drive — no key presses needed. Ctrl-C aborts.\n")
    else:
        print("MANUAL mode: press ENTER when ready for each phase.\n")

    # Try resilient Elm for long runs; fall back to plain Elm if not available.
    try:
        from .resilient_elm import ResilientElm
        elm_ctx = ResilientElm(port=port, init_mode="can")
    except Exception:
        elm_ctx = Elm(port)

    with elm_ctx as e:
        if not hasattr(e, "_elm"):  # plain Elm: init manually
            e.init_can()
        start_state = get_monitor_states(e)
        if not start_state:
            print("[!] Can't read readiness — is the car running and adapter connected?")
            sys.exit(1)
        print(f"Starting state: {summary_status(start_state)}")

        csv = open(csv_path, "w") if csv_path else None
        if csv:
            cols = ["ts", "phase", "t_elapsed", "rpm", "speed", "coolant", "throttle"]
            cols += [f"mon_{name}" for _, _, name in MONITORS]
            csv.write(",".join(cols) + "\n")

        prev_state = start_state
        for idx, phase in enumerate(PHASES):
            print(f"\n{'═'*60}")
            print(f"PHASE {idx+1}/{len(PHASES)}: {phase['title']}")
            print(f"{'═'*60}")
            for step in phase["instructions"]:
                print(f"  • {step}")
            if phase["target_monitors"]:
                print(f"  Target monitors: {', '.join(phase['target_monitors'])}")
            print(f"  Min {phase['min_seconds']}s, max {phase['max_seconds']}s")

            if not auto_advance:
                try:
                    input("\nPress ENTER when ready to begin this phase (or Ctrl-C to abort)…")
                except KeyboardInterrupt:
                    print("\n[*] Aborted.")
                    break
            else:
                print(f"  … auto-advancing when criteria met …")

            t_start = time.time()
            samples = []
            last_report = 0
            while True:
                elapsed = time.time() - t_start
                live = get_live(e)
                live["t_elapsed"] = elapsed
                samples.append(live)

                # Every 10s, poll readiness, print ticker, log CSV
                if int(elapsed) // 10 > last_report:
                    last_report = int(elapsed) // 10
                    rs = get_monitor_states(e)
                    if rs:
                        events = diff_monitors(prev_state, rs)
                        if events:
                            for ev in events:
                                print(f"    >>> {ev}")
                        prev_state = rs
                        rpm_s = f"{live.get('rpm',0):4.0f}"
                        spd_s = f"{live.get('speed',0):3.0f}"
                        cool_s = f"{live.get('coolant','?')}"
                        # Progress indicator
                        progress_pct = min(100, 100 * elapsed / phase['max_seconds'])
                        print(f"    [{int(elapsed):4d}s / {phase['max_seconds']}s  "
                              f"{progress_pct:3.0f}%] rpm {rpm_s}  speed {spd_s} km/h  "
                              f"cool {cool_s}°C  {summary_status(rs)}")
                        if csv:
                            row = [datetime.now().isoformat(timespec='seconds'),
                                   phase['title'], f"{elapsed:.1f}",
                                   str(live.get('rpm','')), str(live.get('speed','')),
                                   str(live.get('coolant','')), str(live.get('throttle',''))]
                            for sup_k, inc_k, name in MONITORS:
                                if not rs.get(sup_k): row.append('n/a')
                                else: row.append('complete' if not rs.get(inc_k) else 'incomplete')
                            csv.write(",".join(row) + "\n")
                            csv.flush()

                done, reason = check_phase_complete(phase, samples, elapsed)
                if done:
                    print(f"    ✓ Phase complete: {reason}")
                    break
                time.sleep(1.0)

        # Final summary
        final_state = get_monitor_states(e)
        print(f"\n{'═'*60}")
        print(f"CYCLE COMPLETE")
        print(f"{'═'*60}")
        if final_state:
            newly = [name for sup, inc, name in MONITORS
                     if start_state.get(inc) and not final_state.get(inc)
                     and final_state.get(sup)]
            still_incomplete = [name for sup, inc, name in MONITORS
                                if final_state.get(inc) and final_state.get(sup)]
            print(f"Started: {summary_status(start_state)}")
            print(f"Ended  : {summary_status(final_state)}")
            if newly:
                print(f"\n✓ Monitors completed this cycle:")
                for n in newly:
                    print(f"    - {n}")
            if still_incomplete:
                print(f"\n⚠ Still incomplete (may need another cycle):")
                for n in still_incomplete:
                    print(f"    - {n}")
            perm_p = read_pid(e, "0A", 3.0)  # Mode 0A permanent DTCs
            # crude: if final_state is clean and MIL off, permanent should clear
            # after next fault-free drive cycle
        if csv: csv.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--log", default=None)
    ap.add_argument("--nolog", action="store_true")
    ap.add_argument("--manual", action="store_true",
                    help="Require ENTER between phases (default is auto-advance)")
    args = ap.parse_args()

    log_path = None
    if not args.nolog:
        log_path = args.log or f"{REPORT_DIR}/drive_cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs(REPORT_DIR, exist_ok=True)

    try:
        run(args.port, log_path, auto_advance=not args.manual)
    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")


if __name__ == "__main__":
    main()
