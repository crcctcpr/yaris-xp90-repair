"""Tests for ResilientElm. Uses a fake Elm that can be scripted to fail."""
import unittest
from unittest.mock import patch, MagicMock
import serial

from yaris import resilient_elm


class FakeElm:
    """Scripted fake with call count tracked across instances.

    Set FakeElm.fail_first_n to N to make the first N send() calls fail
    (regardless of which Elm instance is current — simulates failures
    persisting across reconnects).
    """
    instances = []
    total_send_calls = 0
    fail_first_n = 0
    send_return = "ELM327 v2.1"

    def __init__(self, port, baud, timeout=4.0):
        self.port = port
        FakeElm.instances.append(self)

    def wake(self): return True
    def init_can(self): return {}
    def init_can_raw(self): return {}
    def adapter_info(self): return {"id": "ELM327"}

    def send(self, cmd, wait=2.0):
        FakeElm.total_send_calls += 1
        if FakeElm.total_send_calls <= FakeElm.fail_first_n:
            raise OSError(5, "Input/output error")
        return FakeElm.send_return

    def set_header(self, h): return "OK"
    def close(self): pass


class TestResilientElm(unittest.TestCase):

    def setUp(self):
        FakeElm.instances = []
        FakeElm.total_send_calls = 0
        FakeElm.fail_first_n = 0

    def _patch_elm(self):
        # Patch both the Elm class in resilient_elm and the subprocess.run used for rebind
        return patch.multiple(
            resilient_elm,
            Elm=FakeElm,
        ), patch("yaris.resilient_elm.subprocess.run", return_value=MagicMock(returncode=0, stderr=b"")), \
               patch("yaris.resilient_elm.time.sleep", return_value=None)

    def test_opens_successfully_first_try(self):
        with patch("yaris.resilient_elm.Elm", FakeElm), \
             patch("yaris.resilient_elm.subprocess.run", return_value=MagicMock(returncode=0, stderr=b"")), \
             patch("yaris.resilient_elm.time.sleep", return_value=None):
            with resilient_elm.ResilientElm() as e:
                r = e.send("ATZ")
                self.assertEqual(r, "ELM327 v2.1")
            self.assertEqual(e.stats["errors"], 0)
            self.assertEqual(e.stats["reconnects"], 0)

    def test_retries_on_io_error(self):
        FakeElm.fail_first_n = 2  # fail 2 times across any instances
        with patch("yaris.resilient_elm.Elm", FakeElm), \
             patch("yaris.resilient_elm.subprocess.run", return_value=MagicMock(returncode=0, stderr=b"")), \
             patch("yaris.resilient_elm.time.sleep", return_value=None):
            re = resilient_elm.ResilientElm(max_retries=3)
            re._open()
            r = re.send("ATZ")
            self.assertEqual(r, "ELM327 v2.1")
            self.assertGreaterEqual(re.stats["errors"], 2)
            self.assertGreaterEqual(re.stats["reconnects"], 1)
            re.close()

    def test_raises_after_max_retries(self):
        class AlwaysFail(FakeElm):
            def send(self, cmd, wait=2.0):
                raise OSError(5, "always fails")

        with patch("yaris.resilient_elm.Elm", AlwaysFail), \
             patch("yaris.resilient_elm.subprocess.run", return_value=MagicMock(returncode=0, stderr=b"")), \
             patch("yaris.resilient_elm.time.sleep", return_value=None):
            re = resilient_elm.ResilientElm(max_retries=2)
            re._open()
            with self.assertRaises(RuntimeError):
                re.send("ATZ")
            re.close()

    def test_passthrough_methods(self):
        with patch("yaris.resilient_elm.Elm", FakeElm), \
             patch("yaris.resilient_elm.subprocess.run", return_value=MagicMock(returncode=0, stderr=b"")), \
             patch("yaris.resilient_elm.time.sleep", return_value=None):
            with resilient_elm.ResilientElm() as e:
                info = e.adapter_info()
                self.assertEqual(info["id"], "ELM327")
                self.assertEqual(e.set_header("7E0"), "OK")


if __name__ == "__main__":
    unittest.main()
