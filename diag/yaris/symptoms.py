"""Symptom → likely-issue inference tree.

Many owners describe a symptom (rough idle, overheating, no-start) before
knowing any DTC. This module maps common symptoms to weighted lists of
issues, drawing from ISSUES in knowledge.py.

Weighting logic:
  - Each symptom maps to a list of (issue_slug, weight 0-1).
  - Weight = prior probability that this symptom is caused by that issue,
    as a rough rank. 1.0 = very likely, 0.3 = possible.
  - When user picks multiple symptoms, weights sum across each issue, so
    issues that match ALL symptoms rank highest.
  - Results are normalized and returned sorted by total weight.
"""
from dataclasses import dataclass
from .knowledge import ISSUES


@dataclass
class Symptom:
    slug: str
    label: str
    category: str   # "driveability", "start", "sound", "fluid", "warning_lights", "performance"
    description: str = ""
    # weighted issue list: (issue_slug, weight 0-1)
    likely_issues: list[tuple[str, float]] = None


SYMPTOMS: dict[str, Symptom] = {}


def _s(slug, label, category, description, issues):
    SYMPTOMS[slug] = Symptom(slug, label, category, description, issues)


# ── Driveability ────────────────────────────────────────────────────────
_s("rough-idle", "Rough / unstable idle", "driveability",
   "Idle RPM bounces or fluctuates, engine feels rough at stoplights.",
   [("throttle-carbon", 0.9), ("p0171-lean", 0.7),
    ("vvti-malfunction", 0.5), ("p0101-maf-fault", 0.5),
    ("engine-mount-dogbone", 0.3)])

_s("hesitation-accel", "Hesitation on acceleration", "driveability",
   "Car stumbles or hesitates when you press the gas pedal.",
   [("p0101-maf-fault", 0.7), ("p0171-lean", 0.7),
    ("vvti-malfunction", 0.5), ("throttle-carbon", 0.5)])

_s("stall", "Engine stalls at idle or low speed", "driveability",
   "Engine dies unexpectedly when coasting or at idle.",
   [("throttle-carbon", 0.7), ("p0171-lean", 0.5),
    ("battery-drain", 0.3), ("alternator-failure", 0.3)])

_s("stumble-cold", "Cold-start stumble or rough running first 1-2 min", "driveability",
   "Engine runs poorly when first started, smooths out after warm-up.",
   [("vvti-malfunction", 0.6), ("p0171-lean", 0.4),
    ("throttle-carbon", 0.4), ("p0101-maf-fault", 0.3)])

# ── Starting ────────────────────────────────────────────────────────────
_s("no-crank", "Car won't crank (click or silence)", "start",
   "Turning the key gives a click or nothing — engine doesn't rotate.",
   [("starter-failure", 0.7), ("battery-drain", 0.7)])

_s("slow-crank", "Slow / weak cranking", "start",
   "Starter turns engine slowly, like a weak battery.",
   [("battery-drain", 0.8), ("alternator-failure", 0.4),
    ("starter-failure", 0.3)])

_s("hard-start", "Hard start — cranks a long time before firing", "start",
   "Cranks many revolutions before the engine catches.",
   [("p0101-maf-fault", 0.5), ("p0171-lean", 0.5),
    ("vvti-malfunction", 0.3)])

_s("no-start-after-sitting", "Dead battery after sitting a few days", "start",
   "Battery is flat when the car has been parked for 1-3 weeks.",
   [("battery-drain", 1.0)])

# ── Warning lights ──────────────────────────────────────────────────────
_s("mil-solid", "Check Engine Light (MIL) on solid", "warning_lights",
   "The check-engine warning stays on while driving.",
   [("p0101-maf-fault", 0.4), ("p0171-lean", 0.4),
    ("vvti-malfunction", 0.3), ("catalyst-failure", 0.3),
    ("thermostat-stuck-open", 0.2)])

_s("mil-flashing", "Check Engine Light flashing", "warning_lights",
   "CRITICAL: MIL blinks while driving — misfire active, catalyst at risk.",
   [])  # Handled specially in the UI — stop driving warning

_s("battery-light", "Battery / charging warning light", "warning_lights",
   "Red battery icon illuminated on dash.",
   [("alternator-failure", 0.9), ("battery-drain", 0.3)])

_s("temp-light", "Engine temperature warning", "warning_lights",
   "Red/orange coolant-temp warning; overheating territory.",
   [("water-pump-seep", 0.6), ("thermostat-stuck-open", 0.3)])

_s("abs-light", "ABS warning light on", "warning_lights",
   "Amber ABS light illuminated.",
   [])

# ── Sounds ──────────────────────────────────────────────────────────────
_s("cold-start-rattle", "Rattle on cold start, 1-3 sec", "sound",
   "Metallic clatter from engine top for a few seconds after first start.",
   [("timing-chain-rattle", 0.8), ("vvti-malfunction", 0.5)])

_s("persistent-rattle", "Persistent metallic rattle (not just cold start)", "sound",
   "Rattle continues after warm-up or throughout driving.",
   [("timing-chain-rattle", 0.7)])

_s("squeak-brakes", "Brake squeak (especially rear)", "sound",
   "High-pitched squeal when braking.",
   [("brake-judder", 0.2)])

_s("grinding-turn", "Grinding/rumbling worse when turning", "sound",
   "Wheel noise that changes with steering angle.",
   [("wheel-bearing-noise", 0.9)])

_s("brake-pulsation", "Pedal pulsation under braking", "sound",
   "Brake pedal / steering wheel oscillates during firm stops.",
   [("brake-judder", 1.0)])

_s("engine-rock-thunk", "Engine rocks / thunks on shift", "sound",
   "Noticeable thunk when shifting from N to D, or during 1→2.",
   [("engine-mount-dogbone", 0.9)])

# ── Fluids / visible signs ─────────────────────────────────────────────
_s("coolant-drip", "Coolant puddle / drip under engine bay", "fluid",
   "Pink/green fluid visible on driveway beneath front of car.",
   [("water-pump-seep", 0.8), ("thermostat-stuck-open", 0.2)])

_s("oil-consumption", "Oil level drops between changes, no visible leak", "fluid",
   "Engine uses 0.5-1L oil per 5,000 km; no drips visible.",
   [("oil-consumption-1nrfe", 1.0)])

_s("blue-smoke-exhaust", "Blue smoke from exhaust", "fluid",
   "Blue-tinted smoke, especially on start-up or deceleration.",
   [("oil-consumption-1nrfe", 0.9)])

_s("black-smoke", "Black smoke from exhaust under load", "fluid",
   "Dark exhaust when accelerating hard.",
   [("p0171-lean", 0.3)])

# ── Performance / economy ──────────────────────────────────────────────
_s("poor-mpg", "Poor fuel economy / MPG dropping", "performance",
   "Tank range shorter than usual; computer shows worse MPG.",
   [("p0101-maf-fault", 0.7), ("p0171-lean", 0.5),
    ("thermostat-stuck-open", 0.4), ("catalyst-failure", 0.3),
    ("oil-consumption-1nrfe", 0.2)])

_s("slow-warmup", "Slow warm-up / heater weak in winter", "performance",
   "Takes >10 min to reach normal temp; heater blows lukewarm.",
   [("thermostat-stuck-open", 1.0)])

_s("power-loss", "Reduced power / feels sluggish", "performance",
   "Car doesn't accelerate like it used to.",
   [("catalyst-failure", 0.5), ("p0101-maf-fault", 0.4),
    ("p0171-lean", 0.4), ("throttle-carbon", 0.3),
    ("oil-consumption-1nrfe", 0.2)])

_s("emissions-fail", "Failed emissions / smog test", "performance",
   "Test station flagged catalyst efficiency or lean condition.",
   [("catalyst-failure", 0.9), ("p0171-lean", 0.3),
    ("p0101-maf-fault", 0.2)])

# ── Electrical ──────────────────────────────────────────────────────────
_s("flickering-lights", "Interior / headlight flickering at idle", "performance",
   "Lights dim or flicker when engine is idling.",
   [("alternator-failure", 0.9), ("battery-drain", 0.3)])

_s("window-wont-work", "Power window won't go up/down", "performance",
   "One window unresponsive or slow.",
   [("power-window-regulator", 1.0)])

_s("door-wont-open-inside", "Door won't open from inside", "performance",
   "Inside door handle feels loose or doesn't release latch.",
   [("door-handle-broken", 1.0)])

_s("no-cold-ac", "A/C blows warm air", "performance",
   "Air conditioner doesn't cool.",
   [("ac-compressor-fail", 0.8)])


def rank_issues(selected_symptom_slugs: list[str]) -> list[dict]:
    """Given user-selected symptoms, return issue slugs ranked by combined weight.

    Returns list of dicts: {issue_slug, total_weight, matching_symptoms, issue_obj_summary}
    """
    if not selected_symptom_slugs:
        return []
    scores: dict[str, dict] = {}
    for sym_slug in selected_symptom_slugs:
        sym = SYMPTOMS.get(sym_slug)
        if not sym:
            continue
        for issue_slug, weight in sym.likely_issues:
            entry = scores.setdefault(issue_slug, {"weight": 0.0, "matching_symptoms": []})
            entry["weight"] += weight
            entry["matching_symptoms"].append(sym.label)
    ranked = []
    for issue_slug, entry in scores.items():
        i = ISSUES.get(issue_slug)
        if not i:
            continue
        # Normalize weight by number of selected symptoms (so an issue that
        # matches 3/3 symptoms with 0.5 each ranks above 1/3 with 1.0)
        coverage = len(entry["matching_symptoms"]) / len(selected_symptom_slugs)
        score = entry["weight"] * (0.6 + 0.4 * coverage)
        ranked.append({
            "issue_slug": issue_slug,
            "issue_name": i.name,
            "issue_system": i.system,
            "issue_rank": i.rank,
            "cost_diy_usd": list(i.cost_diy_usd),
            "difficulty": i.difficulty,
            "score": round(score, 3),
            "raw_weight": round(entry["weight"], 3),
            "matching_symptoms": entry["matching_symptoms"],
            "coverage_pct": round(100 * coverage, 0),
        })
    ranked.sort(key=lambda r: -r["score"])
    return ranked


def symptoms_by_category() -> dict[str, list[Symptom]]:
    out: dict[str, list[Symptom]] = {}
    for s in SYMPTOMS.values():
        out.setdefault(s.category, []).append(s)
    return out
