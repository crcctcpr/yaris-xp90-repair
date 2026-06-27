"""DTC knowledge base for 2011 Yaris (XP90 / 1NR-FE).

Sourced from: YarisRepair KB, Toyota FSM, 1NR-FE service info, field reports.

Each entry: symptoms, ranked causes (by frequency), DIY steps, part numbers,
cost estimates, severity. Use resolve() to look up a code.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DtcEntry:
    code: str
    title: str
    severity: str  # "critical", "warn", "minor"
    system: str    # "cooling", "fuel", "ignition", "emissions", "abs", "srs", etc.
    symptoms: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)  # ranked by frequency
    diy_steps: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    cost_diy_usd: tuple[int, int] = (0, 0)
    cost_shop_usd: tuple[int, int] = (0, 0)
    difficulty: int = 1  # 1=easy, 5=expert
    notes: str = ""
    # Relative paths into ../YarisRepair/ with optional #anchor:
    #   "engine/ENGINE_REPAIR.md#vvt-i-oil-control-valve-cleaning"
    kb_links: list[str] = field(default_factory=list)


DTC_DATABASE: dict[str, DtcEntry] = {
    # ─── Fuel / Air Metering ────────────────────────────────────────────
    "P0101": DtcEntry(
        code="P0101", title="MAF Sensor Circuit Range/Performance",
        severity="warn", system="fuel",
        symptoms=["MIL on", "rough idle possibly", "reduced MPG", "stumbling accel", "LTFT stuck high"],
        causes=[
            "MAF element contaminated (oil film, dust) — most common",
            "Vacuum leak between MAF and throttle body",
            "Air filter oiled (aftermarket K&N) migrating onto element",
            "MAF connector corroded or loose",
            "MAF sensor dead/drifted",
            "Intake boot cracked",
        ],
        diy_steps=[
            "Compare live MAF at idle to expected ~2-4 g/s for 1.3L",
            "Pull MAF, spray with CRC 05110 only (NEVER brake cleaner)",
            "Let dry 5+ min, reinstall, clear codes",
            "If ratio stays below 0.85× expected after clean → replace",
            "Inspect intake boot, airbox seal for leaks",
        ],
        parts=["CRC MAF cleaner 05110 (~$8)", "Denso 22204-21010 OEM MAF (~$60-120)"],
        cost_diy_usd=(8, 120), cost_shop_usd=(150, 300), difficulty=2,
        notes="Permanent code needs 2 clean drive cycles to clear.",
        kb_links=[
            "engine/ENGINE_REPAIR.md",
            "fuel/FUEL_GUIDE.md",
            "guides/COMMON_PROBLEMS.md",
        ],
    ),
    "P0171": DtcEntry(
        code="P0171", title="System Too Lean (Bank 1)",
        severity="warn", system="fuel",
        symptoms=["MIL on", "possible hesitation", "rough idle", "LTFT > +25%"],
        causes=[
            "Vacuum leak (intake boot, PCV hose, gasket)",
            "MAF under-reading (often pairs with P0101)",
            "Fuel pump weakening",
            "Fuel filter clogged",
            "Leaky injector(s)",
            "Exhaust leak before O2 sensor",
            "O2 sensor (B1S1) biased lean",
        ],
        diy_steps=[
            "Smoke-test intake for leaks",
            "Check PCV hose and valve cover gasket",
            "Compare STFT+LTFT at idle vs 2500 RPM (vacuum leak: high idle, low load)",
            "Measure fuel pressure (should be ~41-43 psi static, ~35-38 running)",
        ],
        parts=["PCV valve", "intake gasket", "fuel filter (internal to tank)"],
        cost_diy_usd=(0, 80), cost_shop_usd=(150, 400), difficulty=2,
    ),
    "P0172": DtcEntry(
        code="P0172", title="System Too Rich (Bank 1)",
        severity="warn", system="fuel",
        symptoms=["MIL on", "black smoke possible", "fuel smell", "fouled plugs over time"],
        causes=[
            "Leaky injector",
            "MAF over-reading (less common than under)",
            "Fuel pressure regulator stuck",
            "Dirty air filter (restricts airflow but reports normal)",
            "O2 sensor biased rich",
        ],
        diy_steps=[
            "Replace air filter",
            "Inspect fuel pressure, check for fuel in vacuum line",
            "Check injector balance (compare individual rates)",
        ],
        cost_diy_usd=(20, 150), cost_shop_usd=(200, 500), difficulty=3,
    ),
    "P0300": DtcEntry(
        code="P0300", title="Random / Multiple Cylinder Misfire",
        severity="warn", system="ignition",
        symptoms=["MIL flashing = damaging cat, solid = recurring", "rough idle", "loss of power"],
        causes=[
            "Ignition coil failing (one or more)",
            "Spark plugs worn or fouled (1NR-FE uses iridium, 100k mi interval)",
            "Vacuum leak causing lean misfire",
            "Low compression",
            "Injector failing",
            "Timing chain stretched (1NR-FE: check for rattle at cold start)",
        ],
        diy_steps=[
            "Pull mode 06 misfire counts per cylinder to localize",
            "Swap coils between cylinders, see if misfire follows",
            "Inspect spark plugs (gap 1.0-1.1mm)",
            "Check compression (should be ~190-210 psi, within 10% across cylinders)",
        ],
        parts=["NGK Iridium plugs (~$8 ea)", "Denso ignition coil (~$45 ea)"],
        cost_diy_usd=(30, 180), cost_shop_usd=(200, 600), difficulty=3,
        notes="If MIL FLASHING while driving: stop immediately, catalyst damage imminent.",
    ),
    "P0301": DtcEntry(code="P0301", title="Cylinder 1 Misfire", severity="warn", system="ignition",
                       symptoms=["rough idle", "MIL"], causes=["coil", "plug", "injector", "compression"],
                       cost_diy_usd=(30, 100), difficulty=3),
    "P0302": DtcEntry(code="P0302", title="Cylinder 2 Misfire", severity="warn", system="ignition",
                       symptoms=["rough idle", "MIL"], causes=["coil", "plug", "injector", "compression"],
                       cost_diy_usd=(30, 100), difficulty=3),
    "P0303": DtcEntry(code="P0303", title="Cylinder 3 Misfire", severity="warn", system="ignition",
                       symptoms=["rough idle", "MIL"], causes=["coil", "plug", "injector", "compression"],
                       cost_diy_usd=(30, 100), difficulty=3),
    "P0304": DtcEntry(code="P0304", title="Cylinder 4 Misfire", severity="warn", system="ignition",
                       symptoms=["rough idle", "MIL"], causes=["coil", "plug", "injector", "compression"],
                       cost_diy_usd=(30, 100), difficulty=3),
    # ─── Cooling ────────────────────────────────────────────────────────
    "P0115": DtcEntry(
        code="P0115", title="Engine Coolant Temp Sensor Circuit",
        severity="warn", system="cooling",
        symptoms=["MIL", "cold-start driveability issues", "cooling fan may run constantly"],
        causes=["ECT sensor failing", "wiring to ECT", "ECM issue (rare)"],
        parts=["Denso ECT sensor (~$25)"],
        cost_diy_usd=(25, 50), cost_shop_usd=(100, 200), difficulty=2,
    ),
    "P0125": DtcEntry(
        code="P0125", title="Insufficient Coolant Temp for Closed Loop",
        severity="warn", system="cooling",
        causes=["thermostat stuck open", "ECT sensor drifted low", "running too cold"],
        diy_steps=["Check if coolant reaches normal operating temp within 10 min",
                   "Replace thermostat (common at 100k+ km)"],
        parts=["Toyota thermostat 90916-03093 (~$25)", "coolant 1gal (~$15)"],
        cost_diy_usd=(40, 60), cost_shop_usd=(150, 300), difficulty=3,
    ),
    "P0128": DtcEntry(
        code="P0128", title="Coolant Temp Below Thermostat Regulating Temp",
        severity="warn", system="cooling",
        symptoms=["MIL", "poor MPG", "takes forever to warm up"],
        causes=["thermostat stuck open (most common at 100k+ km)", "low coolant level", "ECT sensor drift"],
        parts=["Toyota OEM thermostat 90916-03093 (~$25)"],
        cost_diy_usd=(40, 60), cost_shop_usd=(150, 300), difficulty=3,
    ),
    # ─── Emissions ──────────────────────────────────────────────────────
    "P0420": DtcEntry(
        code="P0420", title="Catalyst System Efficiency Below Threshold (Bank 1)",
        severity="warn", system="emissions",
        symptoms=["MIL on", "fail emissions test", "possible H2S/sulfur smell"],
        causes=[
            "Catalyst aged / failing (common at 150k+ km)",
            "Downstream O2 sensor aged",
            "Upstream/downstream O2 sensors swapped",
            "Exhaust leak",
            "Prior rich operation (P0172/misfire) damaged cat",
        ],
        diy_steps=[
            "Compare upstream (0134) and downstream (0115) switching rates",
            "Downstream should cycle slowly (< 0.5 Hz); if cycling fast = cat dead",
            "Replace downstream O2 first (~$60) — cheapest test",
        ],
        parts=["Denso downstream O2 89465-52380 (~$60)", "Catalytic converter (~$400 aftermarket, $800 OEM)"],
        cost_diy_usd=(60, 450), cost_shop_usd=(500, 1500), difficulty=3,
    ),
    "P0441": DtcEntry(
        code="P0441", title="EVAP Emission Control Incorrect Purge Flow",
        severity="minor", system="emissions",
        causes=["EVAP VSV (purge valve) stuck", "hose cracked/disconnected", "canister blocked"],
        cost_diy_usd=(40, 120), difficulty=3,
    ),
    "P0442": DtcEntry(
        code="P0442", title="EVAP System Small Leak",
        severity="minor", system="emissions",
        symptoms=["MIL only"],
        causes=["loose fuel cap (tighten and drive 3 cycles)", "cracked EVAP hose",
                "failing fuel cap gasket", "vent valve"],
        diy_steps=["Tighten cap, clear code, drive 3 cycles before replacing parts"],
        parts=["fuel cap (~$20)"],
        cost_diy_usd=(0, 50), cost_shop_usd=(100, 300), difficulty=1,
    ),
    "P0446": DtcEntry(
        code="P0446", title="EVAP Vent Control Circuit",
        severity="minor", system="emissions",
        causes=["EVAP vent valve failed", "wiring to vent valve"],
        cost_diy_usd=(40, 100), difficulty=2,
    ),
    "P0456": DtcEntry(
        code="P0456", title="EVAP System Very Small Leak",
        severity="minor", system="emissions",
        causes=["tiny hose crack", "fuel cap seal", "purge/vent valve leak"],
        cost_diy_usd=(0, 50), difficulty=2,
    ),
    # ─── VVT-i (1NR-FE dual VVT) ─────────────────────────────────────────
    "P0010": DtcEntry(
        code="P0010", title="VVT Intake Camshaft Position Actuator Circuit (Bank 1)",
        severity="warn", system="fuel",
        causes=["VVT OCV solenoid clogged with oil sludge", "wiring", "low oil / wrong viscosity"],
        diy_steps=["Clean OCV with MAF cleaner", "replace if still failing"],
        parts=["Toyota OCV 15330-40010 (~$80)"],
        cost_diy_usd=(10, 90), cost_shop_usd=(200, 400), difficulty=3,
    ),
    "P0011": DtcEntry(
        code="P0011", title="VVT Intake Advanced / Timing Over-Advanced",
        severity="warn", system="fuel",
        causes=["OCV stuck", "cam phaser worn", "low oil pressure", "wrong oil"],
        diy_steps=["Verify oil level/condition", "clean or replace OCV", "inspect cam phaser"],
        cost_diy_usd=(10, 150), difficulty=3,
    ),
    "P0012": DtcEntry(
        code="P0012", title="VVT Intake Retarded / Timing Over-Retarded",
        severity="warn", system="fuel",
        causes=["OCV stuck", "cam phaser worn"],
        cost_diy_usd=(10, 150), difficulty=3,
    ),
    "P1349": DtcEntry(
        code="P1349", title="VVT System Malfunction (Toyota-specific)",
        severity="warn", system="fuel",
        causes=["OCV clogged/failed", "VVT solenoid", "cam phaser"],
        diy_steps=["Clean OCV (top of valve cover, 1-2 bolts)"],
        cost_diy_usd=(10, 90), difficulty=2,
    ),
    # ─── O2 sensor ──────────────────────────────────────────────────────
    "P0135": DtcEntry(
        code="P0135", title="O2 Sensor Heater Circuit (B1S1)",
        severity="warn", system="emissions",
        causes=["Upstream O2 heater circuit failed — replace O2 sensor", "wiring/fuse"],
        parts=["Denso upstream O2 89467-52040 (~$130)"],
        cost_diy_usd=(130, 150), cost_shop_usd=(250, 400), difficulty=3,
    ),
    "P0141": DtcEntry(
        code="P0141", title="O2 Sensor Heater Circuit (B1S2)",
        severity="warn", system="emissions",
        parts=["Denso downstream O2 89465-52380 (~$60)"],
        cost_diy_usd=(60, 80), cost_shop_usd=(180, 300), difficulty=2,
    ),
    "P2195": DtcEntry(
        code="P2195", title="O2 Sensor Signal Biased Lean (B1S1)",
        severity="warn", system="emissions",
        causes=["upstream O2 aged", "vacuum leak sustained"], cost_diy_usd=(130, 180), difficulty=3,
    ),
    "P2196": DtcEntry(
        code="P2196", title="O2 Sensor Signal Biased Rich (B1S1)",
        severity="warn", system="emissions",
        causes=["upstream O2 aged", "fuel pressure too high", "leaky injector"],
        cost_diy_usd=(130, 200), difficulty=3,
    ),
    # ─── CKP / CMP / throttle ────────────────────────────────────────────
    "P0335": DtcEntry(
        code="P0335", title="CKP Sensor Circuit (Crank)",
        severity="critical", system="ignition",
        symptoms=["may no-start", "stalling"],
        causes=["CKP sensor failing", "wiring", "reluctor ring on crank"],
        parts=["Toyota CKP 90919-05060 (~$80)"],
        cost_diy_usd=(80, 100), difficulty=3,
    ),
    "P0340": DtcEntry(
        code="P0340", title="CMP Sensor Circuit (Cam)",
        severity="critical", system="ignition",
        symptoms=["no start or hard start", "misfire", "rough"],
        causes=["CMP sensor failing", "wiring", "timing chain stretch affecting cam phasing"],
        cost_diy_usd=(80, 150), difficulty=3,
    ),
    "P2122": DtcEntry(
        code="P2122", title="Throttle Pedal Position Sensor Circuit Low",
        severity="warn", system="fuel",
        causes=["accelerator pedal sensor", "wiring"], cost_diy_usd=(100, 200), difficulty=3,
    ),
    # ─── Electrical / comms ─────────────────────────────────────────────
    "U0100": DtcEntry(
        code="U0100", title="Lost Communication with ECM",
        severity="critical", system="electrical",
        causes=["CAN wiring damaged", "ECM power/ground", "ECM failing"],
        cost_diy_usd=(0, 600), difficulty=5,
    ),
    "U0155": DtcEntry(
        code="U0155", title="Lost Communication with Instrument Cluster",
        severity="warn", system="electrical",
        causes=["body/K-Line wiring", "cluster failing"],
        cost_diy_usd=(0, 400), difficulty=4,
    ),
    "P0685": DtcEntry(
        code="P0685", title="ECM Power Relay Control Circuit / Open",
        severity="warn", system="electrical",
        causes=["EFI relay failed", "relay socket corroded"],
        cost_diy_usd=(15, 40), difficulty=2,
    ),
    # ─── ABS / chassis (C-codes) ────────────────────────────────────────
    "C1201": DtcEntry(
        code="C1201", title="Engine Control System Malfunction (ABS will not arm)",
        severity="warn", system="abs",
        causes=["ECM has active P-code — fix engine code first"],
        difficulty=1, notes="Clear engine codes; C1201 usually self-clears after.",
    ),
    "C1223": DtcEntry(
        code="C1223", title="ABS Pump Motor Relay",
        severity="warn", system="abs",
        causes=["pump motor relay", "wiring", "ABS actuator"],
        cost_diy_usd=(40, 400), difficulty=4,
    ),
    "C1425": DtcEntry(
        code="C1425", title="Stop Lamp Switch Circuit",
        severity="minor", system="abs",
        symptoms=["brake lights always on or never on", "ABS disabled", "cruise unavailable"],
        causes=["brake light switch failed", "switch out of adjustment"],
        parts=["Brake light switch (~$15)"],
        cost_diy_usd=(15, 20), difficulty=1,
    ),
}


# ── Bulk-assign KB cross-links by system ────────────────────────────────
# Each DTC entry gets default kb_links based on its `system` field.
# Entries can override by setting kb_links explicitly in their definition.
_DEFAULT_KB_BY_SYSTEM = {
    "fuel":       ["fuel/FUEL_GUIDE.md", "engine/ENGINE_REPAIR.md"],
    "ignition":   ["engine/ENGINE_REPAIR.md", "guides/COMMON_PROBLEMS.md"],
    "cooling":    ["cooling/COOLING_GUIDE.md", "guides/COMMON_PROBLEMS.md"],
    "emissions":  ["engine/ENGINE_REPAIR.md", "engine/DTC_FULL_DATABASE.md"],
    "electrical": ["electrical/ELECTRICAL_GUIDE.md"],
    "abs":        ["brakes/BRAKE_GUIDE.md", "electrical/ELECTRICAL_GUIDE.md"],
    "srs":        ["electrical/ELECTRICAL_GUIDE.md"],
}

for _code, _entry in DTC_DATABASE.items():
    if not _entry.kb_links:
        _entry.kb_links = list(_DEFAULT_KB_BY_SYSTEM.get(_entry.system, []))


# Merge parsed KB entries (full 127 DTCs from YarisRepair/engine/DTC_FULL_DATABASE.md)
try:
    from . import dtc_kb_parser
    dtc_kb_parser.merge_into(DTC_DATABASE)
except Exception as _e:
    pass  # Parser errors shouldn't break the rest of the toolkit


def resolve(code: str) -> Optional[DtcEntry]:
    """Look up a DTC code (case-insensitive)."""
    return DTC_DATABASE.get(code.upper())


def summarize(code: str) -> str:
    """One-line summary for a code, or 'unknown' marker."""
    e = resolve(code)
    if not e:
        return f"{code}: (not in DB — consult generic OBD-II reference)"
    return f"{code}: {e.title} [{e.severity}/{e.system}] diff={e.difficulty}★"


def rank_and_explain(codes: list[str]) -> list[dict]:
    """Return list of ranked entries with full detail for a list of codes.

    Ranked by severity: critical > warn > minor > unknown.
    """
    order = {"critical": 0, "warn": 1, "minor": 2}
    enriched = []
    for c in codes:
        e = resolve(c)
        if e:
            enriched.append({
                "code": e.code, "title": e.title, "severity": e.severity,
                "system": e.system, "symptoms": e.symptoms, "causes": e.causes,
                "diy_steps": e.diy_steps, "parts": e.parts,
                "cost_diy_usd": list(e.cost_diy_usd), "cost_shop_usd": list(e.cost_shop_usd),
                "difficulty": e.difficulty, "notes": e.notes,
                "kb_links": list(e.kb_links),
            })
        else:
            enriched.append({"code": c, "title": "(unknown code)", "severity": "warn",
                             "system": "?", "notes": "Not in local DB.",
                             "kb_links": []})
    enriched.sort(key=lambda x: order.get(x["severity"], 9))
    return enriched
