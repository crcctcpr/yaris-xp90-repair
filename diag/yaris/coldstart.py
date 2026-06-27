"""Cold-start analyzer.

Captures the first N seconds after engine start and analyzes warm-up behavior.
Flags: stuck thermostat (coolant slow to rise), weak cat (stays cold), rich/lean
cold-start trim, slow O2 light-off, long open-loop period.

Workflow:
  1. Turn key OFF. Wait 10 seconds. Start the tool.
  2. Start the engine when the tool prompts "READY".
  3. Tool captures first 120s then produces the report.

Usage:
  python3 -m yaris.coldstart [--duration 120]
"""
import argparse
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, decode_pid
from .vehicle import DEFAULT_PORT, REPORT_DIR, EXPECTED_COOLANT_WARM_C


SAMPLE_PIDS = [
    ("rpm",     0x0C, lambda v: v),
    ("maf",     0x10, lambda v: v),
    ("coolant", 0x05, lambda v: v),
    ("iat",     0x0F, lambda v: v),
    ("stft",    0x06, lambda v: v),
    ("ltft",    0x07, lambda v: v),
    ("load",    0x04, lambda v: v),
    ("throttle",0x11, lambda v: v),
    ("o2_b1s2", 0x15, lambda v: v.get("V") if isinstance(v, dict) else None),
    ("cat_t",   0x3C, lambda v: v),
    ("ctlv",    0x42, lambda v: v),
    ("fs",      0x03, lambda v: v.get("FS1") if isinstance(v, dict) else None),
    ("timing",  0x0E, lambda v: v),
]


def sample(elm: Elm) -> dict:
    row = {"t": time.time()}
    for name, pid, extract in SAMPLE_PIDS:
        p = read_pid(elm, f"01{pid:02X}", 0.7)
        if p is None:
            continue
        try:
            v = decode_pid(pid, p)
            row[name] = extract(v)
        except Exception:
            pass
    return row


def wait_for_start(elm: Elm) -> tuple[float, dict]:
    """Block until RPM jumps from 0 to >300, return (t0, first_running_sample)."""
    print("[*] Waiting for engine start (watching RPM)…")
    t0 = None
    while True:
        p = read_pid(elm, "010C", 0.5)
        if p:
            rpm = decode_pid(0x0C, p)
            if rpm > 300:
                t0 = time.time()
                first = sample(elm)
                print(f"[+] Engine started — RPM {rpm:.0f} at t=0")
                return t0, first
        time.sleep(0.3)


def analyze(samples: list[dict]) -> dict:
    """Produce warm-up metrics."""
    if not samples:
        return {}
    t0 = samples[0]["t"]
    # Coolant trajectory
    coolants = [(s["t"] - t0, s.get("coolant")) for s in samples if s.get("coolant") is not None]
    warm_at = None
    target_lo = EXPECTED_COOLANT_WARM_C[0]
    for t, c in coolants:
        if c >= target_lo:
            warm_at = t
            break

    # O2 activity onset (first 0.1-0.9V swing)
    o2_active_at = None
    prev = None
    for s in samples:
        v = s.get("o2_b1s2")
        if v is None:
            continue
        if prev is not None and abs(v - prev) > 0.4:
            o2_active_at = s["t"] - t0
            break
        prev = v

    # Closed-loop entry (fuel system byte transitions from OL → CL)
    cl_at = None
    for s in samples:
        fs = s.get("fs")
        if fs == 2:  # CL
            cl_at = s["t"] - t0
            break

    # LTFT at end
    final_ltft = samples[-1].get("ltft")
    final_stft = samples[-1].get("stft")

    # Cat warm-up
    cat_temps = [(s["t"] - t0, s.get("cat_t")) for s in samples if s.get("cat_t") is not None]
    cat_400_at = None
    for t, ct in cat_temps:
        if ct and ct >= 400:
            cat_400_at = t
            break

    # RPM idle stabilization (first time RPM stays <900 for 10s)
    rpm_stab_at = None
    for i, s in enumerate(samples):
        if s.get("rpm", 99999) < 900:
            # check next 10s
            tpast = s["t"] + 10
            if all(ns.get("rpm", 99999) < 900 for ns in samples[i:] if ns["t"] <= tpast):
                rpm_stab_at = s["t"] - t0
                break

    return {
        "duration_s": samples[-1]["t"] - t0,
        "warm_up_s": warm_at,
        "o2_active_s": o2_active_at,
        "closed_loop_s": cl_at,
        "cat_400c_s": cat_400_at,
        "rpm_stabilized_s": rpm_stab_at,
        "final_ltft": final_ltft,
        "final_stft": final_stft,
        "coolant_start_c": samples[0].get("coolant"),
        "coolant_end_c": samples[-1].get("coolant"),
        "iat_c": samples[0].get("iat"),
    }


def flag_issues(a: dict) -> list[str]:
    out = []
    if a.get("warm_up_s") is None:
        out.append(f"⚠ Coolant did not reach {EXPECTED_COOLANT_WARM_C[0]}°C in {a['duration_s']:.0f}s — suspect thermostat stuck open")
    elif a["warm_up_s"] > 600:
        out.append(f"⚠ Slow warm-up ({a['warm_up_s']:.0f}s to hit {EXPECTED_COOLANT_WARM_C[0]}°C)")
    if a.get("closed_loop_s") is None:
        out.append("⚠ Never entered closed-loop — O2 sensor heater or ECM fuel control issue")
    elif a["closed_loop_s"] > 60:
        out.append(f"⚠ Slow closed-loop entry ({a['closed_loop_s']:.0f}s) — O2 heater slow?")
    if a.get("cat_400c_s") is None:
        out.append("⚠ Catalyst did not reach 400°C — possible weak/failing cat, exhaust leak, or engine not running long enough")
    if abs(a.get("final_ltft") or 0) > 15:
        out.append(f"⚠ LTFT {a['final_ltft']:+.1f}% saturated")
    if abs(a.get("final_stft") or 0) > 10:
        out.append(f"⚠ STFT {a['final_stft']:+.1f}% not converging")
    if a.get("rpm_stabilized_s") is not None and a["rpm_stabilized_s"] > 30:
        out.append(f"⚠ RPM took {a['rpm_stabilized_s']:.0f}s to stabilize — idle control or vacuum leak?")
    if not out:
        out.append("✓ Cold-start profile looks healthy")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--duration", type=float, default=120.0, help="Seconds to sample after start")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"{REPORT_DIR}/coldstart_{ts}.csv"
    txt_path = f"{REPORT_DIR}/coldstart_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"═══ Cold-start analyzer — {ts} ═══\n")
    print(f"  1. Turn the key OFF now if it isn't already.")
    print(f"  2. Wait here until tool says READY.")
    print(f"  3. When you see READY, start the engine.\n")

    with Elm(args.port) as e:
        e.init_can()
        # Wait for key-on confirmation (ATRV > 11V)
        while True:
            v = e.send("ATRV", 1.0)
            if "V" in v:
                try:
                    volt = float(v.replace("V", "").strip())
                    if volt > 11.5:
                        break
                except Exception:
                    pass
            time.sleep(1)
        print("READY — start the engine now.")
        t0, first = wait_for_start(e)
        samples = [first]
        with open(csv_path, "w") as f:
            f.write("t_s,rpm,maf,coolant,iat,stft,ltft,load,throttle,o2_b1s2,cat_t,ctlv,fs,timing\n")
            while time.time() - t0 < args.duration:
                s = sample(e)
                samples.append(s)
                row = [f"{s['t']-t0:.2f}"]
                for name, _, _ in SAMPLE_PIDS:
                    v = s.get(name, "")
                    row.append(f"{v}" if v != "" else "")
                f.write(",".join(row) + "\n")
                f.flush()
                # Light progress
                if int(s["t"] - t0) % 10 == 0:
                    print(f"  [{int(s['t']-t0):4d}s] rpm {s.get('rpm',0):.0f}  "
                          f"coolant {s.get('coolant','?'):>4}°C  "
                          f"ltft {s.get('ltft','?')}%")

    a = analyze(samples)
    flags = flag_issues(a)

    lines = [f"═══ Cold-start analysis — {ts} ═══\n"]
    lines.append(f"Sampled {len(samples)} rows over {a.get('duration_s',0):.0f}s")
    lines.append(f"Start IAT: {a.get('iat_c')}°C,   start coolant: {a.get('coolant_start_c')}°C,   end coolant: {a.get('coolant_end_c')}°C")
    lines.append("")
    lines.append("── Warm-up metrics ──")
    def _s(v):
        return f"{v:.0f}s" if v is not None else "(not reached)"
    lines.append(f"  RPM stabilized (< 900 for 10s)   : {_s(a.get('rpm_stabilized_s'))}")
    lines.append(f"  O2 B1S2 first activity           : {_s(a.get('o2_active_s'))}")
    lines.append(f"  Entered closed-loop fuel control : {_s(a.get('closed_loop_s'))}")
    lines.append(f"  Cat reached 400°C                : {_s(a.get('cat_400c_s'))}")
    lines.append(f"  Coolant reached {EXPECTED_COOLANT_WARM_C[0]}°C           : {_s(a.get('warm_up_s'))}")
    lines.append(f"  Final LTFT / STFT                : {a.get('final_ltft')}% / {a.get('final_stft')}%")
    lines.append("")
    lines.append("── Flags ──")
    for fl in flags:
        lines.append(f"  {fl}")
    with open(txt_path, "w") as f:
        f.write("\n".join(lines))
    print("\n" + "\n".join(lines))
    print(f"\n[+] CSV: {csv_path}")
    print(f"[+] Report: {txt_path}")


if __name__ == "__main__":
    main()
