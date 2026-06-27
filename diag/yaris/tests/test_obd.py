"""Tests for obd.py — CAN parser, PID decoders, DTC decoder."""
import unittest

from yaris.obd import (
    parse_can, decode_dtcs, decode_pid, decode_readiness,
    PID_DECODE, PID_NAMES,
)


class TestParseCan(unittest.TestCase):
    """Parse raw ELM CAN responses into per-ECU byte streams."""

    def test_single_frame(self):
        # Single-frame: header 7E8, PCI=0 L=4, data 41 0C 0A F3 (RPM response)
        resp = "7E8 04 41 0C 0A F3"
        out = parse_can(resp)
        self.assertIn("7E8", out)
        self.assertEqual(out["7E8"], bytes.fromhex("41 0C 0A F3".replace(" ", "")))

    def test_single_frame_no_spaces(self):
        resp = "7E804410C0AF3"
        out = parse_can(resp)
        self.assertEqual(out["7E8"].hex(), "410c0af3")

    def test_multi_frame_vin(self):
        # Mode 09 PID 02 (VIN) multi-frame response for the example VIN.
        # First frame: 7E8 10 14 49 02 01 4A 54 44     (L=0x014=20 bytes)
        # Consec 1:    7E8 21 45 58 41 4D 50 4C 45     (skip PCI byte)
        # Consec 2:    7E8 22 30 30 30 30 30 30 30
        resp = (
            "7E81014490201 4A 54 44\n"
            "7E8214558414D50 4C 45\n"
            "7E8223030303030 30 30"
        )
        out = parse_can(resp)
        self.assertIn("7E8", out)
        # 20 bytes: 49 02 01 + JTDEXAMPLE0000000 (17 chars)
        assembled = out["7E8"]
        self.assertEqual(assembled[0], 0x49)
        self.assertEqual(assembled[1], 0x02)
        self.assertEqual(assembled[2], 0x01)
        vin = bytes(assembled[3:20]).decode("ascii")
        self.assertEqual(vin, "JTDEXAMPLE0000000")

    def test_noise_lines_ignored(self):
        resp = "SEARCHING...\n7E804410C0AF3\nOK"
        out = parse_can(resp)
        self.assertEqual(out["7E8"].hex(), "410c0af3")

    def test_no_data(self):
        resp = "NO DATA"
        out = parse_can(resp)
        self.assertEqual(out, {})

    def test_empty(self):
        self.assertEqual(parse_can(""), {})


class TestDecodeDtcs(unittest.TestCase):
    """Decode Mode 03/07/0A payload → list of DTC strings."""

    def test_single_p0101(self):
        # Payload (after mode+count): count=1, DTC bytes = 01 01
        payload = bytes([1, 0x01, 0x01])
        self.assertEqual(decode_dtcs(payload), ["P0101"])

    def test_multiple_codes(self):
        payload = bytes([2, 0x01, 0x01, 0x02, 0x04])  # P0101, P0204
        self.assertEqual(decode_dtcs(payload), ["P0101", "P0204"])

    def test_p_c_b_u_prefix(self):
        # b1 upper 2 bits: 00=P, 01=C, 10=B, 11=U
        self.assertEqual(decode_dtcs(bytes([1, 0x00, 0x00])), ["P0000"])
        self.assertEqual(decode_dtcs(bytes([1, 0x42, 0x00])), ["C0200"])
        self.assertEqual(decode_dtcs(bytes([1, 0x81, 0x80])), ["B0180"])
        self.assertEqual(decode_dtcs(bytes([1, 0xC1, 0x00])), ["U0100"])

    def test_empty_count(self):
        self.assertEqual(decode_dtcs(bytes([0])), [])

    def test_truncated(self):
        # Claims 2 codes but only 1 pair present
        self.assertEqual(decode_dtcs(bytes([2, 0x01, 0x01])), ["P0101"])


class TestDecodePid(unittest.TestCase):
    """Validated PID decoders — values matched to real responses from the car."""

    def test_rpm(self):
        self.assertEqual(decode_pid(0x0C, bytes([0x0A, 0xF3])), 700.75)

    def test_rpm_low(self):
        # 688 RPM — from our driveway test
        self.assertEqual(decode_pid(0x0C, bytes([0x0A, 0xC1])), 688.25)

    def test_coolant(self):
        # 0x7E → 126-40 = 86°C
        self.assertEqual(decode_pid(0x05, bytes([0x7E])), 86)

    def test_speed(self):
        self.assertEqual(decode_pid(0x0D, bytes([0x32])), 50)

    def test_maf(self):
        # 2 bytes / 100 → 0x0079 = 121 / 100 = 1.21 g/s (our faulty-MAF idle reading)
        self.assertEqual(decode_pid(0x10, bytes([0x00, 0x79])), 1.21)

    def test_timing_advance(self):
        # (A-128)/2 → 0x91 = 145 → (145-128)/2 = 8.5°
        self.assertEqual(decode_pid(0x0E, bytes([0x91])), 8.5)

    def test_stft(self):
        # (A-128)*100/128 → 0x81 = 129 → (129-128)*100/128 ≈ 0.78%
        v = decode_pid(0x06, bytes([0x81]))
        self.assertAlmostEqual(v, 0.78125, places=4)

    def test_ltft_saturated(self):
        # +17.97% → 0x97 = 151 → (151-128)*100/128 = 17.96875
        v = decode_pid(0x07, bytes([0x97]))
        self.assertAlmostEqual(v, 17.96875, places=4)

    def test_load(self):
        # 0x6B = 107 → 107*100/255 = 41.96%
        v = decode_pid(0x04, bytes([0x6B]))
        self.assertAlmostEqual(v, 107 * 100 / 255, places=2)

    def test_iat(self):
        self.assertEqual(decode_pid(0x0F, bytes([0x4B])), 35)  # 75-40

    def test_throttle(self):
        # 0x2A = 42 → 42*100/255 ≈ 16.47%
        v = decode_pid(0x11, bytes([0x2A]))
        self.assertAlmostEqual(v, 42 * 100 / 255, places=2)

    def test_control_module_v(self):
        # 2 bytes /1000 → 0x34B8 = 13496 → 13.496 V
        self.assertEqual(decode_pid(0x42, bytes([0x34, 0xB8])), 13.496)

    def test_o2_wideband(self):
        # 0x34: {lambda, current}
        d = decode_pid(0x34, bytes([0x82, 0xD7, 0x80, 0x0B]))
        self.assertAlmostEqual(d["lambda"], (0x82D7) * 2 / 65536, places=4)

    def test_unknown_pid_hex_fallback(self):
        # Undefined PID → hex string
        self.assertEqual(decode_pid(0xFE, bytes([0xAB])), "ab")


class TestReadiness(unittest.TestCase):
    def test_all_bits(self):
        # A=0x81 (MIL on, 1 DTC), B=0x07 (continuous all sup), C=0xE5, D=0x00 (all complete)
        r = decode_readiness(bytes([0x81, 0x07, 0xE5, 0x00]))
        self.assertTrue(r["MIL"])
        self.assertEqual(r["DTC_count"], 1)
        self.assertTrue(r["misfire_sup"])
        self.assertFalse(r["misfire_incomplete"])
        self.assertTrue(r["cat_sup"])
        self.assertFalse(r["cat_incomplete"])
        self.assertTrue(r["evap_sup"])
        self.assertFalse(r["evap_incomplete"])

    def test_mil_off_post_clear(self):
        # After clear: A=0x00, B=0x07, C=0xE5, D=0xE5 (all non-continuous incomplete)
        r = decode_readiness(bytes([0x00, 0x07, 0xE5, 0xE5]))
        self.assertFalse(r["MIL"])
        self.assertEqual(r["DTC_count"], 0)
        self.assertTrue(r["cat_incomplete"])
        self.assertTrue(r["evap_incomplete"])
        self.assertTrue(r["egr_incomplete"])
        self.assertFalse(r["misfire_incomplete"])  # Continuous monitors stay complete

    def test_short_payload(self):
        self.assertEqual(decode_readiness(bytes([0x00, 0x07])), {})


if __name__ == "__main__":
    unittest.main()
