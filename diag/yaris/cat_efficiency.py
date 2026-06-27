"""Catalyst efficiency monitor.

Samples upstream (wideband λ via PID 0134) and downstream (narrowband V via
PID 0115) O2 signals at ~2 Hz. Computes swing magnitudes; a healthy cat
stores O2 and smooths the downstream signal relative to upstream.

Metric:  swing_ratio = std(downstream_V) / std(upstream_λ)
  - Healthy cat:  ratio << 1 (downstream is smooth, upstream oscillates)
  - Failing cat:  ratio approaches 1 (downstream mirrors upstream switching)

Also reports downstream switch rate (Hz). > ~1 Hz sustained = P0420 likely.

Usage:
  python3 -m yaris.cat_efficiency [--duration 90]
"""
import argparse
import math
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, decode_pid
from .vehicle import DEFAULT_PORT, REPORT_DIR


def sample(elm: Elm) -> tuple[float | None, float | None, float | None]:
    """(upstream_lambda, downstream_V, rpm) or None per field."""
    p34 = read_pid(elm, "0134", 0.5)
    p15 = read_pid(elm, "0115", 0.5)
    pC = read_pid(elm, "010C", 0.5)
    up_l = None
    dn_v = None
    rpm = None
    if p34:
        d = decode_pid(0x34, p34)
        if isinstance(d, dict):
            up_l = d.get("lambda")
    if p15:
        d = decode_pid(0x15, p15)
        if isinstance(d, dict):
            dn_v = d.get("V")
    if pC:
        rpm = decode_pid(0x0C, pC)
    return up_l, dn_v, rpm


def std(vals):
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))


def switch_rate(values: list[tuple[float, float]], threshold_low: float, threshold_high: float) -> float:
    """Count crossings through midpoint band. values: [(t, v)]"""
    crossings = 0
    state = None
    for t, v in values:
        if v < threshold_low:
            new = "lo"
        elif v > threshold_high:
            new = "hi"
        else:
            continue
        if state and new != state:
            crossings += 1
        state = new
    if len(values) < 2:
        return 0.0
    duration = values[-1][0] - values[0][0]
    return crossings / duration if duration > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--duration", type=float, default=90.0)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"{REPORT_DIR}/cat_eff_{ts}.csv"
    txt_path = f"{REPORT_DIR}/cat_eff_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"═══ Catalyst efficiency monitor — {ts} ═══")
    print(f"  Need: engine warm (coolant > 80°C), RPM 1500-2500 steady if possible.")
    print(f"  Sampling for {args.duration:.0f}s at ~1.5 Hz…\n")

    up_vals: list[tuple[float, float]] = []
    dn_vals: list[tuple[float, float]] = []
    rpm_vals: list[float] = []

    with Elm(args.port) as e:
        e.init_can()
        t0 = time.time()
        with open(csv_path, "w") as f:
            f.write("t_s,upstream_lambda,downstream_V,rpm\n")
            while time.time() - t0 < args.duration:
                up_l, dn_v, rpm = sample(e)
                t = time.time() - t0
                if up_l is not None:
                    up_vals.append((t, up_l))
                if dn_v is not None:
                    dn_vals.append((t, dn_v))
                if rpm is not None:
                    rpm_vals.append(rpm)
                f.write(f"{t:.2f},{up_l if up_l is not None else ''},"
                        f"{dn_v if dn_v is not None else ''},{rpm if rpm is not None else ''}\n")
                f.flush()
                if int(t) % 10 == 0:
                    up_s = f"{up_l:.3f}" if up_l is not None else "-"
                    dn_s = f"{dn_v:.3f}" if dn_v is not None else "-"
                    rp = f"{rpm:.0f}" if rpm else "?"
                    print(f"  [{t:5.1f}s] λ={up_s}  dnV={dn_s}  rpm={rp}")

    # Metrics
    up_std = std([v for _, v in up_vals])
    dn_std = std([v for _, v in dn_vals])
    dn_switch = switch_rate(dn_vals, 0.3, 0.6)
    up_switch = switch_rate(up_vals, 0.98, 1.02)
    rpm_mean = sum(rpm_vals)/len(rpm_vals) if rpm_vals else 0

    if up_std > 0:
        ratio = dn_std / up_std
    else:
        ratio = float("inf")

    verdict = []
    if len(up_vals) < 20 or len(dn_vals) < 20:
        verdict.append("⚠ Not enough samples — rerun after engine warm-up / steady cruise.")
    elif rpm_mean < 1200:
        verdict.append(f"⚠ Average RPM {rpm_mean:.0f} too low — cat monitor runs best at 1500-2500 RPM cruise.")
    if dn_switch > 1.0:
        verdict.append(f"✗ Downstream O2 switching {dn_switch:.2f} Hz — cat efficiency poor (typical P0420 signature)")
    elif dn_switch > 0.5:
        verdict.append(f"~ Downstream switching {dn_switch:.2f} Hz — marginal, watch for P0420")
    else:
        verdict.append(f"✓ Downstream switching {dn_switch:.2f} Hz — cat storing O2 correctly")

    if ratio < 0.2:
        verdict.append(f"✓ Swing ratio {ratio:.2f} (healthy <0.3)")
    elif ratio < 0.5:
        verdict.append(f"~ Swing ratio {ratio:.2f} (borderline)")
    else:
        verdict.append(f"✗ Swing ratio {ratio:.2f} — downstream mirroring upstream, cat likely weak")

    lines = [f"═══ Catalyst efficiency — {ts} ═══", ""]
    lines.append(f"Samples upstream: {len(up_vals)},  downstream: {len(dn_vals)}")
    lines.append(f"Average RPM: {rpm_mean:.0f}")
    lines.append("")
    lines.append(f"Upstream λ std   : {up_std:.4f}")
    lines.append(f"Downstream V std : {dn_std:.4f}")
    lines.append(f"Swing ratio (dn/up std) : {ratio:.3f}")
    lines.append(f"Upstream λ switch rate   : {up_switch:.3f} Hz (expected > 0.3)")
    lines.append(f"Downstream V switch rate : {dn_switch:.3f} Hz (expected < 0.3 healthy)")
    lines.append("")
    lines.append("── Verdict ──")
    for v in verdict:
        lines.append(f"  {v}")

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))
    print()
    print("\n".join(lines))
    print(f"\n[+] CSV: {csv_path}")
    print(f"[+] Report: {txt_path}")


if __name__ == "__main__":
    main()
