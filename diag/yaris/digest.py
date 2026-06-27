"""Weekly digest report generator.

"State of your car, this week." Pulls from history, services, alerts, DTCs,
maintenance schedule. Markdown output suitable for piping to email / Slack.
"""
import json
import os
from datetime import datetime, timedelta

from .vehicle import REPORT_DIR, VIN, MODEL_YEAR, ENGINE


def generate(days: int = 7) -> str:
    """Build markdown digest covering the last N days."""
    from .store import Store, DEFAULT_DB
    from .analytics import forecast_ltft, forecast_maf_ratio, forecast_charging
    from .odometer import latest_km, service_status

    ts = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 🚗 Yaris Weekly Digest — {ts}", ""]
    lines.append(f"*{MODEL_YEAR} Toyota Yaris · {ENGINE} · VIN {VIN}*")
    lines.append(f"*Period: last {days} days*")
    lines.append("")

    # ── Driving activity ──
    try:
        with Store(DEFAULT_DB) as s:
            since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
            sessions = [x for x in s.sessions(vin=VIN, days=days)]
            n_sess = len(sessions)
            total_samples = 0
            for sess in sessions:
                summ = s.session_summary(sess["id"])
                total_samples += summ.get("stats", {}).get("n", 0)
    except Exception:
        n_sess = 0; total_samples = 0

    lines.append("## 📊 Driving activity")
    lines.append("")
    if n_sess:
        lines.append(f"- **{n_sess} sessions** recorded ({total_samples} OBD samples)")
    else:
        lines.append(f"- No sessions this week. Consider running `yaris-diag dash` during a drive.")
    lines.append("")

    # ── Current health ──
    km = latest_km()
    lines.append("## 💚 Current health")
    lines.append("")
    if km is not None:
        lines.append(f"- **Odometer:** {km:,} km")
    else:
        lines.append(f"- **Odometer:** not set — set via /overview")

    try:
        f_ltft = forecast_ltft(days=60)
        f_maf = forecast_maf_ratio(days=60)
        f_volt = forecast_charging(days=60)
        if f_ltft.current_value != 0:
            mark = "⚠️" if abs(f_ltft.current_value) > 15 else ("~" if abs(f_ltft.current_value) > 7 else "✓")
            lines.append(f"- {mark} **LTFT:** {f_ltft.current_value:+.2f}% (healthy ±5)")
        if f_maf.current_value != 0:
            mark = "✓" if f_maf.current_value >= 0.85 else ("~" if f_maf.current_value >= 0.70 else "⚠️")
            lines.append(f"- {mark} **MAF ratio:** {f_maf.current_value:.2f}× expected")
        if f_volt.current_value != 0:
            mark = "✓" if f_volt.current_value >= 13.4 else "~"
            lines.append(f"- {mark} **Charging V:** {f_volt.current_value:.2f}V (healthy 13.4-14.5)")
    except Exception:
        pass
    lines.append("")

    # ── Trends / forecasts ──
    if f_ltft.days_until_threshold is not None and f_ltft.confidence != "none":
        lines.append("## 📈 Trend forecasts")
        lines.append("")
        days_val = f_ltft.days_until_threshold
        if days_val <= 30:
            lines.append(f"- ⚠️ **LTFT projected to hit +25% threshold in ~{days_val:.0f} days** at current rate ({f_ltft.confidence} confidence)")
        elif days_val <= 90:
            lines.append(f"- **LTFT trajectory: ~{days_val:.0f} days to threshold** at current rate")
        lines.append("")

    # ── DTCs ──
    try:
        with Store(DEFAULT_DB) as s:
            dtcs = s.dtc_occurrences(vin=VIN, days=days)
    except Exception:
        dtcs = []
    if dtcs:
        lines.append("## ⚠️ DTCs this week")
        lines.append("")
        for d in dtcs:
            lines.append(f"- `{d['code']}` ({d['bucket']}) — seen {d['occurrences']}× "
                          f"· last {d['last_ts'][:10]}")
        lines.append("")

    # ── Maintenance ──
    if km is not None:
        due = [x for x in service_status() if x["status"] in ("OVERDUE", "due soon")][:5]
        if due:
            lines.append("## 🔧 Maintenance due")
            lines.append("")
            for d in due:
                mark = "⚠️" if d["status"] == "OVERDUE" else "~"
                lines.append(f"- {mark} **{d['next_due_km']:,} km** ({d['status']}, "
                              f"{d['km_until']} km away): {d['items'][0]}")
            lines.append("")

    # ── Services logged ──
    services_file = os.path.join(REPORT_DIR, "services.json")
    services_week = []
    if os.path.exists(services_file):
        try:
            with open(services_file) as f:
                all_services = json.load(f)
            cutoff = datetime.now() - timedelta(days=days)
            for sv in all_services:
                try:
                    svd = datetime.fromisoformat(sv.get("date", "2000-01-01"))
                    if svd >= cutoff:
                        services_week.append(sv)
                except Exception:
                    continue
        except Exception:
            pass
    if services_week:
        lines.append("## 🛠 Services performed")
        lines.append("")
        total = 0
        for sv in services_week:
            cost = (sv.get("parts", 0) or 0) + (sv.get("labor", 0) or 0)
            total += cost
            lines.append(f"- **{sv.get('date')}** @ {sv.get('km', 0):,} km — "
                          f"{sv.get('type', '?').replace('_', ' ')} · ${cost:.2f} ({sv.get('where', '')})")
        lines.append(f"")
        lines.append(f"*Total spent this week: ${total:.2f}*")
        lines.append("")

    # ── Quick verdict ──
    lines.append("## 🎯 Bottom line")
    lines.append("")
    if dtcs:
        lines.append(f"- Active faults detected — review `/dtc` and `/walkthroughs`")
    if f_ltft.current_value > 15:
        lines.append(f"- LTFT saturated — MAF likely needs attention")
    if not dtcs and (f_ltft.current_value == 0 or abs(f_ltft.current_value) < 10):
        lines.append(f"- No urgent concerns in the automated checks")
    lines.append("")
    lines.append(f"---")
    lines.append(f"*Generated by yaris-diag toolkit · http://localhost:8080/overview*")

    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    text = generate(days=args.days)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"[+] Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
