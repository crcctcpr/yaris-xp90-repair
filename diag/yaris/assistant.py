"""Natural-language assistant for the Yaris toolkit.

Rule-based intent router. The query universe is bounded (DTCs, issues, trims,
maintenance, history, costs, etc.), so we can cover most useful questions with
~30 patterns that map to existing functions.

No external LLM dependency — this is a deterministic, local-first answerer.
When the intent isn't matched, falls back to the global search.
"""
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Answer:
    text: str
    links: list[dict] = None  # [{label, href}]
    data: dict = None         # structured blob for UI to render richer
    confidence: float = 1.0
    intent: str = ""


# ── Intent patterns ──────────────────────────────────────────────────
def _contains(text: str, *words) -> bool:
    return all(w in text for w in words)


def _any(text: str, *words) -> bool:
    return any(w in text for w in words)


def match_and_answer(query: str) -> Answer:
    q = query.lower().strip()
    if not q:
        return Answer("Ask me something about your car.")

    # ── DTC / code lookup ─────────────────────────────────────────
    m = re.search(r"\b([pcbu])\s*0?\s*(\d{3,4})\b", q)
    if m:
        letter = m.group(1).upper()
        digits = m.group(2).zfill(4)
        code = f"{letter}{digits[-4:]}"
        from .dtc_db import resolve
        e = resolve(code)
        if e:
            return Answer(
                text=f"**{code}** — {e.title}\n\n"
                     f"System: {e.system} · Severity: {e.severity} · "
                     f"Difficulty: {'★' * e.difficulty}\n\n"
                     + ("**Symptoms**: " + ", ".join(e.symptoms[:3]) + "\n\n" if e.symptoms else "")
                     + ("**Top causes**: " + "; ".join(e.causes[:3]) + "\n\n" if e.causes else "")
                     + (f"**Cost DIY**: ${e.cost_diy_usd[0]}–${e.cost_diy_usd[1]}\n" if e.cost_diy_usd[1] > 0 else ""),
                links=[
                    {"label": f"full DTC page", "href": f"/dtc?code={code}"},
                ],
                intent="dtc_lookup",
            )
        return Answer(f"Code {code} isn't in the DB.", intent="dtc_unknown")

    # ── Current LTFT / trims ──────────────────────────────────────
    if _any(q, "ltft", "long term trim", "long-term trim", "fuel trim"):
        from .store import Store, DEFAULT_DB
        from .vehicle import VIN
        try:
            with Store(DEFAULT_DB) as s:
                rows = s.ltft_history(vin=VIN, days=30)
            if rows:
                r = rows[0]
                return Answer(
                    f"Your most recent session had **LTFT average {r['ltft_avg']:+.2f}%** "
                    f"(peak {r['ltft_max']:+.2f}%) over {r['n']} samples. "
                    f"Healthy range is ±7%; anything above +15% is saturated.",
                    links=[{"label": "Full history", "href": "/history"},
                           {"label": "Forecast trajectory", "href": "/forecast"}],
                    intent="ltft_current",
                )
        except Exception as e:
            return Answer(f"Couldn't read history: {e}", intent="ltft_error")
        return Answer("No sessions in history yet. Run yaris-diag dash first.",
                       intent="ltft_nodata")

    # ── Current MAF ratio / sensor health ─────────────────────────
    if _any(q, "maf", "air flow", "airflow sensor"):
        from .store import Store, DEFAULT_DB
        from .vehicle import VIN
        try:
            with Store(DEFAULT_DB) as s:
                rows = s.maf_ratio_trend(vin=VIN, days=30)
            if rows:
                r = rows[0]
                status = ("healthy" if r["ratio_mean"] >= 0.85
                          else ("borderline" if r["ratio_mean"] >= 0.70
                                else "under-reading"))
                return Answer(
                    f"Last session MAF ratio: **{r['ratio_mean']:.2f}× expected** "
                    f"({status}). Healthy cars ≥0.85×. "
                    f"Current MAF values range {r['ratio_min']:.2f}–{r['ratio_max']:.2f}.",
                    links=[{"label": "P0101 walkthrough", "href": "/walkthrough/p0101-diag"},
                           {"label": "Shopping list", "href": "/shopping/issue/p0101-maf-fault"}],
                    intent="maf_current",
                )
        except Exception: pass
        return Answer("No MAF history yet.", intent="maf_nodata")

    # ── Maintenance due ───────────────────────────────────────────
    if _any(q, "maintenance", "service due", "when is", "when should", "oil change"):
        from .odometer import latest_km, service_status
        km = latest_km()
        if km is None:
            return Answer(
                "No odometer reading set yet. Go to /overview and set your current mileage.",
                links=[{"label": "Set odometer", "href": "/overview"}],
                intent="maintenance_nokm",
            )
        items = service_status()
        soon = [i for i in items if i["status"] in ("OVERDUE", "due soon")][:5]
        text = f"Current odometer: **{km:,} km**.\n\n"
        if soon:
            text += "**Due soon / overdue**:\n\n"
            for i in soon:
                text += f"- {i['next_due_km']:,} km ({i['status']}, {i['km_until']} km away): {i['items'][0]}\n"
        else:
            text += "Nothing overdue. Next major service is at:\n"
            for i in items[:2]:
                text += f"- {i['next_due_km']:,} km: {i['items'][0]}\n"
        return Answer(text,
                       links=[{"label": "Full schedule", "href": "/knowledge/maintenance"}],
                       intent="maintenance_due")

    # ── Costs / spending ──────────────────────────────────────────
    if _any(q, "how much", "spent", "cost", "expensive", "money"):
        import os, json
        from .vehicle import REPORT_DIR
        services_file = os.path.join(REPORT_DIR, "services.json")
        if not os.path.exists(services_file):
            return Answer("No service log entries yet. Start logging in /services.",
                           links=[{"label": "Services", "href": "/services"}],
                           intent="cost_empty")
        try:
            with open(services_file) as f:
                services = json.load(f)
        except Exception:
            services = []
        if not services:
            return Answer("No services logged.",
                           links=[{"label": "Services", "href": "/services"}],
                           intent="cost_empty")
        total = sum((s.get("parts", 0) or 0) + (s.get("labor", 0) or 0) for s in services)
        by_type = {}
        for s in services:
            t = s.get("type", "?")
            by_type[t] = by_type.get(t, 0) + (s.get("parts", 0) or 0) + (s.get("labor", 0) or 0)
        top = sorted(by_type.items(), key=lambda x: -x[1])[:3]
        text = f"Total spent on car: **${total:.2f}** across {len(services)} services.\n\n"
        text += "Top categories:\n" + "\n".join(f"- {t}: ${c:.2f}" for t, c in top)
        return Answer(text,
                       links=[{"label": "Service log", "href": "/services"}],
                       intent="cost_total")

    # ── Overall health / can I drive? ─────────────────────────────
    if _any(q, "can i drive", "is it safe", "pre-flight", "pre flight", "healthy"):
        return Answer(
            "Running the pre-flight checklist will give you a verdict.",
            links=[{"label": "Pre-flight checklist", "href": "/checklist"}],
            intent="health_redirect",
        )

    # ── Current status / overview ─────────────────────────────────
    if _any(q, "how is the car", "status", "overview", "summary", "doing"):
        return Answer(
            "Overview has at-a-glance MIL, DTCs, LTFT avg, MAF ratio, charging V, and next maintenance.",
            links=[{"label": "Car overview", "href": "/overview"}],
            intent="status_redirect",
        )

    # ── Forecast ──────────────────────────────────────────────────
    if _any(q, "forecast", "predict", "when will", "future"):
        return Answer(
            "The forecast page projects LTFT, MAF ratio, and charging voltage "
            "trends forward using linear regression. Needs 3+ sessions for a useful projection.",
            links=[{"label": "Forecast", "href": "/forecast"}],
            intent="forecast_redirect",
        )

    # ── Timeline / history ────────────────────────────────────────
    if _any(q, "timeline", "history", "journal", "events", "what happened"):
        from .analytics import build_timeline
        events = build_timeline(days=30)
        if not events:
            return Answer("No events logged yet in the last 30 days.",
                           intent="timeline_empty")
        last = events[0]
        text = f"**Most recent event**: [{last.timestamp[:16]}] {last.category} — {last.title}\n\n"
        text += f"Total events in last 30 days: **{len(events)}** "
        text += f"({sum(1 for e in events if e.category == 'session')} sessions, "
        text += f"{sum(1 for e in events if e.category == 'service')} services, "
        text += f"{sum(1 for e in events if e.category == 'dtc')} DTC observations)."
        return Answer(text,
                       links=[{"label": "Full timeline", "href": "/timeline"}],
                       intent="timeline_summary")

    # ── Economy / mpg ─────────────────────────────────────────────
    if _any(q, "mpg", "fuel economy", "consumption", "l/100"):
        return Answer(
            "The economy page computes L/100km and MPG from MAF-derived fuel flow. "
            "Post-MAF-fix, your moving economy should drop to ~7 L/100km (~34 MPG).",
            links=[{"label": "Economy", "href": "/economy"}],
            intent="economy_redirect",
        )

    # ── Symptoms / diagnose ───────────────────────────────────────
    if _any(q, "rough idle", "won't start", "no start", "overheating", "diagnose", "symptom"):
        return Answer(
            "Start with the symptom picker — it ranks likely issues weighted against the 20-issue KB.",
            links=[{"label": "Symptom diagnose", "href": "/diagnose"},
                   {"label": "Interactive walkthroughs", "href": "/walkthroughs"}],
            intent="diagnose_redirect",
        )

    # ── Specific part / shopping ──────────────────────────────────
    if _any(q, "what part", "which part", "part number", "where to buy", "buy"):
        return Answer(
            "Shopping lists have OEM + aftermarket numbers with direct product-search URLs "
            "for every issue.",
            links=[{"label": "Shopping home", "href": "/shopping"},
                   {"label": "Parts catalog", "href": "/knowledge/parts"}],
            intent="shopping_redirect",
        )

    # ── Fuses / electrical ────────────────────────────────────────
    if _any(q, "fuse", "relay", "electrical", "battery drain"):
        return Answer(
            "Fuse box reference with color-coded amperage + diagnostic tips.",
            links=[{"label": "Fuse box", "href": "/fusebox"}],
            intent="fuse_redirect",
        )

    # ── TSBs / recalls ────────────────────────────────────────────
    if _any(q, "tsb", "recall", "bulletin"):
        return Answer(
            "6 TSBs and 3 Takata airbag recalls apply to your 2011 Yaris. The 3 recalls "
            "don't VIN-match (car is JDM-export) but the hardware is identical.",
            links=[{"label": "TSBs & Recalls", "href": "/knowledge/tsbs"}],
            intent="tsb_redirect",
        )

    # ── Specs / torque / fluid ────────────────────────────────────
    if _any(q, "torque", "fluid", "capacity", "spec", "how much oil"):
        if "oil" in q:
            return Answer(
                "Engine oil: **5W-30, 3.0 L** (with filter). Drain plug torque **37 Nm** "
                "(use new crush washer). Filter 10 Nm (3/4 turn after O-ring contact). "
                "Toyota cartridge 04152-YZZA1.",
                links=[{"label": "All specs", "href": "/knowledge/specs"},
                       {"label": "Oil change procedure", "href": "/knowledge/procedure/oil-change"}],
                intent="spec_oil",
            )
        if _any(q, "coolant", "antifreeze"):
            return Answer(
                "Coolant: **Toyota SLLC (bright pink/red), 50/50 with distilled water, "
                "4.0–4.5 L total**. Thermostat housing bolts 20 Nm.",
                links=[{"label": "Coolant flush procedure", "href": "/knowledge/procedure/coolant-flush"}],
                intent="spec_coolant",
            )
        if _any(q, "brake fluid"):
            return Answer(
                "Brake fluid: **DOT 3 or DOT 4, ~0.7–1.0 L full system**. "
                "Never mix types; never DOT 5 (silicone).",
                intent="spec_brake",
            )
        if _any(q, "lug", "wheel torque"):
            return Answer(
                "Wheel lug nuts: **103 Nm** (76 ft-lbs) in star pattern. "
                "Recheck after first 80 km.",
                intent="spec_lugs",
            )
        return Answer(
            "Check the specs page for all 68 torques, fluid types, and capacities.",
            links=[{"label": "Specifications", "href": "/knowledge/specs"}],
            intent="spec_generic",
        )

    # ── Help / what can you do ────────────────────────────────────
    if _any(q, "help", "what can you", "commands", "examples"):
        return Answer(
            "I can answer things like:\n\n"
            "• *What's my LTFT?* — latest trim reading\n"
            "• *Explain P0101* — or any DTC code\n"
            "• *When is oil change due?* — maintenance check\n"
            "• *How much have I spent?* — cost summary\n"
            "• *Can I drive?* — pre-flight verdict\n"
            "• *What happened this week?* — timeline\n"
            "• *Oil capacity?* — torque/fluid specs\n"
            "• *Forecast LTFT* — trend projection\n"
            "• *Rough idle* or *no start* → symptom diagnose",
            intent="help",
        )

    # ── VIN ────────────────────────────────────────────────────────
    if "vin" in q:
        from .vehicle import VIN, MODEL_YEAR, ENGINE
        return Answer(
            f"VIN: **{VIN}**\n\n{MODEL_YEAR} Toyota Yaris · {ENGINE} engine. "
            "Japan-built (JDM export) based on VIN prefix JTD.",
            intent="vin",
        )

    # ── Fall back: global search ──────────────────────────────────
    from .knowledge import search
    results = search(q)
    if results:
        top = results[:5]
        text = f"I'm not sure how to answer that directly, but found {len(results)} matches:\n\n"
        for r in top:
            text += f"- [{r.get('type')}] {r.get('name') or r.get('item')}\n"
        return Answer(text,
                       links=[{"label": "Full search", "href": f"/search"}],
                       intent="fallback_search",
                       confidence=0.3)

    return Answer(
        "I don't have an answer for that. Try the search page or ask differently.\n\n"
        "*Try*: 'what's my LTFT?', 'explain P0101', 'when is oil due?'",
        links=[{"label": "Search", "href": "/search"},
               {"label": "Help", "href": "/assistant?q=help"}],
        intent="unknown",
        confidence=0.0,
    )
