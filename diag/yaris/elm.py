"""ELM327 I/O — clean wrappers over pyserial with robust send/receive."""
import serial
import time
from .vehicle import DEFAULT_PORT, DEFAULT_BAUD, PROTOCOL_NUMBER


class ElmError(Exception):
    pass


class Elm:
    """Thin wrapper around a pyserial port to an ELM327."""

    def __init__(self, port=DEFAULT_PORT, baud=DEFAULT_BAUD, timeout=4.0):
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.3)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def send(self, cmd: str, wait: float = 2.0) -> str:
        """Send one AT or OBD command, return raw response string (no \r, no prompt)."""
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode() + b"\r")
        t0 = time.time()
        buf = b""
        while time.time() - t0 < wait:
            n = self.ser.in_waiting
            if n:
                buf += self.ser.read(n)
                if buf.endswith(b">"):
                    break
            time.sleep(0.02)
        return buf.decode("ascii", "replace").replace("\r", "\n").replace(">", "").strip()

    # ── ELM init ──────────────────────────────────────────────────────────
    def wake(self) -> bool:
        """Send a CR+ATZ+ATE0 to wake the adapter and disable echo.
        Returns True if ELM responds with its version banner."""
        self.ser.write(b"\r")
        time.sleep(0.4)
        self.ser.reset_input_buffer()
        resp = self.send("ATZ", 3.0)
        self.send("ATE0", 1.0)
        return "ELM" in resp

    def init_can(self, headers_on: bool = True, formatting_on: bool = True, can_auto_format: bool = True) -> dict:
        """Initialise for ISO 15765-4 CAN 11b 500k. Returns dict of step responses."""
        out = {}
        for cmd in [
            "ATZ",
            "ATE0",
            "ATL0",
            "ATH1" if headers_on else "ATH0",
            "ATS0" if not formatting_on else "ATS0",   # spaces off for machine parse
            f"ATSP{PROTOCOL_NUMBER}",
            "ATCAF1" if can_auto_format else "ATCAF0",
            "ATAT1",
            "ATST50",
        ]:
            out[cmd] = self.send(cmd, 1.5)
        return out

    def init_can_raw(self) -> dict:
        """Initialise for raw-frame CAN monitoring (no ISO-TP reassembly, show headers)."""
        out = {}
        for cmd in ["ATZ", "ATE0", "ATL0", "ATH1", "ATS1", f"ATSP{PROTOCOL_NUMBER}", "ATCAF0", "ATAL"]:
            out[cmd] = self.send(cmd, 1.5)
        return out

    def set_header(self, req_id: str) -> str:
        return self.send(f"ATSH{req_id}", 1.0)

    def adapter_info(self) -> dict:
        return {
            "id": self.send("ATI", 1.5),
            "vbatt": self.send("ATRV", 1.5),
            "proto_n": self.send("ATDPN", 1.5),
            "proto": self.send("ATDP", 1.5),
        }

    # ── Monitor mode (read-only) ──────────────────────────────────────────
    def monitor_start(self):
        """Enter ATMA. Caller is responsible for calling monitor_stop() when done."""
        self.ser.reset_input_buffer()
        self.ser.write(b"ATMA\r")

    def monitor_poll(self, max_bytes: int = 4096) -> bytes:
        n = self.ser.in_waiting
        if not n:
            return b""
        return self.ser.read(min(n, max_bytes))

    def monitor_stop(self):
        self.ser.write(b"\r")
        time.sleep(0.3)
        self.ser.reset_input_buffer()
