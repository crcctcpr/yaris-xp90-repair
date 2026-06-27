"""Odometer tracking + maintenance due calculation.

Stores odometer readings (manual entry) in a lightweight JSON file. The
web /overview page reads and writes this via a POST endpoint. Computes
which maintenance intervals are due based on current mileage and last
service dates.
"""
import json
import os
from datetime import datetime

from .vehicle import REPORT_DIR, VIN
from .knowledge import MAINTENANCE


ODOMETER_FILE = os.path.join(REPORT_DIR, "odometer.json")


def _load() -> dict:
    if not os.path.exists(ODOMETER_FILE):
        return {"vin": VIN, "readings": [], "services_done": []}
    try:
        with open(ODOMETER_FILE) as f:
            return json.load(f)
    except Exception:
        return {"vin": VIN, "readings": [], "services_done": []}


def _save(data: dict):
    os.makedirs(os.path.dirname(ODOMETER_FILE), exist_ok=True)
    with open(ODOMETER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_reading(km: int, source: str = "manual", notes: str = "") -> dict:
    """Record an odometer reading. Returns updated data."""
    data = _load()
    data["readings"].append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "km": int(km),
        "source": source,
        "notes": notes,
    })
    # Keep sorted by ts
    data["readings"].sort(key=lambda r: r["ts"])
    _save(data)
    return data


def record_service(km: int, service_km_interval: int, note: str = "") -> dict:
    """Record that a maintenance-interval service was performed at given km.

    e.g. at 85,000 km, oil change was done → record_service(85000, 10000, "oil+filter")
    so that the next 10k-interval item is due at 95,000 km.
    """
    data = _load()
    data["services_done"].append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "km": int(km),
        "interval_km": int(service_km_interval),
        "note": note,
    })
    _save(data)
    return data


def latest_km() -> int | None:
    data = _load()
    if not data["readings"]:
        return None
    return data["readings"][-1]["km"]


def latest_reading() -> dict | None:
    data = _load()
    return data["readings"][-1] if data["readings"] else None


def service_status() -> list[dict]:
    """For each maintenance interval in KB, return {interval_km, status, next_due_km, km_until}."""
    data = _load()
    current_km = latest_km()
    if current_km is None:
        return [{"interval_km": m.km, "status": "unknown (odometer not set)",
                 "items": m.items, "cost": (m.cost_usd_low, m.cost_usd_high)}
                for m in MAINTENANCE]

    # Find the latest service at each interval
    last_by_interval = {}
    for s in data["services_done"]:
        interval = s["interval_km"]
        prev = last_by_interval.get(interval)
        if not prev or s["km"] > prev["km"]:
            last_by_interval[interval] = s

    out = []
    for m in MAINTENANCE:
        last = last_by_interval.get(m.km)
        if last:
            next_due = last["km"] + m.km
        else:
            # Never serviced — first service due at first multiple past current km
            next_due = ((current_km // m.km) + 1) * m.km
        km_until = next_due - current_km
        if km_until <= 0:
            status = "OVERDUE"
        elif km_until <= 1500:
            status = "due soon"
        else:
            status = "on schedule"
        out.append({
            "interval_km": m.km,
            "interval_months": m.months,
            "items": m.items,
            "last_done_km": last["km"] if last else None,
            "last_done_ts": last["ts"] if last else None,
            "next_due_km": next_due,
            "km_until": km_until,
            "status": status,
            "cost_low": m.cost_usd_low,
            "cost_high": m.cost_usd_high,
        })
    out.sort(key=lambda x: x["km_until"])
    return out


def history() -> list[dict]:
    return _load()["readings"]


def services_history() -> list[dict]:
    return _load()["services_done"]
