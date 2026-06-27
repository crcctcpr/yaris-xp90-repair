"""Tests for vehicle.py — expected_maf physical model."""
import unittest

from yaris.vehicle import expected_maf, ENGINE_DISPLACEMENT_L


class TestExpectedMaf(unittest.TestCase):
    """expected_maf is the foundation of our MAF ratio diagnostic."""

    def test_zero_rpm(self):
        self.assertEqual(expected_maf(0, throttle_pct=16), 0.0)
        self.assertEqual(expected_maf(100, throttle_pct=16), 0.0)

    def test_load_mode_formula(self):
        # Physical: MAF = disp/2 × rpm/60 × VE × air_density
        # VE(load=0) = 0.30; VE(load=100) = 0.95
        maf = expected_maf(2000, load_pct=100, mode="load")
        expected = (1.329 / 2) * (2000 / 60) * 0.95 * 1.20
        self.assertAlmostEqual(maf, expected, places=2)

    def test_load_mode_zero_load(self):
        maf = expected_maf(2000, load_pct=0, mode="load")
        expected = (1.329 / 2) * (2000 / 60) * 0.30 * 1.20
        self.assertAlmostEqual(maf, expected, places=2)

    def test_throttle_mode_idle(self):
        """At idle (16% throttle), expected ~3-4 g/s for 1.3L."""
        v = expected_maf(700, throttle_pct=16, mode="throttle")
        self.assertGreater(v, 2.0)
        self.assertLess(v, 5.5)

    def test_throttle_mode_cruise(self):
        """At 2100 RPM with 20% throttle, expected ~12-15 g/s."""
        v = expected_maf(2100, throttle_pct=20, mode="throttle")
        self.assertGreater(v, 10.0)
        self.assertLess(v, 18.0)

    def test_throttle_mode_wot(self):
        """WOT at 4500 RPM should be well into 40+ g/s."""
        v = expected_maf(4500, throttle_pct=85, mode="throttle")
        self.assertGreater(v, 40.0)

    def test_throttle_monotonic_in_rpm(self):
        """At fixed throttle, expected MAF should increase with RPM."""
        prev = 0
        for rpm in [500, 1000, 1500, 2000, 3000, 4000, 5000]:
            v = expected_maf(rpm, throttle_pct=30, mode="throttle")
            self.assertGreater(v, prev)
            prev = v

    def test_fallback_no_throttle(self):
        """If throttle not supplied in throttle mode, uses RPM-only curve."""
        v = expected_maf(2000, throttle_pct=None, mode="throttle")
        self.assertGreater(v, 0)

    def test_rpm_only_mode(self):
        v = expected_maf(2000, mode="rpm_only")
        self.assertGreater(v, 0)


if __name__ == "__main__":
    unittest.main()
