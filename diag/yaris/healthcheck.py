"""One-shot health check.

"Just tell me if my car is OK." Runs full pull, cross-references DTCs against
the local knowledge base, checks live parameters against expected ranges,
produces a ranked priority list.

Usage:
  python3 -m yaris.healthcheck
"""
import argparse
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, read_dtcs, decode_pid, decode_readiness, FUEL_SYSTEM_STATE, parse_can
from .dtc_db import resolve, rank_and_explain
from .vehicle import (
    DEFAULT_PORT, REPORT_DIR, expected_maf,
    EXPECTED_IDLE_RPM, EXPECTED_COOLANT_WARM_C,
    EXPECTED_STFT_PCT, EXPECTED_LTFT_PCT, EXPECTED_LAMBDA,
    EXPECTED_BATT_V_ENGINE_RUNNING, EXPECTED_MAF_IDLE_GS, EXPECTED_TIMING_ADV_IDLE,
)


def check_range(label: str, value, lo: float, hi: float, unit: str = "") -> tuple[str, str]:
    if value is None:
        return "?", f"{label}: (no data)"
    if lo <= value <= hi:
        return "ok", f"{label}: {value}{unit}  (ok)"
    return "warn", f"{label}: {value}{unit}  (expected {lo}..{hi}{unit})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/healthcheck_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    issues: list[tuple[int, str]] = []  # (severity 0=crit,1=warn,2=minor, text)
    ok_items: list[str] = []

    print(f"═══ Health check — {ts} ═══\n")
    with Elm(args.port) as e:
        e.init_can()
        info = e.adapter_info()
        print(f"[+] Adapter {info['id']} on {info['proto']}, OBD V {info['vbatt']}")

        # Engine state
        rpm_p = read_pid(e, "010C", 1.2)
        rpm = decode_pid(0x0C, rpm_p) if rpm_p else None
        engine_running = rpm is not None and rpm > 400
        if engine_running:
            print(f"[+] Engine running at {rpm:.0f} RPM")
        else:
            print(f"[!] Engine NOT running — some checks limited.")

        # DTCs
        dtcs = read_dtcs(e)
        all_codes = []
        for bucket, codes in dtcs.items():
            all_codes.extend(codes)
        all_codes = list(dict.fromkeys(all_codes))  # dedup preserve order
        enriched = rank_and_explain(all_codes)
        if all_codes:
            print(f"[+] {len(all_codes)} unique DTC(s) across stored/pending/permanent")
        else:
            print("[+] No DTCs present")
            ok_items.append("No fault codes in any memory bank")

        # MIL status
        readiness_p = read_pid(e, "0101", 1.0)
        readiness = decode_readiness(readiness_p) if readiness_p else {}
        mil_on = readiness.get("MIL", False)
        if mil_on:
            issues.append((0, f"MIL is ON with {readiness.get('DTC_count',0)} code(s)"))
        else:
            ok_items.append("MIL is OFF")

        # Readiness monitor completion
        if readiness:
            incomp = []
            for key, name in [("cat_incomplete","Catalyst"), ("evap_incomplete","EVAP"),
                              ("o2_incomplete","O2"), ("o2htr_incomplete","O2 heater"),
                              ("egr_incomplete","EGR")]:
                sup = readiness.get(key.replace("incomplete", "sup"), False)
                if sup and readiness.get(key, False):
                    incomp.append(name)
            if incomp:
                issues.append((2, f"Readiness monitors not yet run: {', '.join(incomp)}  "
                                 f"(drive cycle needed — normal after recent clear)"))
            else:
                ok_items.append("All readiness monitors complete")

        if engine_running:
            # Live sensor sanity
            coolant_p = read_pid(e, "0105", 1.0)
            coolant = decode_pid(0x05, coolant_p) if coolant_p else None
            stft_p = read_pid(e, "0106", 1.0); stft = decode_pid(0x06, stft_p) if stft_p else None
            ltft_p = read_pid(e, "0107", 1.0); ltft = decode_pid(0x07, ltft_p) if ltft_p else None
            maf_p = read_pid(e, "0110", 1.0); maf = decode_pid(0x10, maf_p) if maf_p else None
            load_p = read_pid(e, "0104", 1.0); load = decode_pid(0x04, load_p) if load_p else None
            timing_p = read_pid(e, "010E", 1.0); timing = decode_pid(0x0E, timing_p) if timing_p else None
            fs_p = read_pid(e, "0103", 1.0)
            fs = decode_pid(0x03, fs_p) if fs_p else None
            o2wb_p = read_pid(e, "0134", 1.0)
            o2wb = decode_pid(0x34, o2wb_p) if o2wb_p else None
            ctlv_p = read_pid(e, "0142", 1.0)
            ctlv = decode_pid(0x42, ctlv_p) if ctlv_p else None

            is_idle = rpm < 900

            # RPM
            if is_idle:
                lo, hi = EXPECTED_IDLE_RPM
                if not (lo <= rpm <= hi):
                    issues.append((1, f"Idle RPM {rpm:.0f} outside {lo}-{hi}"))
                else:
                    ok_items.append(f"Idle RPM healthy ({rpm:.0f})")

            # Coolant
            if coolant is not None:
                lo, hi = EXPECTED_COOLANT_WARM_C
                if coolant < lo - 20:
                    issues.append((0, f"Coolant {coolant}°C too cold — thermostat or warm-up issue"))
                elif coolant > hi + 5:
                    issues.append((0, f"Coolant {coolant}°C — OVERHEATING, stop engine"))
                elif coolant < lo:
                    issues.append((2, f"Coolant {coolant}°C — not fully warm yet"))
                else:
                    ok_items.append(f"Coolant {coolant}°C (normal)")

            # Trims
            if stft is not None:
                if abs(stft) > 10:
                    issues.append((1, f"STFT {stft:+.1f}% offset — active fuel correction"))
                else:
                    ok_items.append(f"STFT {stft:+.1f}% (centered)")
            if ltft is not None:
                lo, hi = EXPECTED_LTFT_PCT
                if ltft < lo - 3 or ltft > hi + 3:
                    if ltft > hi + 10:
                        issues.append((0, f"LTFT {ltft:+.1f}% saturated rich-side — MAF likely under-reading"))
                    elif ltft < lo - 10:
                        issues.append((0, f"LTFT {ltft:+.1f}% saturated lean-side — vacuum leak or fuel delivery"))
                    else:
                        issues.append((1, f"LTFT {ltft:+.1f}% outside {lo}..{hi}% — adaptive compensation high"))
                else:
                    ok_items.append(f"LTFT {ltft:+.1f}% (healthy)")

            # MAF vs expected — throttle-based (independent of MAF for diagnosis)
            throttle_p = read_pid(e, "0111", 1.0)
            throttle = decode_pid(0x11, throttle_p) if throttle_p else None
            if maf is not None and throttle is not None:
                exp = expected_maf(rpm, throttle_pct=throttle, mode="throttle")
                ratio = maf / exp if exp > 0 else 0
                if is_idle:
                    mlo, mhi = EXPECTED_MAF_IDLE_GS
                    if not (mlo <= maf <= mhi):
                        issues.append((1, f"MAF idle {maf:.2f} g/s outside {mlo}-{mhi}"))
                if ratio < 0.5:
                    issues.append((0, f"MAF ratio {ratio:.2f}× expected — sensor badly under-reading"))
                elif ratio < 0.80:
                    issues.append((1, f"MAF ratio {ratio:.2f}× expected — sensor reading low (healthy: 0.85-1.15×)"))
                elif ratio > 1.35:
                    issues.append((1, f"MAF ratio {ratio:.2f}× expected — sensor over-reading"))
                else:
                    ok_items.append(f"MAF ratio {ratio:.2f}× expected (healthy)")

            # λ
            if o2wb and isinstance(o2wb, dict):
                lam = o2wb.get("lambda", 0)
                lo, hi = EXPECTED_LAMBDA
                if lo <= lam <= hi:
                    ok_items.append(f"Wideband λ {lam:.3f} (stoich)")
                else:
                    issues.append((1, f"Wideband λ {lam:.3f} outside {lo}-{hi}"))

            # Alternator V
            if ctlv is not None:
                lo, hi = EXPECTED_BATT_V_ENGINE_RUNNING
                if ctlv < lo:
                    issues.append((0, f"Alternator V {ctlv:.2f}V below {lo}V — charging issue"))
                elif ctlv > hi:
                    issues.append((1, f"Alternator V {ctlv:.2f}V above {hi}V — regulator issue"))
                else:
                    ok_items.append(f"Charging {ctlv:.2f}V (healthy)")

            # Fuel system state
            if fs and isinstance(fs, dict):
                fs1 = fs.get("FS1", 0)
                state = FUEL_SYSTEM_STATE.get(fs1, "?")
                if fs1 == 2:
                    ok_items.append(f"Closed-loop fuel control active")
                elif fs1 in (1, 4):
                    ok_items.append(f"Fuel sys: {state} (normal transient)")
                else:
                    issues.append((1, f"Fuel system state: {state} (fs1={fs1})"))

        # Build report
        lines = [f"═══ 2011 Yaris Health Check — {ts} ═══\n"]
        lines.append(f"Adapter: {info.get('id','?')}   Protocol: {info.get('proto','?')}")
        lines.append(f"Engine: {'running @ '+str(int(rpm))+' RPM' if engine_running else 'not running'}\n")

        # Issues first, sorted by severity
        issues.sort(key=lambda x: x[0])
        if issues:
            lines.append("── Issues (prioritized) ──")
            for sev, text in issues:
                icon = ["✗", "⚠", "·"][min(sev, 2)]
                lines.append(f"  {icon} {text}")
            lines.append("")

        if enriched:
            lines.append("── Fault codes with explanations ──")
            for e in enriched:
                icon = {"critical": "✗", "warn": "⚠", "minor": "·"}.get(e["severity"], "?")
                lines.append(f"  {icon} {e['code']}: {e['title']}")
                if e.get("causes"):
                    lines.append(f"      likely causes (ranked):")
                    for c in e["causes"][:5]:
                        lines.append(f"        - {c}")
                if e.get("diy_steps"):
                    lines.append(f"      DIY path:")
                    for s in e["diy_steps"][:5]:
                        lines.append(f"        {s}")
                if e.get("parts"):
                    lines.append(f"      parts: {', '.join(e['parts'])}")
                if e.get("cost_diy_usd") and e["cost_diy_usd"] != [0, 0]:
                    lo, hi = e["cost_diy_usd"]
                    lines.append(f"      cost DIY: ${lo}-${hi}")
                if e.get("notes"):
                    lines.append(f"      note: {e['notes']}")
                lines.append("")

        if ok_items:
            lines.append("── Healthy ──")
            for ok in ok_items:
                lines.append(f"  ✓ {ok}")
            lines.append("")

        if not issues and not all_codes:
            lines.append("══════════════════════════════════════")
            lines.append("   Overall: HEALTHY — no action needed")
            lines.append("══════════════════════════════════════")

        with open(report_path, "w") as f:
            f.write("\n".join(lines))
        print("\n" + "\n".join(lines))
        print(f"\n[+] Report: {report_path}")


if __name__ == "__main__":
    main()
