"""UDS Service 0x19 — ReadDTCInformation.

Mode 03/07/0A give you codes. Mode 19 gives you codes PLUS:
  - DTC status byte: 8 bits describing the fault state (failed this cycle,
    test run this cycle, pending, confirmed, fault test completed since
    clear, etc.)
  - Occurrence counter (how many times fault has latched)
  - Mileage-when-set (on some ECUs)
  - Freeze-frame record number

Common sub-functions (per ISO 14229):
  0x01 — reportNumberOfDTCByStatusMask
  0x02 — reportDTCByStatusMask
  0x03 — reportDTCSnapshotIdentification
  0x04 — reportDTCSnapshotRecordByDTCNumber
  0x06 — reportDTCExtDataRecordByDTCNumber
  0x07 — reportNumberOfDTCBySeverityMaskRecord
  0x0A — reportSupportedDTCs
  0x14 — reportDTCFaultDetectionCounter

We focus on 0x02 (report all DTCs with status) and 0x06 (extended data).
"""
from dataclasses import dataclass

from .elm import Elm
from .obd import parse_can, decode_dtcs


# DTC status bit masks (per ISO 14229)
STATUS_BITS = [
    (0x01, "testFailed", "Failed on most recent completed test"),
    (0x02, "testFailedThisCycle", "Failed this operating cycle"),
    (0x04, "pendingDTC", "Latched as pending"),
    (0x08, "confirmedDTC", "Confirmed (i.e. visible to mode 03)"),
    (0x10, "testNotCompletedSinceClear", "Monitor hasn't run since last clear"),
    (0x20, "testFailedSinceClear", "Failed at least once since last clear"),
    (0x40, "testNotCompletedThisCycle", "Monitor hasn't run this cycle"),
    (0x80, "warningIndicatorReq", "MIL (or equivalent warning) requested"),
]


def decode_status(status_byte: int) -> dict:
    """Decode a DTC status byte into named bits."""
    out = {"raw": status_byte, "bits": {}}
    for mask, name, desc in STATUS_BITS:
        out["bits"][name] = bool(status_byte & mask)
    # Derived: is this DTC "active" right now?
    out["is_currently_failing"] = bool(status_byte & 0x01)
    out["confirmed"] = bool(status_byte & 0x08)
    out["mil_requested"] = bool(status_byte & 0x80)
    # Severity guess
    if status_byte & 0x80:
        out["severity"] = "critical"
    elif status_byte & 0x08:
        out["severity"] = "warn"
    elif status_byte & 0x04:
        out["severity"] = "pending"
    else:
        out["severity"] = "info"
    return out


@dataclass
class Mode19DtcRecord:
    code: str
    status: dict  # decoded status bits
    raw_hex: str


def decode_mode19_0x02(payload: bytes) -> list[Mode19DtcRecord]:
    """Parse a mode 19 / 0x02 response.

    Format:  <59> <subfunc=02> <status_availability_mask> <DTC_hi> <DTC_mid>
             <DTC_lo> <status> ... repeating
    But we get to it after the 0x59 0x02 <avail> header.
    """
    records = []
    if len(payload) < 4:
        return records
    # First byte after 0x59 0x02 is the availability mask; skip it
    i = 1
    while i + 3 < len(payload):
        b1 = payload[i]
        b2 = payload[i + 1]
        b3 = payload[i + 2]
        status = payload[i + 3]
        letter = ["P", "C", "B", "U"][(b1 >> 6) & 0x3]
        code = f"{letter}{(b1 >> 4) & 0x3}{b1 & 0x0F:X}{(b2 >> 4) & 0x0F:X}{b2 & 0x0F:X}"
        # Note: mode 19 uses 3-byte DTCs (b3 is usually 00 for standard codes)
        records.append(Mode19DtcRecord(
            code=code, status=decode_status(status),
            raw_hex=f"{b1:02X}{b2:02X}{b3:02X}{status:02X}",
        ))
        i += 4
    return records


def read_enhanced_dtcs(elm: Elm, status_mask: int = 0xFF) -> list[Mode19DtcRecord]:
    """Send 19 02 <mask> and parse the result.

    status_mask = 0xFF returns every DTC regardless of state.
    Mask bits:  0x08 = confirmed, 0x04 = pending, 0x01 = test failed, etc.
    """
    cmd = f"1902{status_mask:02X}"
    resp = elm.send(cmd, 3.0)
    ecus = parse_can(resp)
    out: list[Mode19DtcRecord] = []
    for data in ecus.values():
        if len(data) >= 2 and data[0] == 0x59 and data[1] == 0x02:
            # payload starts after 59 02
            out.extend(decode_mode19_0x02(data[2:]))
    return out


def read_fault_detection_counter(elm: Elm) -> list[dict]:
    """Service 19 sub 14 — each DTC's fault-detection counter (0-127 or -128-0)."""
    resp = elm.send("1914", 3.0)
    ecus = parse_can(resp)
    out = []
    for data in ecus.values():
        if len(data) >= 2 and data[0] == 0x59 and data[1] == 0x14:
            i = 2
            while i + 3 < len(data):
                b1, b2, b3, cnt = data[i], data[i+1], data[i+2], data[i+3]
                if b1 == 0 and b2 == 0 and b3 == 0:
                    i += 4
                    continue
                letter = ["P", "C", "B", "U"][(b1 >> 6) & 0x3]
                code = f"{letter}{(b1 >> 4) & 0x3}{b1 & 0x0F:X}{(b2 >> 4) & 0x0F:X}{b2 & 0x0F:X}"
                # Signed byte
                counter = cnt if cnt < 128 else cnt - 256
                out.append({"code": code, "counter": counter,
                             "interpretation": _interpret_fdc(counter)})
                i += 4
    return out


def _interpret_fdc(counter: int) -> str:
    """Fault detection counter interpretation per ISO 14229-1."""
    if counter == -128: return "never tested"
    if counter < 0: return f"{abs(counter)} passing events"
    if counter == 0: return "test completed, passed last time"
    if counter < 127: return f"{counter} failing events this cycle (pre-confirmation)"
    return "127 failures — confirmed"
