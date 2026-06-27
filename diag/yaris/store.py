"""SQLite-backed longitudinal data store.

Schema (normalised for cross-session queries):

  sessions(id PK, vin, started_ts, ended_ts, source, note)
  samples(id PK, session_id FK, ts, rpm, speed_kmh, maf_gs, stft_pct, ltft_pct,
          load_pct, throttle_pct, coolant_c, iat_c, o2_b1s2_v, o2wr_lambda,
          cat_temp_c, timing_deg, ctlmod_v, fuel_sys, mil, dtc_count)
  dtcs_seen(id PK, session_id FK, first_seen_ts, last_seen_ts, code, bucket)
  events(id PK, session_id FK, ts, type, text)

Every dash run and guided drive cycle can ingest into the store. Separate
query API provides useful roll-ups without having to hand-write SQL.

Usage:
    from yaris.store import Store
    with Store() as s:
        sid = s.start_session(source="dash", note="post-MAF-clean")
        s.record_sample(sid, row_dict)
        s.end_session(sid)

    # Analysis
    s.ltft_history(vin="JTDEXAMPLE0000000", days=30)
    s.maf_ratio_trend(vin=..., days=30)
"""
import csv
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .vehicle import REPORT_DIR, VIN


DEFAULT_DB = os.path.join(REPORT_DIR, "yaris_history.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vin TEXT NOT NULL,
    started_ts TEXT NOT NULL,
    ended_ts TEXT,
    source TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ts TEXT NOT NULL,
    rpm REAL, speed_kmh REAL, maf_gs REAL,
    stft_pct REAL, ltft_pct REAL, load_pct REAL, throttle_pct REAL,
    coolant_c REAL, iat_c REAL,
    o2_b1s2_v REAL, o2wr_lambda REAL, cat_temp_c REAL,
    timing_deg REAL, ctlmod_v REAL,
    fuel_sys INTEGER, mil INTEGER, dtc_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_samples_session ON samples(session_id);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);

CREATE TABLE IF NOT EXISTS dtcs_seen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    first_seen_ts TEXT NOT NULL,
    last_seen_ts TEXT NOT NULL,
    code TEXT NOT NULL,
    bucket TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dtcs_code ON dtcs_seen(code);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
"""


def _f(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _i(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


class Store:
    """Thin SQLite wrapper. Safe for use from a single thread."""

    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ── Sessions ──────────────────────────────────────────────────────
    def start_session(self, vin: str | None = None,
                      source: str = "dash", note: str = "") -> int:
        vin = vin or VIN
        cur = self.conn.execute(
            "INSERT INTO sessions (vin, started_ts, source, note) VALUES (?, ?, ?, ?)",
            (vin, datetime.now().isoformat(timespec="seconds"), source, note),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_session(self, session_id: int):
        self.conn.execute(
            "UPDATE sessions SET ended_ts=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), session_id),
        )
        self.conn.commit()

    # ── Samples ───────────────────────────────────────────────────────
    def record_sample(self, session_id: int, row: dict):
        """Insert one sample. Row keys match the live_dash CSV columns."""
        self.conn.execute(
            """INSERT INTO samples
               (session_id, ts, rpm, speed_kmh, maf_gs, stft_pct, ltft_pct,
                load_pct, throttle_pct, coolant_c, iat_c, o2_b1s2_v, o2wr_lambda,
                cat_temp_c, timing_deg, ctlmod_v, fuel_sys, mil, dtc_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_id,
             row.get("timestamp") or row.get("ts") or datetime.now().isoformat(timespec="seconds"),
             _f(row.get("rpm")), _f(row.get("speed_kmh") or row.get("speed")),
             _f(row.get("maf_gs") or row.get("maf")),
             _f(row.get("stft_b1_pct") or row.get("stft")),
             _f(row.get("ltft_b1_pct") or row.get("ltft")),
             _f(row.get("load_pct") or row.get("load")),
             _f(row.get("throttle_pct") or row.get("throttle")),
             _f(row.get("coolant_c") or row.get("coolant")),
             _f(row.get("iat_c") or row.get("iat")),
             _f(row.get("o2_b1s2_v") or row.get("o2_b1s2")),
             _f(row.get("o2wr_lambda") or row.get("o2wr")),
             _f(row.get("cat_temp_c") or row.get("cat_t")),
             _f(row.get("timing_deg") or row.get("timing")),
             _f(row.get("ctlmod_v") or row.get("ctlv")),
             _i(row.get("fuel_sys") or row.get("fs")),
             _i(row.get("mil")),
             _i(row.get("dtc_count")))
        )

    def record_event(self, session_id: int, etype: str, text: str):
        self.conn.execute(
            "INSERT INTO events (session_id, ts, type, text) VALUES (?, ?, ?, ?)",
            (session_id, datetime.now().isoformat(timespec="seconds"), etype, text),
        )
        self.conn.commit()

    def record_dtc(self, session_id: int, code: str, bucket: str):
        """Insert (or update last_seen) for a DTC in this session."""
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "SELECT id FROM dtcs_seen WHERE session_id=? AND code=? AND bucket=?",
            (session_id, code, bucket)
        ).fetchone()
        if cur:
            self.conn.execute(
                "UPDATE dtcs_seen SET last_seen_ts=? WHERE id=?",
                (now, cur["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO dtcs_seen (session_id, first_seen_ts, last_seen_ts, code, bucket) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, now, now, code, bucket),
            )
        self.conn.commit()

    def flush(self):
        self.conn.commit()

    # ── Bulk import from CSV ──────────────────────────────────────────
    def import_csv(self, csv_path: str, source: str = "imported",
                   note: str | None = None, vin: str | None = None) -> int:
        """Create a session from a CSV and return session_id. Useful for
        retrospective ingestion of existing drive logs."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(csv_path)
        note = note or Path(csv_path).name
        sid = self.start_session(vin=vin, source=source, note=note)
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                self.record_sample(sid, row)
        self.flush()
        self.end_session(sid)
        return sid

    # ── Query API ─────────────────────────────────────────────────────
    def sessions(self, vin: str | None = None, days: int | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM sessions"
        where, params = [], []
        if vin:
            where.append("vin = ?"); params.append(vin)
        if days is not None:
            since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
            where.append("started_ts >= ?"); params.append(since)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY started_ts DESC"
        return list(self.conn.execute(q, params))

    def ltft_history(self, vin: str | None = None, days: int = 30) -> list[dict]:
        """Per-session LTFT summary: min/max/avg across all samples in each session."""
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        q = """
            SELECT s.id, s.started_ts, s.source, s.note,
                   COUNT(samples.id) AS n,
                   MIN(samples.ltft_pct) AS ltft_min,
                   MAX(samples.ltft_pct) AS ltft_max,
                   AVG(samples.ltft_pct) AS ltft_avg,
                   AVG(samples.stft_pct) AS stft_avg
            FROM sessions s
            LEFT JOIN samples ON samples.session_id = s.id
            WHERE s.started_ts >= ?
        """
        params = [since]
        if vin:
            q += " AND s.vin = ?"
            params.append(vin)
        q += " GROUP BY s.id ORDER BY s.started_ts DESC"
        return [dict(r) for r in self.conn.execute(q, params)]

    def maf_ratio_trend(self, vin: str | None = None, days: int = 30) -> list[dict]:
        """Average MAF actual vs expected ratio per session (throttle-based)."""
        from .vehicle import expected_maf
        sessions = self.ltft_history(vin, days)
        out = []
        for sess in sessions:
            rows = self.conn.execute(
                "SELECT rpm, throttle_pct, maf_gs FROM samples "
                "WHERE session_id=? AND rpm > 400 AND maf_gs > 0",
                (sess["id"],)
            ).fetchall()
            ratios = []
            for r in rows:
                if r["throttle_pct"] is None:
                    continue
                exp = expected_maf(r["rpm"], throttle_pct=r["throttle_pct"],
                                   mode="throttle")
                if exp > 0:
                    ratios.append(r["maf_gs"] / exp)
            if ratios:
                out.append({
                    "session_id": sess["id"],
                    "started_ts": sess["started_ts"],
                    "source": sess["source"],
                    "note": sess["note"],
                    "n_samples": len(ratios),
                    "ratio_mean": sum(ratios) / len(ratios),
                    "ratio_min": min(ratios),
                    "ratio_max": max(ratios),
                })
        return out

    def dtc_occurrences(self, vin: str | None = None, days: int = 90) -> list[dict]:
        """Count how often each DTC has appeared across sessions."""
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        q = """
            SELECT d.code, d.bucket, COUNT(*) AS occurrences,
                   MIN(d.first_seen_ts) AS first_ts, MAX(d.last_seen_ts) AS last_ts
            FROM dtcs_seen d
            JOIN sessions s ON s.id = d.session_id
            WHERE s.started_ts >= ?
        """
        params = [since]
        if vin:
            q += " AND s.vin = ?"; params.append(vin)
        q += " GROUP BY d.code, d.bucket ORDER BY occurrences DESC"
        return [dict(r) for r in self.conn.execute(q, params)]

    def session_summary(self, session_id: int) -> dict:
        s = self.conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not s:
            return {}
        stats = self.conn.execute(
            """SELECT COUNT(*) AS n,
                      MIN(rpm) AS rpm_min, MAX(rpm) AS rpm_max,
                      MIN(ltft_pct) AS ltft_min, MAX(ltft_pct) AS ltft_max,
                      AVG(ltft_pct) AS ltft_avg,
                      MIN(coolant_c) AS cool_min, MAX(coolant_c) AS cool_max,
                      MAX(mil) AS mil_ever, MAX(dtc_count) AS dtc_max
               FROM samples WHERE session_id=?""",
            (session_id,),
        ).fetchone()
        evs = self.conn.execute(
            "SELECT * FROM events WHERE session_id=? ORDER BY ts",
            (session_id,),
        ).fetchall()
        dtcs = self.conn.execute(
            "SELECT code, bucket FROM dtcs_seen WHERE session_id=?",
            (session_id,),
        ).fetchall()
        return {
            "session": dict(s),
            "stats": dict(stats) if stats else {},
            "events": [dict(e) for e in evs],
            "dtcs": [dict(d) for d in dtcs],
        }
