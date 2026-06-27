"""ELM327 AT command + OBD2 service reference.

Enumerates every command the ELM327 supports and tracks which ones the toolkit
currently uses. Fuels the /elm-reference page to show capability coverage.
"""
from dataclasses import dataclass


@dataclass
class Command:
    cmd: str                # "ATxx" or OBD "MM"
    name: str
    category: str           # "init", "protocol", "message", "can", "kline", "obd", "safety"
    description: str
    used: bool = False      # Do we actually use this in the toolkit?
    used_in: list[str] = None  # Which modules
    safety: str = "safe"    # "safe" | "write" | "dangerous" | "deprecated"


# ── ELM327 AT commands ──────────────────────────────────────────────────
AT_COMMANDS: list[Command] = [
    # ── Basic init ──
    Command("ATZ", "Reset", "init", "Full reset to power-on defaults. Always start here.",
            used=True, used_in=["elm.init_can", "every tool"]),
    Command("ATD", "Default values", "init", "Reset to defaults without warm reset.",
            used=False),
    Command("ATE0/E1", "Echo off/on", "init", "Turn command echo off (E0) — saves bandwidth.",
            used=True, used_in=["elm.init_can"]),
    Command("ATL0/L1", "Linefeed off/on", "init", "Disable extra linefeeds (L0) — cleaner parsing.",
            used=True, used_in=["elm.init_can"]),
    Command("ATS0/S1", "Spaces off/on", "init", "Space between hex bytes — off for machine parse, on for humans.",
            used=True, used_in=["elm.init_can", "kline"]),
    Command("ATH0/H1", "Headers off/on", "init", "Show source address + header in response (H1) or strip (H0).",
            used=True, used_in=["elm.init_can"]),
    Command("ATI", "Identify adapter", "init", "Returns 'ELM327 v2.1' style banner.",
            used=True, used_in=["elm.adapter_info"]),
    Command("ATRV", "Read battery voltage", "init", "Reads the OBD pin 16 voltage directly.",
            used=True, used_in=["elm.adapter_info", "checklist"]),
    Command("ATWS", "Warm start", "init", "Restart without full reset — keeps config.",
            used=False),

    # ── Protocol selection ──
    Command("ATSP n", "Set protocol", "protocol",
            "0=auto, 1=SAE J1850 PWM, 2=SAE J1850 VPW, 3=ISO 9141-2, "
            "4=KWP 5-baud, 5=KWP fast-init, 6=ISO15765 CAN 11b/500, "
            "7=CAN 29b/500, 8=CAN 11b/250, 9=CAN 29b/250.",
            used=True, used_in=["elm.init_can", "kline"]),
    Command("ATTP n", "Try protocol", "protocol",
            "Like ATSP but doesn't auto-fallback — raises error if fails.",
            used=False),
    Command("ATDPN", "Display protocol number", "protocol", "Returns current proto digit.",
            used=True, used_in=["adapter_info"]),
    Command("ATDP", "Display protocol name", "protocol", "Verbose name.",
            used=True, used_in=["adapter_info"]),
    Command("ATAT n", "Adaptive timing", "protocol",
            "0=fixed, 1=adaptive default, 2=aggressive adaptive.",
            used=True, used_in=["elm.init_can"]),
    Command("ATST hh", "Set timeout", "protocol",
            "Set OBD response timeout in units of 4 ms. ATST96 = 150 ms.",
            used=True, used_in=["elm.init_can"]),

    # ── CAN-specific ──
    Command("ATCAF0/CAF1", "CAN auto-formatting", "can",
            "CAF1 auto-handles ISO-TP framing. CAF0 shows raw frames (for sniffing).",
            used=True, used_in=["elm.init_can", "elm.init_can_raw"]),
    Command("ATSH hhh(hh)", "Set header", "can",
            "Set the 3-byte (11-bit CAN) or 4-byte (29-bit CAN) source header for requests.",
            used=True, used_in=["kline", "multi-ecu-scan"]),
    Command("ATCRA hhh", "CAN Receive-Address filter", "can",
            "Only show frames with this arbitration ID (mask & filter combined).",
            used=False),
    Command("ATCM hhh", "CAN Mask", "can",
            "Set receive filter mask (bits that must match).",
            used=False),
    Command("ATCF hhh", "CAN Filter", "can",
            "Set receive filter pattern (bits to match).",
            used=False),
    Command("ATCP hh", "CAN priority", "can", "Priority byte for 29-bit CAN.",
            used=False),
    Command("ATCSM0/CSM1", "Silent monitoring off/on", "can",
            "CSM1 = receive-only, don't send ACK bit. Safer for sniffing.",
            used=False),
    Command("ATAL", "Allow long messages", "can",
            "Permit more than 7 data bytes per message.",
            used=True, used_in=["elm.init_can_raw"]),
    Command("ATMA", "Monitor All", "can",
            "Passive stream of every CAN frame (buffer-overrun prone at 500k).",
            used=True, used_in=["yaris_can_sniff.py"]),
    Command("ATMR hh", "Monitor for Receiver", "can",
            "Monitor only messages with target address matching hh.",
            used=False),
    Command("ATMI", "Monitor for one message", "can",
            "Returns next matching frame and stops.",
            used=False),
    Command("ATFC SD/SH/SM", "Flow control setup", "can",
            "Configure ISO-TP flow-control frame parameters for long multi-frame requests.",
            used=False),

    # ── K-Line / ISO 9141-2 / KWP2000 ──
    Command("ATIB 10/96", "ISO baud 10400/9600", "kline",
            "Switch K-Line baud rate.",
            used=False),
    Command("ATSI", "Slow init", "kline",
            "Trigger ISO 9141-2 5-baud wakeup manually.",
            used=False),
    Command("ATFI", "Fast init", "kline",
            "Trigger KWP2000 fast init manually.",
            used=False),
    Command("ATWM", "Wakeup message", "kline",
            "Set periodic keep-alive to prevent K-Line bus sleep.",
            used=False),
    Command("ATIIA hh", "ISO init address", "kline",
            "Set the target address for K-Line init.",
            used=False),
    Command("ATKW0/KW1", "Show KW2000 keywords", "kline",
            "Display the keyword bytes received during init (useful for debug).",
            used=False),
    Command("ATBI", "Bypass init", "kline",
            "Skip the init sequence — useful if a manual init was already done.",
            used=False),

    # ── Programmable parameters ──
    Command("ATPP hh", "PP xx", "init",
            "Programmable parameters — persist adapter config in flash.",
            used=False),
    Command("ATRD", "Read PP byte", "init",
            "Read a PP byte value.",
            used=False),
    Command("ATPC hh SV n", "PP save/lock", "init",
            "Save/lock a PP value.",
            used=False),

    # ── Misc ──
    Command("ATTA hh", "Tester address", "init",
            "Set our 'tester' source address for K-Line requests.",
            used=False),
    Command("ATV0/V1", "Variable dlc off/on", "can",
            "Allow variable Data Length Codes on CAN.",
            used=False),
    Command("ATJS", "J1939 SAE mode", "can",
            "Configure for J1939 commercial-vehicle protocol.",
            used=False),
]


# ── OBD2 services (SAE J1979) ───────────────────────────────────────────
OBD_SERVICES: list[Command] = [
    Command("01", "Show current data (PIDs)", "obd",
            "Live sensor values. PIDs 00-FF cover trims, RPM, MAF, O2, lambda, temps, etc.",
            used=True, used_in=["live dash", "yaris_full_pull_can.py", "all live tools"]),
    Command("02", "Show freeze-frame data", "obd",
            "Snapshot of all PIDs at the moment a DTC was set.",
            used=True, used_in=["yaris_full_pull_can.py"]),
    Command("03", "Show stored DTCs", "obd",
            "Confirmed fault codes.",
            used=True, used_in=["obd.read_dtcs", "every tool"]),
    Command("04", "Clear DTCs", "obd",
            "Wipe stored/pending + freeze frame + O2 test + readiness. Permanent (mode 0A) persists.",
            used=True, used_in=["yaris/clear.py"], safety="write"),
    Command("05", "Test results (O2 sensor)", "obd",
            "Non-CAN protocol — deprecated in favor of mode 06.",
            used=False, safety="deprecated"),
    Command("06", "Monitor test results (MIDs/TIDs)", "obd",
            "On-board diagnostic numeric results: cat efficiency %, O2 response ms, EGR flow, etc.",
            used=True, used_in=["yaris/mode06.py"]),
    Command("07", "Pending DTCs", "obd",
            "Codes that have failed one drive cycle but not yet confirmed.",
            used=True, used_in=["obd.read_dtcs"]),
    Command("08", "Request bidirectional control", "obd",
            "Vehicle-specific actuator tests (fuel pump, injectors, ...). Dangerous.",
            used=False, safety="dangerous"),
    Command("09", "Vehicle info (VIN, Cal ID, IPT)", "obd",
            "VIN, calibration IDs, Cal Verification Numbers, ECU name, In-use Performance Tracking.",
            used=True, used_in=["yaris_full_pull_can.py"]),
    Command("0A", "Permanent DTCs", "obd",
            "Codes that require 2 consecutive clean drive cycles to auto-clear — mode 04 cannot remove.",
            used=True, used_in=["obd.read_dtcs"]),

    # Toyota-specific + UDS
    Command("21", "Enhanced (Toyota-specific)", "obd",
            "Manufacturer-specific PIDs. Toyota uses heavily for cam angles, injector PW, etc.",
            used=True, used_in=["yaris/enhanced.py", "yaris_full_pull_can.py"]),
    Command("22", "UDS Read Data By Identifier", "obd",
            "ISO 14229. DIDs from F180-F1FF etc. Most need extended session.",
            used=True, used_in=["yaris_full_pull_can.py"]),
    Command("19", "UDS ReadDTCInformation", "obd",
            "Richer DTC data: status bits, fault occurrence counter, mileage-when-set.",
            used=False),
    Command("10", "UDS Diagnostic session control", "obd",
            "Change from default to extended session to unlock more DIDs.",
            used=False, safety="safe"),
    Command("27", "UDS Security Access", "obd",
            "Unlock protected services via seed/key challenge.",
            used=False, safety="dangerous"),
    Command("2E", "UDS Write Data By Identifier", "obd",
            "Write persistent data to ECU.",
            used=False, safety="dangerous"),
    Command("2F", "UDS Input/Output Control", "obd",
            "Force actuators (fuel pump, injectors, cooling fan).",
            used=False, safety="dangerous"),
    Command("31", "UDS Routine Control", "obd",
            "Run ECU routines (self-tests, calibration procedures).",
            used=False, safety="dangerous"),
    Command("34/36/37", "UDS Download/TransferData/TransferExit", "obd",
            "Firmware flash — absolutely not used here.",
            used=False, safety="dangerous"),
    Command("3B", "UDS Write Data (legacy)", "obd",
            "Older write service.",
            used=False, safety="dangerous"),
]


def coverage_stats() -> dict:
    def _stats(cmds):
        used = sum(1 for c in cmds if c.used)
        safe_unused = sum(1 for c in cmds if not c.used and c.safety == "safe")
        return {"total": len(cmds), "used": used, "safe_unused": safe_unused}

    return {
        "at_commands": _stats(AT_COMMANDS),
        "obd_services": _stats(OBD_SERVICES),
        "combined": {
            "total": len(AT_COMMANDS) + len(OBD_SERVICES),
            "used": sum(1 for c in AT_COMMANDS + OBD_SERVICES if c.used),
        },
    }


def unused_safe_commands() -> list[Command]:
    """Commands we haven't used but are safe — candidates for future work."""
    return [c for c in AT_COMMANDS + OBD_SERVICES
            if not c.used and c.safety == "safe"]
