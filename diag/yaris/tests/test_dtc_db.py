"""Tests for dtc_db.py — DTC knowledge base."""
import unittest

from yaris.dtc_db import resolve, rank_and_explain, DTC_DATABASE


class TestDtcDb(unittest.TestCase):

    def test_p0101_resolvable(self):
        e = resolve("P0101")
        self.assertIsNotNone(e)
        self.assertEqual(e.code, "P0101")
        self.assertIn("MAF", e.title)
        self.assertGreater(len(e.causes), 2)
        self.assertGreater(len(e.diy_steps), 2)

    def test_case_insensitive(self):
        self.assertIsNotNone(resolve("p0101"))

    def test_unknown_code(self):
        self.assertIsNone(resolve("P9999"))

    def test_all_entries_well_formed(self):
        """Every entry must have code, title, severity, system."""
        for code, e in DTC_DATABASE.items():
            self.assertEqual(code, e.code, f"{code} key mismatch with .code")
            self.assertTrue(e.title, f"{code} missing title")
            self.assertIn(e.severity, ("critical", "warn", "minor"),
                          f"{code} bad severity {e.severity}")
            self.assertTrue(e.system)

    def test_rank_sorts_critical_first(self):
        out = rank_and_explain(["P0442", "P0335", "P0101"])  # minor, critical, warn
        self.assertEqual(out[0]["severity"], "critical")
        self.assertEqual(out[1]["severity"], "warn")
        self.assertEqual(out[2]["severity"], "minor")

    def test_rank_handles_unknowns(self):
        out = rank_and_explain(["P0101", "P9999"])
        codes = [e["code"] for e in out]
        self.assertIn("P0101", codes)
        self.assertIn("P9999", codes)


if __name__ == "__main__":
    unittest.main()
