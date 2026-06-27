"""Unified entry-point for the Yaris OBD2 toolkit.

Usage:
  yaris-diag <subcommand> [args...]

Subcommands:
  connect      Verify BT + rfcomm + adapter liveness
  pull         Full OBD2 state dump (mode 01/03/07/0A/02/06/09/21/22)
  dash         Live dashboard with CSV logging
  scan         Multi-ECU DTC scan across 14 CAN addresses
  sniff        Passive CAN bus sniff (ATMA)
  tpms         TPMS probe (DTCs + DIDs + mode 21 TPMS subfunctions)
  clear        Audited code clear (snapshot → 04 → snapshot)
  readiness    Readiness-monitor tracker (--once or --watch)
  analyze      Analyze a dash CSV for MAF/LTFT health
  verify       Compare two dash CSVs (before/after repair)
  coldstart    Cold-start warm-up analyzer
  cat          Catalyst efficiency monitor
  healthcheck  One-shot "is my car OK" report
  dtc          Look up a single DTC in the knowledge base

Use `yaris-diag <subcommand> --help` for per-subcommand flags.
"""
import argparse
import os
import sys

from . import vehicle


def cmd_connect(argv):
    from . import connect as C
    status = C.ensure_connected()
    print("── Connection status ──")
    print(f"  port      : {status['port']}")
    print(f"  paired    : {status['paired']}")
    print(f"  rfcomm    : {'bound' if status['bound'] else 'not bound'}")
    print(f"  adapter   : {'ALIVE' if status['live'] else 'not responding'}")
    if status.get("adapter"):
        for k, v in status["adapter"].items():
            print(f"    {k}: {v}")
    for n in status.get("notes", []):
        print(f"  ! {n}")
    return 0 if status["live"] else 1


def cmd_pull(argv):
    # Delegate to existing yaris_full_pull_can.py
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_full_pull_can.py"] + argv)


def cmd_dash(argv):
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_live_dash.py"] + argv)


def cmd_scan(argv):
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_all_ecu_scan.py"] + argv)


def cmd_sniff(argv):
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_can_sniff.py"] + argv)


def cmd_tpms(argv):
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_tpms_probe.py"] + argv)


def cmd_analyze(argv):
    os.execv(sys.executable, [sys.executable,
                              f"{vehicle.TOOLS_DIR}/yaris_maf_analysis.py"] + argv)


def cmd_clear(argv):
    from .clear import main as m
    sys.argv = ["clear"] + argv
    m()


def cmd_readiness(argv):
    from .readiness import main as m
    sys.argv = ["readiness"] + argv
    m()


def cmd_verify(argv):
    from .verify import main as m
    sys.argv = ["verify"] + argv
    m()


def cmd_coldstart(argv):
    from .coldstart import main as m
    sys.argv = ["coldstart"] + argv
    m()


def cmd_cat(argv):
    from .cat_efficiency import main as m
    sys.argv = ["cat"] + argv
    m()


def cmd_healthcheck(argv):
    from .healthcheck import main as m
    sys.argv = ["healthcheck"] + argv
    m()


def cmd_mode06(argv):
    from .mode06 import main as m
    sys.argv = ["mode06"] + argv
    m()


def cmd_enhanced(argv):
    from .enhanced import main as m
    sys.argv = ["enhanced"] + argv
    m()


def cmd_drive(argv):
    from .drive_cycle import main as m
    sys.argv = ["drive"] + argv
    m()


def cmd_web(argv):
    from .webdash import main as m
    sys.argv = ["web"] + argv
    m()


def cmd_history(argv):
    from .history import main as m
    sys.argv = ["history"] + argv
    m()


def cmd_kline(argv):
    from .kline import main as m
    sys.argv = ["kline"] + argv
    m()


def cmd_plot(argv):
    from .plots import main as m
    sys.argv = ["plot"] + argv
    m()


def cmd_economy(argv):
    from .economy import main as m
    sys.argv = ["economy"] + argv
    m()


def cmd_dtc(argv):
    from .dtc_db import resolve, rank_and_explain
    if not argv:
        print("Usage: yaris-diag dtc <CODE> [CODE...]")
        return 1
    out = rank_and_explain([c.upper() for c in argv])
    for e in out:
        icon = {"critical": "✗", "warn": "⚠", "minor": "·"}.get(e.get("severity"), "?")
        print(f"\n{icon} {e['code']}: {e['title']}")
        if e.get("symptoms"):
            print(f"  Symptoms: {'; '.join(e['symptoms'])}")
        if e.get("causes"):
            print(f"  Causes (ranked):")
            for c in e["causes"]:
                print(f"    - {c}")
        if e.get("diy_steps"):
            print(f"  DIY path:")
            for s in e["diy_steps"]:
                print(f"    {s}")
        if e.get("parts"):
            print(f"  Parts: {', '.join(e['parts'])}")
        if e.get("cost_diy_usd") and e["cost_diy_usd"] != [0, 0]:
            print(f"  Cost DIY: ${e['cost_diy_usd'][0]}-${e['cost_diy_usd'][1]}")
        if e.get("cost_shop_usd") and e["cost_shop_usd"] != [0, 0]:
            print(f"  Cost shop: ${e['cost_shop_usd'][0]}-${e['cost_shop_usd'][1]}")
        if e.get("notes"):
            print(f"  Note: {e['notes']}")
        if e.get("kb_links"):
            print(f"  See in YarisRepair/ KB:")
            for link in e["kb_links"]:
                print(f"    → {link}")
    return 0


SUBCOMMANDS = {
    "connect": cmd_connect,
    "pull": cmd_pull,
    "dash": cmd_dash,
    "scan": cmd_scan,
    "sniff": cmd_sniff,
    "tpms": cmd_tpms,
    "analyze": cmd_analyze,
    "clear": cmd_clear,
    "readiness": cmd_readiness,
    "verify": cmd_verify,
    "coldstart": cmd_coldstart,
    "cat": cmd_cat,
    "healthcheck": cmd_healthcheck,
    "mode06": cmd_mode06,
    "enhanced": cmd_enhanced,
    "drive": cmd_drive,
    "web": cmd_web,
    "history": cmd_history,
    "kline": cmd_kline,
    "plot": cmd_plot,
    "economy": cmd_economy,
    "dtc": cmd_dtc,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("\nAvailable subcommands:")
        for k in SUBCOMMANDS:
            print(f"  {k}")
        return 0
    sub = sys.argv[1]
    argv = sys.argv[2:]
    fn = SUBCOMMANDS.get(sub)
    if not fn:
        print(f"Unknown subcommand: {sub}")
        print("Run `yaris-diag --help` for the list.")
        return 1
    return fn(argv) or 0


if __name__ == "__main__":
    sys.exit(main() or 0)
