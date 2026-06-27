"""Web dashboard for the Yaris OBD2 toolkit.

Serves an HTML dashboard at http://<host>:<port>/ that shows:
  - Live gauges (RPM, speed, MAF + expected, coolant, battery V, load, throttle)
  - Time-series charts (STFT/LTFT trims, MAF ratio, cat temp)
  - MIL + DTC status banner
  - Readiness monitor indicators
  - Recent event log

Reads from an existing live-dash CSV (defaults to the newest `drive_live_*.csv`
or `driveway_test_*.csv` in reports/). Pushes new rows to connected browsers
via Server-Sent Events (no polling needed in the browser).

Can view from the same laptop at http://localhost:8080, or from a phone on the
same WiFi at http://<laptop-ip>:8080.

Usage:
  python3 -m yaris.webdash                       # auto-detect newest CSV
  python3 -m yaris.webdash --csv reports/foo.csv # specific file
  python3 -m yaris.webdash --port 8080
"""
import argparse
import csv
import glob
import html
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .vehicle import REPORT_DIR, VIN, MODEL_YEAR, ENGINE, expected_maf


def find_newest_csv(pattern_dir: str) -> str | None:
    candidates = []
    for pat in ("drive_live_*.csv", "driveway_test_*.csv", "drive_*.csv"):
        candidates.extend(glob.glob(os.path.join(pattern_dir, pat)))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def get_lan_ip() -> str:
    """Best-effort find of this machine's LAN IP (for phone access)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


class CsvTailer:
    """Tails a CSV, keeping a ring buffer of the last N rows. Thread-safe."""

    def __init__(self, path: str, max_rows: int = 600):
        self.path = path
        self.rows: list[dict] = []
        self.max_rows = max_rows
        # RLock so add_event() can be called from within run()'s critical section
        self.lock = threading.RLock()
        self.events: list[dict] = []  # (ts, type, text)
        self._stop = False
        self._prev = {}

    def add_event(self, etype: str, text: str):
        with self.lock:
            self.events.append({
                "ts": datetime.now().strftime("%H:%M:%S"),
                "type": etype,
                "text": text,
            })
            if len(self.events) > 40:
                self.events = self.events[-40:]

    def _check_row_alerts(self, row: dict):
        """Watch for critical changes vs previous row."""
        def f(k, default=None):
            v = row.get(k)
            try: return float(v)
            except: return default

        mil = int(row.get("mil", 0) or 0)
        dtc = int(row.get("dtc_count", 0) or 0)
        ltft = f("ltft_b1_pct", 0)
        cool = f("coolant_c", 0)

        prev_mil = self._prev.get("mil", 0)
        prev_dtc = self._prev.get("dtc", 0)
        prev_ltft_alert = self._prev.get("ltft_alert", False)
        prev_cool_alert = self._prev.get("cool_alert", False)

        if mil == 1 and prev_mil == 0:
            self.add_event("critical", f"MIL TURNED ON — rpm={f('rpm'):.0f}")
        if dtc > prev_dtc:
            self.add_event("critical", f"DTC count {prev_dtc} → {dtc}")
        if ltft >= 24 and not prev_ltft_alert:
            self.add_event("warn", f"LTFT {ltft:+.1f}% near P0171 threshold")
            self._prev["ltft_alert"] = True
        if ltft < 22:
            self._prev["ltft_alert"] = False
        if cool >= 105 and not prev_cool_alert:
            self.add_event("critical", f"Coolant {cool:.0f}°C — overheating warn")
            self._prev["cool_alert"] = True
        if cool < 100:
            self._prev["cool_alert"] = False

        self._prev["mil"] = mil
        self._prev["dtc"] = dtc

    def run(self):
        """Blocking loop — read CSV, watch for new rows, update ring buffer."""
        if not os.path.exists(self.path):
            self.add_event("warn", f"CSV not yet present: {self.path}")

        # Initial read of existing rows
        cols = None
        last_size = 0
        last_inode = None

        while not self._stop:
            try:
                if not os.path.exists(self.path):
                    time.sleep(1)
                    continue
                stat = os.stat(self.path)
                if last_inode is None:
                    last_inode = stat.st_ino
                elif stat.st_ino != last_inode:
                    # File replaced (rotated). Re-open.
                    last_size = 0
                    last_inode = stat.st_ino
                    with self.lock:
                        self.rows.clear()
                    self.add_event("info", "CSV rotated — re-attached to new file")

                if stat.st_size < last_size:
                    # Truncated
                    last_size = 0
                    with self.lock:
                        self.rows.clear()

                if stat.st_size == last_size:
                    time.sleep(0.5)
                    continue

                with open(self.path) as f:
                    if last_size == 0:
                        reader = csv.DictReader(f)
                        cols = reader.fieldnames
                        new_rows = list(reader)
                    else:
                        # Seek to last_size; read remainder; parse with cols
                        f.seek(last_size)
                        text = f.read()
                        new_rows = []
                        for line in text.splitlines():
                            if not line.strip() or not cols:
                                continue
                            vals = line.split(",")
                            if len(vals) != len(cols):
                                continue
                            new_rows.append(dict(zip(cols, vals)))

                with self.lock:
                    for r in new_rows:
                        self._check_row_alerts(r)
                        self.rows.append(r)
                    if len(self.rows) > self.max_rows:
                        self.rows = self.rows[-self.max_rows:]

                last_size = stat.st_size
                time.sleep(0.3)
            except Exception as e:
                self.add_event("warn", f"tailer error: {e}")
                time.sleep(2)

    def latest(self) -> dict | None:
        with self.lock:
            return self.rows[-1].copy() if self.rows else None

    def history(self, n: int = 300) -> list[dict]:
        with self.lock:
            return list(self.rows[-n:])

    def recent_events(self) -> list[dict]:
        with self.lock:
            return list(self.events)


def row_to_display(r: dict) -> dict:
    """Normalize a CSV row to display-ready JSON."""
    def f(k, default=None):
        v = r.get(k)
        try: return float(v)
        except: return default

    rpm = f("rpm", 0)
    speed = f("speed_kmh", 0)
    maf = f("maf_gs", 0)
    throttle = f("throttle_pct", 0)
    load = f("load_pct", 0)
    coolant = f("coolant_c", 0)
    iat = f("iat_c", 0)
    stft = f("stft_b1_pct", 0)
    ltft = f("ltft_b1_pct", 0)
    o2 = f("o2_b1s2_v", 0)
    lam = f("o2wr_lambda", 0)
    cat_t = f("cat_temp_c", 0)
    timing = f("timing_deg", 0)
    ctlv = f("ctlmod_v", 0)
    fs = r.get("fuel_sys", "")
    mil = int(r.get("mil", 0) or 0)
    dtc = int(r.get("dtc_count", 0) or 0)

    # Expected MAF via throttle-based model
    exp = expected_maf(rpm, throttle_pct=throttle, mode="throttle") if rpm > 300 else 0
    ratio = (maf / exp) if exp > 0 else None

    return {
        "ts": r.get("timestamp", ""),
        "rpm": rpm, "speed": speed, "maf": maf, "maf_exp": exp, "maf_ratio": ratio,
        "throttle": throttle, "load": load, "coolant": coolant, "iat": iat,
        "stft": stft, "ltft": ltft, "o2": o2, "lambda": lam,
        "cat_t": cat_t, "timing": timing, "ctlv": ctlv,
        "fs": fs, "mil": mil, "dtc": dtc,
    }


# ── Shared navigation header (inserted into each page) ─────────────────
NAV_HTML = """
<nav class="topnav">
  <b style="color:#c9d1d9;">Yaris Diag</b>
  <a href="/assistant" style="color:#3fb950;font-weight:600;">💬 Ask</a>
  <a href="/">live</a>
  <a href="/overview">overview</a>
  <a href="/checklist">checklist</a>
  <a href="/diagnose">diagnose</a>
  <a href="/walkthroughs">walkthru</a>
  <a href="/history">history</a>
  <a href="/timeline">timeline</a>
  <a href="/compare">compare</a>
  <a href="/economy">economy</a>
  <a href="/services">services</a>
  <a href="/forecast">forecast</a>
  <a href="/anomalies">anomalies</a>
  <a href="/dyno">dyno</a>
  <a href="/replay">replay</a>
  <a href="/trip">trips</a>
  <a href="/dtc">DTCs</a>
  <a href="/crossref">parts</a>
  <a href="/fusebox">fuses</a>
  <a href="/monitors">monitors</a>
  <a href="/alerts">alerts</a>
  <a href="/digest">digest</a>
  <a href="/import">import</a>
  <a href="/plots">plots</a>
  <a href="/knowledge">KB</a>
  <a href="/search" title="global search (/)">🔎</a>
  <a href="/vehicles" style="margin-left:auto;color:#6e7681;font-size:11px;text-decoration:none;"
     title="Switch vehicle">🚗 __VIN_TITLE__ ›</a>
</nav>
"""


# ── Shared page CSS (re-used across pages) ─────────────────────────────
PAGE_STYLE = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
       margin: 0; background: #0d1117; color: #c9d1d9; font-size: 14px; }
main { padding: 12px; max-width: 1200px; margin: 0 auto; }

.topnav { background: #161b22; border-bottom: 1px solid #30363d; padding: 8px 14px;
          display: flex; gap: 12px; font-size: 13px; align-items: center;
          flex-wrap: wrap; position: sticky; top: 0; z-index: 100; }
.topnav a { color: #58a6ff; text-decoration: none; padding: 2px 4px; border-radius: 3px; }
.topnav a:hover { background: #21262d; text-decoration: none; }

/* Mobile: tighten nav, make cards full-width, larger touch targets */
@media (max-width: 720px) {
  .topnav { gap: 8px; font-size: 12px; padding: 6px 10px; overflow-x: auto; flex-wrap: nowrap; white-space: nowrap; }
  .topnav a { padding: 4px 6px; }
  main { padding: 8px; }
  .row { grid-template-columns: 1fr !important; gap: 8px !important; }
  .card { padding: 10px !important; }
  .card .value { font-size: 18px !important; }
  h1 { font-size: 17px; }
  h2 { font-size: 14px; }
  button { min-height: 36px; font-size: 14px; }
  input, select, textarea { font-size: 14px; min-height: 32px; }
  table { font-size: 12px; }
  th, td { padding: 4px 6px; }
}
h1, h2 { color: #c9d1d9; margin: 14px 0 10px 0; }
h1 { font-size: 18px; font-weight: 500; }
h2 { font-size: 15px; font-weight: 500; color: #8b949e; margin-top: 18px; }
.row { display: grid; gap: 10px; margin-bottom: 10px;
       grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; }
.card .label { color: #8b949e; font-size: 11px; text-transform: uppercase; }
.card .value { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.card .sub { color: #8b949e; font-size: 11px; margin-top: 2px; }
.val-ok   { color: #3fb950; }
.val-warn { color: #d29922; }
.val-err  { color: #f85149; }
table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
th { color: #8b949e; text-align: left; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #30363d; font-size: 11px; text-transform: uppercase; }
td { padding: 6px 8px; border-bottom: 1px solid #21262d; }
tr:hover { background: #1c2128; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 12px;
        font-size: 11px; font-weight: 500; }
.pill.ok { background: rgba(63,185,80,0.15); color: #3fb950; }
.pill.warn { background: rgba(210,153,34,0.15); color: #d29922; }
.pill.err  { background: rgba(248,81,73,0.15);  color: #f85149; }
.pill.sev-critical { background: rgba(248,81,73,0.15); color: #f85149; }
.pill.sev-warn     { background: rgba(210,153,34,0.15); color: #d29922; }
.pill.sev-minor    { background: rgba(99,110,123,0.2); color: #8b949e; }
input[type=search], input[type=text] { background: #0d1117; border: 1px solid #30363d;
    color: #c9d1d9; padding: 6px 8px; border-radius: 4px; font-size: 13px; }
.chart-wrap { height: 220px; position: relative; }
"""


GLOBAL_KEYBOARD_JS = """
<!-- Command palette overlay -->
<div id="palette-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9998;" onclick="closePalette()"></div>
<div id="palette" style="display:none;position:fixed;top:15vh;left:50%;transform:translateX(-50%);
     width:90%;max-width:560px;background:#161b22;border:1px solid #30363d;border-radius:8px;
     box-shadow:0 20px 60px rgba(0,0,0,0.5);z-index:9999;padding:0;">
  <input id="palette-input" type="text" placeholder="Search pages, DTCs, issues, parts, commands…"
         style="width:100%;padding:14px;background:transparent;border:none;color:#c9d1d9;font-size:16px;outline:none;border-bottom:1px solid #30363d;"
         oninput="updatePalette()">
  <div id="palette-results" style="max-height:50vh;overflow-y:auto;"></div>
  <div style="padding:8px 12px;border-top:1px solid #30363d;color:#6e7681;font-size:11px;">
    ↑↓ navigate · Enter go · Esc close
  </div>
</div>

<!-- Toast container -->
<div id="toast-container" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
     z-index:9997;display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none;"></div>

<script>
// ── Toast system ────────────────────────────────────────────────
window.toast = function(message, type) {
  type = type || 'info';
  const colors = {info:'#58a6ff', success:'#3fb950', warn:'#d29922', error:'#f85149'};
  const el = document.createElement('div');
  el.style.cssText = `background:#161b22;border:1px solid ${colors[type]};
    border-radius:6px;padding:10px 16px;color:#c9d1d9;font-size:13px;
    box-shadow:0 4px 12px rgba(0,0,0,0.4);pointer-events:auto;
    animation:toast-in 0.2s ease-out;min-width:250px;`;
  el.textContent = message;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300); }, 3000);
};

// ── Command palette ─────────────────────────────────────────────
const PALETTE_ITEMS = [
  {label:"💬 Assistant", href:"/assistant", tags:"chat ask"},
  {label:"🚦 Live dashboard", href:"/", tags:"live realtime"},
  {label:"📊 Overview", href:"/overview", tags:"summary"},
  {label:"✅ Pre-flight checklist", href:"/checklist", tags:"safe drive"},
  {label:"🧭 Diagnose by symptom", href:"/diagnose", tags:"symptom"},
  {label:"🗺 Walkthroughs", href:"/walkthroughs", tags:"guide tree"},
  {label:"📈 History", href:"/history", tags:"sessions trends"},
  {label:"🕐 Timeline", href:"/timeline", tags:"journal events"},
  {label:"⛽ Economy", href:"/economy", tags:"mpg fuel"},
  {label:"🛠 Service log", href:"/services", tags:"cost"},
  {label:"🔮 Forecast", href:"/forecast", tags:"predict"},
  {label:"🎯 Anomalies", href:"/anomalies", tags:"baseline"},
  {label:"🏁 Dyno", href:"/dyno", tags:"power hp torque"},
  {label:"⏯ Replay", href:"/replay", tags:"playback"},
  {label:"🛣 Trip analysis", href:"/trip", tags:"phases"},
  {label:"⚠️ DTCs", href:"/dtc", tags:"codes"},
  {label:"🔩 Parts cross-reference", href:"/crossref", tags:"oem"},
  {label:"⚡ Fuses", href:"/fusebox", tags:"electrical relay"},
  {label:"📋 Mode 06 monitors", href:"/monitors", tags:"test"},
  {label:"📣 Alerts config", href:"/alerts", tags:"ntfy webhook"},
  {label:"📰 Weekly digest", href:"/digest", tags:"summary"},
  {label:"📷 Plot gallery", href:"/plots", tags:"png images"},
  {label:"📚 Knowledge base", href:"/knowledge", tags:"kb"},
  {label:"🔎 Global search", href:"/search", tags:""},
  {label:"📖 Mode 19 enhanced DTCs", href:"/mode19", tags:"status bits"},
  {label:"📊 IPT / performance tracking", href:"/ipt", tags:"ratio monitor"},
  {label:"🔧 ELM327 capability reference", href:"/elm-reference", tags:"at commands"},
  {label:"📦 Import / Export", href:"/import", tags:"backup archive"},
];
let paletteFocused = 0, paletteVisible = [];

function openPalette() {
  document.getElementById('palette-overlay').style.display = 'block';
  document.getElementById('palette').style.display = 'block';
  document.getElementById('palette-input').value = '';
  document.getElementById('palette-input').focus();
  updatePalette();
}
function closePalette() {
  document.getElementById('palette-overlay').style.display = 'none';
  document.getElementById('palette').style.display = 'none';
}
function updatePalette() {
  const q = document.getElementById('palette-input').value.toLowerCase().trim();
  paletteVisible = PALETTE_ITEMS.filter(it =>
    !q || it.label.toLowerCase().includes(q) || it.tags.toLowerCase().includes(q)
  );
  // Fetch additional dynamic results if query length >= 2
  if (q.length >= 2) {
    fetch('/palette_search?q=' + encodeURIComponent(q)).then(r=>r.json()).then(extra => {
      paletteVisible = paletteVisible.concat(extra.slice(0, 8));
      renderPalette();
    }).catch(() => renderPalette());
  } else {
    renderPalette();
  }
}
function renderPalette() {
  paletteFocused = 0;
  const el = document.getElementById('palette-results');
  el.innerHTML = paletteVisible.slice(0, 20).map((it, i) =>
    `<div class="p-item" data-i="${i}"
          style="padding:10px 14px;cursor:pointer;display:flex;justify-content:space-between;border-bottom:1px solid #21262d;background:${i===0?'#21262d':'transparent'};"
          onclick="goPalette(${i})">
      <span>${it.label}</span>
      <span style="color:#6e7681;font-size:11px;">${it.href || ''}</span>
    </div>`
  ).join('') || '<div style="padding:14px;color:#6e7681;">no matches</div>';
}
function goPalette(i) {
  const it = paletteVisible[i];
  if (it && it.href) window.location = it.href;
}

// ── Keyboard shortcuts (global) ─────────────────────────────────
document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl + K → open palette
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault(); openPalette(); return;
  }
  // Palette-active key handling
  if (document.getElementById('palette').style.display === 'block') {
    if (e.key === 'Escape') { closePalette(); return; }
    if (e.key === 'Enter') { goPalette(paletteFocused); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      paletteFocused += (e.key === 'ArrowDown' ? 1 : -1);
      paletteFocused = Math.max(0, Math.min(paletteVisible.length - 1, paletteFocused));
      document.querySelectorAll('.p-item').forEach((d, i) => {
        d.style.background = i === paletteFocused ? '#21262d' : 'transparent';
      });
      return;
    }
  }
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === '/') { e.preventDefault(); window.location = '/search'; }
  else if (e.key === 'g') {
    const handler = (e2) => {
      document.removeEventListener('keydown', handler);
      const map = {
        'h': '/', 'o': '/overview', 'd': '/diagnose', 'c': '/checklist',
        'w': '/walkthroughs', 't': '/timeline', 'k': '/knowledge',
        's': '/services', 'a': '/assistant', 'l': '/', 'f': '/forecast',
        'r': '/replay', 'x': '/anomalies', 'y': '/dyno', 'p': '/plots',
        'e': '/elm-reference', 'i': '/ipt', 'm': '/mode19',
      };
      if (map[e2.key]) window.location = map[e2.key];
    };
    setTimeout(() => document.addEventListener('keydown', handler, {once:true}), 10);
  }
});
</script>

<style>
@keyframes toast-in { from {opacity:0;transform:translateY(10px);} to {opacity:1;transform:translateY(0);} }
.p-item:hover { background:#21262d !important; }
</style>
"""


def render_breadcrumbs(trail: list[tuple[str, str]]) -> str:
    """Render a breadcrumb bar. trail = [(label, href), ...]. Last entry should have href="" (current)."""
    if not trail:
        return ""
    parts = []
    for i, (label, href) in enumerate(trail):
        is_last = (i == len(trail) - 1)
        if href and not is_last:
            parts.append(f'<a href="{html.escape(href)}" style="color:#58a6ff;text-decoration:none;">{html.escape(label)}</a>')
        else:
            parts.append(f'<span style="color:#c9d1d9;">{html.escape(label)}</span>')
    return (
        '<div style="padding:6px 14px;background:#0d1117;border-bottom:1px solid #21262d;'
        'color:#6e7681;font-size:12px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
        + ' <span style="color:#6e7681;">›</span> '.join(parts)
        + '</div>'
    )


def render_page(body: str, title: str = "", breadcrumbs=None) -> str:
    """Wrap a body fragment with shared nav + style into a full HTML page.

    breadcrumbs: optional list of (label, href) tuples — last entry is current.
    """
    crumbs = render_breadcrumbs(breadcrumbs) if breadcrumbs else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Yaris Diag</title>
<style>{PAGE_STYLE}</style>
</head><body>
{NAV_HTML}
{crumbs}
{body}
{GLOBAL_KEYBOARD_JS}
</body></html>"""


# ── HTML frontend (inline, served as a single page) ─────────────────────

HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__VIN_TITLE__ — Yaris Live Dashboard</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", Roboto, sans-serif;
       margin: 0; background: #0d1117; color: #c9d1d9; font-size: 14px; }
.topnav { background: #161b22; border-bottom: 1px solid #30363d; padding: 8px 14px;
         display: flex; gap: 14px; font-size: 13px; align-items: center; flex-wrap: wrap; }
.topnav a { color: #58a6ff; text-decoration: none; }
.topnav a:hover { text-decoration: underline; }
.topnav .live-status { margin-left: auto; font-size: 12px; color: #8b949e; }
header { background: #161b22; padding: 10px 14px; border-bottom: 1px solid #30363d;
         display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
header h1 { margin: 0; font-size: 15px; font-weight: 500; }
header .sub { color: #8b949e; font-size: 12px; }
header .conn { font-size: 12px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
       background: #7d8590; margin-right: 5px; }
.dot.on { background: #3fb950; box-shadow: 0 0 4px #3fb950; }
.dot.err { background: #f85149; box-shadow: 0 0 4px #f85149; }

.banner { padding: 8px 14px; font-weight: 600; display: none; }
.banner.mil-on  { display: block; background: #7d2424; color: #ffdcdc; }
.banner.new-dtc { display: block; background: #7a6200; color: #fff7cc; }

main { padding: 10px; max-width: 1100px; margin: 0 auto; }
.row { display: grid; gap: 8px; margin-bottom: 8px; }
.g6 { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
.g3 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 10px 12px; }
.card.big { padding: 14px; }
.card .label { color: #8b949e; font-size: 11px; text-transform: uppercase;
               letter-spacing: 0.5px; margin-bottom: 4px; }
.card .value { font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums;
               line-height: 1.1; }
.card .unit { color: #8b949e; font-size: 13px; margin-left: 4px; font-weight: 400; }
.card .sub { color: #8b949e; font-size: 11px; margin-top: 2px; font-variant-numeric: tabular-nums; }
.val-ok   { color: #3fb950; }
.val-warn { color: #d29922; }
.val-err  { color: #f85149; }

.chart-wrap { height: 160px; position: relative; }

.leds { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; }
.led { display: flex; align-items: center; gap: 5px; }
.led-dot { width: 10px; height: 10px; border-radius: 50%; background: #30363d; }
.led-dot.ok    { background: #3fb950; }
.led-dot.wait  { background: #d29922; }
.led-dot.fail  { background: #f85149; }
.led-dot.none  { background: #30363d; }

.log { max-height: 140px; overflow-y: auto; font-family: ui-monospace, monospace;
       font-size: 11px; color: #8b949e; line-height: 1.5; }
.log .l-info     { color: #58a6ff; }
.log .l-warn     { color: #d29922; }
.log .l-critical { color: #f85149; font-weight: 600; }

footer { padding: 10px 14px; color: #6e7681; font-size: 11px; text-align: center; }
</style>
</head>
<body>
<header>
  <div>
    <h1>__VIN_TITLE__</h1>
    <div class="sub">__ENGINE__ · VIN __VIN__</div>
  </div>
  <div class="conn">
    <span id="conn-dot" class="dot"></span><span id="conn-text">connecting…</span>
    <span style="margin-left: 12px;" id="last-update">—</span>
  </div>
</header>
<nav class="topnav">
  <b style="color:#c9d1d9;">Yaris Diag</b>
  <a href="/">live</a>
  <a href="/compare">compare</a>
  <a href="/history">history</a>
  <a href="/economy">economy</a>
  <a href="/dtc">DTCs</a>
  <a href="/overview">overview</a>
  <a href="/diagnose">diagnose</a>
  <a href="/monitors">monitors</a>
  <a href="/fusebox">fuses</a>
  <a href="/alerts">alerts</a>
  <a href="/checklist">checklist</a>
  <a href="/walkthroughs">walkthru</a>
  <a href="/services">services</a>
  <a href="/timeline">timeline</a>
  <a href="/forecast">forecast</a>
  <a href="/anomalies">anomalies</a>
  <a href="/dyno">dyno</a>
  <a href="/replay">replay</a>
  <a href="/search">🔎</a>
  <a href="/plots">plots</a>
  <a href="/knowledge">KB</a>
</nav>

<div id="banner-mil" class="banner mil-on">⚠ MIL ON — check DTCs</div>
<div id="banner-new" class="banner new-dtc">⚠ New DTC detected during this session</div>

<main>
  <!-- Top-row primary gauges -->
  <div class="row g6">
    <div class="card big"><div class="label">RPM</div>
      <div class="value" id="g-rpm">—</div>
      <div class="sub" id="g-rpm-sub">&nbsp;</div></div>
    <div class="card big"><div class="label">Speed</div>
      <div class="value" id="g-speed">—<span class="unit">km/h</span></div>
      <div class="sub" id="g-speed-sub">&nbsp;</div></div>
    <div class="card big"><div class="label">MAF</div>
      <div class="value" id="g-maf">—<span class="unit">g/s</span></div>
      <div class="sub" id="g-maf-sub">ratio &nbsp;—</div></div>
    <div class="card big"><div class="label">Coolant</div>
      <div class="value" id="g-coolant">—<span class="unit">°C</span></div>
      <div class="sub" id="g-coolant-sub">&nbsp;</div></div>
    <div class="card big"><div class="label">Battery</div>
      <div class="value" id="g-batt">—<span class="unit">V</span></div>
      <div class="sub" id="g-batt-sub">&nbsp;</div></div>
    <div class="card big"><div class="label">Cat temp</div>
      <div class="value" id="g-cat">—<span class="unit">°C</span></div>
      <div class="sub">&nbsp;</div></div>
  </div>

  <!-- Fuel trims + lambda -->
  <div class="row g6">
    <div class="card"><div class="label">STFT B1</div>
      <div class="value" id="g-stft">—<span class="unit">%</span></div></div>
    <div class="card"><div class="label">LTFT B1</div>
      <div class="value" id="g-ltft">—<span class="unit">%</span></div>
      <div class="sub">P0171 at +25%</div></div>
    <div class="card"><div class="label">λ (wideband)</div>
      <div class="value" id="g-lambda">—</div>
      <div class="sub">1.0 = stoich</div></div>
    <div class="card"><div class="label">Throttle</div>
      <div class="value" id="g-thr">—<span class="unit">%</span></div></div>
    <div class="card"><div class="label">Load</div>
      <div class="value" id="g-load">—<span class="unit">%</span></div></div>
    <div class="card"><div class="label">IAT</div>
      <div class="value" id="g-iat">—<span class="unit">°C</span></div></div>
  </div>

  <!-- Status row -->
  <div class="row g3">
    <div class="card"><div class="label">Engine status</div>
      <div class="value" id="g-status" style="font-size: 18px;">—</div>
      <div class="sub" id="g-fs">&nbsp;</div></div>
    <div class="card"><div class="label">DTCs</div>
      <div class="value" id="g-dtc">—</div>
      <div class="sub" id="g-mil">&nbsp;</div></div>
    <div class="card"><div class="label">Samples captured</div>
      <div class="value" id="g-n">—</div>
      <div class="sub" id="g-runtime">&nbsp;</div></div>
  </div>

  <!-- Charts -->
  <div class="row g3">
    <div class="card"><div class="label">RPM &amp; Speed</div>
      <div class="chart-wrap"><canvas id="c-rpm"></canvas></div></div>
    <div class="card"><div class="label">Fuel trims (STFT, LTFT)</div>
      <div class="chart-wrap"><canvas id="c-trim"></canvas></div></div>
    <div class="card"><div class="label">MAF vs expected (g/s)</div>
      <div class="chart-wrap"><canvas id="c-maf"></canvas></div></div>
  </div>

  <!-- Event log -->
  <div class="row g3">
    <div class="card" style="grid-column: 1 / -1;">
      <div class="label">Event log</div>
      <div id="event-log" class="log">waiting for events…</div>
    </div>
  </div>
</main>

<footer>
  data streamed live via SSE · toolkit by Open Claw Yaris diagnostics
</footer>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const MAX_POINTS = 120;
function mkChart(ctx, datasets, yTitle) {
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: false, spanGaps: true,
      plugins: { legend: { labels: { color: '#c9d1d9', font: { size: 10 } } } },
      scales: {
        x: { display: false },
        y: { ticks: { color: '#8b949e', font: { size: 10 } },
             grid: { color: '#30363d' } }
      },
      elements: { point: { radius: 0 } },
    },
  });
}
const tNow = () => new Date().toLocaleTimeString();
const chartRpm = mkChart(document.getElementById('c-rpm').getContext('2d'), [
  { label: 'RPM',   data: [], borderColor: '#58a6ff', tension: 0.3, yAxisID: 'y' },
  { label: 'km/h',  data: [], borderColor: '#3fb950', tension: 0.3, yAxisID: 'y' },
]);
const chartTrim = mkChart(document.getElementById('c-trim').getContext('2d'), [
  { label: 'STFT %', data: [], borderColor: '#58a6ff', tension: 0.3 },
  { label: 'LTFT %', data: [], borderColor: '#f85149', tension: 0.3 },
]);
const chartMaf = mkChart(document.getElementById('c-maf').getContext('2d'), [
  { label: 'MAF actual',   data: [], borderColor: '#58a6ff', tension: 0.3 },
  { label: 'MAF expected', data: [], borderColor: '#d29922', tension: 0.3, borderDash: [4,4] },
]);

function pushPoint(chart, values) {
  const t = tNow();
  chart.data.labels.push(t);
  values.forEach((v, i) => chart.data.datasets[i].data.push(v));
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets.forEach(d => d.data.shift());
  }
  chart.update('none');
}

function colorFor(el, val, ok, warn) {
  el.classList.remove('val-ok', 'val-warn', 'val-err');
  if (val == null) return;
  const [olo, ohi] = ok;
  const [wlo, whi] = warn;
  if (val >= olo && val <= ohi) el.classList.add('val-ok');
  else if (val >= wlo && val <= whi) el.classList.add('val-warn');
  else el.classList.add('val-err');
}

function fmt(v, d=0) { return (v == null || isNaN(v)) ? '—' : v.toFixed(d); }

function applyUpdate(d) {
  document.getElementById('g-rpm').firstChild.nodeValue = fmt(d.rpm, 0);
  document.getElementById('g-speed').firstChild.nodeValue = fmt(d.speed, 0);
  document.getElementById('g-maf').firstChild.nodeValue = fmt(d.maf, 2);
  if (d.maf_ratio != null)
    document.getElementById('g-maf-sub').textContent = 'ratio ' + fmt(d.maf_ratio, 2) + '×  (exp ' + fmt(d.maf_exp, 1) + ')';
  document.getElementById('g-coolant').firstChild.nodeValue = fmt(d.coolant, 0);
  document.getElementById('g-batt').firstChild.nodeValue = fmt(d.ctlv, 2);
  document.getElementById('g-cat').firstChild.nodeValue = fmt(d.cat_t, 0);
  document.getElementById('g-stft').firstChild.nodeValue = fmt(d.stft, 1);
  document.getElementById('g-ltft').firstChild.nodeValue = fmt(d.ltft, 1);
  document.getElementById('g-lambda').textContent = fmt(d.lambda, 3);
  document.getElementById('g-thr').firstChild.nodeValue = fmt(d.throttle, 1);
  document.getElementById('g-load').firstChild.nodeValue = fmt(d.load, 1);
  document.getElementById('g-iat').firstChild.nodeValue = fmt(d.iat, 0);

  colorFor(document.getElementById('g-ltft'),    d.ltft,    [-7, 7],  [-12, 12]);
  colorFor(document.getElementById('g-stft'),    d.stft,    [-7, 7],  [-12, 12]);
  colorFor(document.getElementById('g-coolant'), d.coolant, [85, 100], [75, 105]);
  colorFor(document.getElementById('g-batt'),    d.ctlv,    [13.4, 14.5], [12.5, 15.0]);
  colorFor(document.getElementById('g-lambda'),  d.lambda,  [0.97, 1.03], [0.92, 1.08]);
  if (d.maf_ratio != null)
    colorFor(document.getElementById('g-maf'), d.maf_ratio, [0.85, 1.15], [0.75, 1.3]);

  document.getElementById('g-status').textContent =
    d.rpm > 400 ? 'Running @ ' + fmt(d.rpm, 0) + ' RPM' : 'Key-on / engine off';
  document.getElementById('g-fs').textContent = 'Fuel sys code: ' + d.fs;
  document.getElementById('g-dtc').textContent = d.dtc;
  document.getElementById('g-mil').textContent = d.mil ? 'MIL: ON' : 'MIL: OFF';

  document.getElementById('banner-mil').style.display = d.mil ? 'block' : 'none';

  if (d.rpm > 300) {
    pushPoint(chartRpm,  [d.rpm, d.speed]);
    pushPoint(chartTrim, [d.stft, d.ltft]);
    pushPoint(chartMaf,  [d.maf, d.maf_exp]);
  }

  document.getElementById('last-update').textContent = 'last: ' + tNow();
}

function applyInitial(data) {
  document.getElementById('g-n').textContent = data.history.length;
  data.history.forEach(r => {
    if (r.rpm > 300) {
      const t = r.ts ? r.ts.split('T')[1] || '' : '';
      chartRpm.data.labels.push(t);
      chartRpm.data.datasets[0].data.push(r.rpm);
      chartRpm.data.datasets[1].data.push(r.speed);
      chartTrim.data.labels.push(t);
      chartTrim.data.datasets[0].data.push(r.stft);
      chartTrim.data.datasets[1].data.push(r.ltft);
      chartMaf.data.labels.push(t);
      chartMaf.data.datasets[0].data.push(r.maf);
      chartMaf.data.datasets[1].data.push(r.maf_exp);
    }
  });
  [chartRpm, chartTrim, chartMaf].forEach(c => {
    while (c.data.labels.length > MAX_POINTS) {
      c.data.labels.shift();
      c.data.datasets.forEach(d => d.data.shift());
    }
    c.update('none');
  });
  if (data.history.length) applyUpdate(data.history[data.history.length - 1]);
  applyEvents(data.events);
}

function applyEvents(evts) {
  const el = document.getElementById('event-log');
  if (!evts || !evts.length) return;
  el.innerHTML = evts.slice().reverse().map(ev =>
    `<div class="l-${ev.type}">[${ev.ts}] ${ev.text}</div>`
  ).join('');
}

// Initial fetch then SSE
fetch('/snapshot').then(r => r.json()).then(applyInitial).catch(e => {
  document.getElementById('event-log').textContent = 'Snapshot fetch failed: ' + e;
});

// Web Audio API beep tones
let audioCtx = null;
let audioEnabled = true;
function audioInit() { if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
function beep(freq, duration=200, volume=0.3) {
  if (!audioEnabled || !audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.frequency.value = freq;
  osc.type = 'sine';
  gain.gain.value = volume;
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration / 1000);
  osc.connect(gain); gain.connect(audioCtx.destination);
  osc.start(); osc.stop(audioCtx.currentTime + duration / 1000);
}
function alertSound(sev) {
  if (sev === 'critical') {
    beep(880, 300, 0.4); setTimeout(() => beep(660, 300, 0.4), 350);
    setTimeout(() => beep(880, 300, 0.4), 700);
  } else if (sev === 'warn') {
    beep(660, 200, 0.3); setTimeout(() => beep(880, 200, 0.3), 250);
  } else { beep(440, 150, 0.2); }
}
// Mute toggle button (inject if not present)
if (!document.getElementById('audio-toggle')) {
  const btn = document.createElement('button');
  btn.id = 'audio-toggle';
  btn.textContent = '🔊';
  btn.style.cssText = 'position:fixed;bottom:14px;right:14px;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:50%;width:42px;height:42px;font-size:18px;cursor:pointer;z-index:9999;';
  btn.onclick = () => {
    audioEnabled = !audioEnabled;
    btn.textContent = audioEnabled ? '🔊' : '🔇';
    if (audioEnabled) { audioInit(); beep(880, 100); }
  };
  document.body.appendChild(btn);
}
let prevMil = false, prevDtcCount = 0;

function connect() {
  const es = new EventSource('/stream');
  es.onopen = () => {
    document.getElementById('conn-dot').className = 'dot on';
    document.getElementById('conn-text').textContent = 'live';
    audioInit();
  };
  es.onerror = () => {
    document.getElementById('conn-dot').className = 'dot err';
    document.getElementById('conn-text').textContent = 'reconnecting…';
    setTimeout(connect, 2000);
    es.close();
  };
  es.addEventListener('row', e => {
    const d = JSON.parse(e.data);
    // Audio alerts on threshold crossings
    if (d.mil && !prevMil) alertSound('critical');
    if (d.dtc > prevDtcCount) alertSound('critical');
    if (Math.abs(d.ltft) >= 24) alertSound('warn');
    if (d.coolant >= 105) alertSound('critical');
    prevMil = d.mil; prevDtcCount = d.dtc;
    applyUpdate(d);
    document.getElementById('g-n').textContent =
      (parseInt(document.getElementById('g-n').textContent) || 0) + 1;
  });
  es.addEventListener('event', e => {
    applyEvents(JSON.parse(e.data));
  });
}
connect();
</script>
</body>
</html>
"""


COMPARE_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__VIN_TITLE__ — Compare</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
       margin: 0; background: #0d1117; color: #c9d1d9; font-size: 14px; }
header { background: #161b22; padding: 12px 14px; border-bottom: 1px solid #30363d; }
header h1 { margin: 0; font-size: 16px; font-weight: 500; }
header a { color: #58a6ff; text-decoration: none; }
main { padding: 12px; max-width: 1200px; margin: 0 auto; }
.form { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 12px; margin-bottom: 12px; display: grid; gap: 8px; }
.form label { display: flex; gap: 8px; align-items: center; }
.form label b { min-width: 80px; color: #8b949e; font-weight: 500; }
.form input { flex: 1; background: #0d1117; border: 1px solid #30363d;
              color: #c9d1d9; padding: 6px 8px; border-radius: 4px; font-size: 12px; }
.form button { background: #238636; color: white; border: 0; padding: 8px 14px;
               border-radius: 4px; cursor: pointer; justify-self: start; font-weight: 500; }
.row { display: grid; gap: 10px; margin-bottom: 10px;
       grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; }
.card .label { color: #8b949e; font-size: 11px; text-transform: uppercase; }
.card .value { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.val-ok { color: #3fb950; } .val-warn { color: #d29922; } .val-err { color: #f85149; }
.delta { font-size: 13px; margin-left: 6px; color: #8b949e; }
.delta.good { color: #3fb950; } .delta.bad { color: #f85149; }
.chart-wrap { height: 240px; position: relative; }
.legend { display: flex; gap: 12px; font-size: 12px; }
.legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
</style>
</head><body>
<header>
  <h1>Compare — before vs after repair</h1>
</header>
<nav style="background:#161b22;border-bottom:1px solid #30363d;padding:8px 14px;
            display:flex;gap:14px;font-size:13px;align-items:center;flex-wrap:wrap;">
  <b style="color:#c9d1d9;">Yaris Diag</b>
  <a href="/" style="color:#58a6ff;text-decoration:none;">live</a>
  <a href="/compare" style="color:#58a6ff;text-decoration:none;">compare</a>
  <a href="/history" style="color:#58a6ff;text-decoration:none;">history</a>
  <a href="/economy" style="color:#58a6ff;text-decoration:none;">economy</a>
  <a href="/dtc" style="color:#58a6ff;text-decoration:none;">DTCs</a>
  <a href="/overview" style="color:#58a6ff;text-decoration:none;">overview</a>
  <a href="/diagnose" style="color:#58a6ff;text-decoration:none;">diagnose</a>
  <a href="/monitors" style="color:#58a6ff;text-decoration:none;">monitors</a>
  <a href="/fusebox" style="color:#58a6ff;text-decoration:none;">fuses</a>
  <a href="/alerts" style="color:#58a6ff;text-decoration:none;">alerts</a>
  <a href="/checklist" style="color:#58a6ff;text-decoration:none;">checklist</a>
  <a href="/walkthroughs" style="color:#58a6ff;text-decoration:none;">walkthru</a>
  <a href="/services" style="color:#58a6ff;text-decoration:none;">services</a>
  <a href="/timeline" style="color:#58a6ff;text-decoration:none;">timeline</a>
  <a href="/forecast" style="color:#58a6ff;text-decoration:none;">forecast</a>
  <a href="/anomalies" style="color:#58a6ff;text-decoration:none;">anomalies</a>
  <a href="/dyno" style="color:#58a6ff;text-decoration:none;">dyno</a>
  <a href="/replay" style="color:#58a6ff;text-decoration:none;">replay</a>
  <a href="/search" style="color:#58a6ff;text-decoration:none;">🔎</a>
  <a href="/plots" style="color:#58a6ff;text-decoration:none;">plots</a>
  <a href="/knowledge" style="color:#58a6ff;text-decoration:none;">KB</a>
</nav>
<main>
  <form class="form" onsubmit="return go(event)">
    <label><b>BEFORE</b>
      <input id="inp-a" type="text" value="__PATH_A__"
             placeholder="./reports/before.csv"></label>
    <label><b>AFTER</b>
      <input id="inp-b" type="text" value="__PATH_B__"
             placeholder="./reports/after.csv"></label>
    <button>Load comparison</button>
  </form>

  <div id="summary" class="row"></div>

  <div class="row">
    <div class="card" style="grid-column: 1 / -1;">
      <div class="label">MAF actual — blue=before, green=after (overlay)</div>
      <div class="chart-wrap"><canvas id="c-maf"></canvas></div>
    </div>
    <div class="card" style="grid-column: 1 / -1;">
      <div class="label">LTFT B1 trajectory</div>
      <div class="chart-wrap"><canvas id="c-ltft"></canvas></div>
    </div>
    <div class="card" style="grid-column: 1 / -1;">
      <div class="label">STFT B1 trajectory</div>
      <div class="chart-wrap"><canvas id="c-stft"></canvas></div>
    </div>
    <div class="card" style="grid-column: 1 / -1;">
      <div class="label">RPM</div>
      <div class="chart-wrap"><canvas id="c-rpm"></canvas></div>
    </div>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const COLOR_A = '#58a6ff', COLOR_B = '#3fb950';

function mkChart(id, labelA, labelB) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [
      { label: labelA, data: [], borderColor: COLOR_A, borderWidth: 1,
        tension: 0.3, pointRadius: 0 },
      { label: labelB, data: [], borderColor: COLOR_B, borderWidth: 1,
        tension: 0.3, pointRadius: 0 }
    ] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { labels: { color: '#c9d1d9', font: { size: 11 } } } },
      scales: {
        x: { display: false },
        y: { ticks: { color: '#8b949e', font: { size: 10 } },
             grid: { color: '#30363d' } }
      },
    }
  });
}

const cMaf  = mkChart('c-maf',  'MAF before (g/s)',  'MAF after (g/s)');
const cLtft = mkChart('c-ltft', 'LTFT before (%)',   'LTFT after (%)');
const cStft = mkChart('c-stft', 'STFT before (%)',   'STFT after (%)');
const cRpm  = mkChart('c-rpm',  'RPM before',        'RPM after');

function fmt(v, d=2) { return (v==null||isNaN(v)) ? '—' : v.toFixed(d); }

function summaryCard(label, valA, valB, unit, goodDirection) {
  const delta = (valA!=null && valB!=null) ? valB - valA : null;
  let deltaClass = 'delta';
  if (delta != null && goodDirection) {
    const isGood = (goodDirection === 'down') ? delta < 0 : delta > 0;
    deltaClass = 'delta ' + (isGood ? 'good' : 'bad');
  }
  const deltaStr = delta!=null ? ` Δ ${delta>=0?'+':''}${fmt(delta, 2)}${unit}` : '';
  return `<div class="card"><div class="label">${label}</div>
    <div class="value">
      ${fmt(valA, 2)}${unit} → ${fmt(valB, 2)}${unit}
      <span class="${deltaClass}">${deltaStr}</span>
    </div></div>`;
}

function render(data) {
  const a = data.a, b = data.b;
  if (a.error) document.getElementById('summary').innerHTML = `<div class="card val-err">BEFORE: ${a.error} (${a.path})</div>`;
  if (b.error) document.getElementById('summary').innerHTML += `<div class="card val-err">AFTER: ${b.error} (${b.path})</div>`;
  if (a.error || b.error) return;

  // Summary
  const sa = a.summary || {}, sb = b.summary || {};
  const html = [
    summaryCard('LTFT avg', sa.ltft?.mean, sb.ltft?.mean, '%', 'down'),
    summaryCard('STFT avg', sa.stft?.mean, sb.stft?.mean, '%', 'down'),
    summaryCard('MAF ratio avg', sa.maf_ratio?.mean, sb.maf_ratio?.mean, '×', 'up'),
    `<div class="card"><div class="label">Samples</div><div class="value">${a.n} → ${b.n}</div></div>`,
  ].join('');
  document.getElementById('summary').innerHTML = html;

  // Fill charts — use index as X axis since timestamps may differ
  const fillChart = (chart, key) => {
    const la = a.rows.map(r => r[key]).filter(v => v !== null && !isNaN(v));
    const lb = b.rows.map(r => r[key]).filter(v => v !== null && !isNaN(v));
    const maxLen = Math.max(la.length, lb.length);
    chart.data.labels = Array.from({length: maxLen}, (_, i) => i);
    chart.data.datasets[0].data = la;
    chart.data.datasets[1].data = lb;
    chart.update('none');
  };
  fillChart(cMaf,  'maf');
  fillChart(cLtft, 'ltft');
  fillChart(cStft, 'stft');
  fillChart(cRpm,  'rpm');
}

function go(e) {
  if (e) e.preventDefault();
  const a = document.getElementById('inp-a').value;
  const b = document.getElementById('inp-b').value;
  if (!a || !b) return false;
  const url = `/compare_data?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
  fetch(url).then(r => r.json()).then(render).catch(err => {
    document.getElementById('summary').innerHTML =
      `<div class="card val-err">Request failed: ${err}</div>`;
  });
  return false;
}

// Auto-load if URL had paths
if (document.getElementById('inp-a').value && document.getElementById('inp-b').value) {
  go();
}
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    tailer: CsvTailer = None  # set by server

    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        p = self.path
        if p == "/":
            self._serve_html()
        elif p == "/snapshot":
            self._serve_snapshot()
        elif p == "/stream":
            self._serve_stream()
        elif p.startswith("/compare_data"):
            self._serve_compare_data()
        elif p.startswith("/compare"):
            self._serve_compare_page()
        elif p.startswith("/history_data"):
            self._serve_history_data()
        elif p.startswith("/history"):
            self._serve_history_page()
        elif p.startswith("/session_data"):
            self._serve_session_data()
        elif p.startswith("/session"):
            self._serve_session_page()
        elif p.startswith("/dtc_data"):
            self._serve_dtc_data()
        elif p.startswith("/dtc"):
            self._serve_dtc_page()
        elif p.startswith("/economy_data"):
            self._serve_economy_data()
        elif p.startswith("/economy"):
            self._serve_economy_page()
        elif p.startswith("/plots"):
            self._serve_plots_page()
        elif p.startswith("/reports/"):
            self._serve_report_file()
        elif p.startswith("/knowledge/search"):
            self._serve_knowledge_search()
        elif p.startswith("/knowledge/issue/"):
            self._serve_knowledge_issue()
        elif p.startswith("/knowledge/procedure/"):
            self._serve_knowledge_procedure()
        elif p.startswith("/knowledge/system/"):
            self._serve_knowledge_system()
        elif p.startswith("/knowledge/maintenance"):
            self._serve_knowledge_maintenance()
        elif p.startswith("/knowledge/specs"):
            self._serve_knowledge_specs()
        elif p.startswith("/knowledge/tsbs"):
            self._serve_knowledge_tsbs()
        elif p.startswith("/knowledge/parts"):
            self._serve_knowledge_parts()
        elif p.startswith("/knowledge/baselines"):
            self._serve_knowledge_baselines()
        elif p.startswith("/knowledge"):
            self._serve_knowledge_home()
        elif p.startswith("/diagnose/rank"):
            self._serve_diagnose_rank()
        elif p.startswith("/diagnose"):
            self._serve_diagnose_page()
        elif p.startswith("/shopping/issue/"):
            self._serve_shopping_issue()
        elif p.startswith("/shopping/procedure/"):
            self._serve_shopping_procedure()
        elif p.startswith("/shopping"):
            self._serve_shopping_home()
        elif p.startswith("/overview_data"):
            self._serve_overview_data()
        elif p.startswith("/overview"):
            self._serve_overview_page()
        elif p.startswith("/monitors"):
            self._serve_monitors_page()
        elif p.startswith("/fusebox"):
            self._serve_fusebox_page()
        elif p.startswith("/maintenance_due"):
            self._serve_maintenance_due_data()
        elif p.startswith("/print/session"):
            self._serve_print_session()
        elif p.startswith("/alerts/test"):
            self._serve_alerts_test()
        elif p.startswith("/alerts/config_data"):
            self._serve_alerts_config_data()
        elif p.startswith("/alerts"):
            self._serve_alerts_page()
        elif p.startswith("/walkthrough/"):
            self._serve_walkthrough_page()
        elif p.startswith("/walkthroughs"):
            self._serve_walkthroughs_home()
        elif p.startswith("/checklist_data"):
            self._serve_checklist_data()
        elif p.startswith("/checklist"):
            self._serve_checklist_page()
        elif p.startswith("/services_data"):
            self._serve_services_data()
        elif p.startswith("/services"):
            self._serve_services_page()
        elif p.startswith("/search_data"):
            self._serve_global_search_data()
        elif p.startswith("/search"):
            self._serve_global_search_page()
        elif p.startswith("/forecast_data"):
            self._serve_forecast_data()
        elif p.startswith("/forecast"):
            self._serve_forecast_page()
        elif p.startswith("/anomalies_data"):
            self._serve_anomalies_data()
        elif p.startswith("/anomalies"):
            self._serve_anomalies_page()
        elif p.startswith("/timeline_data"):
            self._serve_timeline_data()
        elif p.startswith("/timeline"):
            self._serve_timeline_page()
        elif p.startswith("/dyno_data"):
            self._serve_dyno_data()
        elif p.startswith("/dyno"):
            self._serve_dyno_page()
        elif p.startswith("/replay_data"):
            self._serve_replay_data()
        elif p.startswith("/replay"):
            self._serve_replay_page()
        elif p.startswith("/assistant/ask"):
            self._serve_assistant_ask()
        elif p.startswith("/assistant"):
            self._serve_assistant_page()
        elif p.startswith("/trip_data"):
            self._serve_trip_data()
        elif p.startswith("/trip"):
            self._serve_trip_page()
        elif p.startswith("/crossref_data"):
            self._serve_crossref_data()
        elif p.startswith("/crossref"):
            self._serve_crossref_page()
        elif p.startswith("/digest"):
            self._serve_digest_page()
        elif p.startswith("/elm-reference"):
            self._serve_elm_ref_page()
        elif p.startswith("/elm_coverage_data"):
            self._serve_elm_coverage_data()
        elif p.startswith("/ipt_data"):
            self._serve_ipt_data()
        elif p.startswith("/ipt"):
            self._serve_ipt_page()
        elif p.startswith("/mode19_data"):
            self._serve_mode19_data()
        elif p.startswith("/mode19"):
            self._serve_mode19_page()
        elif p.startswith("/palette_search"):
            self._serve_palette_search()
        elif p.startswith("/export"):
            self._serve_export()
        elif p.startswith("/import_csv_data"):
            self._serve_import_list()
        elif p.startswith("/import"):
            self._serve_import_page()
        elif p.startswith("/vehicles"):
            self._serve_vehicles_page()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/session_note"):
            self._handle_session_note_post()
        elif self.path.startswith("/odometer"):
            self._handle_odometer_post()
        elif self.path.startswith("/alerts/save"):
            self._handle_alerts_save()
        elif self.path.startswith("/services/add"):
            self._handle_service_add()
        elif self.path.startswith("/import_csv"):
            self._handle_import_csv()
        else:
            self.send_error(404)

    def _serve_html(self):
        page = HTML_PAGE
        page = page.replace("__VIN__", html.escape(VIN))
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__ENGINE__", html.escape(ENGINE))
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_snapshot(self):
        history = [row_to_display(r) for r in self.tailer.history(400)]
        payload = {
            "history": history,
            "events": self.tailer.recent_events(),
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_compare_page(self):
        """Serves the /compare HTML page. Expects ?a=<csv>&b=<csv> in query."""
        import urllib.parse as up
        qs = up.urlparse(self.path).query
        params = up.parse_qs(qs)
        a = params.get("a", [""])[0]
        b = params.get("b", [""])[0]
        page = COMPARE_HTML
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__PATH_A__", html.escape(a))
        page = page.replace("__PATH_B__", html.escape(b))
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_compare_data(self):
        """JSON endpoint: ?a=<csv>&b=<csv> returns both series decoded."""
        import urllib.parse as up
        qs = up.urlparse(self.path).query
        params = up.parse_qs(qs)
        a = params.get("a", [""])[0]
        b = params.get("b", [""])[0]

        def _load(p):
            if not p or not os.path.exists(p):
                return {"path": p, "error": "file not found", "rows": []}
            try:
                import csv as _csv
                with open(p) as f:
                    raw = list(_csv.DictReader(f))
                rows = [row_to_display(r) for r in raw]
                # Summary stats
                def _stats(k):
                    vals = [r[k] for r in rows if r.get(k) is not None and r.get("rpm", 0) > 300]
                    if not vals:
                        return None
                    return {"mean": sum(vals) / len(vals),
                            "min": min(vals), "max": max(vals), "n": len(vals)}
                summary = {
                    "ltft": _stats("ltft"), "stft": _stats("stft"),
                    "maf_ratio": _stats("maf_ratio"),
                }
                return {"path": p, "rows": rows, "summary": summary,
                        "n": len(rows)}
            except Exception as e:
                return {"path": p, "error": str(e), "rows": []}

        payload = {"a": _load(a), "b": _load(b)}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── /history ──────────────────────────────────────────────────
    def _serve_history_page(self):
        body = """
<main>
  <h1>History</h1>
  <div class="row">
    <div class="card"><div class="label">Total sessions</div><div class="value" id="s-total">—</div></div>
    <div class="card"><div class="label">Total samples</div><div class="value" id="s-samples">—</div></div>
    <div class="card"><div class="label">Distinct DTCs (all time)</div><div class="value" id="s-dtcs">—</div></div>
  </div>

  <h2>LTFT trend (30 days)</h2>
  <div class="card"><div class="chart-wrap"><canvas id="c-ltft"></canvas></div></div>

  <h2>MAF ratio trend (30 days)</h2>
  <div class="card"><div class="chart-wrap"><canvas id="c-maf"></canvas></div></div>

  <h2>Sessions</h2>
  <div class="card">
    <table id="t-sessions">
      <thead><tr><th>#</th><th>started</th><th>source</th><th>samples</th>
             <th>LTFT avg</th><th>LTFT peak</th><th>MAF ratio</th><th>note</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <h2>DTC occurrences (all time)</h2>
  <div class="card"><table id="t-dtcs">
    <thead><tr><th>code</th><th>bucket</th><th>seen</th><th>first</th><th>last</th></tr></thead>
    <tbody></tbody></table></div>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const C_BLUE='#58a6ff', C_GREEN='#3fb950', C_RED='#f85149', C_YEL='#d29922', C_GRID='#30363d', C_FG='#c9d1d9';
function mkChart(id, type, datasets, thresholds) {
  const ctx=document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type, data:{labels:[], datasets},
    options:{
      responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{legend:{labels:{color:C_FG,font:{size:11}}}},
      scales:{x:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:C_GRID}},
              y:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:C_GRID}}},
      elements:{point:{radius:2}},
    }
  });
}
const cLtft = mkChart('c-ltft','bar',
  [{label:'LTFT avg %', data:[], backgroundColor:C_BLUE, borderColor:C_BLUE},
   {label:'LTFT peak %', data:[], type:'line', borderColor:C_RED, tension:0.3}]);
const cMaf = mkChart('c-maf','bar',
  [{label:'MAF ratio avg ×', data:[], backgroundColor:C_GREEN, borderColor:C_GREEN}]);

function pill(text, cls) { return `<span class="pill ${cls}">${text}</span>`; }

fetch('/history_data').then(r=>r.json()).then(d=>{
  document.getElementById('s-total').textContent = d.sessions.length;
  document.getElementById('s-samples').textContent = d.total_samples;
  document.getElementById('s-dtcs').textContent = d.dtc_rows.length;

  const lt = d.ltft_history.slice().reverse();
  cLtft.data.labels = lt.map(r=>r.started_ts.split('T')[0]);
  cLtft.data.datasets[0].data = lt.map(r=>r.ltft_avg);
  cLtft.data.datasets[1].data = lt.map(r=>r.ltft_max);
  cLtft.update();

  const mr = d.maf_trend.slice().reverse();
  cMaf.data.labels = mr.map(r=>r.started_ts.split('T')[0]);
  cMaf.data.datasets[0].data = mr.map(r=>r.ratio_mean);
  cMaf.update();

  const tbody = document.querySelector('#t-sessions tbody');
  tbody.innerHTML = d.sessions.map(s => {
    const ratio = s.maf_ratio==null ? '—' : s.maf_ratio.toFixed(2)+'×';
    const ratioCls = s.maf_ratio>=0.85 ? 'ok' : (s.maf_ratio>=0.7 ? 'warn' : 'err');
    return `<tr>
      <td><a href="/session?id=${s.id}">#${s.id}</a></td>
      <td>${s.started_ts}</td>
      <td>${s.source||''}</td>
      <td>${s.n||0}</td>
      <td>${s.ltft_avg==null?'—':s.ltft_avg.toFixed(2)+'%'}</td>
      <td>${s.ltft_max==null?'—':s.ltft_max.toFixed(2)+'%'}</td>
      <td>${s.maf_ratio==null?'—':pill(ratio, ratioCls)}</td>
      <td style="color:#8b949e;">${s.note||''}</td></tr>`;
  }).join('') || '<tr><td colspan="8">no sessions yet — run yaris-diag dash to begin</td></tr>';

  const dtbody = document.querySelector('#t-dtcs tbody');
  dtbody.innerHTML = d.dtc_rows.map(r =>
    `<tr><td><a href="/dtc?code=${r.code}">${r.code}</a></td>
     <td>${r.bucket}</td><td>${r.occurrences}</td>
     <td>${r.first_ts.slice(0,10)}</td><td>${r.last_ts.slice(0,10)}</td></tr>`
  ).join('') || '<tr><td colspan="5">no DTCs recorded yet</td></tr>';
});
</script>"""
        page = render_page(body, title="History")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_history_data(self):
        from .store import Store, DEFAULT_DB
        payload = {"sessions": [], "ltft_history": [], "maf_trend": [],
                   "dtc_rows": [], "total_samples": 0}
        try:
            with Store(DEFAULT_DB) as s:
                all_sessions = s.sessions(vin=VIN, days=365)
                ltft = s.ltft_history(vin=VIN, days=30)
                maf = s.maf_ratio_trend(vin=VIN, days=30)
                dtcs = s.dtc_occurrences(vin=VIN, days=365)
                ltft_map = {r["id"]: r for r in ltft}
                maf_map = {r["session_id"]: r for r in maf}
                total_samples = 0
                sessions_list = []
                for sess in all_sessions:
                    lt = ltft_map.get(sess["id"])
                    mf = maf_map.get(sess["id"])
                    n = lt["n"] if lt else 0
                    total_samples += n
                    sessions_list.append({
                        "id": sess["id"], "started_ts": sess["started_ts"],
                        "source": sess["source"], "note": sess["note"],
                        "n": n,
                        "ltft_avg": lt["ltft_avg"] if lt else None,
                        "ltft_max": lt["ltft_max"] if lt else None,
                        "maf_ratio": mf["ratio_mean"] if mf else None,
                    })
                payload["sessions"] = sessions_list
                payload["ltft_history"] = [dict(r) for r in ltft]
                payload["maf_trend"] = maf
                payload["dtc_rows"] = dtcs
                payload["total_samples"] = total_samples
        except Exception as e:
            payload["error"] = str(e)
        self._send_json(payload)

    # ── /session?id=N ─────────────────────────────────────────────
    def _serve_session_page(self):
        import urllib.parse as up
        sid = up.parse_qs(up.urlparse(self.path).query).get("id", [""])[0]
        body = f"""
<main>
  <h1>Session #{html.escape(sid)}</h1>
  <div id="detail">loading…</div>
</main>
<script>
const sid = {sid or 'null'};
fetch('/session_data?id='+sid).then(r=>r.json()).then(d=>{{
  const el = document.getElementById('detail');
  if (d.error) {{ el.innerHTML = `<div class="card val-err">${{d.error}}</div>`; return; }}
  const s = d.session, st = d.stats;
  el.innerHTML = `
    <div class="row">
      <div class="card"><div class="label">VIN</div><div class="value" style="font-size:14px;">${{s.vin}}</div></div>
      <div class="card"><div class="label">Started</div><div class="value" style="font-size:14px;">${{s.started_ts}}</div></div>
      <div class="card"><div class="label">Ended</div><div class="value" style="font-size:14px;">${{s.ended_ts||'(open)'}}</div></div>
      <div class="card"><div class="label">Source</div><div class="value" style="font-size:14px;">${{s.source}}</div></div>
    </div>
    <h2>Note</h2>
    <div class="card">
      <textarea id="note-text" style="width:100%;min-height:60px;background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:4px;padding:8px;font-family:inherit;font-size:13px;">${{s.note||''}}</textarea>
      <div style="display:flex;gap:8px;margin-top:6px;align-items:center;">
        <button onclick="saveNote()" style="background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">Save note</button>
        <span id="save-status" style="color:#8b949e;font-size:12px;"></span>
      </div>
    </div>
    <div class="row">
      <div class="card"><div class="label">Samples</div><div class="value">${{st.n||0}}</div></div>
      <div class="card"><div class="label">RPM range</div><div class="value" style="font-size:15px;">${{(st.rpm_min||0).toFixed(0)}} – ${{(st.rpm_max||0).toFixed(0)}}</div></div>
      <div class="card"><div class="label">LTFT avg / max</div><div class="value" style="font-size:15px;">${{(st.ltft_avg||0).toFixed(1)}}% / ${{(st.ltft_max||0).toFixed(1)}}%</div></div>
      <div class="card"><div class="label">Coolant range</div><div class="value" style="font-size:15px;">${{(st.cool_min||0).toFixed(0)}} – ${{(st.cool_max||0).toFixed(0)}}°C</div></div>
      <div class="card"><div class="label">MIL ever</div><div class="value" style="font-size:15px;color:${{st.mil_ever?'#f85149':'#3fb950'}};">${{st.mil_ever?'YES':'no'}}</div></div>
      <div class="card"><div class="label">Max DTCs</div><div class="value">${{st.dtc_max||0}}</div></div>
    </div>
    <h2>DTCs seen</h2>
    <div class="card"><table>
      <thead><tr><th>code</th><th>bucket</th></tr></thead>
      <tbody>${{d.dtcs.map(x=>`<tr><td><a href="/dtc?code=${{x.code}}">${{x.code}}</a></td><td>${{x.bucket}}</td></tr>`).join('')||'<tr><td colspan="2">none</td></tr>'}}</tbody>
    </table></div>
    <h2>Events</h2>
    <div class="card"><table>
      <thead><tr><th>ts</th><th>type</th><th>text</th></tr></thead>
      <tbody>${{d.events.map(e=>`<tr><td>${{e.ts}}</td><td><span class="pill ${{e.type==='critical'?'err':(e.type==='warn'?'warn':'ok')}}">${{e.type}}</span></td><td>${{e.text}}</td></tr>`).join('')||'<tr><td colspan="3">(none)</td></tr>'}}</tbody>
    </table></div>
  `;
}});
function saveNote() {{
  const note = document.getElementById('note-text').value;
  const form = new URLSearchParams();
  form.append('id', sid);
  form.append('note', note);
  fetch('/session_note', {{method:'POST', body: form,
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}}}})
    .then(r=>r.json()).then(d=>{{
      document.getElementById('save-status').textContent =
        d.ok ? '✓ saved' : '✗ error: ' + (d.error||'unknown');
    }}).catch(e => {{
      document.getElementById('save-status').textContent = '✗ ' + e;
    }});
}}
</script>"""
        page = render_page(body, title=f"Session #{sid}")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_session_data(self):
        import urllib.parse as up
        sid = up.parse_qs(up.urlparse(self.path).query).get("id", [""])[0]
        from .store import Store, DEFAULT_DB
        try:
            sid_int = int(sid)
        except (ValueError, TypeError):
            self._send_json({"error": "invalid id"})
            return
        try:
            with Store(DEFAULT_DB) as s:
                self._send_json(s.session_summary(sid_int))
        except Exception as e:
            self._send_json({"error": str(e)})

    # ── /dtc ──────────────────────────────────────────────────────
    def _serve_dtc_page(self):
        import urllib.parse as up
        code = up.parse_qs(up.urlparse(self.path).query).get("code", [""])[0].upper()
        body = f"""
<main>
  <h1>DTC knowledge base</h1>
  <input id="search" type="search" placeholder="filter codes or titles…"
         style="width:100%;margin-bottom:12px;" oninput="filterTable()" value="{html.escape(code)}">
  <div id="detail"></div>
  <div class="card"><table id="t-dtcs">
    <thead><tr><th>code</th><th>system</th><th>severity</th><th>title</th><th>diff.</th></tr></thead>
    <tbody></tbody>
  </table></div>
</main>
<script>
let ALL = [];
fetch('/dtc_data').then(r=>r.json()).then(d=>{{
  ALL = d.entries;
  render(ALL);
  const code = document.getElementById('search').value.trim().toUpperCase();
  if (code) showDetail(code);
}});
function render(entries) {{
  const tbody = document.querySelector('#t-dtcs tbody');
  tbody.innerHTML = entries.map(e => `
    <tr onclick="showDetail('${{e.code}}')" style="cursor:pointer;">
      <td><a href="/dtc?code=${{e.code}}">${{e.code}}</a></td>
      <td>${{e.system}}</td>
      <td><span class="pill sev-${{e.severity}}">${{e.severity}}</span></td>
      <td>${{e.title}}</td>
      <td>${{'★'.repeat(e.difficulty||1)}}</td>
    </tr>`).join('');
}}
function showDetail(code) {{
  const e = ALL.find(x=>x.code===code);
  const el = document.getElementById('detail');
  if (!e) {{ el.innerHTML = `<div class="card val-err">Code ${{code}} not in database.</div>`; return; }}
  el.innerHTML = `
    <div class="card" style="margin-bottom:12px;">
      <div><span class="pill sev-${{e.severity}}">${{e.severity}}</span>
        <b style="font-size:17px;">${{e.code}}: ${{e.title}}</b></div>
      <p style="color:#8b949e;">${{e.system}} system · difficulty ${{'★'.repeat(e.difficulty||1)}} · cost DIY $${{e.cost_diy_usd[0]}}-$${{e.cost_diy_usd[1]}} · shop $${{e.cost_shop_usd[0]}}-$${{e.cost_shop_usd[1]}}</p>
      ${{e.symptoms && e.symptoms.length ? '<h2>Symptoms</h2><ul>'+e.symptoms.map(s=>`<li>${{s}}</li>`).join('')+'</ul>' : ''}}
      ${{e.causes && e.causes.length ? '<h2>Likely causes (ranked)</h2><ol>'+e.causes.map(c=>`<li>${{c}}</li>`).join('')+'</ol>' : ''}}
      ${{e.diy_steps && e.diy_steps.length ? '<h2>DIY path</h2><ol>'+e.diy_steps.map(c=>`<li>${{c}}</li>`).join('')+'</ol>' : ''}}
      ${{e.parts && e.parts.length ? '<h2>Parts</h2><ul>'+e.parts.map(p=>`<li>${{p}}</li>`).join('')+'</ul>' : ''}}
      ${{e.notes ? `<p style="color:#d29922;"><b>Note:</b> ${{e.notes}}</p>` : ''}}
      ${{e.kb_links && e.kb_links.length ? '<h2>Also in YarisRepair/ KB</h2><ul>'+e.kb_links.map(l=>`<li>${{l}}</li>`).join('')+'</ul>' : ''}}
    </div>`;
}}
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  render(ALL.filter(e => e.code.toLowerCase().includes(q) || e.title.toLowerCase().includes(q) || (e.system||'').toLowerCase().includes(q)));
  // If the query is an exact code, show detail
  const m = ALL.find(e=>e.code.toLowerCase()===q);
  if (m) showDetail(m.code); else document.getElementById('detail').innerHTML = '';
}}
</script>"""
        page = render_page(body, title="DTCs")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_dtc_data(self):
        from .dtc_db import DTC_DATABASE
        entries = []
        for code, e in sorted(DTC_DATABASE.items()):
            entries.append({
                "code": e.code, "title": e.title, "severity": e.severity,
                "system": e.system, "symptoms": list(e.symptoms),
                "causes": list(e.causes), "diy_steps": list(e.diy_steps),
                "parts": list(e.parts),
                "cost_diy_usd": list(e.cost_diy_usd),
                "cost_shop_usd": list(e.cost_shop_usd),
                "difficulty": e.difficulty, "notes": e.notes,
                "kb_links": list(e.kb_links),
            })
        self._send_json({"entries": entries, "count": len(entries)})

    # ── /economy ──────────────────────────────────────────────────
    def _serve_economy_page(self):
        body = """
<main>
  <h1>Fuel economy (MAF-derived)</h1>
  <p style="color:#8b949e;">Computed from live MAF + trim-compensated AFR. Post-repair these numbers should drop toward healthy 1.3L territory (~7 L/100km / 34 mpg moving).</p>

  <div class="row" id="totals"></div>

  <h2>Per-session economy</h2>
  <div class="card"><div class="chart-wrap"><canvas id="c-econ"></canvas></div></div>
  <div class="card"><table id="t-econ">
    <thead><tr><th>#</th><th>started</th><th>distance</th><th>moving fuel</th>
           <th>L/100km total</th><th>L/100km moving</th><th>MPG moving</th><th>note</th></tr></thead>
    <tbody></tbody>
  </table></div>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const C_BLUE='#58a6ff', C_GREEN='#3fb950', C_FG='#c9d1d9', C_GRID='#30363d';
const chart = new Chart(document.getElementById('c-econ').getContext('2d'), {
  type:'bar', data:{labels:[], datasets:[
    {label:'moving L/100km', data:[], backgroundColor:C_BLUE},
    {label:'total L/100km',  data:[], backgroundColor:C_GREEN},
  ]},
  options:{responsive:true, maintainAspectRatio:false,
    plugins:{legend:{labels:{color:C_FG,font:{size:11}}}},
    scales:{x:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:C_GRID}},
            y:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:C_GRID}}}}
});

fetch('/economy_data').then(r=>r.json()).then(d=>{
  const tot = d.aggregate || {};
  const pct = (tot.idle_fraction||0)*100;
  document.getElementById('totals').innerHTML = `
    <div class="card"><div class="label">Total fuel burned (all sessions)</div>
      <div class="value">${(tot.total_fuel_L||0).toFixed(3)} L</div>
      <div class="sub">${(tot.idle_fuel_L||0).toFixed(3)} L idle · ${pct.toFixed(0)}%</div></div>
    <div class="card"><div class="label">Total distance</div>
      <div class="value">${(tot.total_distance_km||0).toFixed(2)} km</div></div>
    <div class="card"><div class="label">Moving avg</div>
      <div class="value">${(tot.running_L_per_100km||0).toFixed(2)} L/100km</div>
      <div class="sub">${(tot.running_mpg||0).toFixed(1)} mpg</div></div>
    <div class="card"><div class="label">Sessions with data</div>
      <div class="value">${d.sessions.length}</div></div>
  `;

  const labels = d.sessions.map(s => s.started_ts.slice(5, 16));
  chart.data.labels = labels;
  chart.data.datasets[0].data = d.sessions.map(s => s.running_L_per_100km || 0);
  chart.data.datasets[1].data = d.sessions.map(s => s.avg_L_per_100km || 0);
  chart.update();

  const tbody = document.querySelector('#t-econ tbody');
  tbody.innerHTML = d.sessions.map(s => {
    const fuel = s.running_fuel_L==null ? '—' : s.running_fuel_L.toFixed(3)+' L';
    return `<tr>
      <td><a href="/session?id=${s.id}">#${s.id}</a></td>
      <td>${s.started_ts}</td>
      <td>${(s.total_distance_km||0).toFixed(2)} km</td>
      <td>${fuel}</td>
      <td>${s.avg_L_per_100km==null?'—':s.avg_L_per_100km.toFixed(2)}</td>
      <td>${s.running_L_per_100km==null?'—':s.running_L_per_100km.toFixed(2)}</td>
      <td>${s.running_mpg==null?'—':s.running_mpg.toFixed(1)}</td>
      <td style="color:#8b949e;">${s.note||''}</td></tr>`;
  }).join('') || '<tr><td colspan="8">(no data yet)</td></tr>';
});
</script>"""
        page = render_page(body, title="Economy")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_economy_data(self):
        from .store import Store, DEFAULT_DB
        from .economy import integrate_economy
        payload = {"sessions": [], "aggregate": {}}
        try:
            with Store(DEFAULT_DB) as s:
                sessions = s.sessions(vin=VIN, days=365)
                tot_fuel_g = 0.0
                tot_dist_km = 0.0
                tot_run_fuel_g = 0.0
                tot_run_dist_km = 0.0
                tot_idle_fuel_g = 0.0
                for sess in sessions:
                    rows = [dict(r) for r in s.conn.execute(
                        "SELECT ts as timestamp, rpm, speed_kmh, maf_gs, "
                        "stft_pct as stft, ltft_pct as ltft "
                        "FROM samples WHERE session_id=?",
                        (sess["id"],),
                    )]
                    # Remap to the shape economy.integrate_economy expects
                    mapped = [{
                        "rpm": r["rpm"] or 0,
                        "speed": r["speed_kmh"] or 0,
                        "maf": r["maf_gs"] or 0,
                        "stft": r["stft"] or 0,
                        "ltft": r["ltft"] or 0,
                    } for r in rows]
                    stats = integrate_economy(mapped, sample_interval_s=1.3)
                    tot_fuel_g += stats.get("total_fuel_g", 0)
                    tot_dist_km += stats.get("total_distance_km", 0)
                    tot_run_fuel_g += (stats.get("running_fuel_L", 0) * 745)
                    tot_run_dist_km += stats.get("running_distance_km", 0)
                    tot_idle_fuel_g += (stats.get("idle_fuel_L", 0) * 745)
                    payload["sessions"].append({
                        "id": sess["id"], "started_ts": sess["started_ts"],
                        "source": sess["source"], "note": sess["note"],
                        **{k: stats.get(k) for k in [
                            "total_distance_km", "running_distance_km",
                            "total_fuel_L", "running_fuel_L",
                            "avg_L_per_100km", "avg_mpg",
                            "running_L_per_100km", "running_mpg",
                        ]}
                    })
                # Aggregate
                agg = {
                    "total_fuel_L": tot_fuel_g / 745.0,
                    "idle_fuel_L":  tot_idle_fuel_g / 745.0,
                    "total_distance_km": tot_dist_km,
                    "idle_fraction": tot_idle_fuel_g / tot_fuel_g if tot_fuel_g > 0 else 0,
                }
                if tot_run_dist_km > 0:
                    l100 = (tot_run_fuel_g / 745.0) / tot_run_dist_km * 100
                    agg["running_L_per_100km"] = l100
                    agg["running_mpg"] = 235.214 / l100 if l100 > 0 else None
                payload["aggregate"] = agg
        except Exception as e:
            payload["error"] = str(e)
        self._send_json(payload)

    # ── /plots ────────────────────────────────────────────────────
    def _serve_plots_page(self):
        import glob as _glob
        pngs = sorted(_glob.glob(os.path.join(REPORT_DIR, "*.png")),
                      key=os.path.getmtime, reverse=True)
        items = "".join(
            f'<div class="card"><div class="label">{html.escape(os.path.basename(p))}</div>'
            f'<img src="/reports/{html.escape(os.path.basename(p))}" '
            f'style="max-width:100%;border-radius:4px;margin-top:4px;"></div>'
            for p in pngs
        )
        if not items:
            items = '<div class="card">No PNG plots yet. Generate with <code>yaris-diag plot --csv ...</code></div>'
        body = f"""<main>
  <h1>Plot gallery</h1>
  <p style="color:#8b949e;">PNGs in <code>reports/</code>. Newest first.</p>
  <div class="row">{items}</div>
</main>"""
        page = render_page(body, title="Plots")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── /reports/<file> — serve PNGs, CSVs, reports ──────────────
    def _serve_report_file(self):
        import urllib.parse as up
        rel = up.unquote(self.path[len("/reports/"):])
        # Simple safety: no path traversal
        if ".." in rel or rel.startswith("/"):
            self.send_error(400); return
        full = os.path.normpath(os.path.join(REPORT_DIR, rel))
        if not full.startswith(REPORT_DIR) or not os.path.isfile(full):
            self.send_error(404); return
        mime = "application/octet-stream"
        if full.endswith(".png"): mime = "image/png"
        elif full.endswith(".csv"): mime = "text/csv"
        elif full.endswith(".txt") or full.endswith(".md"): mime = "text/plain; charset=utf-8"
        elif full.endswith(".json"): mime = "application/json"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── /knowledge — home, system, issue, procedure, specs, etc. ─
    def _serve_knowledge_home(self):
        from .knowledge import (ISSUES, PROCEDURES, SPECS, MAINTENANCE,
                                 TSBS, RECALLS, PARTS, BASELINES, issues_by_system)
        systems = issues_by_system()
        SYSTEM_ICONS = {
            "engine": "🔧", "fuel": "⛽", "cooling": "❄️", "electrical": "⚡",
            "brakes": "🛑", "suspension": "🏁", "drivetrain": "⚙️",
            "emissions": "💨", "body": "🚗", "hvac": "🌡️",
        }
        cards = ""
        for system in sorted(systems):
            issues_list = systems[system]
            icon = SYSTEM_ICONS.get(system, "📋")
            top3 = "".join(
                f'<li><a href="/knowledge/issue/{html.escape(i.slug)}">{html.escape(i.name)}</a> '
                f'<span style="color:#6e7681;font-size:11px;">#{i.rank}</span></li>'
                for i in issues_list[:3]
            )
            cards += f'''
<a href="/knowledge/system/{html.escape(system)}" style="text-decoration:none;">
<div class="card" style="height:100%;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:28px;">{icon}</span>
    <div>
      <div class="label">{html.escape(system)}</div>
      <div class="value" style="font-size:16px;">{len(issues_list)} issues</div>
    </div>
  </div>
  <ul style="margin:8px 0 0 0;padding-left:16px;font-size:12px;color:#c9d1d9;">{top3}</ul>
</div></a>'''

        body = f'''
<main>
  <h1>Knowledge Base — 2011 Yaris XP90 / 1NR-FE 1.3L</h1>
  <p style="color:#8b949e;">Curated from local repair KB + toyota-club.net NR FAQ + NHTSA + forum reports. All data is read-only.</p>

  <div class="row">
    <div class="card"><div class="label">Issues documented</div><div class="value">{len(ISSUES)}</div></div>
    <div class="card"><div class="label">Repair procedures</div><div class="value">{len(PROCEDURES)}</div></div>
    <div class="card"><div class="label">Specs (torque/fluid/spec)</div><div class="value">{len(SPECS)}</div></div>
    <div class="card"><div class="label">Maintenance intervals</div><div class="value">{len(MAINTENANCE)}</div></div>
    <div class="card"><div class="label">TSBs</div><div class="value">{len(TSBS)}</div></div>
    <div class="card"><div class="label">NHTSA recalls</div><div class="value">{len(RECALLS)}</div></div>
    <div class="card"><div class="label">Parts catalog</div><div class="value">{len(PARTS)}</div></div>
    <div class="card"><div class="label">Diagnostic baselines</div><div class="value">{len(BASELINES)}</div></div>
  </div>

  <h2>Search</h2>
  <input id="kb-search" type="search" placeholder="Try: MAF, P0101, coolant, brake, water pump…"
         style="width:100%;margin-bottom:12px;" oninput="doSearch()">
  <div id="search-results"></div>

  <h2>Browse by system</h2>
  <div class="row" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr));">
    {cards}
  </div>

  <h2>Quick links</h2>
  <div class="row">
    <a href="/knowledge/maintenance" class="card" style="text-decoration:none;"><div class="label">📅 Maintenance schedule</div><div class="value" style="font-size:14px;">Visual timeline, 5k → 200k km</div></a>
    <a href="/knowledge/specs" class="card" style="text-decoration:none;"><div class="label">📏 Specs reference</div><div class="value" style="font-size:14px;">Torque, fluid, capacity</div></a>
    <a href="/knowledge/tsbs" class="card" style="text-decoration:none;"><div class="label">📣 TSBs & Recalls</div><div class="value" style="font-size:14px;">Toyota bulletins + NHTSA</div></a>
    <a href="/knowledge/parts" class="card" style="text-decoration:none;"><div class="label">🔩 Parts catalog</div><div class="value" style="font-size:14px;">OEM + aftermarket numbers</div></a>
    <a href="/knowledge/baselines" class="card" style="text-decoration:none;"><div class="label">🎯 Healthy baselines</div><div class="value" style="font-size:14px;">Expected PID ranges</div></a>
  </div>
</main>

<script>
function doSearch() {{
  const q = document.getElementById('kb-search').value.trim();
  const el = document.getElementById('search-results');
  if (q.length < 2) {{ el.innerHTML = ''; return; }}
  fetch('/knowledge/search?q=' + encodeURIComponent(q))
    .then(r => r.json())
    .then(results => {{
      if (!results.length) {{ el.innerHTML = '<p style="color:#8b949e;">no matches</p>'; return; }}
      el.innerHTML = '<div class="card"><ul style="margin:0;padding-left:20px;">' +
        results.map(r => {{
          let link = '';
          if (r.type === 'issue') link = `/knowledge/issue/${{r.slug}}`;
          else if (r.type === 'procedure') link = `/knowledge/procedure/${{r.slug}}`;
          else if (r.type === 'spec') link = '/knowledge/specs';
          else if (r.type === 'part') link = '/knowledge/parts';
          return `<li><span class="pill sev-${{r.type==='issue'?'warn':'minor'}}">${{r.type}}</span>
                  <a href="${{link}}">${{r.name || r.item}}</a>
                  <span style="color:#6e7681;">(${{r.system||''}})</span></li>`;
        }}).join('') + '</ul></div>';
    }});
}}
</script>'''
        page = render_page(body, title="Knowledge Base")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_system(self):
        import urllib.parse as up
        system = up.unquote(self.path.rsplit("/", 1)[-1])
        from .knowledge import issues_by_system, procedures_by_system, specs_by_system, PARTS
        issues = issues_by_system().get(system, [])
        procs = procedures_by_system().get(system, [])
        specs = specs_by_system().get(system, [])
        parts = [(slug, p) for slug, p in PARTS.items() if p.system == system]

        def issue_card(i):
            return f'''<a href="/knowledge/issue/{html.escape(i.slug)}" class="card" style="text-decoration:none;display:block;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:600;">#{i.rank} · {html.escape(i.name)}</span>
                <span class="pill sev-{'critical' if i.difficulty>=4 else ('warn' if i.difficulty>=3 else 'minor')}">diff {'★'*i.difficulty}</span>
              </div>
              <div style="color:#8b949e;font-size:12px;margin-top:4px;">{html.escape(i.frequency)}</div>
              <div style="font-size:12px;margin-top:4px;">DIY ${i.cost_diy_usd[0]}-${i.cost_diy_usd[1]} · Shop ${i.cost_shop_usd[0]}-${i.cost_shop_usd[1]}</div>
            </a>'''

        issues_html = "".join(issue_card(i) for i in issues) or "<p>(no issues documented)</p>"
        procs_html = "".join(
            f'<a href="/knowledge/procedure/{html.escape(p.slug)}" class="card" style="text-decoration:none;display:block;">'
            f'<div style="font-weight:600;">{html.escape(p.name)}</div>'
            f'<div style="color:#8b949e;font-size:12px;margin-top:4px;">diff {"★"*p.difficulty} · ~{p.time_minutes} min</div>'
            f'</a>' for p in procs) or "<p>(no procedures)</p>"
        specs_html = ("<div class='card'><table><thead><tr><th>item</th><th>value</th><th>unit</th><th>note</th></tr></thead><tbody>" +
            "".join(f"<tr><td>{html.escape(s.item)}</td><td>{html.escape(str(s.value))}</td><td>{html.escape(s.unit)}</td><td style='color:#8b949e;'>{html.escape(s.notes)}</td></tr>" for s in specs) +
            "</tbody></table></div>") if specs else "<p>(no specs)</p>"
        parts_html = "".join(
            f'<div class="card"><div style="font-weight:600;">{html.escape(p.name)}</div>'
            f'<div style="color:#8b949e;font-size:12px;margin-top:4px;">OEM: {html.escape(p.oem or "—")}</div>'
            f'<div style="font-size:12px;">${p.price_usd[0]}-${p.price_usd[1]}</div></div>'
            for _, p in parts) or ""

        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>{html.escape(system).capitalize()} system</h1>
          <h2>Issues ({len(issues)})</h2>
          <div class="row">{issues_html}</div>
          <h2>Procedures ({len(procs)})</h2>
          <div class="row">{procs_html}</div>
          <h2>Specifications ({len(specs)})</h2>
          {specs_html}
          {'<h2>Parts ('+str(len(parts))+')</h2><div class="row">'+parts_html+'</div>' if parts_html else ''}
        </main>'''
        page = render_page(body, title=f"System: {system}")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_issue(self):
        import urllib.parse as up
        slug = up.unquote(self.path.rsplit("/", 1)[-1])
        from .knowledge import ISSUES, PROCEDURES, PARTS
        i = ISSUES.get(slug)
        if not i:
            self.send_error(404); return

        def bullets(items):
            return "".join(f"<li>{html.escape(x)}</li>" for x in items)
        diff_stars = "★" * i.difficulty + "☆" * (5 - i.difficulty)
        rel_procs = "".join(
            f'<a href="/knowledge/procedure/{html.escape(ps)}" class="pill ok" '
            f'style="margin-right:4px;text-decoration:none;">{html.escape(PROCEDURES[ps].name)}</a>'
            for ps in i.related_procedures if ps in PROCEDURES)
        rel_parts = "".join(
            f'<span class="pill minor" style="margin-right:4px;">{html.escape(PARTS[p].name)}</span>'
            for p in i.related_parts if p in PARTS)
        rel_dtcs = "".join(
            f'<a href="/dtc?code={html.escape(c)}" class="pill warn" style="margin-right:4px;text-decoration:none;">{html.escape(c)}</a>'
            for c in i.related_dtcs)
        kb_links = "".join(f'<li>{html.escape(l)}</li>' for l in i.kb_links)
        tsb_refs = "".join(f'<li>{html.escape(t)}</li>' for t in i.tsb_refs)

        body = f'''<main>
          <p><a href="/knowledge/system/{html.escape(i.system)}">← {html.escape(i.system)}</a>
             · <a href="/knowledge">Knowledge home</a></p>
          <h1>#{i.rank} · {html.escape(i.name)}</h1>

          <div class="row">
            <div class="card"><div class="label">Frequency</div><div class="value" style="font-size:14px;">{html.escape(i.frequency)}</div></div>
            <div class="card"><div class="label">Typical mileage</div><div class="value" style="font-size:14px;">{html.escape(i.typical_mileage)}</div></div>
            <div class="card"><div class="label">Difficulty</div><div class="value" style="font-size:14px;">{diff_stars}</div></div>
            <div class="card"><div class="label">DIY cost</div><div class="value" style="font-size:14px;">${i.cost_diy_usd[0]} – ${i.cost_diy_usd[1]}</div></div>
            <div class="card"><div class="label">Shop cost</div><div class="value" style="font-size:14px;">${i.cost_shop_usd[0]} – ${i.cost_shop_usd[1]}</div></div>
          </div>

          {f'<h2>Related DTCs</h2><div>{rel_dtcs}</div>' if rel_dtcs else ''}

          <h2>Symptoms</h2>
          <div class="card"><ul>{bullets(i.symptoms)}</ul></div>

          <h2>Ranked causes (most likely first)</h2>
          <div class="card"><ol>{bullets(i.causes)}</ol></div>

          {'<h2>Diagnostic steps</h2><div class="card"><ol>'+bullets(i.diagnostics)+'</ol></div>' if i.diagnostics else ''}

          {f'<h2>Related repair procedures</h2><div>{rel_procs}</div>' if rel_procs else ''}
          {f'<h2>Likely parts needed</h2><div>{rel_parts}</div>' if rel_parts else ''}

          {'<h2>TSB references</h2><div class="card"><ul>'+tsb_refs+'</ul></div>' if tsb_refs else ''}
          {'<h2>Also in YarisRepair/ KB</h2><div class="card"><ul>'+kb_links+'</ul></div>' if kb_links else ''}

          {'<h2>Notes</h2><div class="card" style="color:#d29922;">'+html.escape(i.notes)+'</div>' if i.notes else ''}
        </main>'''
        crumbs = [("Home", "/"), ("Knowledge", "/knowledge"),
                  (i.system.capitalize(), f"/knowledge/system/{i.system}"),
                  (i.name, "")]
        page = render_page(body, title=i.name, breadcrumbs=crumbs)
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_procedure(self):
        import urllib.parse as up
        slug = up.unquote(self.path.rsplit("/", 1)[-1])
        from .knowledge import PROCEDURES
        p = PROCEDURES.get(slug)
        if not p:
            self.send_error(404); return
        diff_stars = "★" * p.difficulty + "☆" * (5 - p.difficulty)
        tools_html = "".join(f"<li>{html.escape(t)}</li>" for t in p.tools)
        parts_html = "".join(f"<li><b>{html.escape(k)}</b>: {html.escape(v)}</li>"
                             for k, v in p.parts.items())
        steps_html = "".join(f"<li>{html.escape(s)}</li>" for s in p.steps)
        torque_html = "".join(f"<li>{html.escape(t)}</li>" for t in p.torque_specs)
        specs_html = "".join(f"<li><b>{html.escape(k)}</b>: {html.escape(str(v))}</li>"
                              for k, v in p.specs.items())

        body = f'''<main>
          <p><a href="/knowledge/system/{html.escape(p.system)}">← {html.escape(p.system)}</a>
             · <a href="/knowledge">Knowledge home</a></p>
          <h1>{html.escape(p.name)}</h1>
          <div class="row">
            <div class="card"><div class="label">Difficulty</div><div class="value" style="font-size:14px;">{diff_stars}</div></div>
            <div class="card"><div class="label">Estimated time</div><div class="value" style="font-size:14px;">~{p.time_minutes} min</div></div>
            <div class="card"><div class="label">System</div><div class="value" style="font-size:14px;">{html.escape(p.system)}</div></div>
          </div>
          {f'<h2>⚠ Safety</h2><div class="card" style="color:#f85149;">{html.escape(p.safety)}</div>' if p.safety else ''}
          <h2>Tools needed</h2>
          <div class="card"><ul>{tools_html}</ul></div>
          {'<h2>Parts</h2><div class="card"><ul>'+parts_html+'</ul></div>' if parts_html else ''}
          {'<h2>Torque specs</h2><div class="card"><ul>'+torque_html+'</ul></div>' if torque_html else ''}
          {'<h2>Specs</h2><div class="card"><ul>'+specs_html+'</ul></div>' if specs_html else ''}
          <h2>Steps</h2>
          <div class="card"><ol>{steps_html}</ol></div>
        </main>'''
        crumbs = [("Home", "/"), ("Knowledge", "/knowledge"),
                  (p.system.capitalize(), f"/knowledge/system/{p.system}"),
                  ("Procedures", ""), (p.name, "")]
        page = render_page(body, title=p.name, breadcrumbs=crumbs)
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_specs(self):
        from .knowledge import specs_by_system
        sys_specs = specs_by_system()
        sections = ""
        for system in sorted(sys_specs):
            rows = "".join(
                f'<tr><td>{html.escape(s.item)}</td>'
                f'<td style="font-variant-numeric:tabular-nums;">{html.escape(str(s.value))}</td>'
                f'<td>{html.escape(s.unit)}</td>'
                f'<td style="color:#8b949e;">{html.escape(s.notes)}</td></tr>'
                for s in sys_specs[system]
            )
            sections += f'''
              <h2>{html.escape(system).capitalize()}</h2>
              <div class="card"><table>
                <thead><tr><th>item</th><th>value</th><th>unit</th><th>notes</th></tr></thead>
                <tbody>{rows}</tbody>
              </table></div>'''
        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>Specifications</h1>
          <input id="search" type="search" placeholder="filter by item, unit, system…"
                 oninput="filterSpecs()" style="width:100%;margin-bottom:12px;">
          <div id="specs">{sections}</div>
        </main>
        <script>
        function filterSpecs() {{
          const q = document.getElementById('search').value.toLowerCase();
          document.querySelectorAll('#specs tr').forEach(r => {{
            r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
          }});
        }}
        </script>'''
        page = render_page(body, title="Specs")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_maintenance(self):
        from .knowledge import MAINTENANCE
        items_html = ""
        for mi in MAINTENANCE:
            items_list = "".join(f"<li>{html.escape(x)}</li>" for x in mi.items)
            cost = f"${mi.cost_usd_low}–${mi.cost_usd_high}" if mi.cost_usd_high else "—"
            items_html += f'''
              <div class="card" style="margin-bottom:12px;display:grid;grid-template-columns:120px 1fr auto;gap:16px;align-items:start;">
                <div style="text-align:right;">
                  <div style="font-size:22px;font-weight:600;color:#58a6ff;">{mi.km:,} km</div>
                  <div style="color:#8b949e;font-size:11px;">{mi.months} months</div>
                </div>
                <div>
                  <ul style="margin:0;padding-left:18px;">{items_list}</ul>
                </div>
                <div style="color:#3fb950;font-weight:500;white-space:nowrap;">{cost}</div>
              </div>'''
        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>Maintenance schedule</h1>
          <p style="color:#8b949e;">Toyota OEM service intervals for XP90 2006-2012. DIY costs in USD.</p>
          {items_html}
        </main>'''
        page = render_page(body, title="Maintenance")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_tsbs(self):
        from .knowledge import TSBS, RECALLS
        tsbs_html = "".join(
            f'''<div class="card" style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <b style="color:#58a6ff;">{html.escape(t.number)}</b>
                <span class="pill {'ok' if t.applies_to_2011 else 'minor'}">
                  {'applies to 2011' if t.applies_to_2011 else 'check VIN'}</span>
              </div>
              <div style="font-weight:500;margin-top:4px;">{html.escape(t.area)}</div>
              <p style="color:#c9d1d9;margin:6px 0;">{html.escape(t.summary)}</p>
              {f'<p style="color:#d29922;font-size:12px;"><b>Fix:</b> {html.escape(t.fix)}</p>' if t.fix else ''}
              {f'<p style="color:#6e7681;font-size:11px;">source: {html.escape(t.source)}</p>' if t.source else ''}
            </div>'''
            for t in TSBS
        )
        recalls_html = "".join(
            f'''<div class="card" style="margin-bottom:10px;border-left:3px solid #f85149;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <b style="color:#f85149;">{html.escape(r.campaign)}</b>
                <span style="color:#8b949e;font-size:12px;">{html.escape(r.date)}</span>
              </div>
              <div style="font-weight:500;margin-top:4px;">{html.escape(r.component)}</div>
              <p style="color:#c9d1d9;margin:6px 0;">{html.escape(r.description)}</p>
              <p style="color:#3fb950;margin:6px 0;"><b>Remedy:</b> {html.escape(r.remedy)}</p>
              <p style="color:#6e7681;font-size:12px;">Applies to your VIN: <b>{html.escape(r.applies_to_vin)}</b></p>
            </div>'''
            for r in RECALLS
        )
        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>TSBs &amp; Recalls</h1>
          <h2>Toyota Technical Service Bulletins ({len(TSBS)})</h2>
          {tsbs_html}
          <h2>NHTSA Recalls ({len(RECALLS)})</h2>
          <p style="color:#8b949e;">Car is JDM-export build (VIN JTDBT9K...) — US recall IDs don't VIN-match but the hardware is identical.</p>
          {recalls_html}
        </main>'''
        page = render_page(body, title="TSBs & Recalls")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_parts(self):
        from .knowledge import PARTS
        by_system = {}
        for slug, p in PARTS.items():
            by_system.setdefault(p.system, []).append((slug, p))
        sections = ""
        for system in sorted(by_system):
            parts_html = ""
            for slug, p in by_system[system]:
                aft = "".join(f'<li><b>{html.escape(mfr)}</b>: {html.escape(num)}</li>'
                              for mfr, num in p.aftermarket.items())
                parts_html += f'''
                  <div class="card" style="margin-bottom:8px;">
                    <div style="font-weight:600;font-size:15px;">{html.escape(p.name)}</div>
                    <div style="margin-top:4px;">
                      <b>OEM:</b> <code>{html.escape(p.oem or "—")}</code>
                      · <span style="color:#3fb950;">${p.price_usd[0]} – ${p.price_usd[1]}</span>
                    </div>
                    {f'<ul style="margin:4px 0 0 16px;font-size:12px;">{aft}</ul>' if aft else ''}
                    {f'<p style="color:#8b949e;font-size:12px;margin-top:6px;">{html.escape(p.notes)}</p>' if p.notes else ''}
                  </div>'''
            sections += f'<h2>{html.escape(system).capitalize()}</h2>{parts_html}'
        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>Parts catalog</h1>
          {sections}
        </main>'''
        page = render_page(body, title="Parts")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_baselines(self):
        from .knowledge import BASELINES
        rows = "".join(
            f'''<tr>
              <td><code>{html.escape(b.pid)}</code></td>
              <td>{html.escape(b.name)}</td>
              <td style="color:#3fb950;">{html.escape(b.healthy_range)}</td>
              <td style="color:#d29922;">{html.escape(b.warning_range)}</td>
              <td style="color:#8b949e;">{html.escape(b.notes)}</td>
            </tr>'''
            for b in BASELINES
        )
        body = f'''<main>
          <p><a href="/knowledge">← Back to knowledge home</a></p>
          <h1>Healthy diagnostic baselines</h1>
          <p style="color:#8b949e;">Known-good PID ranges for a warm 1NR-FE at idle, accessories off. The /live dashboard checks against these.</p>
          <div class="card"><table>
            <thead><tr><th>PID</th><th>parameter</th><th>healthy</th><th>warning</th><th>notes</th></tr></thead>
            <tbody>{rows}</tbody>
          </table></div>
        </main>'''
        page = render_page(body, title="Baselines")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_knowledge_search(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0]
        from .knowledge import search
        self._send_json(search(q))

    # ── /diagnose — symptom-first tree ────────────────────────────
    def _serve_diagnose_page(self):
        from .symptoms import symptoms_by_category
        cats = symptoms_by_category()
        CAT_ICONS = {
            "driveability": "🏎️", "start": "🔑", "warning_lights": "⚠️",
            "sound": "🔊", "fluid": "💧", "performance": "⚡",
        }
        sections = ""
        for cat in ["start", "warning_lights", "driveability", "sound", "fluid", "performance"]:
            if cat not in cats:
                continue
            icon = CAT_ICONS.get(cat, "•")
            checks = "".join(
                f'''<label style="display:flex;align-items:center;gap:8px;padding:6px 10px;
                              background:#161b22;border:1px solid #30363d;border-radius:6px;
                              margin-bottom:6px;cursor:pointer;">
                      <input type="checkbox" name="sym" value="{html.escape(s.slug)}"
                             onchange="rank()" style="transform:scale(1.2);">
                      <div>
                        <div style="font-size:13px;color:#c9d1d9;">{html.escape(s.label)}</div>
                        <div style="font-size:11px;color:#8b949e;">{html.escape(s.description)}</div>
                      </div>
                    </label>'''
                for s in cats[cat])
            title = cat.replace("_", " ").title()
            sections += f'''
            <div class="card" style="margin-bottom:12px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#c9d1d9;">
                <span style="font-size:18px;">{icon}</span> {html.escape(title)}
              </h3>
              {checks}
            </div>'''

        body = f'''<main>
          <h1>Diagnose by symptom</h1>
          <p style="color:#8b949e;">Check every symptom you notice. The ranker weighs them against the 20-issue KB and surfaces the most likely culprits. <b>Doesn't need a DTC.</b></p>

          <div class="row" style="grid-template-columns:1fr 1fr;">
            <div>
              <h2>Symptoms</h2>
              {sections}
              <button onclick="clearAll()" style="background:#30363d;color:#c9d1d9;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;">clear</button>
            </div>
            <div>
              <h2>Ranked likely issues</h2>
              <div id="results"><p style="color:#8b949e;">Pick one or more symptoms to see ranked diagnoses.</p></div>
            </div>
          </div>
        </main>
        <script>
        function rank() {{
          const syms = Array.from(document.querySelectorAll('input[name=sym]:checked'))
                         .map(el => el.value);
          if (!syms.length) {{
            document.getElementById('results').innerHTML =
              '<p style="color:#8b949e;">Pick one or more symptoms.</p>';
            return;
          }}
          fetch('/diagnose/rank?' + syms.map(s => 'sym=' + encodeURIComponent(s)).join('&'))
            .then(r => r.json()).then(data => {{
              if (!data.length) {{
                document.getElementById('results').innerHTML =
                  '<div class="card"><p>No matching issues in the knowledge base. Try different symptoms or check the DTC page directly.</p></div>';
                return;
              }}
              document.getElementById('results').innerHTML = data.map((d, idx) => {{
                const diffStars = '★'.repeat(d.difficulty) + '☆'.repeat(5 - d.difficulty);
                const pct = d.coverage_pct;
                const matches = d.matching_symptoms.join(', ');
                const rank = idx + 1;
                return `<div class="card" style="margin-bottom:8px;border-left:3px solid ${{idx===0?'#3fb950':(idx<3?'#d29922':'#30363d')}};">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <span style="font-size:18px;color:#3fb950;">#${{rank}}</span>
                      <a href="/knowledge/issue/${{d.issue_slug}}" style="font-weight:600;font-size:15px;">${{d.issue_name}}</a>
                      <span class="pill minor">${{d.issue_system}}</span>
                    </div>
                    <div style="text-align:right;">
                      <div style="font-size:18px;color:#58a6ff;">${{d.score.toFixed(2)}}</div>
                      <div style="color:#8b949e;font-size:11px;">score</div>
                    </div>
                  </div>
                  <div style="display:flex;gap:12px;margin-top:6px;font-size:12px;color:#8b949e;">
                    <span>difficulty ${{diffStars}}</span>
                    <span>DIY $${{d.cost_diy_usd[0]}}–$${{d.cost_diy_usd[1]}}</span>
                    <span>matches ${{pct}}% of symptoms</span>
                  </div>
                  <div style="margin-top:6px;font-size:12px;color:#8b949e;">
                    matching: ${{matches}}
                  </div>
                  <div style="margin-top:6px;font-size:12px;">
                    <a href="/knowledge/issue/${{d.issue_slug}}">full issue</a> ·
                    <a href="/shopping/issue/${{d.issue_slug}}">shopping list</a>
                  </div>
                </div>`;
              }}).join('');
            }});
        }}
        function clearAll() {{
          document.querySelectorAll('input[name=sym]:checked').forEach(el => el.checked = false);
          rank();
        }}
        </script>'''
        page = render_page(body, title="Diagnose")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_diagnose_rank(self):
        import urllib.parse as up
        params = up.parse_qs(up.urlparse(self.path).query)
        syms = params.get("sym", [])
        from .symptoms import rank_issues
        self._send_json(rank_issues(syms))

    # ── /shopping — parts shopping lists ──────────────────────────
    def _serve_shopping_home(self):
        from .knowledge import ISSUES, PROCEDURES
        issue_cards = "".join(
            f'<a href="/shopping/issue/{html.escape(slug)}" class="card" style="text-decoration:none;display:block;">'
            f'<div style="font-weight:600;">{html.escape(i.name)}</div>'
            f'<div style="color:#8b949e;font-size:12px;margin-top:4px;">'
            f'DIY ${i.cost_diy_usd[0]}-${i.cost_diy_usd[1]} · diff {"★"*i.difficulty}</div>'
            f'</a>' for slug, i in sorted(ISSUES.items(), key=lambda x: x[1].rank))
        body = f'''<main>
          <h1>Shopping lists</h1>
          <p style="color:#8b949e;">Generate a printable parts list for any issue or procedure. Includes direct product-search links to RockAuto, AutoZone, Amazon, eBay, and ToyotaPartsDeal.</p>
          <h2>By issue</h2>
          <div class="row">{issue_cards}</div>
        </main>'''
        page = render_page(body, title="Shopping")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_shopping_issue(self):
        import urllib.parse as up
        slug = up.unquote(self.path.rsplit("/", 1)[-1])
        from .shopping import list_for_issue
        data = list_for_issue(slug)
        if data.get("error"):
            self.send_error(404); return
        items_html = ""
        for it in data["items"]:
            aft_html = "".join(
                f'<li><b>{html.escape(mfr)}</b>: <code>{html.escape(num)}</code></li>'
                for mfr, num in it.get("aftermarket", {}).items()
            )
            links_html = " · ".join(
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="background:#21262d;padding:3px 8px;border-radius:4px;'
                f'text-decoration:none;margin-right:4px;font-size:12px;">{html.escape(r)}</a>'
                for r, url in it["search"].items()
            )
            items_html += f'''
              <div class="card" style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                  <div>
                    <input type="checkbox" style="transform:scale(1.2);margin-right:8px;">
                    <b>{html.escape(it["name"])}</b>
                  </div>
                  <span style="color:#3fb950;">${it["price_usd"][0]}–${it["price_usd"][1]}</span>
                </div>
                <div style="margin-top:6px;font-size:13px;">
                  <b>OEM:</b> <code>{html.escape(it.get("oem") or "—")}</code>
                </div>
                {f'<ul style="font-size:12px;margin:6px 0 0 16px;">{aft_html}</ul>' if aft_html else ''}
                <div style="margin-top:8px;">{links_html}</div>
                {f'<div style="color:#8b949e;font-size:11px;margin-top:6px;">{html.escape(it.get("notes") or "")}</div>' if it.get("notes") else ''}
              </div>'''
        rel_procs = "".join(
            f'<li><a href="/knowledge/procedure/{html.escape(p["slug"])}">{html.escape(p["name"])}</a> (~{p["time_min"]} min)</li>'
            for p in data["related_procedures"]
        )
        body = f'''<main>
          <p><a href="/knowledge/issue/{html.escape(slug)}">← Back to issue</a></p>
          <h1>Shopping list: {html.escape(data["issue_name"])}</h1>
          <div class="row">
            <div class="card"><div class="label">Estimated budget</div>
              <div class="value">${data["total_low"]} – ${data["total_high"]}</div>
              <div class="sub">total DIY parts</div></div>
            <div class="card"><div class="label">Difficulty</div>
              <div class="value" style="font-size:16px;">{'★'*data['difficulty']}{'☆'*(5-data['difficulty'])}</div></div>
            <div class="card"><div class="label">Items</div>
              <div class="value">{len(data['items'])}</div></div>
          </div>
          <h2>Parts needed</h2>
          {items_html}
          {'<h2>Related procedures</h2><div class="card"><ul>'+rel_procs+'</ul></div>' if rel_procs else ''}
          <div class="card" style="margin-top:16px;background:#21262d;">
            <b>Tip:</b> Check the box on items as you acquire them. Use your browser's print function for a hardcopy for the store.
          </div>
        </main>'''
        page = render_page(body, title=f"Shopping: {data['issue_name']}")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_shopping_procedure(self):
        import urllib.parse as up
        slug = up.unquote(self.path.rsplit("/", 1)[-1])
        from .shopping import list_for_procedure
        data = list_for_procedure(slug)
        if data.get("error"):
            self.send_error(404); return
        items_html = "".join(
            f'<div class="card" style="margin-bottom:8px;">'
            f'<b>{html.escape(it["name"])}</b>: {html.escape(it["description"])}'
            f'<div style="margin-top:6px;">'
            + " · ".join(f'<a href="{u}" target="_blank" style="background:#21262d;padding:2px 6px;border-radius:4px;font-size:12px;text-decoration:none;">{html.escape(r)}</a>' for r, u in it["search"].items())
            + '</div></div>'
            for it in data["items"]
        )
        tools_html = "".join(f"<li>{html.escape(t)}</li>" for t in data["tools"])
        body = f'''<main>
          <p><a href="/knowledge/procedure/{html.escape(slug)}">← Back to procedure</a></p>
          <h1>Shopping list: {html.escape(data["procedure_name"])}</h1>
          <h2>Parts</h2>{items_html}
          <h2>Tools</h2><div class="card"><ul>{tools_html}</ul></div>
        </main>'''
        page = render_page(body, title="Shopping procedure")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── /overview — car at-a-glance splash ────────────────────────
    def _serve_overview_page(self):
        body = '''<main>
          <h1>Car overview</h1>
          <div id="content">loading…</div>
        </main>
        <script>
        fetch('/overview_data').then(r=>r.json()).then(d => {
          const st = d.latest_status || {};
          const milColor = st.mil ? '#f85149' : '#3fb950';
          const milText = st.mil ? 'ON — action needed' : 'OFF — nominal';
          const ltftCls = !st.ltft_avg ? 'val-ok' : (Math.abs(st.ltft_avg) > 15 ? 'val-err' : (Math.abs(st.ltft_avg) > 7 ? 'val-warn' : 'val-ok'));
          const mafRatioCls = st.maf_ratio == null ? '' : (st.maf_ratio >= 0.85 ? 'val-ok' : (st.maf_ratio >= 0.70 ? 'val-warn' : 'val-err'));
          const voltCls = !st.charging_v ? '' : (st.charging_v < 13.4 ? 'val-warn' : 'val-ok');

          let html = `
            <h2>Current health</h2>
            <div class="row">
              <div class="card" style="border-left:4px solid ${milColor};">
                <div class="label">MIL</div>
                <div class="value" style="color:${milColor};">${milText}</div>
                <div class="sub">DTCs present: ${st.dtc_count || 0}</div>
              </div>
              <div class="card">
                <div class="label">LTFT avg (latest session)</div>
                <div class="value ${ltftCls}">${st.ltft_avg != null ? st.ltft_avg.toFixed(1) + '%' : '—'}</div>
                <div class="sub">Healthy: ±5% · Concerning: ±10% · Red: ±20%</div>
              </div>
              <div class="card">
                <div class="label">MAF ratio (latest)</div>
                <div class="value ${mafRatioCls}">${st.maf_ratio != null ? st.maf_ratio.toFixed(2) + '×' : '—'}</div>
                <div class="sub">Healthy: ≥0.85×</div>
              </div>
              <div class="card">
                <div class="label">Charging voltage</div>
                <div class="value ${voltCls}">${st.charging_v != null ? st.charging_v.toFixed(2) + ' V' : '—'}</div>
                <div class="sub">Healthy: 13.4–14.5 V</div>
              </div>
            </div>`;

          if (d.active_dtcs && d.active_dtcs.length) {
            html += '<h2>Active / recent DTCs</h2><div class="row">';
            d.active_dtcs.forEach(x => {
              html += `<a href="/knowledge/issue/${x.related_issue || 'p0101-maf-fault'}" class="card" style="text-decoration:none;border-left:3px solid #f85149;">
                <div style="font-weight:600;color:#f85149;">${x.code}</div>
                <div style="color:#8b949e;font-size:12px;">seen ${x.occurrences}× · last ${x.last_ts.slice(0,10)}</div>
              </a>`;
            });
            html += '</div>';
          }

          // Odometer entry
          html += `<h2>Odometer</h2>
            <div class="card">
              <div style="display:flex;gap:10px;align-items:center;">
                <span style="color:#8b949e;">Current:</span>
                <span style="font-size:20px;color:#58a6ff;font-weight:600;">${d.current_km != null ? d.current_km.toLocaleString() + ' km' : 'not set'}</span>
                <input type="number" id="km-input" placeholder="Update mileage…"
                       style="flex:1;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 10px;border-radius:4px;">
                <button onclick="saveOdo()" style="background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">Save</button>
              </div>
              <div id="odo-status" style="color:#8b949e;font-size:12px;margin-top:6px;"></div>
            </div>`;

          if (d.maintenance_next) {
            const status = d.maintenance_next.status || '';
            const statusColor = status.includes('OVERDUE') ? '#f85149' : (status.includes('due soon') ? '#d29922' : '#3fb950');
            html += `<h2>Next maintenance</h2>
              <div class="card" style="border-left:4px solid ${statusColor};">
                <div style="display:flex;justify-content:space-between;align-items:baseline;">
                  <div style="color:#58a6ff;font-size:22px;font-weight:600;">${d.maintenance_next.km.toLocaleString()} km</div>
                  <div style="color:${statusColor};font-weight:500;">${status}</div>
                </div>
                ${d.maintenance_next.km_until != null ? `<div style="color:#8b949e;margin-top:4px;">${d.maintenance_next.km_until.toLocaleString()} km until due</div>` : ''}
                <div style="color:#8b949e;margin-top:6px;">Items:</div>
                <ul style="margin-top:4px;">${d.maintenance_next.items.map(i=>`<li>${i}</li>`).join('')}</ul>
                <div style="color:#3fb950;">Est. cost: $${d.maintenance_next.cost_low}–$${d.maintenance_next.cost_high}</div>
              </div>`;
          }

          if (d.open_recalls && d.open_recalls.length) {
            html += '<h2>Open recalls (hardware-match)</h2>';
            d.open_recalls.forEach(r => {
              html += `<div class="card" style="border-left:3px solid #d29922;margin-bottom:8px;">
                <b style="color:#d29922;">${r.campaign}</b> <span style="color:#8b949e;font-size:12px;">${r.date}</span>
                <div style="font-weight:500;margin-top:4px;">${r.component}</div>
                <div style="color:#3fb950;margin-top:4px;font-size:13px;"><b>Remedy:</b> ${r.remedy}</div>
              </div>`;
            });
          }

          html += `<h2>Quick actions</h2>
            <div class="row">
              <a href="/live" class="card" style="text-decoration:none;"><div class="label">🚦 Live dashboard</div><div class="value" style="font-size:14px;">Real-time OBD</div></a>
              <a href="/history" class="card" style="text-decoration:none;"><div class="label">📊 History</div><div class="value" style="font-size:14px;">${d.session_count} sessions recorded</div></a>
              <a href="/diagnose" class="card" style="text-decoration:none;"><div class="label">🧭 Diagnose</div><div class="value" style="font-size:14px;">Symptom-based</div></a>
              <a href="/knowledge" class="card" style="text-decoration:none;"><div class="label">📚 Knowledge</div><div class="value" style="font-size:14px;">${d.kb_counts.issues} issues, ${d.kb_counts.procedures} procedures</div></a>
              <a href="/shopping" class="card" style="text-decoration:none;"><div class="label">🛒 Shopping lists</div><div class="value" style="font-size:14px;">For any repair</div></a>
            </div>`;

          document.getElementById('content').innerHTML = html;
        });

        function saveOdo() {
          const km = document.getElementById('km-input').value;
          if (!km) { return; }
          const body = new URLSearchParams();
          body.append('km', km);
          fetch('/odometer', {method:'POST', body,
            headers:{'Content-Type':'application/x-www-form-urlencoded'}})
          .then(r => r.json()).then(d => {
            document.getElementById('odo-status').textContent =
              d.ok ? `✓ saved ${d.km.toLocaleString()} km — reload to refresh` : `✗ ${d.error}`;
          });
        }
        </script>'''
        page = render_page(body, title="Overview")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_overview_data(self):
        from .store import Store, DEFAULT_DB
        from .knowledge import ISSUES, PROCEDURES, MAINTENANCE, RECALLS, TSBS, PARTS
        from .dtc_db import DTC_DATABASE
        payload = {
            "kb_counts": {
                "issues": len(ISSUES), "procedures": len(PROCEDURES),
                "parts": len(PARTS), "dtcs": len(DTC_DATABASE),
                "tsbs": len(TSBS), "recalls": len(RECALLS),
            },
            "latest_status": {},
            "active_dtcs": [],
            "open_recalls": [],
            "maintenance_next": None,
            "session_count": 0,
        }
        try:
            with Store(DEFAULT_DB) as s:
                sessions = s.sessions(vin=VIN, days=365)
                payload["session_count"] = len(sessions)
                ltft_rows = s.ltft_history(vin=VIN, days=30)
                maf_rows = s.maf_ratio_trend(vin=VIN, days=30)
                if sessions:
                    # Latest session details
                    latest = sessions[0]
                    summ = s.session_summary(latest["id"])
                    st = summ.get("stats", {})
                    latest_ltft = next((r["ltft_avg"] for r in ltft_rows if r["id"] == latest["id"]), None)
                    latest_maf = next((r["ratio_mean"] for r in maf_rows if r["session_id"] == latest["id"]), None)
                    # Charging voltage from samples
                    v_row = s.conn.execute(
                        "SELECT AVG(ctlmod_v) AS v FROM samples WHERE session_id=? AND rpm>600",
                        (latest["id"],)
                    ).fetchone()
                    payload["latest_status"] = {
                        "mil": bool(st.get("mil_ever")),
                        "dtc_count": st.get("dtc_max") or 0,
                        "ltft_avg": latest_ltft,
                        "maf_ratio": latest_maf,
                        "charging_v": v_row["v"] if v_row and v_row["v"] else None,
                    }
                # DTC occurrences
                for r in s.dtc_occurrences(vin=VIN, days=90):
                    from .dtc_db import resolve
                    issue = None
                    for slug, i in ISSUES.items():
                        if r["code"].upper() in [c.upper() for c in i.related_dtcs]:
                            issue = slug; break
                    payload["active_dtcs"].append({
                        "code": r["code"], "bucket": r["bucket"],
                        "occurrences": r["occurrences"],
                        "last_ts": r["last_ts"],
                        "related_issue": issue,
                    })
        except Exception as e:
            payload["error"] = str(e)
        # Open recalls — all 3 Takata apply to hardware
        payload["open_recalls"] = [
            {"campaign": r.campaign, "date": r.date, "component": r.component,
             "remedy": r.remedy}
            for r in RECALLS
        ]
        # Next maintenance based on latest odometer reading
        from .odometer import service_status, latest_km
        current_km = latest_km()
        payload["current_km"] = current_km
        if current_km is not None:
            upcoming = service_status()
            # Take the first (soonest due)
            if upcoming:
                first = upcoming[0]
                payload["maintenance_next"] = {
                    "km": first["next_due_km"],
                    "items": first["items"],
                    "cost_low": first["cost_low"],
                    "cost_high": first["cost_high"],
                    "km_until": first["km_until"],
                    "status": first["status"],
                }
        else:
            # No odometer yet — show 100k as placeholder
            if MAINTENANCE:
                m = MAINTENANCE[9]
                payload["maintenance_next"] = {
                    "km": m.km, "items": m.items,
                    "cost_low": m.cost_usd_low, "cost_high": m.cost_usd_high,
                    "km_until": None, "status": "odometer not set",
                }
        self._send_json(payload)

    # ── /monitors — mode 06 + readiness visual ────────────────────
    def _serve_monitors_page(self):
        import glob as _glob
        # Readiness monitors — 8 non-continuous bits
        MONITORS = [
            ("Catalyst", "cat"), ("Heated catalyst", "htd_cat"),
            ("EVAP system", "evap"), ("Secondary air", "sec_air"),
            ("A/C refrigerant", "ac"), ("O2 sensor", "o2"),
            ("O2 heater", "o2htr"), ("EGR", "egr"),
        ]
        CONTINUOUS = [("Misfire", "misfire"), ("Fuel system", "fuel"),
                      ("Comprehensive components", "comp")]

        # Last-known readiness from latest mode 06 probe OR live readiness
        from .store import Store, DEFAULT_DB
        from .obd import decode_readiness
        last_readiness = None
        try:
            with Store(DEFAULT_DB) as s:
                sessions = s.sessions(vin=VIN, days=365)
                if sessions:
                    # We don't store readiness bits directly — would need to run
                    # yaris-diag readiness --once live. For now show "unknown".
                    pass
        except Exception:
            pass

        # Parse the latest mode 06 text report if it exists
        pngs = sorted(_glob.glob(os.path.join(REPORT_DIR, "mode06_*.txt")),
                      key=os.path.getmtime, reverse=True)
        mode06_section = ""
        if pngs:
            latest_m06 = pngs[0]
            try:
                with open(latest_m06) as f:
                    content = f.read()
                mode06_section = f'''
                  <h2>Mode 06 monitor test results</h2>
                  <p style="color:#8b949e;">Latest from <code>{html.escape(os.path.basename(latest_m06))}</code>.
                     Run <code>yaris-diag mode06</code> to refresh.</p>
                  <div class="card">
                    <pre style="margin:0;white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:12px;color:#c9d1d9;">{html.escape(content)}</pre>
                  </div>'''
            except Exception as e:
                mode06_section = f"<p>Error reading mode06 report: {html.escape(str(e))}</p>"
        else:
            mode06_section = '''
              <h2>Mode 06 monitor test results</h2>
              <div class="card" style="color:#8b949e;">
                No mode 06 report yet. Run <code>yaris-diag mode06</code> to populate.<br><br>
                Mode 06 shows <b>actual numeric results</b> of the ECU's on-board tests:
                catalyst efficiency ratio, O2 response time in ms, EGR flow, etc.
                More diagnostic than the bit-level readiness flags.
              </div>'''

        # Readiness bit visualization — show structure even if no live data
        def led(state):
            if state == "complete":
                return '<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#3fb950;box-shadow:0 0 4px #3fb950;"></span>'
            elif state == "incomplete":
                return '<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#d29922;"></span>'
            else:
                return '<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#30363d;"></span>'

        readiness_html = '''
          <h2>Readiness monitors</h2>
          <p style="color:#8b949e;">Non-continuous monitors must complete at least once before MIL stays off and before permanent codes self-clear. Run <code>yaris-diag readiness --once</code> for a current snapshot.</p>
          <div class="card">
            <div style="margin-bottom:12px;">
              <b style="color:#8b949e;">Continuous (always complete when running)</b>
            </div>'''
        for name, _ in CONTINUOUS:
            readiness_html += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">'
                f'{led("complete")}<span>{html.escape(name)}</span>'
                f'<span style="margin-left:auto;color:#8b949e;font-size:11px;">continuous</span></div>'
            )
        readiness_html += '''
            <div style="margin:18px 0 12px 0;">
              <b style="color:#8b949e;">Non-continuous (need drive cycle)</b>
            </div>'''
        for name, _ in MONITORS:
            readiness_html += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">'
                f'{led("unknown")}<span>{html.escape(name)}</span>'
                f'<span style="margin-left:auto;color:#8b949e;font-size:11px;">—</span></div>'
            )
        readiness_html += '''
            <div style="margin-top:14px;padding:10px;background:#21262d;border-radius:4px;color:#8b949e;font-size:12px;">
              <b>Legend:</b>
              <span style="margin-left:10px;">''' + led("complete") + ''' complete</span>
              <span style="margin-left:10px;">''' + led("incomplete") + ''' incomplete</span>
              <span style="margin-left:10px;">''' + led("unknown") + ''' not yet read</span>
              <br>
              <br>
              <b>To populate current state:</b>
              <br>
              <code style="color:#58a6ff;">./yaris-diag readiness --once</code>
            </div>
          </div>'''

        body = f'''<main>
          <h1>Monitors &amp; readiness</h1>
          <p style="color:#8b949e;">On-board diagnostic tests the ECU runs. These are the building blocks for earning permanent code removal after a repair.</p>
          {readiness_html}
          {mode06_section}
          <h2>Quick reference</h2>
          <div class="row">
            <div class="card">
              <div class="label">Continuous monitors</div>
              <div style="font-size:13px;margin-top:6px;">
                Misfire, Fuel-system, Comprehensive Components. These run every
                time the engine is running — auto-complete.
              </div>
            </div>
            <div class="card">
              <div class="label">Non-continuous monitors</div>
              <div style="font-size:13px;margin-top:6px;">
                Catalyst, Evap, O2, O2 Heater, EGR — each requires specific drive
                conditions to run. <a href="/knowledge/procedure/">drive cycle runner</a>
                walks through the Toyota OEM drive-cycle phases to complete them.
              </div>
            </div>
            <div class="card">
              <div class="label">Why it matters</div>
              <div style="font-size:13px;margin-top:6px;">
                A permanent code (Mode 0A) only self-clears after <b>2 consecutive
                drive cycles</b> where every relevant monitor ran and passed. No
                monitors run → permanent code never clears → failed emissions test.
              </div>
            </div>
          </div>
        </main>'''
        page = render_page(body, title="Monitors")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── /fusebox — visual fuse reference ───────────────────────────
    def _serve_fusebox_page(self):
        # Yaris XP90 engine-bay + interior fuse/relay layouts
        engine_bay = [
            ("1", "EFI", "15A", "ECM, fuel injectors, ignition coils"),
            ("2", "IGN", "7.5A", "Ignition coils"),
            ("3", "HORN", "10A", "Horn"),
            ("4", "HAZ-HORN", "10A", "Hazard + horn"),
            ("5", "DOME", "7.5A", "Dome light, clock, ECM memory"),
            ("6", "ECU-B", "10A", "ECM backup, SRS, gauge"),
            ("7", "RADIO", "7.5A", "Audio system"),
            ("8", "CIG", "15A", "Cigarette lighter, accessory outlet"),
            ("9", "AM2", "7.5A", "Ignition system"),
            ("10", "STOP", "10A", "Brake light, cruise, shift lock"),
            ("11", "H-LP RH", "10A", "Headlight right"),
            ("12", "H-LP LH", "10A", "Headlight left"),
            ("13", "HEAD", "7.5A", "Headlight relay"),
            ("14", "TAIL", "15A", "Tail lights, license plate"),
            ("15", "ETCS", "10A", "Electronic throttle control"),
            ("16", "ST", "7.5A", "Starter"),
            ("17", "EFI MAIN", "20A", "Fuel pump relay, injectors"),
            ("18", "HTR", "40A", "Blower motor, A/C"),
            ("19", "RDI FAN", "30A", "Radiator cooling fan"),
            ("20", "ABS-1", "30A", "ABS pump motor"),
            ("21", "ABS-2", "40A", "ABS solenoid"),
            ("22", "AM1", "30A", "Ignition main"),
            ("23", "ALT", "100A", "Alternator main output"),
            ("24", "POWER", "40A", "Power windows"),
        ]

        interior = [
            ("1", "DOOR", "20A", "Power door locks, central locking"),
            ("2", "PWR RR", "20A", "Rear power windows"),
            ("3", "PWR FR", "20A", "Front power windows"),
            ("4", "WSH", "20A", "Windshield washer, wipers"),
            ("5", "GAUGE", "7.5A", "Instrument cluster, warning lights"),
            ("6", "RR WIP", "15A", "Rear wiper (hatch)"),
            ("7", "SEAT HTR", "15A", "Heated seats"),
            ("8", "OBD", "7.5A", "OBD-II port power"),
            ("9", "MIR HTR", "7.5A", "Heated mirrors"),
            ("10", "DEF", "30A", "Rear defogger"),
            ("11", "A/C", "7.5A", "A/C control"),
            ("12", "ECU-IG", "7.5A", "ECM + SRS ignition"),
        ]

        def tile(num, label, amp, circuit):
            # Color-code by amperage: red for heavy, orange mid, blue light
            try:
                a = int(amp.replace("A", ""))
            except ValueError:
                a = 0
            if a >= 30: color = "#f85149"
            elif a >= 15: color = "#d29922"
            else: color = "#58a6ff"
            return (
                f'<div class="card" style="padding:8px;border-left:4px solid {color};cursor:pointer;"'
                f' onclick="toggle(\'f-{num}\')">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span><b>#{num}</b> {html.escape(label)}</span>'
                f'<span style="color:{color};font-weight:600;">{html.escape(amp)}</span></div>'
                f'<div id="f-{num}" style="display:none;color:#8b949e;font-size:12px;margin-top:6px;">'
                f'{html.escape(circuit)}</div></div>'
            )

        engine_html = "".join(tile(*f) for f in engine_bay)
        interior_html = "".join(tile(*f) for f in interior)

        body = f'''<main>
          <h1>Fuse &amp; Relay Reference</h1>
          <p style="color:#8b949e;">Yaris XP90 (2006-2012). Click any fuse for circuit detail.
             Color coded by amperage: <span style="color:#58a6ff;">light (≤10A)</span>,
             <span style="color:#d29922;">medium (15-25A)</span>,
             <span style="color:#f85149;">heavy (≥30A)</span>.</p>

          <h2>Engine bay fuse box</h2>
          <p style="color:#8b949e;font-size:13px;">Located near battery. Flip lid to check.</p>
          <div class="row" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));">
            {engine_html}
          </div>

          <h2>Interior fuse box</h2>
          <p style="color:#8b949e;font-size:13px;">Driver's kick panel below steering column. Kick-panel clip pulls down.</p>
          <div class="row" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));">
            {interior_html}
          </div>

          <h2>Diagnostic tips</h2>
          <div class="row">
            <div class="card">
              <div class="label">🔋 Battery drain</div>
              <div style="font-size:13px;margin-top:6px;">
                Pull fuses one at a time with a DMM on the battery lead; the fuse
                whose removal drops the draw owns the guilty circuit.
                DOME, ECU-B, RADIO, POWER are usual suspects.
              </div>
            </div>
            <div class="card">
              <div class="label">⚡ No start / intermittent</div>
              <div style="font-size:13px;margin-top:6px;">
                Check EFI, EFI MAIN, IGN, AM1/AM2, ST. All must be intact for engine to start.
              </div>
            </div>
            <div class="card">
              <div class="label">💧 Water leak under dash</div>
              <div style="font-size:13px;margin-top:6px;">
                Interior fuse box is at driver's-side kick panel — known water-intrusion
                path on XP90. Wet fuses corrode and cause random electrical faults.
              </div>
            </div>
          </div>
        </main>
        <script>
        function toggle(id) {{
          const el = document.getElementById(id);
          if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }}
        </script>'''
        page = render_page(body, title="Fuse box")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── Maintenance due (based on odometer) ───────────────────────
    def _serve_maintenance_due_data(self):
        from .odometer import service_status, latest_km
        self._send_json({
            "current_km": latest_km(),
            "schedule": service_status(),
        })

    # ── /print/session?id=N — printable one-pager ────────────────
    def _serve_print_session(self):
        import urllib.parse as up
        sid = up.parse_qs(up.urlparse(self.path).query).get("id", [""])[0]
        from .store import Store, DEFAULT_DB
        from .dtc_db import resolve as dtc_resolve
        try:
            sid_int = int(sid)
        except ValueError:
            self.send_error(400); return
        try:
            with Store(DEFAULT_DB) as s:
                summ = s.session_summary(sid_int)
        except Exception as e:
            self.send_error(500); return
        if not summ:
            self.send_error(404); return

        sess = summ["session"]; stats = summ.get("stats", {})
        dtcs = summ.get("dtcs", [])
        events = summ.get("events", [])

        dtcs_html = ""
        for d in dtcs:
            e = dtc_resolve(d["code"])
            title = e.title if e else "(unknown)"
            dtcs_html += (
                f'<tr><td><b>{html.escape(d["code"])}</b></td>'
                f'<td>{html.escape(d["bucket"])}</td>'
                f'<td>{html.escape(title)}</td></tr>'
            )
        events_html = "".join(
            f'<tr><td>{html.escape(ev["ts"])}</td>'
            f'<td>{html.escape(ev["type"])}</td>'
            f'<td>{html.escape(ev["text"])}</td></tr>'
            for ev in events
        )

        # Print-only simple HTML (no nav, no JS)
        body = f'''<!doctype html><html><head>
        <meta charset="utf-8"><title>Session #{sid_int} — Print</title>
        <style>
          body {{ font-family: -apple-system, sans-serif; max-width: 800px;
                  margin: 20px auto; padding: 20px; color: #000; background: #fff;
                  font-size: 12px; }}
          h1 {{ font-size: 18px; border-bottom: 2px solid #000; padding-bottom: 6px; }}
          h2 {{ font-size: 14px; margin-top: 18px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
          th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #eee; }}
          th {{ background: #f0f0f0; }}
          .kv {{ display: grid; grid-template-columns: 150px 1fr; gap: 4px 16px; margin-top: 6px; }}
          .kv b {{ color: #555; }}
          .footer {{ margin-top: 30px; font-size: 10px; color: #888; border-top: 1px solid #ccc; padding-top: 10px; }}
          @media print {{ body {{ margin: 0; padding: 10mm; }} }}
        </style>
        </head><body>
          <h1>Yaris Diagnostic Session #{sid_int}</h1>
          <div class="kv">
            <b>VIN:</b> <span>{html.escape(sess.get("vin",""))}</span>
            <b>Started:</b> <span>{html.escape(sess.get("started_ts",""))}</span>
            <b>Ended:</b> <span>{html.escape(sess.get("ended_ts") or "(open)")}</span>
            <b>Source:</b> <span>{html.escape(sess.get("source",""))}</span>
            <b>Note:</b> <span>{html.escape(sess.get("note") or "")}</span>
          </div>

          <h2>Session statistics</h2>
          <table><tbody>
            <tr><th>Samples</th><td>{stats.get("n", 0)}</td></tr>
            <tr><th>RPM range</th><td>{stats.get("rpm_min", 0):.0f} – {stats.get("rpm_max", 0):.0f}</td></tr>
            <tr><th>LTFT avg</th><td>{stats.get("ltft_avg", 0):.2f}%</td></tr>
            <tr><th>LTFT peak</th><td>{stats.get("ltft_max", 0):.2f}%</td></tr>
            <tr><th>Coolant range</th><td>{stats.get("cool_min", 0):.0f} – {stats.get("cool_max", 0):.0f} °C</td></tr>
            <tr><th>MIL ever triggered</th><td>{"Yes" if stats.get("mil_ever") else "No"}</td></tr>
            <tr><th>Max DTC count</th><td>{stats.get("dtc_max", 0)}</td></tr>
          </tbody></table>

          <h2>DTCs observed</h2>
          {'<table><thead><tr><th>Code</th><th>Bucket</th><th>Description</th></tr></thead><tbody>'+dtcs_html+'</tbody></table>' if dtcs_html else '<p>(none)</p>'}

          <h2>Events</h2>
          {'<table><thead><tr><th>Time</th><th>Type</th><th>Description</th></tr></thead><tbody>'+events_html+'</tbody></table>' if events_html else '<p>(none)</p>'}

          <div class="footer">
            Generated by yaris-diag toolkit · {datetime.now().isoformat(timespec="seconds")}
            · Print this page or save as PDF via your browser (Ctrl/Cmd+P).
          </div>
        </body></html>'''
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    # ── /alerts — webhook/ntfy config ────────────────────────────
    def _serve_alerts_page(self):
        body = '''<main>
          <h1>Alert configuration</h1>
          <p style="color:#8b949e;">Push alerts when critical thresholds cross during a live drive. Free option: <a href="https://ntfy.sh" target="_blank">ntfy.sh</a>.</p>

          <h2>Quick start with ntfy (recommended)</h2>
          <div class="card" style="margin-bottom:14px;">
            <ol style="padding-left:20px;">
              <li>Install the <b>ntfy</b> app on your phone (iOS or Android, free).</li>
              <li>In the app, tap + and subscribe to any unique topic — e.g. <code>my-yaris-alerts</code>.</li>
              <li>Enter the same topic below, enable, and click "Test alert".</li>
              <li>Your phone should buzz within a few seconds.</li>
            </ol>
          </div>

          <div class="card" id="config-card" style="margin-bottom:14px;">
            <div style="margin-bottom:10px;">
              <label style="display:flex;align-items:center;gap:8px;">
                <input type="checkbox" id="c-enabled"> <b>Enable alerts</b>
              </label>
            </div>
            <div style="display:grid;grid-template-columns:200px 1fr;gap:8px 12px;align-items:center;">
              <label>ntfy topic</label>
              <input type="text" id="c-ntfy-topic" placeholder="my-yaris-alerts">
              <label>ntfy server</label>
              <input type="text" id="c-ntfy-server" value="https://ntfy.sh">
              <label>Generic webhook (Discord/Slack)</label>
              <input type="text" id="c-generic" placeholder="https://discord.com/api/webhooks/...">
              <label>LTFT threshold %</label>
              <input type="number" id="t-ltft" step="0.5" value="24">
              <label>Coolant threshold °C</label>
              <input type="number" id="t-cool" value="105">
              <label>Charging V threshold (low)</label>
              <input type="number" id="t-volt" step="0.1" value="12.8">
              <label>Cooldown between same-event alerts (sec)</label>
              <input type="number" id="t-cooldown" value="60">
            </div>
            <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
              <button onclick="saveConfig()" style="background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">Save config</button>
              <button onclick="testAlert()" style="background:#d29922;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">Send test alert</button>
              <span id="save-status" style="color:#8b949e;font-size:12px;"></span>
            </div>
          </div>

          <h2>Events that will fire</h2>
          <div class="row">
            <div class="card"><div class="label">⚠ MIL turned on</div><div style="font-size:12px;color:#8b949e;">priority HIGH · any transition from MIL-off → MIL-on</div></div>
            <div class="card"><div class="label">⚠ New DTC latched</div><div style="font-size:12px;color:#8b949e;">priority HIGH · DTC count went up</div></div>
            <div class="card"><div class="label">⚠ LTFT near threshold</div><div style="font-size:12px;color:#8b949e;">priority DEFAULT · LTFT exceeded configured limit</div></div>
            <div class="card"><div class="label">🔥 Overheating</div><div style="font-size:12px;color:#8b949e;">priority URGENT · coolant exceeded configured limit</div></div>
            <div class="card"><div class="label">🔋 Low charging V</div><div style="font-size:12px;color:#8b949e;">priority DEFAULT · alternator V dropped below limit while running</div></div>
          </div>
        </main>
        <script>
        fetch('/alerts/config_data').then(r=>r.json()).then(c => {
          document.getElementById('c-enabled').checked = !!c.enabled;
          document.getElementById('c-ntfy-topic').value = c.ntfy_topic || '';
          document.getElementById('c-ntfy-server').value = c.ntfy_server || 'https://ntfy.sh';
          document.getElementById('c-generic').value = c.generic_webhook || '';
          document.getElementById('t-ltft').value = (c.thresholds && c.thresholds.ltft_high) || 24;
          document.getElementById('t-cool').value = (c.thresholds && c.thresholds.coolant_high) || 105;
          document.getElementById('t-volt').value = (c.thresholds && c.thresholds.charging_v_low) || 12.8;
          document.getElementById('t-cooldown').value = c.cooldown_seconds || 60;
        });

        function saveConfig() {
          const body = new URLSearchParams();
          body.append('enabled', document.getElementById('c-enabled').checked ? '1' : '0');
          body.append('ntfy_topic', document.getElementById('c-ntfy-topic').value);
          body.append('ntfy_server', document.getElementById('c-ntfy-server').value);
          body.append('generic_webhook', document.getElementById('c-generic').value);
          body.append('ltft_high', document.getElementById('t-ltft').value);
          body.append('coolant_high', document.getElementById('t-cool').value);
          body.append('charging_v_low', document.getElementById('t-volt').value);
          body.append('cooldown_seconds', document.getElementById('t-cooldown').value);
          fetch('/alerts/save', {method:'POST', body,
            headers:{'Content-Type':'application/x-www-form-urlencoded'}})
          .then(r=>r.json()).then(d => {
            document.getElementById('save-status').textContent = d.ok ? '✓ saved' : '✗ ' + d.error;
          });
        }

        function testAlert() {
          document.getElementById('save-status').textContent = 'sending…';
          fetch('/alerts/test').then(r=>r.json()).then(d => {
            document.getElementById('save-status').textContent =
              d.delivered ? '✓ sent (check your device)' :
              '✗ failed — ' + (d.reason || 'check topic + enabled flag');
          });
        }
        </script>'''
        page = render_page(body, title="Alerts")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_alerts_config_data(self):
        from .alerts import load_config
        self._send_json(load_config())

    def _handle_alerts_save(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        import urllib.parse as up
        params = up.parse_qs(body)
        from .alerts import load_config, save_config
        cfg = load_config()
        cfg["enabled"] = params.get("enabled", ["0"])[0] == "1"
        cfg["ntfy_topic"] = params.get("ntfy_topic", [""])[0]
        cfg["ntfy_server"] = params.get("ntfy_server", ["https://ntfy.sh"])[0]
        cfg["generic_webhook"] = params.get("generic_webhook", [""])[0]
        try:
            cfg["thresholds"]["ltft_high"] = float(params.get("ltft_high", ["24"])[0])
            cfg["thresholds"]["coolant_high"] = float(params.get("coolant_high", ["105"])[0])
            cfg["thresholds"]["charging_v_low"] = float(params.get("charging_v_low", ["12.8"])[0])
            cfg["cooldown_seconds"] = int(params.get("cooldown_seconds", ["60"])[0])
        except ValueError as e:
            self._send_json({"error": f"bad number: {e}"}); return
        save_config(cfg)
        self._send_json({"ok": True})

    def _serve_alerts_test(self):
        from .alerts import Alerter, load_config
        cfg = load_config()
        if not cfg.get("enabled"):
            self._send_json({"delivered": False, "reason": "alerts disabled — check 'Enable alerts' and Save"})
            return
        alerter = Alerter(cfg)
        # Bypass cooldown for test
        alerter._last_fire.pop("test", None)
        ok = alerter.test_alert()
        if ok:
            self._send_json({"delivered": True})
        else:
            self._send_json({"delivered": False,
                             "reason": "no channel delivered — check topic / webhook URL"})

    # ── /walkthroughs — interactive diagnostic trees ──────────────
    def _serve_walkthroughs_home(self):
        from .walkthroughs import list_all
        walks = list_all()
        cards = "".join(
            f'''<a href="/walkthrough/{html.escape(w["slug"])}" class="card" style="text-decoration:none;display:block;">
              <div style="font-weight:600;font-size:15px;">{html.escape(w["name"])}</div>
              <div style="color:#8b949e;font-size:12px;margin-top:4px;">{html.escape(w["summary"])}</div>
              <div style="margin-top:8px;font-size:12px;">
                <span style="color:#58a6ff;">{w["n_steps"]} steps</span>
                {' · triggers: ' + ', '.join(w["dtc_triggers"]) if w["dtc_triggers"] else ''}
              </div>
            </a>''' for w in walks
        )
        body = f'''<main>
          <h1>Interactive diagnostic walkthroughs</h1>
          <p style="color:#8b949e;">Step-by-step decision trees that branch based on what you observe or measure. Pick a scenario.</p>
          <div class="row">{cards}</div>
        </main>'''
        page = render_page(body, title="Walkthroughs")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_walkthrough_page(self):
        import urllib.parse as up
        path = up.urlparse(self.path).path
        slug = path.rsplit("/", 1)[-1]
        from .walkthroughs import get
        walk = get(slug)
        if not walk:
            self.send_error(404); return

        # Serialize the walkthrough as JSON for the JS state machine
        steps_json = {
            sid: {
                "id": s.id, "type": s.type, "title": s.title, "body": s.body,
                "next_id": s.next_id, "yes_id": s.yes_id, "no_id": s.no_id,
                "measurement_pid": s.measurement_pid,
                "measurement_units": s.measurement_units,
                "measurement_low": s.measurement_low, "measurement_high": s.measurement_high,
                "pass_id": s.pass_id, "fail_low_id": s.fail_low_id,
                "fail_high_id": s.fail_high_id,
                "choices": s.choices,
                "result_status": s.result_status,
                "linked_issue": s.linked_issue,
                "linked_procedure": s.linked_procedure,
                "linked_shopping": s.linked_shopping,
            }
            for sid, s in walk.steps.items()
        }
        body = f'''<main>
          <p><a href="/walkthroughs">← All walkthroughs</a></p>
          <h1>{html.escape(walk.name)}</h1>
          <p style="color:#8b949e;">{html.escape(walk.summary)}</p>

          <div id="step" class="card"></div>

          <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
            <button onclick="restart()" style="background:#30363d;color:#c9d1d9;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;">↻ Restart</button>
            <button id="back-btn" onclick="back()" style="background:#30363d;color:#c9d1d9;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;display:none;">← Back</button>
            <div id="trail" style="color:#8b949e;font-size:11px;margin-left:auto;"></div>
          </div>
        </main>

        <script>
        const STEPS = {json.dumps(steps_json)};
        const START = {json.dumps(walk.start_id)};
        const history = [START];

        function render() {{
          const s = STEPS[history[history.length - 1]];
          if (!s) return;
          document.getElementById('back-btn').style.display = history.length > 1 ? 'inline-block' : 'none';
          document.getElementById('trail').textContent = `step ${{history.length}} · ${{history.length - 1}} back available`;

          const badge = {{
            "info": {{text: "ℹ info", color: "#58a6ff"}},
            "action": {{text: "🔧 do this", color: "#d29922"}},
            "question": {{text: "❓ answer", color: "#58a6ff"}},
            "measurement": {{text: "📏 measure", color: "#d29922"}},
            "choice": {{text: "↳ pick", color: "#58a6ff"}},
            "result": {{text: s.result_status === "fixed" ? "✓ done" : (s.result_status === "replace_part" ? "🛠 part needed" : "?"), color: s.result_status === "fixed" ? "#3fb950" : "#d29922"}},
          }}[s.type];

          let html = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <span class="pill" style="background:${{badge.color}}22;color:${{badge.color}};">${{badge.text}}</span>
              <span style="color:#6e7681;font-size:11px;">${{s.id}}</span>
            </div>
            <h2 style="margin:0 0 8px 0;">${{s.title}}</h2>
            <p style="white-space:pre-line;">${{s.body}}</p>`;

          if (s.type === "info" || s.type === "action") {{
            html += `<button onclick="advance('${{s.next_id}}')" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-size:15px;margin-top:12px;">Continue →</button>`;
          }} else if (s.type === "question") {{
            html += `<div style="margin-top:12px;display:flex;gap:10px;">
              <button onclick="advance('${{s.yes_id}}')" style="background:#3fb950;color:white;border:none;padding:10px 28px;border-radius:4px;cursor:pointer;font-size:15px;">Yes</button>
              <button onclick="advance('${{s.no_id}}')" style="background:#f85149;color:white;border:none;padding:10px 28px;border-radius:4px;cursor:pointer;font-size:15px;">No</button>
            </div>`;
          }} else if (s.type === "measurement") {{
            html += `<div style="margin-top:12px;">
              <label style="color:#8b949e;font-size:12px;">Reading (${{s.measurement_units||""}})</label>
              <div style="display:flex;gap:8px;align-items:center;margin-top:4px;">
                <input type="number" step="any" id="m-value" placeholder="enter value"
                       style="flex:1;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:8px;border-radius:4px;font-size:15px;">
                <button onclick="checkMeasurement()" style="background:#238636;color:white;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;">Check</button>
              </div>
              ${{ (s.measurement_low !== 0 || s.measurement_high !== 0) ? `<div style="color:#8b949e;font-size:11px;margin-top:4px;">healthy range: ${{s.measurement_low}} – ${{s.measurement_high}} ${{s.measurement_units||""}}</div>` : ""}}
            </div>`;
          }} else if (s.type === "choice") {{
            html += `<div style="margin-top:12px;display:flex;flex-direction:column;gap:6px;">`;
            s.choices.forEach(c => {{
              html += `<button onclick="advance('${{c.next_id}}')" style="background:#21262d;color:#c9d1d9;border:1px solid #30363d;padding:10px 14px;border-radius:4px;cursor:pointer;text-align:left;font-size:14px;">${{c.label}}</button>`;
            }});
            html += `</div>`;
          }} else if (s.type === "result") {{
            html += `<div style="margin-top:14px;padding:12px;background:${{s.result_status==='fixed'?'rgba(63,185,80,0.1)':(s.result_status==='replace_part'?'rgba(210,153,34,0.1)':'rgba(88,166,255,0.1)')}};border-radius:4px;">
              <b>Outcome: ${{s.result_status.replace('_',' ')}}</b>
            </div>`;
            if (s.linked_issue) html += `<div style="margin-top:8px;"><a href="/knowledge/issue/${{s.linked_issue}}">📚 View issue details</a></div>`;
            if (s.linked_procedure) html += `<div><a href="/knowledge/procedure/${{s.linked_procedure}}">🔧 Procedure</a></div>`;
            if (s.linked_shopping) html += `<div><a href="/shopping/issue/${{s.linked_shopping}}">🛒 Shopping list</a></div>`;
          }}
          document.getElementById('step').innerHTML = html;
        }}

        function advance(id) {{
          if (!id || !STEPS[id]) return;
          history.push(id);
          render();
        }}
        function back() {{
          if (history.length <= 1) return;
          history.pop();
          render();
        }}
        function restart() {{
          history.length = 0;
          history.push(START);
          render();
        }}
        function checkMeasurement() {{
          const val = parseFloat(document.getElementById('m-value').value);
          const s = STEPS[history[history.length - 1]];
          if (isNaN(val)) return;
          if (val >= s.measurement_low && val <= s.measurement_high) advance(s.pass_id);
          else if (val < s.measurement_low) advance(s.fail_low_id);
          else advance(s.fail_high_id);
        }}
        render();
        </script>'''
        page = render_page(body, title=walk.name)
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── /checklist — pre-flight check ────────────────────────────
    def _serve_checklist_page(self):
        body = '''<main>
          <h1>Pre-flight checklist</h1>
          <p style="color:#8b949e;">Automated "is my car OK to drive" check. Runs against your latest session data and the KB baselines.</p>
          <div id="content" class="card">running checks…</div>
        </main>
        <script>
        fetch('/checklist_data').then(r=>r.json()).then(d => {
          let html = '';

          // Overall verdict
          const status = d.verdict;
          const color = status === 'go' ? '#3fb950' : (status === 'caution' ? '#d29922' : '#f85149');
          const icon = status === 'go' ? '✓' : (status === 'caution' ? '⚠' : '✗');
          const msg = status === 'go' ? 'Safe to drive' :
                      (status === 'caution' ? 'Caution — review items below' :
                       'Do not drive until fixed');
          html += `<div class="card" style="margin-bottom:14px;border-left:6px solid ${color};">
            <div style="font-size:32px;color:${color};font-weight:700;">${icon} ${msg}</div>
            ${d.summary ? `<div style="color:#8b949e;margin-top:6px;">${d.summary}</div>` : ''}
          </div>`;

          // Items
          html += '<h2>Individual checks</h2><div class="row">';
          d.checks.forEach(c => {
            const pill = c.status === 'pass' ? 'ok' : (c.status === 'warn' ? 'warn' : 'err');
            const cIcon = c.status === 'pass' ? '✓' : (c.status === 'warn' ? '~' : '✗');
            html += `<div class="card" style="border-left:3px solid ${c.status==='pass'?'#3fb950':(c.status==='warn'?'#d29922':'#f85149')};">
              <div style="font-weight:600;">${cIcon} ${c.name}</div>
              <div style="color:#8b949e;font-size:12px;margin-top:4px;">${c.detail || ''}</div>
              ${c.action ? `<div style="margin-top:6px;font-size:13px;"><a href="${c.action.link}">${c.action.text}</a></div>` : ''}
            </div>`;
          });
          html += '</div>';

          document.getElementById('content').innerHTML = html;
        });
        </script>'''
        page = render_page(body, title="Pre-flight")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_checklist_data(self):
        """Run all checks and produce a checklist report."""
        from .store import Store, DEFAULT_DB
        from .odometer import latest_km, service_status
        checks = []

        try:
            with Store(DEFAULT_DB) as s:
                sessions = s.sessions(vin=VIN, days=365)
                if sessions:
                    summ = s.session_summary(sessions[0]["id"])
                    stats = summ.get("stats", {})
                    # MIL check
                    mil = bool(stats.get("mil_ever"))
                    checks.append({
                        "name": "MIL status",
                        "status": "fail" if mil else "pass",
                        "detail": ("MIL activated in last session — active fault"
                                   if mil else "MIL off during last session"),
                        "action": {"text": "View DTCs", "link": "/dtc"} if mil else None,
                    })
                    # DTC count
                    dtc_count = stats.get("dtc_max") or 0
                    checks.append({
                        "name": "DTCs present",
                        "status": "fail" if dtc_count > 0 else "pass",
                        "detail": f"{dtc_count} DTC(s)",
                    })
                    # LTFT health
                    ltft_rows = s.ltft_history(vin=VIN, days=30)
                    if ltft_rows:
                        ltft_avg = ltft_rows[0]["ltft_avg"] or 0
                        if abs(ltft_avg) > 15:
                            status = "fail"
                            detail = f"LTFT {ltft_avg:+.1f}% saturated — needs attention"
                        elif abs(ltft_avg) > 7:
                            status = "warn"
                            detail = f"LTFT {ltft_avg:+.1f}% elevated"
                        else:
                            status = "pass"
                            detail = f"LTFT {ltft_avg:+.1f}% healthy"
                        checks.append({"name": "Fuel trim (LTFT)", "status": status,
                                        "detail": detail,
                                        "action": {"text": "Diagnose", "link": "/walkthroughs"}
                                        if status != "pass" else None})

                    # Charging voltage
                    v_row = s.conn.execute(
                        "SELECT AVG(ctlmod_v) AS v FROM samples WHERE session_id=? AND rpm>600",
                        (sessions[0]["id"],)).fetchone()
                    if v_row and v_row["v"]:
                        v = v_row["v"]
                        if v < 12.8:
                            status = "fail"; detail = f"Charging V {v:.2f}V low"
                        elif v < 13.4:
                            status = "warn"; detail = f"Charging V {v:.2f}V borderline"
                        else:
                            status = "pass"; detail = f"Charging V {v:.2f}V healthy"
                        checks.append({"name": "Alternator / charging",
                                        "status": status, "detail": detail,
                                        "action": {"text": "Alternator issue",
                                                   "link": "/knowledge/issue/alternator-failure"}
                                        if status != "pass" else None})

                    # Coolant
                    cool_max = stats.get("cool_max") or 0
                    if cool_max > 105:
                        checks.append({"name": "Coolant temp (last session)",
                                        "status": "fail",
                                        "detail": f"Peak {cool_max}°C — overheating",
                                        "action": {"text": "Overheat walkthrough",
                                                   "link": "/walkthrough/overheating-diag"}})
                    elif cool_max > 100:
                        checks.append({"name": "Coolant temp (last session)",
                                        "status": "warn",
                                        "detail": f"Peak {cool_max}°C — watch"})
                    elif cool_max > 0:
                        checks.append({"name": "Coolant temp (last session)",
                                        "status": "pass",
                                        "detail": f"Peak {cool_max}°C"})
                else:
                    checks.append({"name": "OBD session data", "status": "warn",
                                    "detail": "No sessions recorded yet — plug in the adapter + run yaris-diag dash"})
        except Exception as e:
            checks.append({"name": "OBD session data", "status": "warn",
                            "detail": f"DB read error: {e}"})

        # Odometer / maintenance
        km = latest_km()
        if km is None:
            checks.append({"name": "Odometer", "status": "warn",
                            "detail": "Not recorded — go to /overview to set",
                            "action": {"text": "Set odometer", "link": "/overview"}})
        else:
            upcoming = service_status()
            overdue = [u for u in upcoming if u["status"] == "OVERDUE"]
            due_soon = [u for u in upcoming if u["status"] == "due soon"]
            if overdue:
                checks.append({"name": "Maintenance", "status": "fail",
                                "detail": f"{len(overdue)} interval(s) OVERDUE",
                                "action": {"text": "See schedule",
                                           "link": "/knowledge/maintenance"}})
            elif due_soon:
                checks.append({"name": "Maintenance", "status": "warn",
                                "detail": f"{len(due_soon)} interval(s) due soon"})
            else:
                checks.append({"name": "Maintenance", "status": "pass",
                                "detail": "All intervals on schedule"})

        # Known critical: Takata recalls
        checks.append({
            "name": "Open recalls", "status": "warn",
            "detail": "3 Takata airbag recalls apply to your hardware — see /knowledge/tsbs",
            "action": {"text": "View recalls", "link": "/knowledge/tsbs"},
        })

        # Manual items
        for name, link in [
            ("Tire pressure (visual)", None),
            ("Oil level (dipstick)", None),
            ("Coolant level (overflow tank)", None),
            ("Windshield washer fluid", None),
        ]:
            checks.append({"name": name, "status": "warn",
                            "detail": "Visual check before trip — can't verify from OBD"})

        # Verdict
        fails = sum(1 for c in checks if c["status"] == "fail")
        warns = sum(1 for c in checks if c["status"] == "warn")
        if fails:
            verdict = "stop"
            summary = f"{fails} failing check{'s' if fails != 1 else ''} — address before driving"
        elif warns > 3:
            verdict = "caution"
            summary = f"{warns} caution item{'s' if warns != 1 else ''} — review above"
        else:
            verdict = "go"
            summary = "All automatic checks pass. Don't forget the visual items."

        self._send_json({"verdict": verdict, "summary": summary, "checks": checks})

    # ── /services — service log & cost tracker ───────────────────
    def _serve_services_page(self):
        body = '''<main>
          <h1>Service log &amp; cost tracker</h1>
          <p style="color:#8b949e;">Record repairs and services as you do them. Tracks total cost of ownership + km-since-last for each type.</p>

          <h2>Add new service</h2>
          <div class="card" style="margin-bottom:14px;">
            <div style="display:grid;grid-template-columns:120px 1fr;gap:8px 12px;align-items:center;">
              <label>Date</label>
              <input type="date" id="f-date">
              <label>Mileage (km)</label>
              <input type="number" id="f-km" placeholder="145000">
              <label>Type</label>
              <select id="f-type" style="background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 8px;border-radius:4px;">
                <option value="oil_change">Oil + filter</option>
                <option value="air_filter">Air filter</option>
                <option value="cabin_filter">Cabin air filter</option>
                <option value="spark_plugs">Spark plugs</option>
                <option value="brake_pads">Brake pads</option>
                <option value="brake_fluid">Brake fluid flush</option>
                <option value="coolant">Coolant flush</option>
                <option value="transmission">Transmission fluid</option>
                <option value="thermostat">Thermostat</option>
                <option value="water_pump">Water pump</option>
                <option value="maf_clean">MAF clean</option>
                <option value="maf_replace">MAF replace</option>
                <option value="battery">Battery</option>
                <option value="tires">Tires</option>
                <option value="alignment">Alignment</option>
                <option value="inspection">Safety inspection</option>
                <option value="other">Other</option>
              </select>
              <label>Parts cost ($)</label>
              <input type="number" step="0.01" id="f-parts" placeholder="8.50">
              <label>Labor cost ($)</label>
              <input type="number" step="0.01" id="f-labor" placeholder="0">
              <label>Where</label>
              <select id="f-where" style="background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 8px;border-radius:4px;">
                <option>DIY</option>
                <option>Dealer</option>
                <option>Independent shop</option>
                <option>Quick lube</option>
              </select>
              <label>Notes</label>
              <textarea id="f-notes" rows="2" style="background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 8px;border-radius:4px;"></textarea>
            </div>
            <div style="margin-top:12px;display:flex;gap:10px;align-items:center;">
              <button onclick="addService()" style="background:#238636;color:white;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;">+ Add service</button>
              <span id="add-status" style="color:#8b949e;font-size:12px;"></span>
            </div>
          </div>

          <h2 id="stats-heading">Total cost of ownership</h2>
          <div class="row" id="cost-summary"></div>

          <h2>Service history</h2>
          <div class="card">
            <table id="t-services">
              <thead><tr><th>date</th><th>km</th><th>type</th><th>parts</th><th>labor</th><th>total</th><th>where</th><th>notes</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </main>
        <script>
        function load() {
          fetch('/services_data').then(r=>r.json()).then(d => {
            // Summary cards
            const cs = document.getElementById('cost-summary');
            cs.innerHTML = `
              <div class="card"><div class="label">Total spent</div><div class="value">$${d.total.toFixed(2)}</div></div>
              <div class="card"><div class="label">Services recorded</div><div class="value">${d.services.length}</div></div>
              <div class="card"><div class="label">Cost per km</div><div class="value">$${d.cost_per_km.toFixed(3)}</div></div>
              <div class="card"><div class="label">Avg per service</div><div class="value">$${d.avg.toFixed(2)}</div></div>
            `;
            const tbody = document.querySelector('#t-services tbody');
            tbody.innerHTML = d.services.slice().reverse().map(s => {
              const total = (s.parts || 0) + (s.labor || 0);
              return `<tr>
                <td>${s.date}</td>
                <td style="text-align:right;">${s.km ? s.km.toLocaleString() : ''}</td>
                <td>${s.type.replace(/_/g, ' ')}</td>
                <td style="text-align:right;">$${(s.parts||0).toFixed(2)}</td>
                <td style="text-align:right;">$${(s.labor||0).toFixed(2)}</td>
                <td style="text-align:right;font-weight:600;">$${total.toFixed(2)}</td>
                <td>${s.where||''}</td>
                <td style="color:#8b949e;font-size:12px;">${s.notes||''}</td>
              </tr>`;
            }).join('') || '<tr><td colspan="8">no services logged yet</td></tr>';
          });
        }
        function addService() {
          const body = new URLSearchParams();
          body.append('date', document.getElementById('f-date').value || new Date().toISOString().slice(0,10));
          body.append('km', document.getElementById('f-km').value || '0');
          body.append('type', document.getElementById('f-type').value);
          body.append('parts', document.getElementById('f-parts').value || '0');
          body.append('labor', document.getElementById('f-labor').value || '0');
          body.append('where', document.getElementById('f-where').value);
          body.append('notes', document.getElementById('f-notes').value);
          fetch('/services/add', {method:'POST', body,
            headers:{'Content-Type':'application/x-www-form-urlencoded'}})
          .then(r=>r.json()).then(d => {
            if (d.ok) {
              document.getElementById('add-status').textContent = '✓ added';
              // clear form
              ['f-km','f-parts','f-labor','f-notes'].forEach(id => document.getElementById(id).value = '');
              load();
            } else {
              document.getElementById('add-status').textContent = '✗ ' + (d.error || 'error');
            }
          });
        }
        // Pre-fill today's date
        document.getElementById('f-date').value = new Date().toISOString().slice(0,10);
        load();
        </script>'''
        page = render_page(body, title="Services")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_services_data(self):
        services_file = os.path.join(REPORT_DIR, "services.json")
        services = []
        if os.path.exists(services_file):
            try:
                with open(services_file) as f:
                    services = json.load(f)
            except Exception:
                services = []
        total = sum((s.get("parts", 0) or 0) + (s.get("labor", 0) or 0) for s in services)
        km_span = 0
        if len(services) >= 2:
            kms = [s.get("km", 0) or 0 for s in services if s.get("km")]
            if len(kms) >= 2:
                km_span = max(kms) - min(kms)
        cost_per_km = total / km_span if km_span > 0 else 0
        avg = total / len(services) if services else 0
        self._send_json({
            "services": services, "total": total,
            "cost_per_km": cost_per_km, "avg": avg,
        })

    def _handle_service_add(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        import urllib.parse as up
        params = up.parse_qs(body)
        services_file = os.path.join(REPORT_DIR, "services.json")
        services = []
        if os.path.exists(services_file):
            try:
                with open(services_file) as f:
                    services = json.load(f)
            except Exception: services = []
        try:
            services.append({
                "date": params.get("date", [""])[0],
                "km": int(params.get("km", ["0"])[0]),
                "type": params.get("type", [""])[0],
                "parts": float(params.get("parts", ["0"])[0]),
                "labor": float(params.get("labor", ["0"])[0]),
                "where": params.get("where", [""])[0],
                "notes": params.get("notes", [""])[0],
            })
        except ValueError as e:
            self._send_json({"error": f"bad value: {e}"}); return
        os.makedirs(os.path.dirname(services_file), exist_ok=True)
        with open(services_file, "w") as f:
            json.dump(services, f, indent=2)
        self._send_json({"ok": True, "count": len(services)})

    # ── /search — global search ──────────────────────────────────
    def _serve_global_search_page(self):
        body = '''<main>
          <h1>Search everything</h1>
          <input type="search" id="q" placeholder="Type to search across issues, procedures, specs, DTCs, parts, symptoms, sessions…"
                 autofocus oninput="go()"
                 style="width:100%;font-size:16px;padding:10px;margin-bottom:16px;">
          <div id="results"></div>
        </main>
        <script>
        let timer = null;
        function go() {
          clearTimeout(timer);
          timer = setTimeout(doSearch, 200);
        }
        function doSearch() {
          const q = document.getElementById('q').value.trim();
          if (q.length < 2) { document.getElementById('results').innerHTML = ''; return; }
          fetch('/search_data?q=' + encodeURIComponent(q)).then(r=>r.json()).then(d => {
            if (!d.results.length) {
              document.getElementById('results').innerHTML = '<p style="color:#8b949e;">no matches</p>';
              return;
            }
            const grouped = {};
            d.results.forEach(r => (grouped[r.type] = grouped[r.type] || []).push(r));
            document.getElementById('results').innerHTML = Object.keys(grouped).map(t => `
              <h2 style="color:#8b949e;">${t} (${grouped[t].length})</h2>
              <div class="row">${grouped[t].map(r => `
                <a href="${r.link}" class="card" style="text-decoration:none;">
                  <div style="font-weight:600;">${r.name}</div>
                  <div style="color:#8b949e;font-size:12px;margin-top:4px;">${r.detail || ''}</div>
                </a>`).join('')}
              </div>`).join('');
          });
        }
        </script>'''
        page = render_page(body, title="Search")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_global_search_data(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0].lower().strip()
        results = []
        if len(q) < 2:
            self._send_json({"results": []}); return
        from .knowledge import ISSUES, PROCEDURES, SPECS, PARTS
        from .dtc_db import DTC_DATABASE
        from .symptoms import SYMPTOMS
        from .walkthroughs import WALKTHROUGHS
        for slug, i in ISSUES.items():
            hay = f"{i.name} {i.system} {i.notes} {' '.join(i.symptoms)} {' '.join(i.related_dtcs)}".lower()
            if q in hay:
                results.append({"type": "issue", "name": i.name, "link": f"/knowledge/issue/{slug}",
                                 "detail": f"#{i.rank} · {i.system}"})
        for slug, p in PROCEDURES.items():
            if q in (p.name + p.system).lower():
                results.append({"type": "procedure", "name": p.name,
                                 "link": f"/knowledge/procedure/{slug}",
                                 "detail": f"{p.system} · ~{p.time_minutes} min · {'★'*p.difficulty}"})
        for s in SPECS:
            hay = f"{s.item} {s.value} {s.unit} {s.system}".lower()
            if q in hay:
                results.append({"type": "spec", "name": s.item,
                                 "link": "/knowledge/specs",
                                 "detail": f"{s.value} {s.unit} · {s.system}"})
        for code, e in DTC_DATABASE.items():
            if q in (code + " " + e.title).lower():
                results.append({"type": "DTC", "name": f"{code}: {e.title}",
                                 "link": f"/dtc?code={code}",
                                 "detail": f"{e.severity} · {e.system}"})
        for slug, p in PARTS.items():
            if q in (p.name + (p.oem or "")).lower():
                results.append({"type": "part", "name": p.name, "link": "/knowledge/parts",
                                 "detail": f"OEM: {p.oem or '—'} · ${p.price_usd[0]}-${p.price_usd[1]}"})
        for slug, sym in SYMPTOMS.items():
            if q in (sym.label + sym.description).lower():
                results.append({"type": "symptom", "name": sym.label,
                                 "link": "/diagnose",
                                 "detail": sym.description[:80]})
        for slug, w in WALKTHROUGHS.items():
            if q in (w.name + w.summary).lower():
                results.append({"type": "walkthrough", "name": w.name,
                                 "link": f"/walkthrough/{slug}",
                                 "detail": w.summary})
        self._send_json({"results": results[:80]})

    # ── /forecast ─────────────────────────────────────────────────
    def _serve_forecast_page(self):
        body = '''<main>
          <h1>Predictive trend forecasting</h1>
          <p style="color:#8b949e;">Linear regression of your historical LTFT, MAF ratio, and charging voltage. Projects when each metric crosses a critical threshold at the current rate of change.</p>
          <div id="content">running analysis…</div>
        </main>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script>
        fetch('/forecast_data').then(r=>r.json()).then(data => {
          let html = '<div class="row">';
          data.forecasts.forEach((f, idx) => {
            const color = f.days_until_threshold != null && f.days_until_threshold < 30 ? '#f85149' :
                         (f.days_until_threshold != null && f.days_until_threshold < 90 ? '#d29922' : '#3fb950');
            const confBadge = f.confidence === 'high' ? '✓ high confidence' :
                              (f.confidence === 'low' ? '~ low confidence' : 'insufficient data');
            let daysText = 'never at current rate';
            if (f.days_until_threshold != null) {
              if (f.days_until_threshold <= 0) daysText = 'ALREADY PAST threshold';
              else daysText = `~${Math.round(f.days_until_threshold)} days at current rate`;
            }
            html += `
              <div class="card" style="border-left:4px solid ${color};">
                <div class="label">${f.metric}</div>
                <div class="value" style="font-size:20px;">${f.current_value.toFixed(2)}</div>
                <div style="color:#8b949e;font-size:12px;">threshold: ${f.threshold}</div>
                <div style="color:${color};font-weight:500;margin-top:4px;">${daysText}</div>
                <div style="color:#8b949e;font-size:11px;margin-top:4px;">
                  slope ${f.slope_per_day.toFixed(4)}/day · R²=${f.r2.toFixed(2)} · ${f.sessions_used} sessions · ${confBadge}
                </div>
                <div style="margin-top:10px;height:140px;"><canvas id="c-${idx}"></canvas></div>
              </div>`;
          });
          html += '</div>';
          document.getElementById('content').innerHTML = html;
          data.forecasts.forEach((f, idx) => {
            new Chart(document.getElementById('c-' + idx).getContext('2d'), {
              type: 'line',
              data: {
                labels: f.history.map(h => h.date.slice(5)),
                datasets: [{
                  label: f.metric,
                  data: f.history.map(h => h.value),
                  borderColor: '#58a6ff', tension: 0.3, pointRadius: 3,
                }]
              },
              options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                plugins: {legend: {display: false}},
                scales: {
                  x: {ticks: {color:'#8b949e',font:{size:9}}, grid:{color:'#30363d'}},
                  y: {ticks: {color:'#8b949e',font:{size:9}}, grid:{color:'#30363d'}},
                }
              }
            });
          });
        });
        </script>'''
        page = render_page(body, title="Forecast")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_forecast_data(self):
        from .analytics import forecast_ltft, forecast_maf_ratio, forecast_charging
        forecasts = []
        for fn in [forecast_ltft, forecast_maf_ratio, forecast_charging]:
            f = fn()
            forecasts.append({
                "metric": f.metric, "current_value": f.current_value,
                "slope_per_day": f.slope_per_day, "r2": f.r2,
                "threshold": f.threshold,
                "days_until_threshold": f.days_until_threshold,
                "confidence": f.confidence,
                "sessions_used": f.sessions_used,
                "history": f.history,
            })
        self._send_json({"forecasts": forecasts})

    # ── /anomalies ────────────────────────────────────────────────
    def _serve_anomalies_page(self):
        body = '''<main>
          <h1>Anomaly detection</h1>
          <p style="color:#8b949e;">Learned personal baselines from your historical idle samples. Flags readings in the latest session that deviate ≥2.5 IQRs from your normal — not a static threshold, but <b>unusual for your specific car</b>.</p>
          <div id="content">learning baselines…</div>
        </main>
        <script>
        fetch('/anomalies_data').then(r=>r.json()).then(d => {
          let html = '<h2>Personal baselines (idle RPM 600-900)</h2><div class="card"><table>';
          html += '<thead><tr><th>PID</th><th>n</th><th>median</th><th>IQR</th><th>p10</th><th>p90</th><th>normal band</th></tr></thead><tbody>';
          Object.entries(d.baselines).forEach(([label, b]) => {
            html += `<tr>
              <td><b>${label}</b></td>
              <td>${b.n}</td>
              <td>${b.median.toFixed(2)}</td>
              <td>${b.iqr.toFixed(2)}</td>
              <td>${b.p10.toFixed(2)}</td>
              <td>${b.p90.toFixed(2)}</td>
              <td>${b.lower.toFixed(2)} – ${b.upper.toFixed(2)}</td>
            </tr>`;
          });
          html += '</tbody></table></div>';
          html += `<h2>Anomalies in latest session (#${d.session_id})</h2>`;
          if (!d.anomalies.length) {
            html += '<p style="color:#3fb950;">✓ No anomalies detected — everything within your personal normal range.</p>';
          } else {
            html += '<div class="card"><table>';
            html += '<thead><tr><th>time</th><th>PID</th><th>value</th><th>median</th><th>σ (IQR)</th><th>direction</th></tr></thead><tbody>';
            d.anomalies.forEach(a => {
              const color = a.direction === 'above' ? '#f85149' : '#d29922';
              html += `<tr>
                <td style="font-size:11px;color:#8b949e;">${a.timestamp}</td>
                <td><b>${a.pid}</b></td>
                <td style="color:${color};font-weight:600;">${a.value.toFixed(2)}</td>
                <td>${a.baseline_median.toFixed(2)}</td>
                <td style="color:${color};">${a.distance_iqrs.toFixed(1)}×</td>
                <td>${a.direction}</td>
              </tr>`;
            });
            html += '</tbody></table></div>';
          }
          document.getElementById('content').innerHTML = html;
        });
        </script>'''
        page = render_page(body, title="Anomalies")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_anomalies_data(self):
        from .analytics import compute_baselines, find_anomalies
        from .store import Store, DEFAULT_DB
        baselines = compute_baselines()
        session_id = None
        anomalies = []
        try:
            with Store(DEFAULT_DB) as s:
                sessions = s.sessions(vin=VIN, days=90)
                if sessions:
                    session_id = sessions[0]["id"]
                    anomalies = find_anomalies(session_id)
        except Exception:
            pass
        self._send_json({
            "baselines": {k: b.__dict__ for k, b in baselines.items()},
            "session_id": session_id,
            "anomalies": [a.__dict__ for a in anomalies],
        })

    # ── /timeline ─────────────────────────────────────────────────
    def _serve_timeline_page(self):
        body = '''<main>
          <h1>Life timeline</h1>
          <p style="color:#8b949e;">Every event in your car's documented life, chronologically. Sessions, services, DTCs, alerts, odometer readings, notes.</p>
          <div id="content">loading timeline…</div>
        </main>
        <script>
        fetch('/timeline_data').then(r=>r.json()).then(events => {
          const ICON = {
            session: '📊', service: '🔧', dtc: '⚠️', alert: '🚨',
            odometer: '🚗', note: '📝'
          };
          const SEV_COLOR = {
            critical: '#f85149', warn: '#d29922', success: '#3fb950', info: '#58a6ff'
          };
          const html = events.map(e => {
            const color = SEV_COLOR[e.severity] || '#8b949e';
            return `
              <div style="display:grid;grid-template-columns:140px 24px 1fr;gap:10px;align-items:start;padding:10px 0;border-left:2px solid #30363d;padding-left:20px;position:relative;">
                <div style="color:#8b949e;font-size:11px;font-variant-numeric:tabular-nums;">${e.timestamp.replace('T', ' ').slice(0, 16)}</div>
                <div style="font-size:20px;">${ICON[e.category] || '•'}</div>
                <div>
                  <div style="font-weight:600;color:${color};">${e.title}</div>
                  <div style="color:#8b949e;font-size:12px;margin-top:2px;">${e.detail}</div>
                  ${e.ref_link ? `<div style="margin-top:4px;"><a href="${e.ref_link}" style="font-size:12px;">view →</a></div>` : ''}
                </div>
              </div>`;
          }).join('');
          document.getElementById('content').innerHTML =
            `<div class="card" style="padding:0;">${html || '<div style="padding:14px;">No events yet.</div>'}</div>`;
        });
        </script>'''
        page = render_page(body, title="Timeline")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_timeline_data(self):
        from .analytics import build_timeline
        events = build_timeline(days=365)
        self._send_json([{
            "timestamp": e.timestamp, "category": e.category,
            "title": e.title, "detail": e.detail,
            "ref_id": e.ref_id, "ref_link": e.ref_link,
            "severity": e.severity,
        } for e in events])

    # ── /dyno ─────────────────────────────────────────────────────
    def _serve_dyno_page(self):
        body = '''<main>
          <h1>Dyno / power estimator</h1>
          <p style="color:#8b949e;">Estimates engine output from MAF flow. BHP = (MAF/AFR × HHV × η_combined) / 746. Uses samples with throttle ≥ 25% (excludes cruise/decel). <b>Rough</b> — not a substitute for a real dyno, but shows the curve shape.</p>
          <div id="content">computing…</div>
        </main>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script>
        fetch('/dyno_data').then(r=>r.json()).then(d => {
          let html = `
            <div class="row">
              <div class="card"><div class="label">Samples used</div><div class="value">${d.samples}</div></div>
              <div class="card"><div class="label">Peak BHP observed</div><div class="value">${d.bins.length ? Math.max(...d.bins.map(b=>b.bhp_peak)).toFixed(1) : '—'}</div></div>
              <div class="card"><div class="label">Peak Nm observed</div><div class="value">${d.bins.length ? Math.max(...d.bins.map(b=>b.nm_peak)).toFixed(1) : '—'}</div></div>
              <div class="card" style="border-left:3px solid #d29922;">
                <div class="label">Factory spec</div>
                <div class="value" style="font-size:14px;">${d.factory.bhp_peak} bhp @ ${d.factory.bhp_rpm}</div>
                <div style="color:#8b949e;font-size:12px;">${d.factory.nm_peak} Nm @ ${d.factory.nm_rpm} · ${d.factory.engine}</div>
              </div>
            </div>
            <div class="card" style="margin-top:12px;"><div style="height:260px;"><canvas id="c-dyno"></canvas></div></div>
            <div class="card" style="margin-top:12px;"><table><thead><tr><th>RPM band</th><th>n</th><th>avg bhp</th><th>peak bhp</th><th>avg Nm</th><th>peak Nm</th></tr></thead><tbody>`;
          d.bins.forEach(b => {
            html += `<tr>
              <td><b>${b.rpm}-${b.rpm+500}</b></td>
              <td>${b.n}</td>
              <td>${b.bhp_avg}</td>
              <td style="color:#58a6ff;font-weight:600;">${b.bhp_peak}</td>
              <td>${b.nm_avg}</td>
              <td style="color:#3fb950;font-weight:600;">${b.nm_peak}</td>
            </tr>`;
          });
          html += '</tbody></table></div>';
          document.getElementById('content').innerHTML = html;
          if (d.bins.length) {
            new Chart(document.getElementById('c-dyno').getContext('2d'), {
              type: 'line',
              data: {
                labels: d.bins.map(b => `${b.rpm}-${b.rpm+500}`),
                datasets: [
                  {label: 'BHP peak', data: d.bins.map(b=>b.bhp_peak), borderColor:'#58a6ff', tension:0.3, yAxisID:'y'},
                  {label: 'BHP avg', data: d.bins.map(b=>b.bhp_avg), borderColor:'#58a6ff', borderDash:[4,4], tension:0.3, yAxisID:'y'},
                  {label: 'Nm peak', data: d.bins.map(b=>b.nm_peak), borderColor:'#3fb950', tension:0.3, yAxisID:'y2'},
                  {label: 'Factory peak BHP', data: d.bins.map(_=>d.factory.bhp_peak), borderColor:'#d29922', borderDash:[2,2], tension:0, pointRadius:0, yAxisID:'y'},
                ]
              },
              options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                plugins: {legend: {labels:{color:'#c9d1d9',font:{size:11}}}},
                scales: {
                  x: {ticks:{color:'#8b949e',font:{size:10}}, grid:{color:'#30363d'}},
                  y: {position:'left', title:{display:true,text:'BHP',color:'#58a6ff'}, ticks:{color:'#8b949e'}, grid:{color:'#30363d'}},
                  y2: {position:'right', title:{display:true,text:'Nm',color:'#3fb950'}, ticks:{color:'#8b949e'}, grid:{display:false}},
                }
              }
            });
          }
        });
        </script>'''
        page = render_page(body, title="Dyno")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_dyno_data(self):
        import urllib.parse as up
        import glob as _glob
        params = up.parse_qs(up.urlparse(self.path).query)
        csv_path = params.get("csv", [""])[0]
        if not csv_path:
            # Default to newest drive_live CSV
            paths = sorted(_glob.glob(os.path.join(REPORT_DIR, "drive_live_*.csv")),
                            key=os.path.getmtime, reverse=True)
            csv_path = paths[0] if paths else ""
        from .analytics import power_curve_from_csv
        result = power_curve_from_csv(csv_path) if csv_path else {"bins": [], "samples": 0, "factory": {}}
        result["csv_used"] = csv_path
        self._send_json(result)

    # ── /replay ───────────────────────────────────────────────────
    def _serve_replay_page(self):
        import glob as _glob
        csvs = sorted(_glob.glob(os.path.join(REPORT_DIR, "*.csv")),
                      key=os.path.getmtime, reverse=True)
        options = "".join(
            f'<option value="{html.escape(p)}">{html.escape(os.path.basename(p))}</option>'
            for p in csvs[:20]
        )
        body = f'''<main>
          <h1>Replay engine</h1>
          <p style="color:#8b949e;">Replay any historical CSV at accelerated speed. Watch what happened during a past drive with the live-dashboard gauges and charts.</p>

          <div class="card" style="margin-bottom:12px;">
            <div style="display:grid;grid-template-columns:80px 1fr;gap:8px 12px;align-items:center;">
              <label>CSV file</label>
              <select id="csv-select" style="background:#0d1117;color:#c9d1d9;border:1px solid #30363d;padding:6px;border-radius:4px;">
                {options}
              </select>
              <label>Speed</label>
              <select id="speed" style="background:#0d1117;color:#c9d1d9;border:1px solid #30363d;padding:6px;border-radius:4px;">
                <option value="1">1× (realtime)</option>
                <option value="5" selected>5×</option>
                <option value="20">20×</option>
                <option value="100">100×</option>
              </select>
              <label>Position</label>
              <div style="display:flex;gap:8px;align-items:center;">
                <input type="range" id="seek" min="0" max="100" value="0" style="flex:1;">
                <span id="seek-label" style="color:#8b949e;font-size:12px;font-variant-numeric:tabular-nums;">—</span>
              </div>
            </div>
            <div style="margin-top:10px;display:flex;gap:8px;">
              <button onclick="startReplay()" id="btn-start" style="background:#238636;color:white;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;">▶ Play</button>
              <button onclick="pauseReplay()" id="btn-pause" style="background:#d29922;color:white;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;" disabled>⏸ Pause</button>
              <button onclick="stopReplay()" style="background:#30363d;color:#c9d1d9;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;">⏹ Stop</button>
            </div>
          </div>

          <!-- Mini gauges -->
          <div class="row">
            <div class="card"><div class="label">RPM</div><div class="value" id="g-rpm">—</div></div>
            <div class="card"><div class="label">Speed km/h</div><div class="value" id="g-speed">—</div></div>
            <div class="card"><div class="label">MAF g/s</div><div class="value" id="g-maf">—</div></div>
            <div class="card"><div class="label">LTFT %</div><div class="value" id="g-ltft">—</div></div>
            <div class="card"><div class="label">Coolant °C</div><div class="value" id="g-coolant">—</div></div>
            <div class="card"><div class="label">Batt V</div><div class="value" id="g-ctlv">—</div></div>
          </div>

          <div class="card" style="margin-top:12px;">
            <div style="height:200px;"><canvas id="c-replay"></canvas></div>
          </div>
        </main>

        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script>
        let rows = [];
        let idx = 0;
        let timer = null;

        const chart = new Chart(document.getElementById('c-replay').getContext('2d'), {{
          type: 'line',
          data: {{labels: [], datasets: [
            {{label:'RPM', data:[], borderColor:'#58a6ff', tension:0.3, yAxisID:'y'}},
            {{label:'LTFT %', data:[], borderColor:'#f85149', tension:0.3, yAxisID:'y2'}},
            {{label:'MAF g/s', data:[], borderColor:'#3fb950', tension:0.3, yAxisID:'y2'}},
          ]}},
          options: {{
            responsive:true, maintainAspectRatio:false, animation:false,
            plugins:{{legend:{{labels:{{color:'#c9d1d9',font:{{size:10}}}}}}}},
            scales:{{
              x:{{ticks:{{color:'#8b949e',font:{{size:9}}}}, grid:{{color:'#30363d'}}}},
              y:{{position:'left', ticks:{{color:'#58a6ff'}}, grid:{{color:'#30363d'}}}},
              y2:{{position:'right', ticks:{{color:'#f85149'}}, grid:{{display:false}}}},
            }}, elements:{{point:{{radius:0}}}},
          }}
        }});

        function loadCsv() {{
          const path = document.getElementById('csv-select').value;
          if (!path) return;
          fetch('/replay_data?csv=' + encodeURIComponent(path)).then(r => r.json()).then(d => {{
            rows = d.rows;
            idx = 0;
            chart.data.labels = []; chart.data.datasets.forEach(ds => ds.data = []);
            chart.update();
            updateSeek();
          }});
        }}

        function renderFrame(r) {{
          document.getElementById('g-rpm').textContent = r.rpm ? r.rpm.toFixed(0) : '—';
          document.getElementById('g-speed').textContent = r.speed != null ? r.speed.toFixed(0) : '—';
          document.getElementById('g-maf').textContent = r.maf != null ? r.maf.toFixed(2) : '—';
          document.getElementById('g-ltft').textContent = r.ltft != null ? r.ltft.toFixed(1) + '%' : '—';
          document.getElementById('g-coolant').textContent = r.coolant != null ? r.coolant.toFixed(0) : '—';
          document.getElementById('g-ctlv').textContent = r.ctlv != null ? r.ctlv.toFixed(2) : '—';

          chart.data.labels.push(idx.toString());
          chart.data.datasets[0].data.push(r.rpm);
          chart.data.datasets[1].data.push(r.ltft);
          chart.data.datasets[2].data.push(r.maf);
          if (chart.data.labels.length > 300) {{
            chart.data.labels.shift();
            chart.data.datasets.forEach(ds => ds.data.shift());
          }}
          chart.update('none');
          updateSeek();
        }}

        function updateSeek() {{
          const pct = rows.length ? (idx / rows.length) * 100 : 0;
          document.getElementById('seek').value = pct;
          document.getElementById('seek-label').textContent =
            rows.length ? `${{idx}} / ${{rows.length}}` : '—';
        }}

        function startReplay() {{
          if (!rows.length) return;
          const speed = parseInt(document.getElementById('speed').value);
          const interval = 1300 / speed; // source is ~1.3s per sample
          document.getElementById('btn-start').disabled = true;
          document.getElementById('btn-pause').disabled = false;
          timer = setInterval(() => {{
            if (idx >= rows.length) {{ stopReplay(); return; }}
            renderFrame(rows[idx]);
            idx++;
          }}, interval);
        }}

        function pauseReplay() {{
          if (timer) {{ clearInterval(timer); timer = null; }}
          document.getElementById('btn-start').disabled = false;
          document.getElementById('btn-pause').disabled = true;
        }}

        function stopReplay() {{
          pauseReplay();
          idx = 0;
          chart.data.labels = []; chart.data.datasets.forEach(ds => ds.data = []);
          chart.update(); updateSeek();
        }}

        document.getElementById('seek').addEventListener('input', e => {{
          if (!rows.length) return;
          idx = Math.floor((e.target.value / 100) * rows.length);
          updateSeek();
        }});
        document.getElementById('csv-select').addEventListener('change', loadCsv);
        loadCsv();
        </script>'''
        page = render_page(body, title="Replay")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_replay_data(self):
        import urllib.parse as up
        path = up.parse_qs(up.urlparse(self.path).query).get("csv", [""])[0]
        rows = []
        if path and os.path.exists(path):
            from .analytics import replay_csv
            for r in replay_csv(path):
                def f(k):
                    try: return float(r.get(k) or 0)
                    except ValueError: return None
                rows.append({
                    "rpm": f("rpm"), "speed": f("speed_kmh"),
                    "maf": f("maf_gs"), "ltft": f("ltft_b1_pct"),
                    "stft": f("stft_b1_pct"), "coolant": f("coolant_c"),
                    "ctlv": f("ctlmod_v"),
                })
        # Cap to 5000 rows to keep payload manageable
        self._send_json({"path": path, "rows": rows[:5000], "n": len(rows)})

    # ── /assistant — NL chat assistant ────────────────────────────
    def _serve_assistant_page(self):
        import urllib.parse as up
        preset_q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0]
        body = f'''<main>
          <h1>💬 Ask about your car</h1>
          <p style="color:#8b949e;">Natural-language queries against your live data + knowledge base. Examples: "what's my LTFT?", "explain P0101", "when is oil due?", "how much have I spent?"</p>

          <div id="chat" style="min-height:200px;margin-bottom:12px;"></div>

          <div style="display:flex;gap:8px;align-items:center;position:sticky;bottom:10px;background:#0d1117;padding:10px 0;">
            <input type="text" id="q" placeholder='Try "explain P0101" or "what happened this week?"'
                   autofocus style="flex:1;padding:10px;font-size:15px;"
                   onkeypress="if(event.key==='Enter')ask()">
            <button onclick="ask()" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;">Ask</button>
          </div>

          <div style="margin-top:20px;color:#8b949e;font-size:12px;">
            <b>Quick-ask chips:</b>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
              {"".join(f'<button onclick="askPreset(\\\'{html.escape(s)}\\\')" style="background:#21262d;color:#c9d1d9;border:1px solid #30363d;padding:4px 10px;border-radius:14px;font-size:12px;cursor:pointer;">{html.escape(s)}</button>' for s in [
                "what is my LTFT?", "explain P0101", "when is oil due?",
                "how much have I spent?", "can I drive?", "forecast LTFT",
                "what happened this week?", "parts for MAF", "oil capacity?",
              ])}
            </div>
          </div>
        </main>
        <script>
        const preset = {json.dumps(preset_q)};
        if (preset) {{
          document.getElementById('q').value = preset;
          setTimeout(ask, 100);
        }}

        function appendMsg(role, text, links) {{
          const chat = document.getElementById('chat');
          const msg = document.createElement('div');
          msg.style.cssText = `padding:10px 12px;border-radius:8px;margin-bottom:8px;
                               background:${{role==='user'?'#1f6feb33':'#161b22'}};
                               border:1px solid #30363d;`;
          const who = document.createElement('div');
          who.style.cssText = 'color:#8b949e;font-size:11px;margin-bottom:4px;';
          who.textContent = role === 'user' ? '👤 You' : '🤖 Yaris Assistant';
          msg.appendChild(who);
          // Render markdown-ish text (bold only)
          const content = document.createElement('div');
          content.innerHTML = text.replace(/\\*\\*(.+?)\\*\\*/g, '<b>$1</b>').replace(/\\n/g, '<br>');
          msg.appendChild(content);
          if (links && links.length) {{
            const lc = document.createElement('div');
            lc.style.cssText = 'margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;';
            links.forEach(l => {{
              const a = document.createElement('a');
              a.href = l.href; a.textContent = '→ ' + l.label;
              a.style.cssText = 'background:#21262d;padding:4px 10px;border-radius:14px;color:#58a6ff;text-decoration:none;font-size:12px;';
              lc.appendChild(a);
            }});
            msg.appendChild(lc);
          }}
          chat.appendChild(msg);
          chat.scrollTop = chat.scrollHeight;
        }}

        function ask() {{
          const q = document.getElementById('q').value.trim();
          if (!q) return;
          document.getElementById('q').value = '';
          appendMsg('user', q);
          fetch('/assistant/ask?q=' + encodeURIComponent(q)).then(r=>r.json()).then(d => {{
            appendMsg('bot', d.text, d.links);
          }}).catch(e => appendMsg('bot', 'Error: ' + e));
        }}
        function askPreset(s) {{
          document.getElementById('q').value = s;
          ask();
        }}
        </script>'''
        page = render_page(body, title="Assistant")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_assistant_ask(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0]
        from .assistant import match_and_answer
        ans = match_and_answer(q)
        self._send_json({
            "text": ans.text,
            "links": ans.links or [],
            "intent": ans.intent,
            "confidence": ans.confidence,
        })

    # ── /trip — trip classification ────────────────────────────────
    def _serve_trip_page(self):
        import glob as _glob
        csvs = sorted(_glob.glob(os.path.join(REPORT_DIR, "*.csv")),
                       key=os.path.getmtime, reverse=True)
        options = "".join(
            f'<option value="{html.escape(p)}">{html.escape(os.path.basename(p))}</option>'
            for p in csvs[:20]
        )
        body = f'''<main>
          <h1>Trip analysis</h1>
          <p style="color:#8b949e;">Segment a drive into phases — idle, city, highway, accel, decel, WOT — with per-phase stats.</p>
          <div class="card" style="margin-bottom:12px;">
            <label>CSV file</label><br>
            <select id="csv" style="width:100%;" onchange="load()">
              {options}
            </select>
          </div>
          <div id="content">select a CSV…</div>
        </main>
        <script>
        const PHASE_COLORS = {{
          idle:'#8b949e', creep:'#58a6ff', city:'#3fb950',
          suburban:'#d29922', highway:'#f85149',
          accel:'#a371f7', decel:'#79c0ff', wot:'#f85149',
          engine_off:'#30363d'
        }};
        function load() {{
          const csv = document.getElementById('csv').value;
          if (!csv) return;
          fetch('/trip_data?csv=' + encodeURIComponent(csv)).then(r=>r.json()).then(d => {{
            if (d.error) {{ document.getElementById('content').innerHTML = '<p>' + d.error + '</p>'; return; }}
            let html = `<div class="row">
              <div class="card"><div class="label">Samples</div><div class="value">${{d.total_samples}}</div></div>
              <div class="card"><div class="label">Total time</div><div class="value">${{(d.total_time_s/60).toFixed(1)}} min</div></div>
              <div class="card"><div class="label">Total distance</div><div class="value">${{d.total_distance_km.toFixed(2)}} km</div></div>
              <div class="card"><div class="label">Phases</div><div class="value">${{d.phases.length}}</div></div>
            </div>`;

            // Horizontal stacked bar: time breakdown
            html += '<h2>Time breakdown</h2><div class="card"><div style="display:flex;height:36px;border-radius:4px;overflow:hidden;">';
            d.phases.forEach(p => {{
              const c = PHASE_COLORS[p.phase] || '#58a6ff';
              html += `<div style="flex:${{p.time_pct}};background:${{c}};display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:600;" title="${{p.phase}}: ${{p.time_pct.toFixed(1)}}%">${{p.time_pct>10?p.phase:''}}</div>`;
            }});
            html += '</div>';
            html += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">';
            d.phases.forEach(p => {{
              const c = PHASE_COLORS[p.phase] || '#58a6ff';
              html += `<span style="font-size:11px;color:#8b949e;"><span style="display:inline-block;width:10px;height:10px;background:${{c}};border-radius:2px;margin-right:4px;"></span>${{p.phase}} ${{p.time_pct.toFixed(1)}}%</span>`;
            }});
            html += '</div></div>';

            html += '<h2>Per-phase stats</h2><div class="card"><table>';
            html += '<thead><tr><th>phase</th><th>time</th><th>dist</th><th>avg RPM</th><th>avg speed</th><th>avg MAF</th><th>avg LTFT</th><th>avg throttle</th></tr></thead><tbody>';
            d.phases.forEach(p => {{
              const c = PHASE_COLORS[p.phase] || '#58a6ff';
              html += `<tr>
                <td><b style="color:${{c}};">${{p.phase}}</b></td>
                <td>${{(p.time_s/60).toFixed(1)}} min</td>
                <td>${{p.distance_km.toFixed(2)}} km</td>
                <td>${{p.avg_rpm}}</td>
                <td>${{p.avg_speed}}</td>
                <td>${{p.avg_maf}}</td>
                <td>${{p.avg_ltft}}</td>
                <td>${{p.avg_throttle}}%</td>
              </tr>`;
            }});
            html += '</tbody></table></div>';
            document.getElementById('content').innerHTML = html;
          }});
        }}
        load();
        </script>'''
        page = render_page(body, title="Trip analysis")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_trip_data(self):
        import urllib.parse as up
        path = up.parse_qs(up.urlparse(self.path).query).get("csv", [""])[0]
        from .trip_class import classify_trip
        self._send_json(classify_trip(path))

    # ── /crossref — parts cross-reference ────────────────────────
    def _serve_crossref_page(self):
        body = '''<main>
          <h1>Parts cross-reference</h1>
          <p style="color:#8b949e;">Enter any part number — Toyota OEM, Denso, Aisin, Fram, Wix, Akebono, NGK — and find all the equivalents. 25+ parts covered.</p>

          <input type="search" id="q" placeholder="e.g. 04152-YZZA1, CH9911, 57212, ILKAR7L11, WPT-181"
                 oninput="search()" style="width:100%;font-size:16px;padding:10px;margin-bottom:16px;">

          <div id="results"></div>
        </main>
        <script>
        let timer = null;
        function search() {
          clearTimeout(timer);
          timer = setTimeout(doSearch, 200);
        }
        function doSearch() {
          const q = document.getElementById('q').value.trim();
          const url = q ? '/crossref_data?q=' + encodeURIComponent(q) : '/crossref_data';
          fetch(url).then(r=>r.json()).then(d => {
            if (!d.results.length) {
              document.getElementById('results').innerHTML = '<p style="color:#8b949e;">no matches</p>';
              return;
            }
            document.getElementById('results').innerHTML = d.results.map(c => {
              let aft = Object.entries(c.equivalents).map(([mfr, nums]) =>
                `<tr><td style="color:#8b949e;">${mfr}</td><td><code>${nums.join(', ')}</code></td></tr>`
              ).join('');
              return `<div class="card" style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <b style="font-size:15px;">${c.category}</b>
                  <span style="color:#3fb950;">$${c.price_oem[0]}-$${c.price_oem[1]}</span>
                </div>
                <div style="color:#8b949e;font-size:12px;margin-top:4px;">${c.description}</div>
                <div style="margin-top:8px;"><b>Toyota OEM:</b> <code>${c.toyota_oem}</code></div>
                <table style="margin-top:8px;">${aft}</table>
                ${c.notes ? `<div style="color:#d29922;font-size:12px;margin-top:6px;">${c.notes}</div>` : ''}
              </div>`;
            }).join('');
          });
        }
        search();
        </script>'''
        page = render_page(body, title="Parts cross-reference")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_crossref_data(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0]
        from .parts_xref import search, CATALOG
        if q:
            self._send_json({"results": search(q)})
        else:
            self._send_json({"results": [{
                "category": c.category, "description": c.description,
                "toyota_oem": c.toyota_oem, "price_oem": list(c.price_oem),
                "equivalents": {k: list(v) for k, v in c.equivalents.items()},
                "notes": c.notes, "matched": [],
            } for c in CATALOG]})

    # ── /digest — weekly markdown digest ────────────────────────
    def _serve_digest_page(self):
        from .digest import generate
        import urllib.parse as up
        days = int(up.parse_qs(up.urlparse(self.path).query).get("days", ["7"])[0])
        text = generate(days=days)
        body = f'''<main>
          <h1>Weekly digest</h1>
          <p style="color:#8b949e;">Auto-generated "state of the car" summary. Pipe to email, print, share.</p>
          <div style="margin-bottom:10px;">
            <label>Period:</label>
            <a href="/digest?days=7" style="background:#21262d;padding:4px 10px;border-radius:4px;margin:0 4px;">7 days</a>
            <a href="/digest?days=30" style="background:#21262d;padding:4px 10px;border-radius:4px;margin:0 4px;">30 days</a>
            <a href="/digest?days=90" style="background:#21262d;padding:4px 10px;border-radius:4px;margin:0 4px;">90 days</a>
          </div>
          <div class="card">
            <pre style="white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:13px;line-height:1.6;margin:0;color:#c9d1d9;">{html.escape(text)}</pre>
          </div>
          <div style="margin-top:10px;color:#8b949e;font-size:12px;">
            Render as markdown: copy the text above and paste into any markdown viewer.
          </div>
        </main>'''
        page = render_page(body, title="Digest")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    # ── /elm-reference — ELM327 capability coverage ──────────────
    def _serve_elm_ref_page(self):
        body = '''<main>
          <h1>ELM327 capability reference</h1>
          <p style="color:#8b949e;">Every AT command + OBD2 service the ELM327 supports, with coverage status. Green = we use it. Yellow = safe but unused (candidate for future work). Red = write/dangerous — intentionally skipped.</p>
          <div id="content">loading…</div>
        </main>
        <script>
        fetch('/elm_coverage_data').then(r=>r.json()).then(d => {
          const stats = d.stats;
          let html = `<div class="row">
            <div class="card"><div class="label">AT commands total</div><div class="value">${stats.at_commands.total}</div></div>
            <div class="card"><div class="label">AT used</div><div class="value" style="color:#3fb950;">${stats.at_commands.used}</div></div>
            <div class="card"><div class="label">AT safe-unused (gaps)</div><div class="value" style="color:#d29922;">${stats.at_commands.safe_unused}</div></div>
            <div class="card"><div class="label">OBD services total</div><div class="value">${stats.obd_services.total}</div></div>
            <div class="card"><div class="label">OBD used</div><div class="value" style="color:#3fb950;">${stats.obd_services.used}</div></div>
            <div class="card"><div class="label">Total coverage</div><div class="value">${stats.combined.used}/${stats.combined.total}</div></div>
          </div>`;

          const renderTable = (title, items) => {
            html += `<h2>${title}</h2><div class="card"><table>
              <thead><tr><th>cmd</th><th>name</th><th>category</th><th>used?</th><th>safety</th><th>description</th></tr></thead><tbody>`;
            items.forEach(c => {
              const usedColor = c.used ? '#3fb950' : (c.safety === 'safe' ? '#d29922' : '#6e7681');
              const safetyColor = {safe:'#3fb950', write:'#d29922', dangerous:'#f85149', deprecated:'#6e7681'}[c.safety] || '#8b949e';
              html += `<tr>
                <td><code>${c.cmd}</code></td>
                <td>${c.name}</td>
                <td style="color:#8b949e;">${c.category}</td>
                <td style="color:${usedColor};">${c.used ? '✓' : '○'}</td>
                <td style="color:${safetyColor};">${c.safety}</td>
                <td style="color:#8b949e;font-size:12px;">${c.description}${c.used_in && c.used_in.length ? '<br><i style="color:#58a6ff;">used in: ' + c.used_in.join(', ') + '</i>' : ''}</td>
              </tr>`;
            });
            html += '</tbody></table></div>';
          };
          renderTable('AT commands (' + d.at_commands.length + ')', d.at_commands);
          renderTable('OBD2 services (' + d.obd_services.length + ')', d.obd_services);

          html += '<h2>Gaps — safe commands we don\\'t use yet</h2><div class="card"><ul>';
          d.unused_safe.forEach(c => {
            html += `<li><b>${c.cmd}</b> — ${c.name}: ${c.description}</li>`;
          });
          html += '</ul></div>';
          document.getElementById('content').innerHTML = html;
        });
        </script>'''
        page = render_page(body, title="ELM327 reference")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_elm_coverage_data(self):
        from .elm_reference import AT_COMMANDS, OBD_SERVICES, coverage_stats, unused_safe_commands
        def _ser(c):
            return {"cmd": c.cmd, "name": c.name, "category": c.category,
                     "description": c.description, "used": c.used,
                     "used_in": c.used_in or [], "safety": c.safety}
        self._send_json({
            "stats": coverage_stats(),
            "at_commands": [_ser(c) for c in AT_COMMANDS],
            "obd_services": [_ser(c) for c in OBD_SERVICES],
            "unused_safe": [_ser(c) for c in unused_safe_commands()],
        })

    # ── /mode19 — Enhanced DTC info ──────────────────────────────
    def _serve_mode19_page(self):
        body = '''<main>
          <h1>Mode 19 — Enhanced DTC information</h1>
          <p style="color:#8b949e;">Richer than Mode 03: each DTC comes with a <b>status byte</b> (8 bits: confirmed / pending / failed-this-cycle / MIL-request / ...) and a fault occurrence counter. Requires live car connection.</p>

          <button onclick="run()" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;">Query Mode 19 now</button>

          <div id="content" style="margin-top:14px;"></div>
        </main>
        <script>
        function run() {
          document.getElementById('content').innerHTML = '<p style="color:#8b949e;">Querying ECM… (requires live adapter connection)</p>';
          fetch('/mode19_data').then(r=>r.json()).then(d => {
            if (d.error) {
              document.getElementById('content').innerHTML = `<div class="card val-err">${d.error}</div>`;
              return;
            }
            let html = `<div class="row">
              <div class="card"><div class="label">DTCs returned</div><div class="value">${d.records.length}</div></div>
              <div class="card"><div class="label">Fault counters</div><div class="value">${d.counters.length}</div></div>
            </div>`;

            html += '<h2>DTCs with status bits</h2><div class="card"><table>';
            html += '<thead><tr><th>code</th><th>status hex</th><th>bit detail</th><th>derived</th></tr></thead><tbody>';
            d.records.forEach(r => {
              const bits = Object.entries(r.status.bits).filter(([k,v]) => v).map(([k,v]) => k).join(', ');
              const sev = r.status.severity;
              const sevColor = {critical:'#f85149', warn:'#d29922', pending:'#58a6ff', info:'#8b949e'}[sev];
              html += `<tr>
                <td><a href="/dtc?code=${r.code}"><b>${r.code}</b></a></td>
                <td><code>0x${r.status.raw.toString(16).padStart(2,'0').toUpperCase()}</code></td>
                <td style="font-size:12px;">${bits || '(no bits set)'}</td>
                <td><span class="pill sev-${sev}" style="background:${sevColor}22;color:${sevColor};">${sev}</span></td>
              </tr>`;
            });
            html += '</tbody></table></div>';

            if (d.counters.length) {
              html += '<h2>Fault detection counters (Service 19 14)</h2><div class="card"><table>';
              html += '<thead><tr><th>code</th><th>counter</th><th>interpretation</th></tr></thead><tbody>';
              d.counters.forEach(c => {
                html += `<tr><td><b>${c.code}</b></td><td>${c.counter}</td><td style="color:#8b949e;">${c.interpretation}</td></tr>`;
              });
              html += '</tbody></table></div>';
            }
            document.getElementById('content').innerHTML = html;
          }).catch(e => {
            document.getElementById('content').innerHTML = `<div class="card val-err">${e}</div>`;
          });
        }
        </script>'''
        page = render_page(body, title="Mode 19")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_mode19_data(self):
        try:
            from .elm import Elm
            from .mode19 import read_enhanced_dtcs, read_fault_detection_counter
            with Elm() as e:
                e.init_can()
                records = read_enhanced_dtcs(e, status_mask=0xFF)
                counters = read_fault_detection_counter(e)
            self._send_json({
                "records": [{"code": r.code, "status": r.status, "raw_hex": r.raw_hex}
                             for r in records],
                "counters": counters,
            })
        except Exception as e:
            self._send_json({"error": f"ECM connection failed: {e}. Car must be on + adapter bound."})

    # ── /ipt — In-use Performance Tracking ───────────────────────
    def _serve_ipt_page(self):
        body = '''<main>
          <h1>IPT — In-use Performance Tracking</h1>
          <p style="color:#8b949e;">Mode 09 PID 08. Per-monitor <b>completion/conditions ratio</b> — how often the ECM actually ran each emissions monitor when conditions were met. CARB/EPA gold standard. Needs live ECM.</p>

          <button onclick="run()" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;">Query IPT now</button>

          <div id="content" style="margin-top:14px;"></div>
        </main>
        <script>
        function run() {
          document.getElementById('content').innerHTML = '<p style="color:#8b949e;">Querying ECM…</p>';
          fetch('/ipt_data').then(r=>r.json()).then(d => {
            if (d.error) {
              document.getElementById('content').innerHTML = `<div class="card val-err">${d.error}</div>`;
              return;
            }
            const ign = d.ign_cycles || 0;
            let html = `<div class="card" style="margin-bottom:12px;">
              <div class="label">Ignition cycles since last code clear</div>
              <div class="value">${ign.toLocaleString()}</div>
            </div>`;

            html += '<h2>Monitor ratios</h2><div class="card"><table>';
            html += '<thead><tr><th>monitor</th><th>completions</th><th>conditions met</th><th>ratio</th><th>visual</th><th>status</th></tr></thead><tbody>';
            d.monitor_ratios.forEach(r => {
              const c = {healthy:'#3fb950', ok:'#58a6ff', low:'#d29922', 'very low':'#f85149', 'never ran':'#8b949e'}[r.status] || '#8b949e';
              const bar = Math.min(100, r.ratio_pct);
              html += `<tr>
                <td><b>${r.monitor}</b></td>
                <td>${r.completions}</td>
                <td>${r.conditions_met}</td>
                <td style="color:${c};font-weight:600;">${r.ratio.toFixed(3)} (${r.ratio_pct}%)</td>
                <td><div style="width:120px;height:10px;background:#21262d;border-radius:5px;overflow:hidden;"><div style="width:${bar}%;height:100%;background:${c};"></div></div></td>
                <td style="color:${c};">${r.status}</td>
              </tr>`;
            });
            html += '</tbody></table></div>';

            html += `<div class="card" style="margin-top:12px;color:#8b949e;">
              <b>How to read this:</b> Healthy cars show ratios ≥0.95. "Completions" = times the ECM ran this monitor to a pass/fail result. "Conditions met" = times the vehicle was in the operating window where this monitor should run. Low ratios mean the ECM skipped the test even though it could have run it — indicates emissions-readiness gaming or a genuine monitor disable condition. Raw hex: <code>${d.raw_hex}</code>
            </div>`;
            document.getElementById('content').innerHTML = html;
          });
        }
        </script>'''
        page = render_page(body, title="IPT")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_ipt_data(self):
        try:
            from .elm import Elm
            from .ipt import read_ipt
            with Elm() as e:
                e.init_can()
                result = read_ipt(e)
            if result is None:
                self._send_json({"error": "ECM didn't return IPT data. Service 09 PID 08 may not be supported."})
                return
            self._send_json({
                "raw_hex": result.raw_hex,
                "fields": result.fields,
                "monitor_ratios": result.monitor_ratios,
                "ign_cycles": result.ign_cycles,
            })
        except Exception as e:
            self._send_json({"error": f"ECM connection failed: {e}"})

    # ── /palette_search — extra dynamic entries ──────────────────
    def _serve_palette_search(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query).get("q", [""])[0].lower().strip()
        from .knowledge import ISSUES
        from .dtc_db import DTC_DATABASE
        results = []
        if len(q) >= 2:
            for code, e in DTC_DATABASE.items():
                if q in code.lower() or q in e.title.lower():
                    results.append({"label": f"🔎 {code}: {e.title}",
                                     "href": f"/dtc?code={code}", "tags": ""})
                    if len(results) >= 6: break
            for slug, issue in ISSUES.items():
                if q in issue.name.lower():
                    results.append({"label": f"📚 {issue.name}",
                                     "href": f"/knowledge/issue/{slug}", "tags": ""})
                    if len(results) >= 12: break
        self._send_json(results)

    # ── /export — full data archive (tar.gz) ─────────────────────
    def _serve_export(self):
        """Build a tar.gz of reports/ + DB + services + odometer + alerts. Stream download."""
        import tarfile
        import io
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Everything in reports/
            for root, dirs, files in os.walk(REPORT_DIR):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, os.path.dirname(REPORT_DIR))
                    try:
                        tar.add(full, arcname=arcname)
                    except Exception: pass
        buf.seek(0)
        body = buf.read()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Disposition",
                         f'attachment; filename="yaris_export_{ts}.tar.gz"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── /import — batch CSV ingestion ────────────────────────────
    def _serve_import_page(self):
        import glob as _glob
        existing = sorted(_glob.glob(os.path.join(REPORT_DIR, "*.csv")),
                           key=os.path.getmtime, reverse=True)
        # Find ones NOT yet in the DB
        from .store import Store, DEFAULT_DB
        imported_notes = set()
        try:
            with Store(DEFAULT_DB) as s:
                for sess in s.sessions(days=365):
                    if sess["note"]:
                        imported_notes.add(sess["note"])
        except Exception:
            pass

        rows = ""
        for p in existing:
            basename = os.path.basename(p)
            is_imported = basename in imported_notes
            size = os.path.getsize(p)
            rows += f'''
              <tr>
                <td><code style="font-size:11px;">{html.escape(basename)}</code></td>
                <td>{size // 1024} KB</td>
                <td>{'<span class="pill ok">imported</span>' if is_imported else '<span class="pill warn">new</span>'}</td>
                <td><button onclick="importOne('{html.escape(p)}')"
                       {'disabled' if is_imported else ''}
                       style="background:#238636;color:white;border:none;padding:4px 10px;border-radius:3px;cursor:pointer;">Import</button></td>
              </tr>'''

        body = f'''<main>
          <h1>Batch CSV import</h1>
          <p style="color:#8b949e;">Ingest any CSV from <code>reports/</code> into the SQLite history store. Import once — duplicates are fine but waste space.</p>

          <div class="card" style="margin-bottom:12px;">
            <button onclick="importAllNew()" style="background:#238636;color:white;border:none;padding:8px 18px;border-radius:4px;cursor:pointer;">▶ Import all unimported</button>
            <span id="bulk-status" style="margin-left:10px;color:#8b949e;font-size:12px;"></span>
          </div>

          <div class="card"><table>
            <thead><tr><th>filename</th><th>size</th><th>status</th><th>action</th></tr></thead>
            <tbody>{rows}</tbody>
          </table></div>

          <h2>Or upload data archive</h2>
          <div class="card">
            <p style="color:#8b949e;font-size:13px;">
              <a href="/export" style="background:#238636;color:white;padding:6px 14px;border-radius:4px;text-decoration:none;">📦 Download full workspace archive (tar.gz)</a>
            </p>
            <p style="color:#8b949e;font-size:12px;margin-top:8px;">
              Contains <code>reports/</code> with all CSVs, SQLite DB, services.json, odometer.json, alerts.json. Portable — untar anywhere to restore.
            </p>
          </div>
        </main>
        <script>
        function importOne(path) {{
          const body = new URLSearchParams();
          body.append('csv', path);
          fetch('/import_csv', {{method:'POST', body,
            headers:{{'Content-Type':'application/x-www-form-urlencoded'}}}})
            .then(r=>r.json()).then(d => {{
              if (d.ok) {{
                window.toast(`✓ Imported: ${{d.path.split('/').pop()}} (#${{d.session_id}}, ${{d.samples}} samples)`, 'success');
                setTimeout(() => location.reload(), 1000);
              }} else {{
                window.toast('Import failed: ' + d.error, 'error');
              }}
            }});
        }}
        function importAllNew() {{
          const unimported = Array.from(document.querySelectorAll('button:not([disabled])'))
            .filter(b => b.textContent === 'Import');
          if (!unimported.length) {{
            window.toast('Nothing to import', 'info'); return;
          }}
          window.toast(`Importing ${{unimported.length}} files…`, 'info');
          let i = 0;
          const next = () => {{
            if (i >= unimported.length) {{ setTimeout(() => location.reload(), 800); return; }}
            unimported[i].click(); i++;
            setTimeout(next, 600);
          }};
          next();
        }}
        </script>'''
        page = render_page(body, title="Import/Export")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _serve_import_list(self):
        # Helper JSON endpoint if needed
        import glob as _glob
        paths = sorted(_glob.glob(os.path.join(REPORT_DIR, "*.csv")),
                        key=os.path.getmtime, reverse=True)
        self._send_json({"files": [{"path": p, "size": os.path.getsize(p)}
                                     for p in paths]})

    def _handle_import_csv(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        import urllib.parse as up
        params = up.parse_qs(body)
        path = params.get("csv", [""])[0]
        if not path or not os.path.exists(path):
            self._send_json({"error": "file not found"}); return
        try:
            from .store import Store, DEFAULT_DB
            with Store(DEFAULT_DB) as s:
                sid = s.import_csv(path, source="imported",
                                    note=os.path.basename(path))
                summ = s.session_summary(sid)
            self._send_json({"ok": True, "path": path, "session_id": sid,
                              "samples": summ.get("stats", {}).get("n", 0)})
        except Exception as e:
            self._send_json({"error": str(e)})

    # ── /vehicles — profile switcher ─────────────────────────────
    def _serve_vehicles_page(self):
        from .vehicle import list_profiles, active_profile
        profiles = list_profiles()
        active = active_profile() or {}
        cards = ""
        for prof_name in profiles:
            try:
                import tomllib
                from pathlib import Path
                path = Path(__file__).parent / "vehicles" / f"{prof_name}.toml"
                with open(path, "rb") as f:
                    cfg = tomllib.load(f)
                ident = cfg.get("identity", {})
                adapter = cfg.get("adapter", {})
                is_active = active.get("identity", {}).get("vin") == ident.get("vin")
                cards += f'''
                  <div class="card" style="margin-bottom:10px;border-left:4px solid {'#3fb950' if is_active else '#30363d'};">
                    <div style="display:flex;justify-content:space-between;align-items:start;">
                      <div>
                        <div style="font-weight:600;font-size:16px;">{html.escape(str(ident.get("model_year","")))} {html.escape(str(ident.get("engine","")))}</div>
                        <div style="color:#8b949e;font-size:13px;margin-top:2px;">{html.escape(str(ident.get("platform","")))} · VIN {html.escape(str(ident.get("vin","")))}</div>
                        <div style="color:#8b949e;font-size:11px;margin-top:4px;">
                          Adapter: {html.escape(str(adapter.get("mac","")))} · SPP ch {adapter.get("spp_channel","?")}
                        </div>
                      </div>
                      <div style="text-align:right;">
                        {"<span class='pill ok'>ACTIVE</span>" if is_active else f'<code style="color:#58a6ff;font-size:11px;">YARIS_VIN={html.escape(prof_name)}</code>'}
                      </div>
                    </div>
                    <div style="font-family:ui-monospace,monospace;font-size:11px;color:#6e7681;margin-top:8px;">
                      protocol={cfg.get("protocol",{}).get("elm_protocol_number")} ·
                      displacement={ident.get("engine_displacement_l")}L ·
                      idle={cfg.get("expected",{}).get("idle_rpm")} ·
                      coolant-warm={cfg.get("expected",{}).get("coolant_warm_c")} ·
                      healthy-MAF-idle={cfg.get("expected",{}).get("maf_idle_gs")}
                    </div>
                  </div>'''
            except Exception as e:
                cards += f'<div class="card val-err">Error loading {prof_name}: {e}</div>'

        body = f'''<main>
          <h1>🚗 Vehicle profiles</h1>
          <p style="color:#8b949e;">Each profile sets adapter / expected ranges / OBD target for a specific car. Switch via environment variable: restart webdash with <code>YARIS_VIN=&lt;profile&gt;</code>.</p>

          {cards}

          <h2>Active profile</h2>
          <div class="card">
            <div style="font-family:ui-monospace,monospace;font-size:12px;color:#c9d1d9;">
              <b>VIN:</b> {html.escape(str(active.get("identity", {}).get("vin", "?")))}<br>
              <b>Engine:</b> {html.escape(str(active.get("identity", {}).get("engine", "?")))}<br>
              <b>Displacement:</b> {active.get("identity", {}).get("engine_displacement_l")}L<br>
              <b>Coolant expected:</b> {active.get("expected", {}).get("coolant_warm_c")}°C<br>
              <b>MAF at idle:</b> {active.get("expected", {}).get("maf_idle_gs")} g/s
            </div>
          </div>

          <h2>Add a new vehicle</h2>
          <div class="card">
            <ol>
              <li>Copy <code>yaris/vehicles/_template.toml</code> to <code>yaris/vehicles/&lt;YOUR_VIN&gt;.toml</code></li>
              <li>Edit the TOML: fill in VIN, engine, expected ranges</li>
              <li>Restart webdash with <code>YARIS_VIN=&lt;YOUR_VIN&gt; python3 -m yaris.webdash</code></li>
              <li>For deep knowledge coverage (issues/walkthroughs/parts), add a <code>&lt;make&gt;_knowledge.py</code> module following the mini_knowledge.py pattern</li>
            </ol>
          </div>

          <h2>Built-in knowledge coverage</h2>
          <div class="row">
            <div class="card"><div class="label">Yaris-specific issues</div>
              <div class="value">20</div>
              <div class="sub">full DTC DB, 10 procedures, 15 parts, 4 walkthroughs</div></div>
            <div class="card"><div class="label">Mini R60 N16 issues</div>
              <div class="value">10</div>
              <div class="sub">15 parts, 5 procedures, 2 walkthroughs, 15 Mini-specific DTCs</div></div>
          </div>
        </main>'''
        page = render_page(body, title="Vehicles")
        page = page.replace("__VIN_TITLE__", f"{MODEL_YEAR} Yaris")
        page = page.replace("__VIN__", html.escape(VIN))
        self._send_html(page)

    def _handle_odometer_post(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        import urllib.parse as up
        params = up.parse_qs(body)
        try:
            km = int(params.get("km", ["0"])[0])
        except ValueError:
            self._send_json({"error": "km must be integer"}); return
        notes = params.get("notes", [""])[0]
        from .odometer import record_reading
        record_reading(km, source="web", notes=notes)
        self._send_json({"ok": True, "km": km})

    # ── POST /session_note ────────────────────────────────────────
    def _handle_session_note_post(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        import urllib.parse as up
        params = up.parse_qs(body)
        sid = params.get("id", [""])[0]
        note = params.get("note", [""])[0]
        try:
            sid_int = int(sid)
        except ValueError:
            self._send_json({"error": "invalid id"}); return
        if len(note) > 500:
            note = note[:500]
        from .store import Store, DEFAULT_DB
        try:
            with Store(DEFAULT_DB) as s:
                s.conn.execute("UPDATE sessions SET note=? WHERE id=?", (note, sid_int))
                s.conn.commit()
                self._send_json({"ok": True, "id": sid_int, "note": note})
        except Exception as e:
            self._send_json({"error": str(e)})

    # ── Helpers ───────────────────────────────────────────────────
    def _send_html(self, page: str):
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last_row_count = len(self.tailer.history())
        last_event_count = len(self.tailer.recent_events())
        try:
            while True:
                time.sleep(0.5)
                hist = self.tailer.history()
                if len(hist) > last_row_count:
                    new = hist[last_row_count:]
                    for r in new:
                        d = row_to_display(r)
                        msg = f"event: row\ndata: {json.dumps(d)}\n\n"
                        try:
                            self.wfile.write(msg.encode("utf-8"))
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                    last_row_count = len(hist)
                evs = self.tailer.recent_events()
                if len(evs) != last_event_count:
                    msg = f"event: event\ndata: {json.dumps(evs)}\n\n"
                    try:
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    last_event_count = len(evs)
                # keep-alive ping
                try:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="CSV to tail (default: newest in reports/)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="127.0.0.1",
                    help="Default 127.0.0.1 (localhost only). Pass 0.0.0.0 to expose on LAN.")
    args = ap.parse_args()

    csv_path = args.csv or find_newest_csv(REPORT_DIR)
    if not csv_path:
        print("[!] No CSV found. Start the live-dash logger first or pass --csv <path>.")
        sys.exit(1)
    print(f"[+] Tailing: {csv_path}")

    tailer = CsvTailer(csv_path)
    t = threading.Thread(target=tailer.run, daemon=True)
    t.start()

    Handler.tailer = tailer
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"[+] Dashboard:")
    print(f"      http://localhost:{args.port}   (bound to {args.bind})")
    if args.bind == "0.0.0.0":
        ip = get_lan_ip()
        print(f"      http://{ip}:{args.port}   (LAN / phone access)")
    else:
        print(f"      (LAN access disabled — pass --bind 0.0.0.0 to expose)")
    print(f"[+] Ctrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
