"""Webhook / ntfy push alerts.

Sends events to a configured webhook when critical thresholds cross during
a live drive. Defaults to ntfy.sh for free phone push notifications (the
user just subscribes to a topic on their phone's ntfy app).

Config file: reports/alerts.json
  {
    "enabled": true,
    "ntfy_topic": "yaris-<yourname>-<random>",
    "ntfy_server": "https://ntfy.sh",
    "generic_webhook": "https://discord.com/api/webhooks/...",
    "thresholds": {
      "ltft_high": 24,
      "coolant_high": 105,
      "charging_v_low": 12.8
    },
    "cooldown_seconds": 60
  }

To subscribe on your phone:
  1. Install "ntfy" app (iOS/Android, free).
  2. Pick any unique topic like "my-yaris-alerts" — same string in the app
     and in alerts.json.
  3. Push arrives within seconds of a threshold crossing.

Events fired:
  - mil_on       : MIL transition off → on
  - new_dtc      : DTC count went up
  - ltft_high    : LTFT exceeded threshold
  - overheating  : Coolant exceeded threshold
  - low_voltage  : Charging V dropped below threshold
"""
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime

from .vehicle import REPORT_DIR, VIN


ALERTS_CONFIG_FILE = os.path.join(REPORT_DIR, "alerts.json")

DEFAULT_CONFIG = {
    "enabled": False,
    "ntfy_topic": "",
    "ntfy_server": "https://ntfy.sh",
    "generic_webhook": "",
    "thresholds": {
        "ltft_high": 24.0,
        "coolant_high": 105.0,
        "charging_v_low": 12.8,
    },
    "cooldown_seconds": 60,
}


def load_config() -> dict:
    if not os.path.exists(ALERTS_CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    try:
        with open(ALERTS_CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    os.makedirs(os.path.dirname(ALERTS_CONFIG_FILE), exist_ok=True)
    with open(ALERTS_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def send_ntfy(cfg: dict, title: str, body: str, priority: str = "default",
              tags: list[str] = None) -> bool:
    """Push via ntfy.sh. Returns True on success."""
    topic = cfg.get("ntfy_topic", "").strip()
    if not topic:
        return False
    server = cfg.get("ntfy_server", "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"
    headers = {
        "Title": title,
        "Priority": priority,  # min/low/default/high/urgent
    }
    if tags:
        headers["Tags"] = ",".join(tags)
    try:
        req = urllib.request.Request(url, data=body.encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"[alert] ntfy failed: {e}")
        return False


def send_webhook(cfg: dict, payload: dict) -> bool:
    """POST JSON to a generic webhook (Discord / Slack / custom)."""
    url = cfg.get("generic_webhook", "").strip()
    if not url:
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"[alert] webhook failed: {e}")
        return False


class Alerter:
    """Stateful alert dispatcher with per-event cooldown."""

    def __init__(self, config: dict | None = None):
        self.cfg = config or load_config()
        self._last_fire: dict[str, float] = {}

    def _should_fire(self, event_key: str) -> bool:
        cooldown = self.cfg.get("cooldown_seconds", 60)
        now = time.time()
        last = self._last_fire.get(event_key, 0)
        if now - last < cooldown:
            return False
        self._last_fire[event_key] = now
        return True

    def fire(self, event_key: str, title: str, body: str,
             priority: str = "default", tags: list[str] = None) -> bool:
        """Send an alert through all configured channels. Returns True if any delivered."""
        if not self.cfg.get("enabled"):
            return False
        if not self._should_fire(event_key):
            return False

        full_title = f"Yaris · {title}"
        full_body = f"{body}\n\nVIN: {VIN}\nTime: {datetime.now().strftime('%H:%M:%S')}"

        success = False
        if self.cfg.get("ntfy_topic"):
            success |= send_ntfy(self.cfg, full_title, full_body, priority=priority,
                                 tags=tags or [])
        if self.cfg.get("generic_webhook"):
            success |= send_webhook(self.cfg, {
                "event": event_key,
                "title": full_title, "body": full_body,
                "vin": VIN,
                "ts": datetime.now().isoformat(timespec="seconds"),
            })
        return success

    # ── Semantic helpers ─────────────────────────────────────────
    def mil_on(self, rpm: float, dtc_count: int):
        return self.fire(
            "mil_on", "⚠ Check Engine Light ON",
            f"MIL activated. RPM {rpm:.0f}, {dtc_count} DTC(s).",
            priority="high", tags=["warning", "car"],
        )

    def new_dtc(self, old: int, new: int, rpm: float):
        return self.fire(
            "new_dtc", "⚠ New DTC",
            f"DTC count {old} → {new} at RPM {rpm:.0f}. Pull codes to identify.",
            priority="high", tags=["warning"],
        )

    def ltft_high(self, ltft: float, rpm: float):
        return self.fire(
            "ltft_high", "⚠ LTFT near P0171 threshold",
            f"LTFT at {ltft:+.1f}% (threshold {self.cfg['thresholds']['ltft_high']:+.0f}%). "
            f"Next lean event could set P0171. RPM {rpm:.0f}.",
            priority="default", tags=["warning"],
        )

    def overheating(self, coolant_c: float):
        return self.fire(
            "overheating", "🔥 Engine OVERHEATING",
            f"Coolant {coolant_c:.0f}°C — STOP DRIVING IMMEDIATELY. "
            f"Pull over and shut off engine.",
            priority="urgent", tags=["rotating_light", "car"],
        )

    def low_voltage(self, v: float, rpm: float):
        return self.fire(
            "low_voltage", "🔋 Charging voltage low",
            f"Alternator reading {v:.2f}V at RPM {rpm:.0f}. "
            f"Healthy is 13.4-14.5V. Battery may be running down.",
            priority="default", tags=["battery"],
        )

    def test_alert(self):
        return self.fire(
            "test", "Yaris alert test", "This is a test alert. Webhook config works.",
            priority="default", tags=["white_check_mark"],
        )
