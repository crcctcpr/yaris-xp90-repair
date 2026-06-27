"""OBD2 request/response + ISO-TP CAN parsing + PID/DTC decoders."""
from .elm import Elm


NRC = {
    0x10: "general reject",
    0x11: "service not supported",
    0x12: "subfunction not supported",
    0x13: "invalid message length",
    0x22: "conditions not correct",
    0x31: "request out of range",
    0x33: "security access denied",
    0x7E: "subfunc not in active session",
    0x7F: "service not in active session",
}


def parse_can(resp: str) -> dict:
    """Parse raw ELM CAN response text into {header: reassembled_bytes}. Handles ISO-TP."""
    ecus: dict[str, bytes] = {}
    cf: dict[str, int] = {}
    for line in resp.splitlines():
        line = line.strip().replace(" ", "")
        if not line:
            continue
        if any(x in line for x in ("NODATA", "SEARCHING", "OK", "?", "STOPPED", "ERROR", "UNABLE", "CANERROR", "BUSINIT")):
            continue
        if len(line) < 6:
            continue
        hdr = line[:3]
        try:
            first = int(line[3:5], 16)
        except ValueError:
            continue
        pci = line[3:4]
        try:
            if pci == "0":  # Single frame
                L = first & 0x0F
                ecus[hdr] = ecus.get(hdr, b"") + bytes.fromhex(line[5:5 + 2 * L])
            elif pci == "1":  # First frame
                L = int(line[3:7], 16) & 0x0FFF
                data = bytes.fromhex(line[7:])
                ecus[hdr] = data
                cf[hdr] = L - len(data)
            elif pci == "2":  # Consecutive frame
                data = bytes.fromhex(line[5:])
                if hdr in ecus:
                    need = cf.get(hdr, len(data))
                    ecus[hdr] += data[:need]
                    cf[hdr] = max(0, need - len(data))
        except ValueError:
            pass
    return ecus


def read_pid(elm: Elm, cmd: str, wait: float = 1.0) -> bytes | None:
    """Send a mode+pid hex command, return payload bytes (after mode+pid echo) or None."""
    resp = elm.send(cmd, wait)
    ecus = parse_can(resp)
    mode_resp = int(cmd[:2], 16) + 0x40
    if len(cmd) >= 4:
        pid = int(cmd[2:4], 16)
    else:
        pid = None
    for data in ecus.values():
        if len(data) >= 1 and data[0] == mode_resp:
            if pid is None or (len(data) >= 2 and data[1] == pid):
                return data[2:] if pid is not None else data[1:]
    return None


def decode_dtcs(payload: bytes) -> list[str]:
    """Mode 03/07/0A payload: count byte + pairs of 2 bytes per DTC."""
    if len(payload) < 1:
        return []
    n = payload[0]
    out = []
    for i in range(n):
        off = 1 + 2 * i
        if off + 1 >= len(payload):
            break
        b1, b2 = payload[off], payload[off + 1]
        letter = ["P", "C", "B", "U"][(b1 >> 6) & 0x3]
        out.append(f"{letter}{(b1 >> 4) & 0x3}{b1 & 0x0F:X}{(b2 >> 4) & 0x0F:X}{b2 & 0x0F:X}")
    return out


# ── PID decoders ─────────────────────────────────────────────────────────
def _u8(d, i=0): return d[i] if len(d) > i else 0
def _u16(d, i=0): return (d[i] << 8) | d[i + 1] if len(d) > i + 1 else 0


PID_DECODE = {
    0x01: lambda d: {"MIL": bool(_u8(d) & 0x80), "DTC_count": _u8(d) & 0x7F,
                      "B": _u8(d, 1), "C": _u8(d, 2), "D": _u8(d, 3)},
    0x03: lambda d: {"FS1": _u8(d), "FS2": _u8(d, 1)},
    0x04: lambda d: _u8(d) * 100 / 255,
    0x05: lambda d: _u8(d) - 40,
    0x06: lambda d: (_u8(d) - 128) * 100 / 128,
    0x07: lambda d: (_u8(d) - 128) * 100 / 128,
    0x08: lambda d: (_u8(d) - 128) * 100 / 128,
    0x09: lambda d: (_u8(d) - 128) * 100 / 128,
    0x0A: lambda d: _u8(d) * 3,
    0x0B: lambda d: _u8(d),
    0x0C: lambda d: _u16(d) / 4,
    0x0D: lambda d: _u8(d),
    0x0E: lambda d: (_u8(d) - 128) / 2,
    0x0F: lambda d: _u8(d) - 40,
    0x10: lambda d: _u16(d) / 100,
    0x11: lambda d: _u8(d) * 100 / 255,
    0x13: lambda d: _u8(d),
    0x14: lambda d: {"V": _u8(d) * 0.005, "STFT": (_u8(d, 1) - 128) * 100 / 128 if _u8(d, 1) != 0xFF else None},
    0x15: lambda d: {"V": _u8(d) * 0.005, "STFT": (_u8(d, 1) - 128) * 100 / 128 if _u8(d, 1) != 0xFF else None},
    0x1C: lambda d: _u8(d),
    0x1F: lambda d: _u16(d),
    0x21: lambda d: _u16(d),
    0x2E: lambda d: _u8(d) * 100 / 255,
    0x2F: lambda d: _u8(d) * 100 / 255,
    0x30: lambda d: _u8(d),
    0x31: lambda d: _u16(d),
    0x33: lambda d: _u8(d),
    0x34: lambda d: {"lambda": _u16(d) * 2 / 65536, "current_mA": (_u16(d, 2) - 32768) / 256},
    0x3C: lambda d: _u16(d) / 10 - 40,
    0x42: lambda d: _u16(d) / 1000,
    0x43: lambda d: _u16(d) * 100 / 255,
    0x44: lambda d: _u16(d) * 2 / 65536,
    0x45: lambda d: _u8(d) * 100 / 255,
    0x46: lambda d: _u8(d) - 40,
    0x47: lambda d: _u8(d) * 100 / 255,
    0x49: lambda d: _u8(d) * 100 / 255,
    0x4A: lambda d: _u8(d) * 100 / 255,
    0x4C: lambda d: _u8(d) * 100 / 255,
    0x51: lambda d: _u8(d),
}

PID_NAMES = {
    0x01: "Monitor status / MIL / DTC count",
    0x03: "Fuel system status",
    0x04: "Calc load %",
    0x05: "Coolant temp °C",
    0x06: "ST fuel trim B1 %",
    0x07: "LT fuel trim B1 %",
    0x08: "ST fuel trim B2 %",
    0x09: "LT fuel trim B2 %",
    0x0A: "Fuel rail pressure kPa",
    0x0B: "MAP kPa",
    0x0C: "RPM",
    0x0D: "Speed km/h",
    0x0E: "Timing advance °",
    0x0F: "IAT °C",
    0x10: "MAF g/s",
    0x11: "Throttle %",
    0x13: "O2 sensors present (bitmask)",
    0x14: "O2 B1S1 V / STFT",
    0x15: "O2 B1S2 V / STFT",
    0x1C: "OBD standard",
    0x1F: "Runtime since start s",
    0x21: "Distance with MIL on km",
    0x2E: "Cmd evap purge %",
    0x2F: "Fuel level %",
    0x30: "Warm-ups since clear",
    0x31: "Distance since clear km",
    0x33: "Barometric pressure kPa",
    0x34: "O2 B1S1 wideband λ + current",
    0x3C: "Cat temp B1S1 °C",
    0x42: "Control module V",
    0x43: "Abs load %",
    0x44: "Cmd equiv ratio",
    0x45: "Relative throttle %",
    0x46: "Ambient °C",
    0x47: "Abs throttle B %",
    0x49: "Accel pos D %",
    0x4A: "Accel pos E %",
    0x4C: "Cmd throttle %",
    0x51: "Fuel type",
}


def decode_pid(pid: int, payload: bytes):
    fn = PID_DECODE.get(pid)
    if fn is None:
        return payload.hex()
    try:
        return fn(payload)
    except Exception:
        return payload.hex()


FUEL_SYSTEM_STATE = {
    0: "off",
    1: "OL-engine (warm-up)",
    2: "CL (O2 feedback)",
    4: "OL-driver (load/decel)",
    8: "OL-fault",
    16: "CL-fault (one O2 sensor bad)",
}


def decode_readiness(payload: bytes) -> dict:
    """Decode mode 01 PID 01 byte B/C/D into named readiness bits."""
    if len(payload) < 4:
        return {}
    A, B, C, D = payload[0], payload[1], payload[2], payload[3]
    return {
        "MIL": bool(A & 0x80),
        "DTC_count": A & 0x7F,
        # Continuous monitors (always "complete" if supported while running)
        "misfire_sup": bool(B & 0x01),  "misfire_incomplete": bool(B & 0x10),
        "fuel_sup":    bool(B & 0x02),  "fuel_incomplete":    bool(B & 0x20),
        "comp_sup":    bool(B & 0x04),  "comp_incomplete":    bool(B & 0x40),
        # Non-continuous monitors (complete only after drive cycle runs them)
        "cat_sup":     bool(C & 0x01),  "cat_incomplete":     bool(D & 0x01),
        "htd_cat_sup": bool(C & 0x02),  "htd_cat_incomplete": bool(D & 0x02),
        "evap_sup":    bool(C & 0x04),  "evap_incomplete":    bool(D & 0x04),
        "sec_air_sup": bool(C & 0x08),  "sec_air_incomplete": bool(D & 0x08),
        "ac_sup":      bool(C & 0x10),  "ac_incomplete":      bool(D & 0x10),
        "o2_sup":      bool(C & 0x20),  "o2_incomplete":      bool(D & 0x20),
        "o2htr_sup":   bool(C & 0x40),  "o2htr_incomplete":   bool(D & 0x40),
        "egr_sup":     bool(C & 0x80),  "egr_incomplete":     bool(D & 0x80),
    }


def mode01_supported(elm: Elm) -> list[int]:
    """Walk 0100, 0120, 0140... to enumerate supported mode-01 PIDs."""
    out = []
    for base in range(0x00, 0xE0, 0x20):
        payload = read_pid(elm, f"01{base:02X}", 1.5)
        if not payload or len(payload) < 4:
            break
        mask = int.from_bytes(payload[:4], "big")
        any_next = False
        for i in range(32):
            if mask & (1 << (31 - i)):
                pid = base + 1 + i
                if pid == base + 0x20:
                    any_next = True
                out.append(pid)
        if not any_next:
            break
    return sorted(set(out))


def read_dtcs(elm: Elm) -> dict[str, list[str]]:
    """Return dict with keys stored/pending/permanent, each a list of DTCs."""
    out = {}
    for mode, key in [("03", "stored"), ("07", "pending"), ("0A", "permanent")]:
        resp = elm.send(mode, 3.0)
        ecus = parse_can(resp)
        expected = int(mode, 16) + 0x40
        codes = []
        for data in ecus.values():
            if data and data[0] == expected:
                codes.extend(decode_dtcs(data[1:]))
        out[key] = codes
    return out
