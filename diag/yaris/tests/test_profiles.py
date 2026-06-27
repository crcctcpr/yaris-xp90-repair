"""Tests for profile loading."""
import tempfile
import unittest
from pathlib import Path

from yaris import vehicle


class TestProfiles(unittest.TestCase):

    def test_default_profile_loaded(self):
        # Default profile loaded at import
        self.assertEqual(vehicle.VIN, "JTDEXAMPLE0000000")
        self.assertEqual(vehicle.ENGINE, "1NR-FE")

    def test_list_profiles_contains_default(self):
        profiles = vehicle.list_profiles()
        self.assertIn("JTDEXAMPLE0000000", profiles)

    def test_load_by_vin(self):
        cfg = vehicle.load_profile("JTDEXAMPLE0000000")
        self.assertEqual(cfg["identity"]["vin"], "JTDEXAMPLE0000000")

    def test_load_unknown_raises(self):
        with self.assertRaises(FileNotFoundError):
            vehicle.load_profile("NONEXISTENT123")

    def test_load_applies_to_globals(self):
        """Writing a temp profile and loading it must change module globals."""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("""
[identity]
vin = "TESTVIN"
model_year = 2024
engine = "TEST-E"
engine_displacement_l = 2.0

[adapter]
mac = "AA:BB:CC:DD:EE:FF"
spp_channel = 1

[expected]
idle_rpm = [700, 900]
""")
            path = f.name
        try:
            vehicle.load_profile(path)
            self.assertEqual(vehicle.VIN, "TESTVIN")
            self.assertEqual(vehicle.MODEL_YEAR, 2024)
            self.assertEqual(vehicle.ELM_MAC, "AA:BB:CC:DD:EE:FF")
            self.assertEqual(vehicle.ELM_SPP_CHANNEL, 1)
            self.assertEqual(vehicle.EXPECTED_IDLE_RPM, (700, 900))
        finally:
            Path(path).unlink()
            # Restore default
            vehicle.load_profile(vehicle.DEFAULT_VIN)

    def test_expected_maf_respects_displacement(self):
        """If displacement changes via profile, expected MAF scales."""
        original = vehicle.expected_maf(2000, throttle_pct=25)
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("""
[identity]
vin = "BIGENGINE"
engine_displacement_l = 3.0
""")
            path = f.name
        try:
            vehicle.load_profile(path)
            big = vehicle.expected_maf(2000, throttle_pct=25)
            # 3.0/1.329 ≈ 2.26× ratio
            self.assertAlmostEqual(big / original, 3.0 / 1.329, places=1)
        finally:
            Path(path).unlink()
            vehicle.load_profile(vehicle.DEFAULT_VIN)


if __name__ == "__main__":
    unittest.main()
