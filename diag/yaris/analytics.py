"""Advanced analytics — the stuff no other OBD tool does.

1. Predictive forecasting: fit linear regression to LTFT / MAF-ratio /
   charging-V trends across sessions, project forward to threshold-crossing.

2. Anomaly detection: rolling per-PID baseline (median + IQR), flag live
   samples outside personal-history normal range.

3. Replay: CSV → streaming iterator with seek/speed control.

4. Life timeline: unify sessions, services, odometer entries, events, DTCs
   in one chronologically-ordered journal.

5. Dyno / power estimator: MAF-based torque/power curve.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median, stdev
from typing import Iterator, Optional

from .vehicle import REPORT_DIR, VIN, ENGINE_DISPLACEMENT_L


# ── Simple linear regression (stdlib, no scipy needed) ───────────────────
def linreg(xs: list[float], ys: list[float]) -> dict:
    """Returns {slope, intercept, r2, n, resid_std}."""
    n = len(xs)
    if n < 2:
        return {"slope": 0, "intercept": ys[0] if ys else 0, "r2": 0, "n": n, "resid_std": 0}
    mx = sum(xs) / n
    my = sum(ys) / n
    var_x = sum((x - mx) ** 2 for x in xs)
    if var_x < 1e-12:
        return {"slope": 0, "intercept": my, "r2": 0, "n": n, "resid_std": 0}
    cov_xy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = cov_xy / var_x
    intercept = my - slope * mx
    # R²
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0
    resid_std = math.sqrt(ss_res / max(1, n - 2))
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n, "resid_std": resid_std}


# ── Predictive forecasting ──────────────────────────────────────────────
@dataclass
class Forecast:
    metric: str
    current_value: float
    slope_per_day: float
    r2: float
    threshold: float
    days_until_threshold: Optional[float]
    confidence: str  # "high" / "low" / "none"
    sessions_used: int
    history: list[dict] = field(default_factory=list)  # [{date, value}]


def forecast_ltft(days: int = 90) -> Forecast:
    """Project when LTFT average will cross the P0171 threshold (+25%)."""
    from .store import Store, DEFAULT_DB
    with Store(DEFAULT_DB) as s:
        rows = s.ltft_history(vin=VIN, days=days)
    return _forecast_metric(rows, "LTFT", "ltft_avg", threshold=25.0)


def forecast_maf_ratio(days: int = 90) -> Forecast:
    from .store import Store, DEFAULT_DB
    with Store(DEFAULT_DB) as s:
        rows = s.maf_ratio_trend(vin=VIN, days=days)
    # Normalize: maf_ratio_trend returns ratio_mean, not ltft_avg
    rows = [{"id": r["session_id"], "started_ts": r["started_ts"],
             "ltft_avg": r["ratio_mean"], "n": r["n_samples"]} for r in rows]
    return _forecast_metric(rows, "MAF ratio", "ltft_avg", threshold=0.70,
                             below_threshold=True)


def forecast_charging(days: int = 90) -> Forecast:
    """Project charging voltage trend."""
    from .store import Store, DEFAULT_DB
    with Store(DEFAULT_DB) as s:
        sessions = s.sessions(vin=VIN, days=days)
        rows = []
        for sess in sessions:
            v_row = s.conn.execute(
                "SELECT AVG(ctlmod_v) AS v FROM samples WHERE session_id=? AND rpm>600",
                (sess["id"],)).fetchone()
            if v_row and v_row["v"]:
                rows.append({"id": sess["id"], "started_ts": sess["started_ts"],
                              "ltft_avg": v_row["v"], "n": 0})
    return _forecast_metric(rows, "Charging V", "ltft_avg", threshold=12.8,
                             below_threshold=True)


def _forecast_metric(rows: list[dict], metric_name: str, value_key: str,
                     threshold: float, below_threshold: bool = False) -> Forecast:
    """Generic forecast: fit slope over days, project to threshold."""
    if not rows or len(rows) < 2:
        return Forecast(metric=metric_name, current_value=0, slope_per_day=0, r2=0,
                         threshold=threshold, days_until_threshold=None,
                         confidence="none", sessions_used=len(rows), history=[])

    # Convert timestamps to days from earliest
    parsed = []
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["started_ts"].replace("Z", ""))
            parsed.append((dt, r[value_key]))
        except (ValueError, TypeError, KeyError):
            continue
    parsed.sort(key=lambda x: x[0])
    if len(parsed) < 2:
        return Forecast(metric=metric_name, current_value=0, slope_per_day=0, r2=0,
                         threshold=threshold, days_until_threshold=None,
                         confidence="none", sessions_used=len(parsed), history=[])

    t0 = parsed[0][0]
    xs = [(p[0] - t0).total_seconds() / 86400 for p in parsed]
    ys = [float(p[1] or 0) for p in parsed]

    reg = linreg(xs, ys)

    current = ys[-1]
    slope = reg["slope"]
    days_until = None
    if below_threshold:
        # Going DOWN toward threshold
        if slope < -1e-6:
            days_until = (threshold - current) / slope if current > threshold else 0
    else:
        # Going UP toward threshold
        if slope > 1e-6:
            days_until = (threshold - current) / slope if current < threshold else 0

    if reg["r2"] > 0.5 and len(parsed) >= 4:
        confidence = "high"
    elif reg["r2"] > 0.15 and len(parsed) >= 3:
        confidence = "low"
    else:
        confidence = "none"

    return Forecast(
        metric=metric_name, current_value=current, slope_per_day=slope,
        r2=reg["r2"], threshold=threshold,
        days_until_threshold=days_until,
        confidence=confidence, sessions_used=len(parsed),
        history=[{"date": p[0].strftime("%Y-%m-%d %H:%M"),
                  "value": float(p[1] or 0)} for p in parsed],
    )


# ── Anomaly detection: rolling baseline per PID ─────────────────────────
@dataclass
class Baseline:
    pid: str
    n: int
    median: float
    iqr: float        # inter-quartile range
    p10: float
    p90: float
    lower: float      # median - 2×IQR
    upper: float      # median + 2×IQR


def compute_baselines(rpm_band: tuple[int, int] = (600, 900)) -> dict[str, Baseline]:
    """Learn per-PID personal-normal ranges from history at idle RPM band."""
    from .store import Store, DEFAULT_DB
    baselines: dict[str, Baseline] = {}
    pids = [
        ("rpm", "rpm"),
        ("maf_gs", "maf"),
        ("ltft_pct", "ltft"),
        ("stft_pct", "stft"),
        ("coolant_c", "coolant"),
        ("ctlmod_v", "ctlv"),
        ("o2wr_lambda", "lambda"),
    ]
    with Store(DEFAULT_DB) as s:
        for col, label in pids:
            q = f"SELECT {col} FROM samples WHERE rpm BETWEEN ? AND ? AND {col} IS NOT NULL"
            vals = [r[0] for r in s.conn.execute(q, rpm_band)
                     if r[0] is not None and not (isinstance(r[0], float) and math.isnan(r[0]))]
            if len(vals) < 10:
                continue
            vals.sort()
            n = len(vals)
            med = median(vals)
            p25 = vals[int(n * 0.25)]
            p75 = vals[int(n * 0.75)]
            p10 = vals[int(n * 0.10)]
            p90 = vals[int(n * 0.90)]
            iqr = p75 - p25
            baselines[label] = Baseline(
                pid=col, n=n, median=med, iqr=iqr, p10=p10, p90=p90,
                lower=med - 2 * iqr, upper=med + 2 * iqr,
            )
    return baselines


@dataclass
class Anomaly:
    pid: str
    timestamp: str
    session_id: int
    value: float
    baseline_median: float
    distance_iqrs: float  # how many IQRs away from median
    direction: str        # "above" / "below"


def find_anomalies(session_id: int, rpm_band: tuple[int, int] = (600, 900),
                   min_iqrs: float = 2.5) -> list[Anomaly]:
    """Find samples in one session that are anomalous vs the personal baseline."""
    from .store import Store, DEFAULT_DB
    baselines = compute_baselines(rpm_band)
    out: list[Anomaly] = []
    if not baselines:
        return out
    with Store(DEFAULT_DB) as s:
        rows = s.conn.execute(
            "SELECT ts, rpm, maf_gs, stft_pct, ltft_pct, coolant_c, ctlmod_v, "
            "o2wr_lambda FROM samples WHERE session_id=? AND rpm BETWEEN ? AND ?",
            (session_id, rpm_band[0], rpm_band[1])
        ).fetchall()
    pids_to_check = [("rpm", 1), ("maf_gs", 2), ("stft_pct", 3), ("ltft_pct", 4),
                      ("coolant_c", 5), ("ctlmod_v", 6), ("o2wr_lambda", 7)]
    label_map = {"rpm": "rpm", "maf_gs": "maf", "stft_pct": "stft",
                 "ltft_pct": "ltft", "coolant_c": "coolant",
                 "ctlmod_v": "ctlv", "o2wr_lambda": "lambda"}
    for row in rows:
        ts = row[0]
        for col, idx in pids_to_check:
            v = row[idx]
            if v is None:
                continue
            label = label_map[col]
            b = baselines.get(label)
            if not b or b.iqr < 1e-6:
                continue
            dist = abs(v - b.median) / b.iqr
            if dist >= min_iqrs:
                out.append(Anomaly(
                    pid=col, timestamp=ts, session_id=session_id, value=v,
                    baseline_median=b.median, distance_iqrs=dist,
                    direction="above" if v > b.median else "below",
                ))
    out.sort(key=lambda a: -a.distance_iqrs)
    return out[:40]  # top 40


# ── Replay engine ───────────────────────────────────────────────────────
def replay_csv(csv_path: str) -> Iterator[dict]:
    """Generator that yields rows from a CSV in order."""
    if not os.path.exists(csv_path):
        return
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            yield row


# ── Car life timeline ───────────────────────────────────────────────────
@dataclass
class LifeEvent:
    timestamp: str
    category: str   # "session", "service", "dtc", "alert", "odometer", "note"
    title: str
    detail: str = ""
    ref_id: int | None = None
    ref_link: str = ""
    severity: str = "info"  # "info", "warn", "critical", "success"


def build_timeline(days: int = 365) -> list[LifeEvent]:
    """Gather every event type into one chronologically-sorted journal."""
    from .store import Store, DEFAULT_DB
    from .odometer import _load as odo_load
    events: list[LifeEvent] = []

    # Sessions
    with Store(DEFAULT_DB) as s:
        for sess in s.sessions(vin=VIN, days=days):
            summ = s.session_summary(sess["id"])
            stats = summ.get("stats", {})
            source = sess["source"] if sess["source"] else "dash"
            note = sess["note"] or ""
            events.append(LifeEvent(
                timestamp=sess["started_ts"], category="session",
                title=f"Session #{sess['id']} — {source}",
                detail=f"{stats.get('n', 0)} samples, LTFT avg {stats.get('ltft_avg', 0) or 0:.1f}%"
                       + (f" — {note}" if note else ''),
                ref_id=sess["id"], ref_link=f"/session?id={sess['id']}",
                severity="warn" if stats.get("mil_ever") else "info",
            ))
            # Events inside that session
            for ev in summ.get("events", []):
                events.append(LifeEvent(
                    timestamp=ev["ts"], category="alert",
                    title=ev["text"], detail=f"during session #{sess['id']}",
                    ref_id=sess["id"], ref_link=f"/session?id={sess['id']}",
                    severity=ev.get("type", "warn"),
                ))
            # DTCs
            for d in summ.get("dtcs", []):
                events.append(LifeEvent(
                    timestamp=sess["started_ts"], category="dtc",
                    title=f"DTC {d['code']} observed",
                    detail=f"{d['bucket']} · session #{sess['id']}",
                    ref_id=sess["id"], ref_link=f"/dtc?code={d['code']}",
                    severity="warn",
                ))

    # Services
    services_file = os.path.join(REPORT_DIR, "services.json")
    if os.path.exists(services_file):
        try:
            with open(services_file) as f:
                services = json.load(f)
            for s_ in services:
                cost = (s_.get("parts", 0) or 0) + (s_.get("labor", 0) or 0)
                events.append(LifeEvent(
                    timestamp=s_.get("date", "") + "T12:00:00",
                    category="service",
                    title=f"🔧 {s_.get('type', '?').replace('_', ' ').title()}",
                    detail=f"{s_.get('km', 0):,} km · ${cost:.2f} ({s_.get('where', '')}) "
                           + (f"— {s_.get('notes', '')}" if s_.get("notes") else ""),
                    ref_link="/services",
                    severity="success",
                ))
        except Exception:
            pass

    # Odometer readings
    odo = odo_load()
    for r in odo.get("readings", []):
        events.append(LifeEvent(
            timestamp=r["ts"], category="odometer",
            title=f"Odometer {r['km']:,} km",
            detail=r.get("notes") or f"source: {r.get('source', '?')}",
            ref_link="/overview",
            severity="info",
        ))

    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events


# ── Dyno / power estimator ──────────────────────────────────────────────
GASOLINE_ENERGY_J_PER_G = 43500  # J/g (lower heating value)
BSFC_OPTIMISTIC = 240           # g / (kW*h) at best-BSFC operating point
# Thermal + mechanical efficiency combined for a modern small NA engine
ETA_COMBINED_OPT = 0.30         # ~30% best point


def estimate_power(maf_gs: float, rpm: float, load_pct: float = 50) -> dict:
    """Estimate engine output power from MAF and RPM.

    Approach:
      Fuel flow (g/s) = MAF / AFR_stoich   (at λ=1)
      Fuel power (W) = fuel_flow_g_s × HHV × η_combined
      BHP = fuel_power / 746
      Torque (Nm) = power_W × 60 / (2π × RPM)

    Returns estimated BHP + Nm. Rough — not a bolt-on substitute for a real
    dyno — but close enough to visualize the shape of the curve.
    """
    if maf_gs <= 0 or rpm <= 0:
        return {"bhp": 0, "nm": 0, "fuel_lph": 0}
    AFR = 14.7
    fuel_g_s = maf_gs / AFR
    # Assume η scales with load (inlet air utilisation)
    eta = max(0.15, min(0.32, 0.15 + 0.17 * (load_pct / 100.0)))
    fuel_power_W = fuel_g_s * GASOLINE_ENERGY_J_PER_G * eta
    bhp = fuel_power_W / 746
    nm = fuel_power_W * 60 / (2 * math.pi * rpm) if rpm > 0 else 0
    # Fuel flow L/hr for display
    gasoline_density_g_l = 745
    fuel_lph = fuel_g_s * 3600 / gasoline_density_g_l
    return {"bhp": round(bhp, 1), "nm": round(nm, 1), "fuel_lph": round(fuel_lph, 2)}


def power_curve_from_csv(csv_path: str) -> dict:
    """Build a power curve from CSV samples: bins RPM 500-6500 @ 500 RPM intervals."""
    if not os.path.exists(csv_path):
        return {"bins": [], "samples": 0}
    bins: dict[int, list[dict]] = {}
    n = 0
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            try:
                rpm = float(row.get("rpm") or 0)
                maf = float(row.get("maf_gs") or 0)
                load = float(row.get("load_pct") or 50)
                throttle = float(row.get("throttle_pct") or 0)
            except ValueError:
                continue
            if rpm < 500 or maf <= 0.5:
                continue
            # Need throttle >30% to get meaningful power data (otherwise cruise/decel)
            if throttle < 25:
                continue
            band = int(rpm // 500 * 500)
            est = estimate_power(maf, rpm, load)
            bins.setdefault(band, []).append(est)
            n += 1
    out_bins = []
    for band in sorted(bins):
        entries = bins[band]
        if not entries:
            continue
        avg_bhp = sum(e["bhp"] for e in entries) / len(entries)
        peak_bhp = max(e["bhp"] for e in entries)
        avg_nm = sum(e["nm"] for e in entries) / len(entries)
        peak_nm = max(e["nm"] for e in entries)
        out_bins.append({
            "rpm": band, "n": len(entries),
            "bhp_avg": round(avg_bhp, 1), "bhp_peak": round(peak_bhp, 1),
            "nm_avg": round(avg_nm, 1), "nm_peak": round(peak_nm, 1),
        })
    # Factory spec for 1NR-FE (dual VVT-i 1.3L): ~99 PS / ~97 BHP @ 6000, 121 Nm @ 4000
    return {
        "bins": out_bins,
        "samples": n,
        "factory": {
            "bhp_peak": 97, "bhp_rpm": 6000,
            "nm_peak": 121, "nm_rpm": 4000,
            "engine": "1NR-FE 1.3L dual VVT-i",
        },
    }
