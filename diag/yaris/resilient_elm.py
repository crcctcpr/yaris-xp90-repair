"""Auto-reconnecting ELM327 wrapper.

On BT/serial failures (OSError Errno 5 I/O, SerialException, timeouts),
releases + rebinds /dev/rfcomm0, re-inits the ELM, and retries the failed
operation. Tools should use this instead of raw Elm for long-running work.

Usage (drop-in replacement):
    from yaris.resilient_elm import ResilientElm
    with ResilientElm() as e:
        e.init_can()
        # Normal elm.send/read_pid calls — auto-retry on transient failures
"""
import logging
import subprocess
import time
import serial

from .elm import Elm
from .vehicle import DEFAULT_PORT, DEFAULT_BAUD, ELM_MAC, ELM_SPP_CHANNEL


log = logging.getLogger("yaris.resilient")


class ResilientElm:
    """Wraps Elm with transparent reconnect on I/O failure.

    Re-initialises ATZ/ATSP6/etc after reconnect so the caller doesn't need
    to worry about link state. If rebind fails completely, raises after
    `max_rebinds` attempts.
    """

    # Exceptions that indicate link failure (vs protocol / logic errors)
    LINK_ERRORS = (OSError, serial.SerialException)

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baud: int = DEFAULT_BAUD,
        timeout: float = 4.0,
        max_retries: int = 3,
        max_rebinds: int = 2,
        backoff_s: float = 1.5,
        init_mode: str = "can",  # "can", "can_raw", or None
    ):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_rebinds = max_rebinds
        self.backoff_s = backoff_s
        self.init_mode = init_mode
        self._elm: Elm | None = None
        self._reconnect_count = 0
        self._total_errors = 0

    # ── lifecycle ─────────────────────────────────────────────────────
    def __enter__(self):
        self._open()
        return self

    def __exit__(self, *a):
        self.close()

    def _open(self):
        last_err = None
        for attempt in range(self.max_rebinds + 1):
            try:
                self._elm = Elm(self.port, self.baud, self.timeout)
                self._elm.wake()
                if self.init_mode == "can":
                    self._elm.init_can()
                elif self.init_mode == "can_raw":
                    self._elm.init_can_raw()
                return
            except self.LINK_ERRORS as e:
                last_err = e
                log.warning("open failed (attempt %d): %s", attempt + 1, e)
                try:
                    if self._elm:
                        self._elm.close()
                except Exception:
                    pass
                self._elm = None
                if attempt < self.max_rebinds:
                    self._rebind_rfcomm()
                    time.sleep(self.backoff_s)
        raise RuntimeError(f"Could not open ELM after {self.max_rebinds+1} attempts: {last_err}")

    def close(self):
        if self._elm:
            try:
                self._elm.close()
            except Exception:
                pass
            self._elm = None

    @property
    def stats(self) -> dict:
        return {"reconnects": self._reconnect_count, "errors": self._total_errors}

    # ── rebind helper ─────────────────────────────────────────────────
    def _rebind_rfcomm(self):
        """Release + re-bind /dev/rfcomm0 on the configured MAC/channel."""
        dev = self.port.replace("/dev/", "")
        try:
            subprocess.run(["sudo", "-n", "rfcomm", "release", dev],
                           capture_output=True, timeout=8)
        except Exception:
            pass
        time.sleep(0.3)
        try:
            r = subprocess.run(
                ["sudo", "-n", "rfcomm", "bind", dev, ELM_MAC, str(ELM_SPP_CHANNEL)],
                capture_output=True, timeout=10,
            )
            if r.returncode != 0:
                log.warning("rfcomm bind failed: %s", r.stderr.decode("utf-8", "replace"))
            subprocess.run(["sudo", "-n", "chmod", "666", self.port],
                           capture_output=True, timeout=5)
        except Exception as e:
            log.warning("rfcomm bind exception: %s", e)

    # ── core wrap ────────────────────────────────────────────────────
    def _with_retry(self, fn, *args, **kwargs):
        """Execute fn on underlying Elm, retrying through reconnects."""
        last_err = None
        for attempt in range(self.max_retries + 1):
            if self._elm is None:
                self._open()
            try:
                return fn(self._elm, *args, **kwargs)
            except self.LINK_ERRORS as e:
                last_err = e
                self._total_errors += 1
                log.warning("link error on attempt %d: %s", attempt + 1, e)
                # Full rebind
                self.close()
                if attempt < self.max_retries:
                    self._reconnect_count += 1
                    self._rebind_rfcomm()
                    time.sleep(self.backoff_s * (attempt + 1))
                    try:
                        self._open()
                    except Exception as re:
                        log.warning("reopen after error failed: %s", re)
                        continue
        raise RuntimeError(f"Failed after {self.max_retries+1} retries: {last_err}")

    # ── passthrough API (same surface as Elm) ────────────────────────
    def send(self, cmd: str, wait: float = 2.0) -> str:
        return self._with_retry(lambda e, c, w: e.send(c, w), cmd, wait)

    def adapter_info(self) -> dict:
        return self._with_retry(lambda e: e.adapter_info())

    def init_can(self) -> dict:
        return self._with_retry(lambda e: e.init_can())

    def init_can_raw(self) -> dict:
        return self._with_retry(lambda e: e.init_can_raw())

    def set_header(self, req_id: str) -> str:
        return self._with_retry(lambda e, h: e.set_header(h), req_id)

    def monitor_start(self):
        return self._with_retry(lambda e: e.monitor_start())

    def monitor_poll(self, max_bytes: int = 4096) -> bytes:
        return self._with_retry(lambda e, n: e.monitor_poll(n), max_bytes)

    def monitor_stop(self):
        return self._with_retry(lambda e: e.monitor_stop())

    # Expose the underlying pyserial for anything that needs raw access
    @property
    def ser(self):
        if self._elm is None:
            self._open()
        return self._elm.ser
