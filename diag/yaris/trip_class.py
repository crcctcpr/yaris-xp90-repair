"""Trip classification — segment a CSV into driving phases.

Phases:
  - idle      : engine on, speed == 0, rpm < 1200
  - creep     : speed 0-20, light load (parking lots, stop-go)
  - city      : speed 20-50
  - suburban  : speed 50-80
  - highway   : speed 80+
  - accel     : d(speed)/dt > threshold regardless of band
  - decel     : d(speed)/dt < -threshold and throttle < 5 (coasting)
  - wot       : throttle > 80 (wide open throttle)

Reports per-phase: time fraction, distance, avg RPM, avg MAF, avg LTFT.
"""
import csv
import os
from dataclasses import dataclass, field


@dataclass
class PhaseStats:
    phase: str
    samples: int = 0
    time_s: float = 0
    distance_km: float = 0
    avg_rpm: float = 0
    avg_speed: float = 0
    avg_maf: float = 0
    avg_ltft: float = 0
    avg_throttle: float = 0


def classify_trip(csv_path: str, sample_interval_s: float = 1.3) -> dict:
    if not os.path.exists(csv_path):
        return {"error": "file not found", "phases": []}
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "rpm": float(r.get("rpm") or 0),
                    "speed": float(r.get("speed_kmh") or 0),
                    "maf": float(r.get("maf_gs") or 0),
                    "stft": float(r.get("stft_b1_pct") or 0),
                    "ltft": float(r.get("ltft_b1_pct") or 0),
                    "throttle": float(r.get("throttle_pct") or 0),
                    "load": float(r.get("load_pct") or 0),
                })
            except ValueError:
                continue
    if not rows:
        return {"error": "no valid rows", "phases": []}

    # Classify each row
    for i, r in enumerate(rows):
        prev_speed = rows[i - 1]["speed"] if i > 0 else r["speed"]
        dspeed = r["speed"] - prev_speed
        if r["rpm"] < 200:
            r["phase"] = "engine_off"
        elif dspeed > 4 and r["throttle"] > 30:
            r["phase"] = "accel"
        elif dspeed < -3 and r["throttle"] < 8:
            r["phase"] = "decel"
        elif r["throttle"] > 75:
            r["phase"] = "wot"
        elif r["speed"] == 0:
            r["phase"] = "idle"
        elif r["speed"] < 20:
            r["phase"] = "creep"
        elif r["speed"] < 50:
            r["phase"] = "city"
        elif r["speed"] < 80:
            r["phase"] = "suburban"
        else:
            r["phase"] = "highway"

    # Aggregate per-phase
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["phase"], []).append(r)

    phases = []
    for phase, entries in buckets.items():
        n = len(entries)
        time_s = n * sample_interval_s
        dist = sum(r["speed"] for r in entries) * sample_interval_s / 3600
        phases.append(PhaseStats(
            phase=phase, samples=n, time_s=time_s, distance_km=dist,
            avg_rpm=sum(r["rpm"] for r in entries) / n,
            avg_speed=sum(r["speed"] for r in entries) / n,
            avg_maf=sum(r["maf"] for r in entries) / n,
            avg_ltft=sum(r["ltft"] for r in entries) / n,
            avg_throttle=sum(r["throttle"] for r in entries) / n,
        ))

    total_time = sum(p.time_s for p in phases)
    total_dist = sum(p.distance_km for p in phases)
    return {
        "csv_path": csv_path,
        "total_samples": len(rows),
        "total_time_s": total_time,
        "total_distance_km": total_dist,
        "phases": [
            {
                "phase": p.phase, "samples": p.samples, "time_s": p.time_s,
                "time_pct": 100 * p.time_s / total_time if total_time else 0,
                "distance_km": round(p.distance_km, 3),
                "avg_rpm": round(p.avg_rpm, 0),
                "avg_speed": round(p.avg_speed, 1),
                "avg_maf": round(p.avg_maf, 2),
                "avg_ltft": round(p.avg_ltft, 2),
                "avg_throttle": round(p.avg_throttle, 1),
            }
            for p in sorted(phases, key=lambda x: -x.time_s)
        ],
    }
