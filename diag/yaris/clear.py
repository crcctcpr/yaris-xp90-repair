"""Audited DTC clear.

Captures full ECU state (DTCs, freeze frame, readiness, MIL status, live trims,
MIL-distance, warm-up count) BEFORE clearing, sends mode 04, captures state
AFTER clearing, and writes a complete audit trail. Never clears blindly.

Usage:
  python3 -m yaris.clear [--yes]   # --yes skips the confirmation prompt
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

from .elm import Elm
from .obd import read_pid, read_dtcs, decode_pid, decode_readiness, PID_NAMES, FUEL_SYSTEM_STATE, parse_can
from .vehicle import DEFAULT_PORT, REPORT_DIR


DIAGNOSTIC_PIDS = [0x01, 0x03, 0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D, 0x0E, 0x0F,
                   0x10, 0x11, 0x15, 0x21, 0x30, 0x31, 0x34, 0x3C, 0x42, 0x44, 0x46, 0x1F]

FREEZE_FRAME_PIDS = [0x02, 0x03, 0x04, 0x05, 0x0C, 0x0D, 0x0F, 0x10, 0x11]


def snapshot(elm: Elm) -> dict:
    """Capture a full diagnostic state."""
    snap = {"ts": datetime.now().isoformat(timespec="seconds"), "live": {}, "dtcs": {}, "freeze": {}, "readiness": {}}
    # Live PIDs
    for pid in DIAGNOSTIC_PIDS:
        p = read_pid(elm, f"01{pid:02X}", 1.2)
        if p is None:
            continue
        val = decode_pid(pid, p)
        name = PID_NAMES.get(pid, f"PID {pid:02X}")
        # Normalize fuel-sys state
        if pid == 0x03 and isinstance(val, dict):
            fs1 = val.get("FS1", 0)
            val["FS1_state"] = FUEL_SYSTEM_STATE.get(fs1, "?")
        snap["live"][f"01{pid:02X}"] = {"name": name, "value": val, "raw": p.hex()}
        if pid == 0x01:
            snap["readiness"] = decode_readiness(p)
    # DTCs
    snap["dtcs"] = read_dtcs(elm)
    # Freeze frame
    for pid in FREEZE_FRAME_PIDS:
        resp = elm.send(f"02{pid:02X}00", 1.5)
        ecus = parse_can(resp)
        for data in ecus.values():
            if len(data) >= 3 and data[0] == 0x42 and data[1] == pid:
                payload = data[3:] if len(data) > 3 else b""
                val = decode_pid(pid, payload) if pid != 0x02 else payload.hex()
                snap["freeze"][f"02{pid:02X}"] = {"raw": payload.hex(), "value": val}
                break
    return snap


def format_snapshot(s: dict, title: str) -> list[str]:
    lines = [f"── {title} ({s['ts']}) ──"]
    r = s.get("readiness", {})
    if r:
        lines.append(f"   MIL: {'ON' if r.get('MIL') else 'OFF'}   DTC count: {r.get('DTC_count')}")
    for bucket, label in [("stored", "Stored"), ("pending", "Pending"), ("permanent", "Permanent")]:
        codes = s["dtcs"].get(bucket, [])
        lines.append(f"   {label:10}: {', '.join(codes) if codes else '(none)'}")
    # Key live values
    for pid, key in [(0x07, "LTFT"), (0x06, "STFT"), (0x10, "MAF"), (0x0C, "RPM"),
                     (0x05, "Coolant"), (0x21, "MIL-dist"), (0x30, "Warmups"), (0x31, "Dist since clear")]:
        k = f"01{pid:02X}"
        if k in s["live"]:
            v = s["live"][k]["value"]
            lines.append(f"   {key:16}: {v}")
    if s["freeze"]:
        lines.append(f"   Freeze frame: {len(s['freeze'])} PID(s) captured")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = f"{REPORT_DIR}/clear_audit_{ts}.json"
    txt_path = f"{REPORT_DIR}/clear_audit_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"═══ Audited Code Clear — {ts} ═══\n")
    try:
        with Elm(args.port) as e:
            e.init_can()
            print("[*] Capturing BEFORE snapshot…")
            before = snapshot(e)
            for l in format_snapshot(before, "BEFORE"):
                print(l)
            print()

            if not args.yes:
                resp = input("Proceed with code clear (mode 04)? [y/N]: ").strip().lower()
                if resp not in ("y", "yes"):
                    print("[*] Aborted by user. No clear sent.")
                    audit = {"ts": ts, "before": before, "cleared": False, "abort_reason": "user declined"}
                    with open(audit_path, "w") as f:
                        json.dump(audit, f, indent=2)
                    print(f"[+] Audit (no-op) written: {audit_path}")
                    sys.exit(0)

            print("[*] Sending mode 04 (clear DTCs + freeze frame + readiness)…")
            resp = e.send("04", 4.0)
            print(f"    response: {resp!r}")
            ecus = parse_can(resp)
            ok = any(data and data[0] == 0x44 for data in ecus.values())
            print(f"    clear {'ACCEPTED ✓' if ok else 'NOT accepted ✗'}")

            # Let ECM settle
            time.sleep(1.5)

            print("\n[*] Capturing AFTER snapshot…")
            after = snapshot(e)
            for l in format_snapshot(after, "AFTER"):
                print(l)

            audit = {
                "ts": ts, "cleared": ok, "before": before, "after": after,
                "clear_response": resp,
            }
            with open(audit_path, "w") as f:
                json.dump(audit, f, indent=2, default=str)

            # Text report
            with open(txt_path, "w") as f:
                f.write(f"Audited code clear — {ts}\n\n")
                f.write("\n".join(format_snapshot(before, "BEFORE")))
                f.write(f"\n\nMode 04 response: {resp}\nClear accepted: {ok}\n\n")
                f.write("\n".join(format_snapshot(after, "AFTER")))
                f.write("\n\n")
                # Notes
                perm_before = set(before["dtcs"].get("permanent", []))
                perm_after = set(after["dtcs"].get("permanent", []))
                if perm_after:
                    f.write(f"NOTE: Permanent code(s) {sorted(perm_after)} persist — this is correct. ")
                    f.write("Permanent codes clear only after 2 consecutive drive cycles without the fault.\n")

            print(f"\n[+] Audit JSON: {audit_path}")
            print(f"[+] Audit TXT : {txt_path}")
    except KeyboardInterrupt:
        print("\n[!] Interrupted. No clear sent unless the 04 command had already been issued.")
        sys.exit(1)


if __name__ == "__main__":
    main()
