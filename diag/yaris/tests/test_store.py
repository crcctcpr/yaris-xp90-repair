"""Tests for the SQLite store."""
import os
import tempfile
import unittest
from pathlib import Path

from yaris.store import Store


class TestStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.store = Store(self.db_path)

    def tearDown(self):
        self.store.close()
        Path(self.db_path).unlink()

    def test_start_end_session(self):
        sid = self.store.start_session(source="test", note="smoke")
        self.assertGreater(sid, 0)
        self.store.end_session(sid)
        sessions = self.store.sessions()
        self.assertEqual(len(sessions), 1)
        self.assertIsNotNone(sessions[0]["ended_ts"])

    def test_record_sample(self):
        sid = self.store.start_session(source="test")
        self.store.record_sample(sid, {
            "timestamp": "2026-04-21T17:00:00",
            "rpm": 700.5, "speed_kmh": 0, "maf_gs": 1.21,
            "stft_b1_pct": 3.1, "ltft_b1_pct": 17.9,
            "load_pct": 42, "throttle_pct": 16.5,
            "coolant_c": 86, "iat_c": 40,
            "fuel_sys": "2", "mil": "0", "dtc_count": "0",
        })
        self.store.flush()
        n = self.store.conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        self.assertEqual(n, 1)

    def test_record_sample_handles_missing_keys(self):
        sid = self.store.start_session()
        # Missing some fields — should not raise
        self.store.record_sample(sid, {"rpm": 700, "maf_gs": 1.2})
        self.store.flush()
        s = self.store.conn.execute("SELECT * FROM samples").fetchone()
        self.assertEqual(s["rpm"], 700.0)
        self.assertIsNone(s["ltft_pct"])

    def test_record_dtc_dedups(self):
        sid = self.store.start_session()
        self.store.record_dtc(sid, "P0101", "stored")
        self.store.record_dtc(sid, "P0101", "stored")  # same — updates last_seen
        self.store.record_dtc(sid, "P0101", "permanent")  # different bucket
        rows = self.store.conn.execute("SELECT COUNT(*) FROM dtcs_seen").fetchone()
        self.assertEqual(rows[0], 2)

    def test_events_recorded(self):
        sid = self.store.start_session()
        self.store.record_event(sid, "critical", "MIL on")
        self.store.record_event(sid, "warn", "LTFT +24")
        n = self.store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(n, 2)

    def test_import_csv(self):
        """Import the bundled example drive CSV (if present) and summarise."""
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "examples", "sample_drive.csv",
        )
        if not os.path.exists(csv_path):
            self.skipTest("example drive CSV not available")
        sid = self.store.import_csv(csv_path, source="driveway", note="smoke test")
        summary = self.store.session_summary(sid)
        self.assertGreater(summary["stats"]["n"], 100)
        self.assertGreaterEqual(summary["stats"]["ltft_max"], 17.9)

    def test_ltft_history(self):
        sid1 = self.store.start_session(source="a")
        for i in range(5):
            self.store.record_sample(sid1, {"rpm": 700, "ltft_b1_pct": 17.9})
        self.store.end_session(sid1)
        sid2 = self.store.start_session(source="b")
        for i in range(5):
            self.store.record_sample(sid2, {"rpm": 700, "ltft_b1_pct": 5.0})
        self.store.end_session(sid2)
        h = self.store.ltft_history()
        self.assertEqual(len(h), 2)
        means = {row["source"]: row["ltft_avg"] for row in h}
        self.assertAlmostEqual(means["a"], 17.9, places=1)
        self.assertAlmostEqual(means["b"], 5.0, places=1)

    def test_maf_ratio_trend(self):
        sid = self.store.start_session()
        # Simulate 10 samples at idle with MAF far too low
        for _ in range(10):
            self.store.record_sample(sid, {
                "rpm": 700, "throttle_pct": 16, "maf_gs": 1.2,
            })
        self.store.end_session(sid)
        trend = self.store.maf_ratio_trend()
        self.assertEqual(len(trend), 1)
        self.assertLess(trend[0]["ratio_mean"], 0.5)

    def test_dtc_occurrences(self):
        sid1 = self.store.start_session()
        self.store.record_dtc(sid1, "P0101", "permanent")
        self.store.end_session(sid1)
        sid2 = self.store.start_session()
        self.store.record_dtc(sid2, "P0101", "permanent")
        self.store.record_dtc(sid2, "C1425", "stored")
        self.store.end_session(sid2)
        occ = self.store.dtc_occurrences()
        codes = {r["code"]: r["occurrences"] for r in occ}
        self.assertEqual(codes.get("P0101"), 2)
        self.assertEqual(codes.get("C1425"), 1)


if __name__ == "__main__":
    unittest.main()
