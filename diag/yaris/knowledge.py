"""Structured Yaris knowledge base — XP90, 2011, 1NR-FE 1.3L, Japan-built.

Populated from:
  (a) Local repair-kb/ markdown KB (20 common issues,
      68 specs, 15 maintenance intervals, 127 DTCs)
  (b) Web research: toyota-club.net NR engine FAQ, NHTSA, YarisWorld,
      ToyotaNation, BobIsTheOilGuy, Denso/Aisin/Akebono parts catalogs.

Exposed as Python data, queryable from the CLI and rendered by webdash.
"""
from dataclasses import dataclass, field
from typing import Optional


# ── Dataclasses ─────────────────────────────────────────────────────────
@dataclass
class Issue:
    slug: str
    name: str
    system: str                  # engine, cooling, fuel, electrical, brakes, etc.
    rank: int                    # 1=most common
    frequency: str               # "Very common 50%+", "Moderate 10-15%", etc.
    typical_mileage: str = ""
    symptoms: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    difficulty: int = 3
    cost_diy_usd: tuple[int, int] = (0, 0)
    cost_shop_usd: tuple[int, int] = (0, 0)
    related_dtcs: list[str] = field(default_factory=list)
    related_parts: list[str] = field(default_factory=list)
    related_procedures: list[str] = field(default_factory=list)
    kb_links: list[str] = field(default_factory=list)
    tsb_refs: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Procedure:
    slug: str
    name: str
    system: str
    difficulty: int
    time_minutes: int
    tools: list[str] = field(default_factory=list)
    parts: dict[str, str] = field(default_factory=dict)
    torque_specs: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    safety: str = ""
    specs: dict = field(default_factory=dict)
    kb_link: str = ""


@dataclass
class Spec:
    item: str
    value: str
    unit: str
    system: str
    notes: str = ""


@dataclass
class MaintenanceItem:
    km: int
    months: int
    items: list[str]
    cost_usd_low: int = 0
    cost_usd_high: int = 0


@dataclass
class TSB:
    number: str
    area: str
    summary: str
    applies_to_2011: bool = True
    fix: str = ""
    source: str = ""


@dataclass
class Recall:
    campaign: str
    date: str
    component: str
    description: str
    remedy: str
    applies_to_vin: str  # "direct", "hardware same (JDM)", "no"
    source: str = ""


@dataclass
class Part:
    name: str
    system: str
    oem: str = ""
    aftermarket: dict[str, str] = field(default_factory=dict)
    price_usd: tuple[int, int] = (0, 0)
    replaces: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class DiagnosticBaseline:
    """Known-healthy PID range for a warm idle."""
    pid: str
    name: str
    healthy_range: str
    warning_range: str = ""
    notes: str = ""


# ── Common Issues (top 20 from local KB + forum reports) ────────────────
ISSUES: dict[str, Issue] = {
    "timing-chain-rattle": Issue(
        slug="timing-chain-rattle", name="Timing Chain Rattle on Cold Start",
        system="engine", rank=1, frequency="Very common (30-40% on high-mileage 1NR-FE)",
        typical_mileage="60,000+ km",
        symptoms=["Distinct rattle/clinking on cold start (lasts 1-3 sec)",
                  "Rattle worsens with age", "May extend past 3 sec if chain is stretched"],
        causes=["VVT-i OCV filter clogged with sludge (test this first)",
                "Timing chain tensioner O-ring hardened/leaking",
                "Chain stretch (at 150k+ km)",
                "Oil starvation accelerates wear"],
        diagnostics=["Pull VVT-i OCV, soak in brake cleaner",
                     "Check tensioner O-ring condition",
                     "Listen for rattle duration — under 3s=normal feature per TSB EG-00039T"],
        difficulty=5, cost_diy_usd=(20, 200), cost_shop_usd=(800, 1200),
        related_dtcs=["P0010", "P0011", "P0012", "P0016", "P0017", "P1349"],
        related_parts=["vvti-ocv", "timing-chain-kit"],
        related_procedures=["vvti-ocv-cleaning", "timing-chain-replacement"],
        kb_links=["engine/ENGINE_REPAIR.md", "guides/COMMON_PROBLEMS.md"],
        tsb_refs=["EG-00039T-TME"],
        notes="Toyota TSB declares brief cold-start rattle 'a normal feature', but goodwill replacement of chain+tensioner arm sometimes offered.",
    ),

    "vvti-malfunction": Issue(
        slug="vvti-malfunction", name="VVT-i Malfunction (P1349/P0010/P0011)",
        system="engine", rank=2, frequency="Common (20-30% past 80k km)",
        typical_mileage="80,000+ km",
        symptoms=["P1349 / P0010 / P0011 / P0016 / P0017 codes",
                  "Rough cold idle", "Hesitation on acceleration",
                  "Rattle from cam area on cold start"],
        causes=["Oil Control Valve (OCV) solenoid screen clogged with sludge — MOST COMMON",
                "Wiring to OCV", "Stretched timing chain (less common but possible)",
                "Low oil pressure (check oil level!)"],
        diagnostics=["Pull OCV — 10mm bolt, single connector",
                     "Measure OCV coil resistance: 5-15 Ω (spec varies by year; 6.9-7.9 Ω at 20°C per FSM)",
                     "Inspect filter screen on end of solenoid — should be clean metal mesh",
                     "If dirty: soak in brake cleaner 10-15 min, brush, blow dry, reinstall"],
        difficulty=2, cost_diy_usd=(20, 90), cost_shop_usd=(300, 400),
        related_dtcs=["P1349", "P0010", "P0011", "P0012", "P0016", "P0017"],
        related_parts=["vvti-ocv"],
        related_procedures=["vvti-ocv-cleaning"],
        kb_links=["engine/ENGINE_REPAIR.md"],
        notes="Screen filter clogs first. Cleaning fixes ~70% of cases.",
    ),

    "p0101-maf-fault": Issue(
        slug="p0101-maf-fault", name="P0101 — MAF Sensor Range/Performance",
        system="fuel", rank=3, frequency="Common (15-20% at some point)",
        typical_mileage="Any",
        symptoms=["Check engine light (P0101)", "LTFT stuck high (+15% to +25%)",
                  "Reduced MPG 2-3 mpg", "Possible hesitation on accel",
                  "MAF reads below expected 2.5-3.5 g/s at warm idle"],
        causes=["MAF hot-wire element contaminated by oil/dust (most common)",
                "Oiled aftermarket air filter migrating onto sensor",
                "Vacuum leak between MAF and throttle body",
                "Cracked intake boot",
                "MAF connector corroded or loose",
                "Genuine sensor failure (rare)"],
        diagnostics=["Compare live MAF at idle to expected ~2.5-3.5 g/s for 1.3L",
                     "Clean with CRC MAF cleaner PN 05110 ONLY (not brake cleaner!)",
                     "Let dry 5+ min, reinstall, clear codes",
                     "If ratio still <0.85× expected → replace sensor",
                     "Always inspect intake boot for cracks AND airbox seal"],
        difficulty=2, cost_diy_usd=(8, 120), cost_shop_usd=(150, 300),
        related_dtcs=["P0101", "P0102", "P0103", "P0171"],
        related_parts=["maf-sensor", "maf-cleaner", "air-filter"],
        related_procedures=["maf-clean", "maf-replace"],
        kb_links=["engine/ENGINE_REPAIR.md", "fuel/FUEL_GUIDE.md"],
        notes="Permanent P0101 clears after 2 clean drive cycles.",
    ),

    "p0171-lean": Issue(
        slug="p0171-lean", name="P0171 — System Too Lean (Bank 1)",
        system="fuel", rank=4, frequency="Common (15-20%)",
        symptoms=["MIL with P0171", "Rough idle, hesitation", "MPG drop 2-3",
                  "LTFT saturated at +25%", "Possible P0101 alongside"],
        causes=["Vacuum leak (PCV hose, intake gaskets, throttle body gasket)",
                "Dirty MAF sensor (cleaning helps ~70%)",
                "Weak fuel pump", "Clogged fuel filter (tank-internal)",
                "Exhaust leak before O2 sensor", "Upstream O2 aged/biased lean"],
        diagnostics=["Compare LTFT at idle vs 2500 RPM held steady",
                     "  - Vacuum leak: LTFT high at idle, decreases with RPM",
                     "  - MAF/fuel: LTFT high across all conditions",
                     "Smoke test intake",
                     "Measure fuel pressure: ~41-43 psi static, ~35-38 running"],
        difficulty=2, cost_diy_usd=(0, 80), cost_shop_usd=(150, 400),
        related_dtcs=["P0171", "P0174", "P0101"],
        related_parts=["pcv-valve", "intake-gasket", "maf-cleaner"],
        related_procedures=["maf-clean", "smoke-test-intake"],
        kb_links=["fuel/FUEL_GUIDE.md"],
    ),

    "throttle-carbon": Issue(
        slug="throttle-carbon", name="Rough Idle / Throttle Body Carbon Buildup",
        system="engine", rank=5, frequency="Very common (50%+ past 100k km)",
        typical_mileage="100,000+ km",
        symptoms=["Idle bounces 500-1200 rpm", "Hesitation off idle",
                  "Stumble on cold start", "Engine may stall at idle"],
        causes=["Carbon deposits on throttle butterfly and bore",
                "PCV fumes depositing on throttle plate",
                "ETC needs recalibration after cleaning"],
        diagnostics=["Visual inspection — if throttle bore is black/sticky, clean",
                     "Use throttle body cleaner + clean rag",
                     "After cleaning: perform throttle-position relearn"],
        difficulty=2, cost_diy_usd=(10, 20), cost_shop_usd=(150, 250),
        related_procedures=["throttle-body-clean"],
        kb_links=["engine/ENGINE_REPAIR.md", "fuel/FUEL_GUIDE.md"],
    ),

    "oil-consumption-1nrfe": Issue(
        slug="oil-consumption-1nrfe", name="Oil Consumption (1NR-FE pre-2014)",
        system="engine", rank=6, frequency="Moderate (10-15% of pre-2014 1NR-FE)",
        typical_mileage="80,000+ km",
        symptoms=["Oil level drops 0.5-1.0L between 5,000 km intervals",
                  "~0.5 qt per 1,000 mi typical",
                  "Blue smoke on deceleration (rings) or start-up (valve seals)",
                  "No external leaks visible"],
        causes=["Piston ring lands trap carbon → rings stick → blow-by → oil past rings (primary on 1NR-FE, Toyota TSB EG-0095T)",
                "Valve stem seal aging (secondary)",
                "PCV system fault (third)"],
        diagnostics=["Do compression test: 150-180 psi healthy, <130 = problem",
                     "Wet test: add 15ml oil through plug hole; if pressure rises = rings",
                     "Toyota TSB EG-0095T remedy: replace pistons + rings + rods + oil jets (NOT reboring)",
                     "Cheap DIY: top-engine cleaner through plug holes to de-coke rings"],
        difficulty=5, cost_diy_usd=(15, 100), cost_shop_usd=(1500, 2500),
        related_dtcs=["P0301", "P0302", "P0303", "P0304"],
        tsb_refs=["EG-0095T-1112", "EG-0094T-0714"],
        kb_links=["engine/ENGINE_REPAIR.md"],
        notes="Post-2014 production has revised ring pack. Pre-2014 build (our 2011) is affected. Some owners fix with top-engine cleaner before committing to engine rebuild.",
    ),

    "water-pump-seep": Issue(
        slug="water-pump-seep", name="Water Pump Weep / Seal Leak",
        system="cooling", rank=7, frequency="Common (20-30% at 120-180k km)",
        typical_mileage="120,000-180,000 km",
        symptoms=["Coolant drip below alternator area", "Slow coolant level drop",
                  "Occasional overheating if leak accelerates", "Weep hole visible drip"],
        causes=["Water pump seal hardened / failing",
                "Thermostat housing gasket leak (often coexists)",
                "Rubber hoses hardened from age"],
        diagnostics=["Inspect weep hole on water pump — bottom side",
                     "Pressure test cooling system at 15 psi for 15 min",
                     "Sniff/inspect thermostat housing for wet coolant"],
        difficulty=3, cost_diy_usd=(35, 80), cost_shop_usd=(150, 300),
        related_parts=["water-pump", "thermostat", "coolant-slcc"],
        related_procedures=["water-pump-replace", "coolant-flush"],
        kb_links=["cooling/COOLING_GUIDE.md"],
    ),

    "thermostat-stuck-open": Issue(
        slug="thermostat-stuck-open", name="Thermostat Stuck Open — P0128",
        system="cooling", rank=8, frequency="Common (20%+ past 100k km)",
        symptoms=["P0128 stored", "Slow warm-up (>10 min to 80°C)",
                  "Heater doesn't get hot in winter", "Poor MPG in winter",
                  "Cooling fan never runs (coolant never gets hot enough)"],
        causes=["Thermostat stuck in open position (most common failure mode)",
                "Low coolant level", "ECT sensor drifted low"],
        diagnostics=["Compare coolant reach to target 85-92°C",
                     "Replace thermostat — it's cheap and rarely the wrong call at 100k+",
                     "Toyota OEM 90916-03084 family (verify housing style for 1NR-FE)"],
        difficulty=3, cost_diy_usd=(40, 60), cost_shop_usd=(150, 300),
        related_dtcs=["P0128", "P0125"],
        related_parts=["thermostat"],
        related_procedures=["thermostat-replace"],
        kb_links=["cooling/COOLING_GUIDE.md"],
    ),

    "engine-mount-dogbone": Issue(
        slug="engine-mount-dogbone", name='Upper-Right ("Dog-Bone") Engine Mount Failure',
        system="drivetrain", rank=9, frequency="Common (20-30% past 100k km)",
        symptoms=['Vibration at idle in "D"', 'Thunk on 1→2 upshift',
                  "Engine visibly rocks forward under acceleration"],
        causes=["Upper torque-strut bushing rubber breaks down",
                "Common weakness on XP90 platform"],
        diagnostics=["Open hood at idle in D — watch engine for excessive rock",
                     "Inspect dog-bone bushing — should be intact rubber, not torn/collapsed"],
        difficulty=2, cost_diy_usd=(30, 60), cost_shop_usd=(150, 250),
        related_procedures=["engine-mount-replace"],
        kb_links=["engine/ENGINE_REPAIR.md"],
    ),

    "power-window-regulator": Issue(
        slug="power-window-regulator", name="Power Window Regulator Failure",
        system="body", rank=10, frequency="Common (20-30% of doors by 100k km)",
        symptoms=["Window won't operate", "Window drops into door",
                  "Slow operation before failure", "Motor buzzes but no movement"],
        causes=["Plastic clips on regulator fatigue and snap",
                "Motor usually OK"],
        diagnostics=["Remove door panel — 3 screws + clips",
                     "Inspect for snapped plastic clips"],
        difficulty=3, cost_diy_usd=(25, 45), cost_shop_usd=(100, 200),
        related_procedures=["window-regulator-replace"],
        kb_links=["body/BODY_GUIDE.md", "electrical/ELECTRICAL_GUIDE.md"],
    ),

    "door-handle-broken": Issue(
        slug="door-handle-broken", name="Interior Door Handle Plastic Clip Failure",
        system="body", rank=11, frequency="Common (20% by 100k km, especially rear)",
        symptoms=["Door won't open from inside", "Handle feels loose",
                  "Clicking noise when pulling handle"],
        causes=["Plastic clip inside latch mechanism breaks from repeated use"],
        difficulty=3, cost_diy_usd=(25, 40), cost_shop_usd=(100, 150),
        related_procedures=["door-handle-replace"],
        kb_links=["body/BODY_GUIDE.md"],
    ),

    "rust-wheel-arches": Issue(
        slug="rust-wheel-arches", name="Rust Spots — Wheel Arches & Sills",
        system="body", rank=12, frequency="Common in salty climates (30-50% by 100k km)",
        symptoms=["Orange/brown discoloration around wheel arches",
                  "Bubbling paint on lower sills",
                  "Holes through the sheet metal (severe, later stage)"],
        causes=["Weak factory rustproofing (XP90 platform known issue)",
                "Road salt corrosion of bare metal at seams"],
        difficulty=3, cost_diy_usd=(200, 500), cost_shop_usd=(1000, 2500),
        kb_links=["body/BODY_GUIDE.md"],
    ),

    "ac-compressor-fail": Issue(
        slug="ac-compressor-fail", name="A/C Compressor Failure",
        system="hvac", rank=13, frequency="Moderate (10-15% by 150k km)",
        symptoms=["No cold air from vents", "Compressor clutch won't engage",
                  "Rapid clutch cycling", "Grinding noise from engine bay"],
        causes=["Compressor internal bearings fail",
                "Seals degrade → refrigerant leaks → oil carries away",
                "Clutch coil open"],
        diagnostics=["Check high-side/low-side pressures (spec 20-30 / 35-45 psi idle)",
                     "Inspect compressor clutch — should engage with 12V on coil",
                     "Leak-detection dye UV check"],
        difficulty=4, cost_diy_usd=(200, 250), cost_shop_usd=(400, 700),
        related_procedures=["ac-compressor-replace", "ac-system-evacuate"],
        kb_links=["body/BODY_GUIDE.md"],
    ),

    "wheel-bearing-noise": Issue(
        slug="wheel-bearing-noise", name="Wheel Bearing Noise",
        system="suspension", rank=14, frequency="Moderate (10-20% by 150k km)",
        symptoms=["Grinding/rumbling worse on turns (one way)",
                  "Noise rises with speed",
                  "Wheel has play when pushed/pulled"],
        causes=["Bearing wear from age/potholes/salt",
                "Axle nut under-torqued (should be 216 Nm)"],
        diagnostics=["Jack one wheel, spin and feel for roughness",
                     "Push/pull wheel — any measurable play = worn",
                     "Identify side: noise louder when turning AWAY from bad bearing"],
        difficulty=5, cost_diy_usd=(40, 120), cost_shop_usd=(300, 500),
        related_procedures=["wheel-bearing-replace"],
        kb_links=["suspension/SUSPENSION_GUIDE.md"],
    ),

    "clutch-judder": Issue(
        slug="clutch-judder", name="Clutch Judder / Shudder (Manual)",
        system="drivetrain", rank=15, frequency="Moderate (15-25% manual by 100k km)",
        symptoms=["Vibration during engagement (1st or reverse worst)",
                  "Only during actual engagement, not when fully in/out",
                  "Can be felt through pedal and seat"],
        causes=["Worn clutch disc facing",
                "Oil contamination on disc (crankshaft seal leak)",
                "Flywheel glazed/scored"],
        difficulty=5, cost_diy_usd=(100, 180), cost_shop_usd=(600, 900),
        related_procedures=["clutch-replace"],
        kb_links=["transmission/TRANS_GUIDE.md"],
    ),

    "starter-failure": Issue(
        slug="starter-failure", name="Starter Motor Failure",
        system="electrical", rank=16, frequency="Moderate (15-20% by 150k km)",
        symptoms=["Single click, no crank", "Grinding when starting",
                  "Intermittent no-crank (hot or cold)",
                  "Works when tapped with hammer"],
        causes=["Brush wear (most common)", "Armature damage",
                "Solenoid contacts worn"],
        diagnostics=["Check battery voltage first — must be >12.2V",
                     "Measure voltage at starter solenoid when cranking",
                     "If good power but no crank → starter"],
        difficulty=3, cost_diy_usd=(60, 100), cost_shop_usd=(150, 250),
        related_procedures=["starter-replace"],
        kb_links=["electrical/ELECTRICAL_GUIDE.md"],
    ),

    "alternator-failure": Issue(
        slug="alternator-failure", name="Alternator Failure",
        system="electrical", rank=17, frequency="Moderate (10-15% by 150k km)",
        symptoms=["Battery light on dashboard",
                  "Voltage <13.0V while driving",
                  "Flickering lights at idle",
                  "Engine stalls while driving"],
        causes=["Diode failure inside alternator",
                "Voltage regulator failure",
                "Bearing seize"],
        diagnostics=["Measure battery voltage key-on-engine-off (~12.3V)",
                     "Measure engine-running (~13.8-14.5V healthy)",
                     "If engine-running <13.4V = charging issue",
                     "Load test alternator at parts store"],
        difficulty=3, cost_diy_usd=(80, 150), cost_shop_usd=(300, 400),
        related_parts=["alternator"],
        related_procedures=["alternator-replace"],
        kb_links=["electrical/ELECTRICAL_GUIDE.md"],
        notes="Our car currently reads 13.12-13.30V — borderline. Worth re-checking after MAF fix.",
    ),

    "brake-judder": Issue(
        slug="brake-judder", name="Brake Judder — Warped Front Rotors",
        system="brakes", rank=18, frequency="Very common (50%+ by 80k km)",
        symptoms=["Pedal pulsation under braking",
                  "Steering wheel oscillates under braking",
                  "Worse under firm/hot braking"],
        causes=["Rotor thickness variation from heat cycling (not literal 'warp' but pad-transfer-layer uneven)",
                "Aggressive braking in stop-and-go",
                "Rust/debris on rotor face"],
        diagnostics=["Measure rotor thickness with caliper — min 17.0 mm",
                     "Check rotor runout with dial indicator",
                     "Resurface if still within spec, otherwise replace"],
        difficulty=2, cost_diy_usd=(30, 60), cost_shop_usd=(100, 150),
        related_parts=["front-rotors", "front-pads"],
        related_procedures=["brake-pad-replace", "rotor-replace"],
        kb_links=["brakes/BRAKE_GUIDE.md"],
    ),

    "catalyst-failure": Issue(
        slug="catalyst-failure", name="Catalytic Converter Failure — P0420",
        system="emissions", rank=19, frequency="Moderate (10-15% by 150k km)",
        symptoms=["P0420 stored", "Failed emissions test",
                  "Rotten-egg smell at times", "Rattling noise (broken substrate)"],
        causes=["Catalyst aged out of efficiency (most common)",
                "Downstream O2 sensor drift (cheaper first test)",
                "Prior rich running (misfire/P0172) damaged catalyst",
                "Exhaust leak upstream"],
        diagnostics=["Swap downstream O2 with known-good first — cheapest test",
                     "Compare upstream vs downstream switching rates (yaris-diag cat)",
                     "Downstream should be slow (<0.3 Hz); fast = cat dead"],
        difficulty=3, cost_diy_usd=(60, 450), cost_shop_usd=(500, 1500),
        related_dtcs=["P0420", "P0421"],
        related_parts=["downstream-o2", "catalytic-converter"],
        related_procedures=["o2-downstream-replace", "cat-efficiency-test"],
        kb_links=["engine/ENGINE_REPAIR.md"],
    ),

    "battery-drain": Issue(
        slug="battery-drain", name="Battery Drain / Parasitic Draw",
        system="electrical", rank=20, frequency="Common (20-30% of older units)",
        symptoms=["Battery dead after parked 1-3 weeks",
                  "Jump-start required after sitting",
                  "Clock resets / radio code needed"],
        causes=["Stuck interior light / trunk light",
                "Aftermarket alarm drawing power",
                "Failing body ECU or stereo",
                "Battery simply old/weak"],
        diagnostics=["DMM in series with battery negative — should be <50 mA after 30 min sleep",
                     "If higher: pull fuses one at a time until draw drops",
                     "Battery load test at parts store"],
        difficulty=3, cost_diy_usd=(0, 100), cost_shop_usd=(200, 400),
        kb_links=["electrical/ELECTRICAL_GUIDE.md"],
    ),
}


# ── Repair Procedures ───────────────────────────────────────────────────
PROCEDURES: dict[str, Procedure] = {
    "oil-change": Procedure(
        slug="oil-change", name="Engine Oil & Filter Change",
        system="engine", difficulty=1, time_minutes=20,
        tools=["14mm socket", "Oil filter wrench", "Drain pan", "Torque wrench"],
        parts={"oil": "Toyota 5W-30, 3.0L capacity",
               "filter": "Toyota cartridge 04152-YZZA1",
               "crush_washer": "14mm drain plug (replace every change)"},
        torque_specs=["Drain plug: 37 Nm", "Oil filter: 10 Nm (3/4 turn after O-ring contact)"],
        steps=["Warm engine 5 min, shut off",
               "Raise on jack stands",
               "Drain into pan (14mm drain plug)",
               "Remove old filter, oil new O-ring, thread new filter",
               "Reinstall drain plug with new crush washer (37 Nm)",
               "Fill 2.7L, start engine, check dipstick, top to full (3.0L total)",
               "Check for leaks after 5 min idle"],
        safety="Warm engine first; hot oil burns. Don't overtighten filter.",
        kb_link="guides/MAINTENANCE_SCHEDULE.md",
    ),

    "spark-plug-replace": Procedure(
        slug="spark-plug-replace", name="Spark Plug Replacement",
        system="engine", difficulty=1, time_minutes=30,
        tools=["16mm spark plug socket", "Torque wrench", "150mm extension"],
        parts={"plugs": "NGK Iridium ILKAR7L11 (3x) OR Denso VCH16 (3x), pre-gapped 1.0-1.1mm"},
        torque_specs=["Spark plugs: 18 Nm", "Coil hold-down: 10 Nm"],
        steps=["Remove engine cover",
               "Disconnect 3 coil connectors",
               "Remove coil hold-down bolts (10mm)",
               "Wiggle coils straight up (don't pull wires)",
               "Remove old plugs with 16mm socket",
               "Do NOT adjust iridium electrode",
               "Thread new plugs by hand first, then torque 18 Nm",
               "Reinstall coils (press firmly), torque hold-downs 10 Nm",
               "Reconnect, test drive"],
        kb_link="engine/ENGINE_REPAIR.md",
    ),

    "maf-clean": Procedure(
        slug="maf-clean", name="MAF Sensor Cleaning",
        system="fuel", difficulty=2, time_minutes=20,
        tools=["T20 Torx", "10mm for battery", "Clean rag"],
        parts={"cleaner": "CRC Mass Air Flow Sensor Cleaner PN 05110 ONLY",
               "replacement_if_bad": "Denso 22204-21010 (~$60-120)"},
        torque_specs=["MAF mounting screws: hand-tight (small plastic)"],
        steps=["Disconnect battery negative (wait 90 s)",
               "Locate MAF in intake tube between airbox and throttle body",
               "Unplug 5-pin connector",
               "Remove 2 T20 Torx screws",
               "Slide sensor straight out — DO NOT TOUCH ELEMENT",
               "Spray CRC 05110 on element from 6\" away, 10-15 short bursts",
               "Let dry 5+ min — no wiping, no blowing",
               "Reinstall, reconnect connector",
               "Reconnect battery",
               "Start engine, idle 30 s for ECM relearn"],
        safety="Only CRC MAF cleaner — brake cleaner destroys the element. Never touch the hot-wire.",
        kb_link="fuel/FUEL_GUIDE.md",
    ),

    "vvti-ocv-cleaning": Procedure(
        slug="vvti-ocv-cleaning", name="VVT-i OCV Solenoid Cleaning / Replacement",
        system="engine", difficulty=2, time_minutes=30,
        tools=["10mm socket", "Multimeter", "Brake cleaner", "Small brush"],
        parts={"ocv": "Toyota 15330-40011 (~$45 OEM, $20-40 aftermarket)",
               "o_ring": "OEM"},
        torque_specs=["OCV bolt: 9 Nm"],
        specs={"resistance_ohms": "6.9-7.9 Ω at 20°C (spec varies 5-15 Ω by year)"},
        steps=["Warm engine briefly (thins oil)",
               "Disconnect battery negative",
               "Locate OCV — top front of head, intake cam side, near alternator",
               "Disconnect electrical connector",
               "Remove single 10mm bolt",
               "Pull out solenoid (have rag ready — oil drips)",
               "Inspect filter screen: if clogged with sludge, soak in brake cleaner 10-15 min",
               "Brush screen gently, flush with cleaner, blow dry",
               "Check O-ring condition, replace if worn",
               "Measure coil resistance with multimeter",
               "Reinstall, torque bolt 9 Nm",
               "Reconnect, clear codes, test drive"],
        kb_link="engine/ENGINE_REPAIR.md",
    ),

    "throttle-body-clean": Procedure(
        slug="throttle-body-clean", name="Throttle Body Cleaning + ETC Relearn",
        system="fuel", difficulty=2, time_minutes=45,
        tools=["10mm socket", "Throttle body cleaner (CRC Throttle Body Cleaner)",
               "Clean rag", "Soft brush (optional)"],
        parts={"gasket": "OEM (if disassembled completely)"},
        torque_specs=["Throttle body bolts: 10 Nm"],
        steps=["Cool engine",
               "Disconnect battery negative (wait 10 s)",
               "Loosen intake tube hose clamp at throttle body",
               "Unplug TPS/ETC connector",
               "Remove 4 bolts (10mm) from throttle body",
               "Hold throttle plate open manually, spray cleaner inside bore",
               "Wipe clean with rag — no brown deposits visible",
               "Do NOT spray cleaner on TPS or harness",
               "Inspect gasket, replace if damaged",
               "Reinstall, torque 10 Nm, reconnect tube and TPS",
               "ETC relearn: key ON 15 s, OFF 15 s, key ON 15 s, then start",
               "Idle 3 min for ECM to stabilize"],
        kb_link="fuel/FUEL_GUIDE.md",
    ),

    "brake-pad-replace": Procedure(
        slug="brake-pad-replace", name="Front Brake Pad Replacement",
        system="brakes", difficulty=2, time_minutes=60,
        tools=["14mm wrench", "C-clamp or pad spreader",
               "Brake cleaner", "Wire brush", "Torque wrench"],
        parts={"pads": "Akebono ACT908 / Toyota 04465-52260 (front, both sides)",
               "min_rotor_thickness": "17.0 mm"},
        torque_specs=["Caliper slide pin bolts: 29 Nm",
                      "Caliper carrier bolts: 79 Nm",
                      "Wheel lug nuts: 103 Nm"],
        steps=["Loosen lug nuts (on ground first)",
               "Raise + jack stands",
               "Remove wheel",
               "Loosen 2 slide pin bolts (14mm, top + bottom)",
               "Swing caliper up off bracket",
               "Withdraw old pads",
               "Use C-clamp to compress piston back into caliper",
               "Clean rotor and bracket with brake cleaner",
               "Install new inner pad into piston recess, outer pad in bracket",
               "Lower caliper, reinstall slide pins — torque 29 Nm",
               "Repeat other front wheel",
               "Pump brake pedal 5-6x with vehicle raised",
               "Check brake fluid level",
               "Reinstall wheels, torque 103 Nm",
               "Test drive conservatively first 100 km (break-in)"],
        safety="Never let caliper hang by brake line — use wire hook. Bed-in procedure: 6-8 hard stops from 50→20 km/h without stopping, then 15 min cooling.",
        kb_link="brakes/BRAKE_GUIDE.md",
    ),

    "coolant-flush": Procedure(
        slug="coolant-flush", name="Coolant Flush & Refill",
        system="cooling", difficulty=2, time_minutes=60,
        tools=["Drain pan", "Coolant funnel (optional)", "Rags"],
        parts={"coolant": "Toyota SLLC (Super Long Life, bright pink/red) — 4.0-4.5 L",
               "distilled_water": "For 50/50 mix",
               "radiator_cap": "if old/weak"},
        steps=["Engine cold. Place drain pan under radiator",
               "Open radiator petcock (bottom of radiator)",
               "Drain fully (~4 L)",
               "Close petcock",
               "If system was dirty: refill with distilled water, run 10 min, drain again",
               "Mix 50/50 Toyota SLLC + distilled water = ~4.5 L",
               "Fill through radiator cap slowly",
               "Squeeze upper radiator hose to burp air",
               "Start engine with cap off, let idle until thermostat opens",
               "Top up to full, install cap",
               "Heater on full hot during warm-up to bleed heater core",
               "Check level after drive cycle (next day)"],
        safety="Never open radiator cap on hot engine — scalding spray. Coolant is toxic to pets.",
        kb_link="cooling/COOLING_GUIDE.md",
    ),

    "thermostat-replace": Procedure(
        slug="thermostat-replace", name="Thermostat Replacement",
        system="cooling", difficulty=3, time_minutes=60,
        tools=["10mm socket", "Drain pan", "Scraper for gasket"],
        parts={"thermostat": "Aisin THT-019 / Toyota 90916-03084 family (verify for 1NR-FE vs 1NZ-FE housing)",
               "gasket": "OEM",
               "coolant": "Toyota SLLC, ~2 L top-up"},
        torque_specs=["Thermostat housing bolts: 20 Nm"],
        steps=["Engine cold. Drain radiator partial (~2 L)",
               "Remove air intake tube if needed for access",
               "Disconnect upper radiator hose at thermostat housing",
               "Remove 2-3 bolts from housing (10mm)",
               "Remove housing, then thermostat and old gasket",
               "Clean sealing surfaces",
               "Install new thermostat — SPRING SIDE FACES ENGINE",
               "New gasket, reinstall housing, torque 20 Nm",
               "Reconnect upper hose",
               "Refill coolant, burp air (see coolant-flush)",
               "Run engine until fan cycles — verify thermostat opens"],
        kb_link="cooling/COOLING_GUIDE.md",
    ),

    "compression-test": Procedure(
        slug="compression-test", name="Compression Test (1NR-FE)",
        system="engine", difficulty=2, time_minutes=30,
        tools=["Compression gauge", "Spark plug socket", "Ratchet"],
        parts={},
        specs={"normal_psi": "150-180 (healthy)",
               "normal_bar": "10.3-12.4",
               "min_acceptable": "130 psi (9.0 bar)",
               "max_cyl_variation": "14 psi (1.0 bar)"},
        steps=["Engine at operating temp, shut off",
               "Disable ignition: disconnect all 3 coil connectors (or pull EFI fuse)",
               "Disable fuel: pull fuel pump fuse",
               "Remove all 3 spark plugs",
               "Thread gauge into cylinder #1",
               "Crank engine 5 seconds (stable reading)",
               "Record, repeat for #2 and #3",
               "If cylinder <130 psi: wet test — squirt 15 ml oil in, retest",
               "  - If pressure rises: worn rings",
               "  - If stays low: valve leak or head gasket"],
        safety="Disable ignition+fuel before cranking or injectors will flood + plugs may not seal.",
        kb_link="engine/ENGINE_REPAIR.md",
    ),

    "timing-chain-replace": Procedure(
        slug="timing-chain-replace", name="Timing Chain Replacement (1NR-FE)",
        system="engine", difficulty=5, time_minutes=300,
        tools=["Cam locking pins", "Crank holding tool or flywheel lock",
               "19mm socket for crank bolt", "Torque wrench",
               "RTV gasket cutter", "Impact wrench (strongly recommended)"],
        parts={"chain": "Toyota 13506-40030",
               "tensioner": "Toyota 13540-40011",
               "guide_slipper": "Toyota 13560-40010",
               "damper": "Toyota 13561-40010",
               "cover_gasket_set": "OEM",
               "seal_packing": "Toyota 08826-00080"},
        torque_specs=["Crankshaft damper bolt: 120-140 Nm",
                      "Cam sprocket bolt (VVT): 55 Nm",
                      "Tensioner: 8 Nm"],
        steps=["Disconnect battery, drain oil + coolant",
               "Remove RH wheel and inner fender liner",
               "Remove accessory belt + alternator",
               "Remove A/C compressor (hang with wire), PS pump if equipped",
               "Crank pulley bolt out (19mm, ~120+ Nm — impact helpful)",
               "Remove crank pulley, lower timing cover bolts",
               "Oil pan off (RTV cut), upper timing cover",
               "Rotate crank to TDC — crank + cam marks all aligned",
               "Insert cam locking pins; lock crankshaft",
               "Insert pin through tensioner ratchet lock",
               "Remove tensioner and slide old chain off",
               "Install new chain — colored links at crank, intake cam, exhaust cam marks",
               "Install new tensioner (pin retracted), release ratchet pin",
               "Remove cam pins, rotate engine 2 full turns by hand",
               "Verify all timing marks realign",
               "RTV new cover, torque all to spec",
               "Reinstall pan with new RTV bead",
               "Reassemble accessories, refill oil + coolant",
               "Start — should fire within few cranks",
               "Chain rattle should stop once oil pressure builds"],
        safety="TDC verification mandatory before starting. Getting this wrong bends valves.",
        kb_link="engine/ENGINE_REPAIR.md",
    ),
}


# ── Specifications ──────────────────────────────────────────────────────
SPECS: list[Spec] = [
    # Engine oil
    Spec("Engine oil viscosity", "5W-30", "grade", "engine",
         "Toyota Genuine preferred; 0W-30 acceptable in cold climates"),
    Spec("Engine oil capacity (with filter)", "3.0", "L", "engine"),
    Spec("Oil drain plug", "37", "Nm", "engine", "New crush washer each change"),
    Spec("Oil filter", "10 Nm (3/4 turn after contact)", "Nm", "engine"),
    Spec("Oil filter part", "Toyota 04152-YZZA1", "OEM", "engine"),

    # Ignition
    Spec("Spark plug torque", "18", "Nm", "engine"),
    Spec("Spark plug part", "NGK ILKAR7L11 or Denso VCH16", "OEM", "engine"),
    Spec("Spark plug gap", "1.0-1.1", "mm", "engine", "Pre-gapped, do not adjust iridium"),
    Spec("Coil hold-down", "10", "Nm", "engine"),

    # Timing
    Spec("Crankshaft damper bolt", "120-140", "Nm", "engine", "Impact wrench recommended"),
    Spec("Cam sprocket bolt (VVT)", "55", "Nm", "engine"),
    Spec("Timing chain tensioner", "8", "Nm", "engine"),
    Spec("VVT-i OCV bolt", "9", "Nm", "engine"),
    Spec("VVT-i OCV resistance", "6.9-7.9 Ω (at 20°C)", "Ω", "engine"),

    # Cooling
    Spec("Coolant type", "Toyota SLLC bright pink", "50/50 with distilled", "cooling"),
    Spec("Coolant capacity", "4.0-4.5", "L", "cooling"),
    Spec("Thermostat housing bolts", "20", "Nm", "cooling"),
    Spec("Water pump bolts", "10-12", "Nm", "cooling"),
    Spec("Coolant freeze point (50/50)", "-37", "°C", "cooling"),
    Spec("Coolant boiling point (50/50, 1 atm)", "109", "°C", "cooling"),

    # Intake
    Spec("Intake manifold bolts", "15 (two passes)", "Nm", "engine"),
    Spec("Throttle body bolts", "10", "Nm", "engine"),
    Spec("Valve cover bolts", "8 (criss-cross)", "Nm", "engine"),

    # Suspension
    Spec("Strut upper mount bolts", "35", "Nm", "suspension"),
    Spec("Strut-to-knuckle pinch bolts", "167", "Nm", "suspension"),
    Spec("Control arm ball joint nut", "49", "Nm", "suspension"),
    Spec("Tie rod end nut", "49", "Nm", "suspension"),
    Spec("Front hub/axle nut", "216", "Nm", "suspension", "Critical bearing preload"),
    Spec("Wheel lug nuts", "103", "Nm", "wheels"),

    # Brakes
    Spec("Front caliper slide pin bolts", "29", "Nm", "brakes"),
    Spec("Front caliper carrier bolts", "79", "Nm", "brakes"),
    Spec("Front rotor minimum thickness", "17.0", "mm", "brakes"),
    Spec("Front rotor OD", "255", "mm", "brakes"),
    Spec("Front pad minimum thickness", "2.0 (replace below)", "mm", "brakes"),
    Spec("Rear drum ID", "200 (max 201.0)", "mm", "brakes"),
    Spec("Rear shoe min lining", "1.0", "mm", "brakes"),
    Spec("Wheel cylinder bolts", "11", "Nm", "brakes"),
    Spec("Master cylinder bolts", "14", "Nm", "brakes"),
    Spec("Brake line fittings", "11", "Nm", "brakes"),
    Spec("Brake fluid type", "DOT 3 or DOT 4", "grade", "brakes", "Never mix, never DOT 5"),

    # Transmission
    Spec("Manual trans fluid (C50/C52)", "75W-90 GL-5", "grade", "drivetrain"),
    Spec("Manual trans capacity", "2.8-3.2", "L", "drivetrain"),
    Spec("Manual trans drain plug", "27", "Nm", "drivetrain"),
    Spec("Auto trans fluid (U340E)", "Toyota WS (red)", "grade", "drivetrain",
         "Do NOT mix with Dexron"),
    Spec("Auto trans drain/refill", "3.7", "L", "drivetrain"),
    Spec("Auto trans full system", "5.5-6.0", "L", "drivetrain"),
    Spec("Auto trans pan bolts", "10 (star pattern)", "Nm", "drivetrain"),

    # Engine mounts
    Spec("Engine mount-to-engine", "52", "Nm", "engine"),
    Spec("Engine mount-to-frame", "87", "Nm", "engine"),

    # Electrical
    Spec("Battery type", "12V Lead-Acid", "Group 35 or JDM 55B24L", "electrical"),
    Spec("Battery CCA", "500 (min 400)", "CCA", "electrical"),
    Spec("Battery capacity", "45-55", "Ah", "electrical"),
    Spec("Alternator mounting long bolt", "38", "Nm", "electrical"),
    Spec("Starter bolts", "37", "Nm", "electrical"),
    Spec("Charging voltage (engine running)", "13.4-14.5", "V", "electrical"),

    # Fuel
    Spec("Fuel tank capacity", "42", "L", "fuel"),
    Spec("Fuel type", "Unleaded 87 AKI / 91 RON min", "grade", "fuel", "E10 acceptable"),
    Spec("Fuel pressure static", "41-43", "psi", "fuel"),
    Spec("Fuel pressure running", "35-38", "psi", "fuel"),

    # HVAC
    Spec("A/C refrigerant", "R134a", "400-500 g charge", "hvac"),
    Spec("A/C high-side idle", "20-30 (summer)", "psi", "hvac"),
    Spec("A/C low-side idle", "35-45 (summer)", "psi", "hvac"),

    # Tires
    Spec("Tire pressure", "30-33 (2.0-2.3 bar)", "psi", "wheels", "Check door jamb sticker"),

    # Engine baseline
    Spec("Compression normal", "150-180", "psi", "engine"),
    Spec("Compression minimum", "130", "psi", "engine"),
    Spec("Max cyl-to-cyl variation", "14", "psi", "engine"),
    Spec("Idle RPM (warm, D)", "650-750", "RPM", "engine"),
    Spec("Thermostat open temp", "~82", "°C", "cooling"),
]


# ── Maintenance Schedule (from KB) ──────────────────────────────────────
MAINTENANCE: list[MaintenanceItem] = [
    MaintenanceItem(5000, 3, ["Visual inspection — tires, wipers, lights, undercarriage"], 0, 0),
    MaintenanceItem(10000, 6, ["Oil + filter (5W-30, 3.0L)",
                                "Tire rotation",
                                "Brake pad inspection",
                                "Hose inspection"], 50, 100),
    MaintenanceItem(15000, 9, ["Cabin air filter"], 15, 30),
    MaintenanceItem(20000, 12, ["Oil + filter",
                                 "Fluid check",
                                 "Wheel alignment if car pulls"], 50, 150),
    MaintenanceItem(30000, 18, ["Oil + filter",
                                 "Engine air filter",
                                 "Spark plug visual (should be tan/gray)",
                                 "Exhaust inspection"], 50, 200),
    MaintenanceItem(40000, 24, ["Oil + filter",
                                 "Brake fluid flush (absorbs moisture)",
                                 "Tire tread depth (min 3 mm for safety)",
                                 "Battery load test"], 100, 250),
    MaintenanceItem(50000, 30, ["Oil + filter",
                                 "Brake rotor thickness check",
                                 "Steering linkage play"], 50, 100),
    MaintenanceItem(60000, 36, ["Oil + filter",
                                 "Manual trans fluid (75W-90 GL-5)",
                                 "Cabin air filter",
                                 "Comprehensive brake check"], 150, 300),
    MaintenanceItem(80000, 48, ["Oil + filter",
                                 "Auto trans fluid partial (if auto)",
                                 "Spark plug inspection",
                                 "Belt + hose inspection",
                                 "Battery load test"], 200, 400),
    MaintenanceItem(100000, 60, ["Oil + filter",
                                  "COOLANT flush + refill (SLLC 50/50)",
                                  "SPARK PLUGS replacement",
                                  "Manual trans fluid (2nd)",
                                  "Cabin air filter",
                                  "TIMING CHAIN inspection (1NR-FE)",
                                  "Full brake overhaul (pads/fluid)",
                                  "Compression test baseline",
                                  "Suspension inspection"], 400, 1500),
    MaintenanceItem(120000, 72, ["Oil + filter",
                                  "Brake fluid flush (2nd)",
                                  "Electrical connector inspection"], 100, 200),
    MaintenanceItem(140000, 84, ["Oil + filter",
                                  "Engine hose inspection",
                                  "Trans fluid color"], 50, 100),
    MaintenanceItem(160000, 96, ["Oil + filter",
                                  "Manual trans fluid (3rd)",
                                  "Brake fluid (3rd)",
                                  "Undercarriage leak inspection"], 200, 300),
    MaintenanceItem(180000, 108, ["Oil + filter",
                                   "Auto trans full flush",
                                   "Alternator + starter diagnostic"], 150, 250),
    MaintenanceItem(200000, 120, ["MAJOR: Compression test 2nd baseline",
                                   "Suspension struts likely worn",
                                   "Complete brake overhaul",
                                   "Trans fluid full flush",
                                   "All rubber hoses",
                                   "Battery (5-6 yr life limit)",
                                   "VVT-i OCV check (P1349 common)",
                                   "Cat efficiency test"], 1000, 3000),
]


# ── TSBs ────────────────────────────────────────────────────────────────
TSBS: list[TSB] = [
    TSB("EG-0095T-1112", "Piston rings / oil consumption",
        "Defect bulletin for excessive oil consumption on 1NR-FE. "
        "Remedy: replace pistons + connecting rods + oil nozzles + valve cover (not rebore).",
        fix="Pre-production-change 2011 build is retrofit candidate.",
        source="https://toyota-club.net/files/faq/13-01-01_faq_nr-engine_eng.htm"),
    TSB("EG-0091T-1112", "Carbon on valve seats — P1603-P1605",
        "Rough idle / stall from carbon deposits on valves. "
        "Fix: replace pistons/rings/rods + cylinder-head clean.",
        source="toyota-club.net NR FAQ"),
    TSB("EG-0094T-0714", "Engine knock/rattle from carbon deposits",
        "Combustion-chamber carbon deposits cause knock. "
        "Updated pistons + ECU reflash. 2011 build affected (pre-fix).",
        source="toyota-club.net NR FAQ"),
    TSB("EG-00037T-TME", "Hard start — P1604",
        ">3 s cranking due to carbon deposits. Replace battery + starter, "
        "clean combustion chambers.",
        source="Toyota Motor Europe"),
    TSB("EG-00039T-TME", "Timing-chain noise on cold start",
        "Cold-start tick/clatter officially declared 'normal feature'; "
        "chain + tensioner-arm goodwill replacement sometimes offered.",
        source="Toyota Motor Europe"),
    TSB("EG-0027T-0313", "Throttle body — P2111/P2112",
        "Replace throttle body + ECU reflash.",
        source="toyota-club.net NR FAQ"),
]


# ── NHTSA Recalls ───────────────────────────────────────────────────────
RECALLS: list[Recall] = [
    Recall("19V-741", "2019-10-17", "Driver frontal airbag inflator (Takata)",
           "Takata airbag inflator may rupture in crash, causing metal fragments "
           "to enter cabin.",
           remedy="Replace inflator/assembly — free at Toyota dealer.",
           applies_to_vin="hardware same (JDM — US campaign won't VIN-match but hardware identical)",
           source="https://www.nhtsa.gov/vehicle/2011/TOYOTA/YARIS"),
    Recall("18V-025", "2018-01-09", "Passenger frontal airbag (Takata re-recall)",
           "Re-recall of previously replaced units due to inflator degradation.",
           remedy="Replace with alternate-chemistry inflator.",
           applies_to_vin="hardware same (JDM)",
           source="nhtsa.gov"),
    Recall("16V-340", "2016-05-23", "Passenger frontal airbag (original Takata)",
           "Original Takata inflator recall — propellant instability over time.",
           remedy="Replace inflator/assembly.",
           applies_to_vin="hardware same (JDM)",
           source="nhtsa.gov"),
]


# ── Aftermarket Parts (OEM-equivalent references) ───────────────────────
PARTS: dict[str, Part] = {
    "maf-sensor": Part(
        name="Mass Airflow Sensor",
        system="fuel",
        oem="Toyota 22204-21010 (Denso manufacturer)",
        aftermarket={"Denso": "22204-21010 (OEM-spec)",
                     "Delphi": "cross-ref",
                     "Hitachi": "cross-ref"},
        price_usd=(60, 150),
        notes="1NR-FE hot-wire MAF. Very sensitive to contamination. Clean first before replacing.",
    ),
    "maf-cleaner": Part(
        name="MAF Sensor Cleaner",
        system="fuel",
        oem="",
        aftermarket={"CRC": "PN 05110 — Mass Air Flow Sensor Cleaner (THE one to buy)",
                     "Gumout": "MAF Sensor Cleaner",
                     "STP": "MAF Sensor Cleaner"},
        price_usd=(8, 10),
        notes="NEVER substitute brake cleaner / carb cleaner / electrical cleaner — destroys element.",
    ),
    "vvti-ocv": Part(
        name="VVT-i Oil Control Valve Solenoid",
        system="engine",
        oem="Toyota 15330-40011",
        aftermarket={"Aisin": "OEM supplier equivalent",
                     "Standard Motor Products": "cross-ref"},
        price_usd=(20, 90),
        notes="Screen filter clogs with sludge — clean with brake cleaner before replacing.",
    ),
    "spark-plugs": Part(
        name="Spark Plugs (3x for 1NR-FE)",
        system="engine",
        oem="Denso VCH16 (= SC16HR11)",
        aftermarket={"NGK Iridium MAX": "DF7H-11B",
                     "NGK Iridium": "ILKAR7L11",
                     "Denso Iridium Tough": "VCH16"},
        price_usd=(24, 40),
        notes="Pre-gapped 1.0-1.1mm, do not adjust electrode.",
    ),
    "ignition-coil": Part(
        name="Ignition Coil (COP, 3x)",
        system="engine",
        oem="Denso 90919-02240 (verify against VIN)",
        aftermarket={"Denso": "OEM spec"},
        price_usd=(40, 70),
        notes="One per cylinder. Swap-test to isolate misfires.",
    ),
    "water-pump": Part(
        name="Water Pump",
        system="cooling",
        oem="Toyota 16100-80004 / 16100-80010",
        aftermarket={"Aisin": "WPT-181 or WPT-181A"},
        price_usd=(40, 80),
        notes="Belt-driven on 1NR-FE (despite chain timing). Check weep hole for seep.",
    ),
    "thermostat": Part(
        name="Thermostat",
        system="cooling",
        oem="Toyota 90916-03084 family",
        aftermarket={"Aisin": "THT-019",
                     "Gates": "cross-ref"},
        price_usd=(15, 30),
        notes="Verify housing style for 1NR-FE vs 1NZ-FE when ordering.",
    ),
    "alternator": Part(
        name="Alternator",
        system="electrical",
        oem="Toyota 27060-47140 class (verify by VIN)",
        aftermarket={"Denso": "OE supplier",
                     "Bosch": "cross-ref"},
        price_usd=(180, 350),
        notes="~80A rating. Remanufactured often available at $80-150.",
    ),
    "front-pads": Part(
        name="Front Brake Pads",
        system="brakes",
        oem="Toyota 04465-52260",
        aftermarket={"Akebono": "ACT908 (ProACT ceramic)",
                     "Brembo": "cross-ref",
                     "Wagner": "cross-ref"},
        price_usd=(25, 60),
        notes="Fits Yaris sedan 2007-2012. Akebono ceramic = low dust, low noise.",
    ),
    "front-rotors": Part(
        name="Front Brake Rotors (pair)",
        system="brakes",
        oem="Toyota 43512-XX180",
        aftermarket={"Brembo": "cross-ref",
                     "Centric": "120.44195"},
        price_usd=(60, 140),
        notes="Min thickness 17.0 mm, OD 255 mm.",
    ),
    "air-filter": Part(
        name="Engine Air Filter",
        system="engine",
        oem="Toyota 17801-40020",
        aftermarket={"Denso": "cross-ref",
                     "Fram": "cross-ref"},
        price_usd=(10, 25),
        notes="Standard paper — avoid oiled filters (migrate onto MAF).",
    ),
    "oil-filter": Part(
        name="Engine Oil Filter (cartridge)",
        system="engine",
        oem="Toyota 04152-YZZA1",
        aftermarket={"Denso": "OEM spec"},
        price_usd=(7, 15),
        notes="Cartridge type — includes new O-rings.",
    ),
    "upstream-o2": Part(
        name="Upstream O2 / Air-Fuel Ratio Sensor",
        system="emissions",
        oem="Denso OE (part varies by VIN)",
        aftermarket={"Denso": "234-9040 or similar"},
        price_usd=(130, 200),
        notes="Wideband A/F sensor — reads lambda, not mV. Very specific to ECM calibration.",
    ),
    "downstream-o2": Part(
        name="Downstream O2 Sensor (post-cat)",
        system="emissions",
        oem="Toyota 89465-52380",
        aftermarket={"Denso": "234-4209 or similar",
                     "Bosch": "cross-ref"},
        price_usd=(50, 90),
        notes="Narrowband — cheaper test before replacing catalytic converter for P0420.",
    ),
    "pcv-valve": Part(
        name="PCV Valve",
        system="engine",
        oem="Toyota 12204-XX010",
        aftermarket={"Motorad": "cross-ref"},
        price_usd=(15, 30),
        notes="Common cause of vacuum leak / P0171.",
    ),
}


# ── Healthy-engine diagnostic baselines (1NR-FE warm idle) ──────────────
BASELINES: list[DiagnosticBaseline] = [
    DiagnosticBaseline("010C", "RPM (warm idle)", "650-750",
                       warning_range="<500 or >900",
                       notes="Slightly higher with A/C compressor engaged."),
    DiagnosticBaseline("0110", "MAF g/s (warm idle)", "2.5-3.5",
                       warning_range="<2.0 or >4.5",
                       notes="Rule of thumb: 1.3L runs ~15-20% below the 1.5L 1NZ-FE."),
    DiagnosticBaseline("0106", "STFT B1 %", "±0 to ±5",
                       warning_range="±10+",
                       notes="Should bounce, not pin."),
    DiagnosticBaseline("0107", "LTFT B1 %", "-5 to +5",
                       warning_range="±7-10 (watch), ±15 (diagnose), ±20 (P0171/P0172 imminent)",
                       notes="Gets dumped on battery disconnect — allow 1-2 drive cycles to resettle."),
    DiagnosticBaseline("0104", "Calc load %", "18-25",
                       warning_range=">30 at idle",
                       notes="ECU-computed from MAF — circular if MAF faulty."),
    DiagnosticBaseline("0105", "Coolant °C", "85-92",
                       warning_range=">100 or <70",
                       notes="Thermostat opens ~82°C."),
    DiagnosticBaseline("0142", "Control module voltage", "13.4-14.5",
                       warning_range="<13.2 (charging issue) or >15.0 (regulator)",
                       notes="Our car reads 13.12-13.30V — borderline."),
    DiagnosticBaseline("0111", "Throttle %", "14-18 at warm idle",
                       notes="ETC base idle position."),
    DiagnosticBaseline("010E", "Timing advance °", "4-14 at idle",
                       notes="Retards under knock; advances at cruise."),
    DiagnosticBaseline("0115", "O2 B1S2 V (post-cat)", "~0.6-0.8 steady",
                       warning_range="Fast oscillation = cat failing",
                       notes="Slow switching = cat storing O2."),
    DiagnosticBaseline("0134", "O2 B1S1 wideband λ", "~1.000 ±0.05",
                       notes="Wideband A/F — ECM holds at stoich (λ=1.0) in closed-loop."),
    DiagnosticBaseline("0103", "Fuel system status", "02 (closed-loop)",
                       warning_range="04 (OL-driver) only transient OK, sustained = issue",
                       notes="01=warm-up, 02=CL, 04=OL-driver (WOT/decel), 16=CL-fault"),
]


# ── Helpers ─────────────────────────────────────────────────────────────
def issues_by_system() -> dict[str, list[Issue]]:
    out: dict[str, list[Issue]] = {}
    for issue in ISSUES.values():
        out.setdefault(issue.system, []).append(issue)
    for lst in out.values():
        lst.sort(key=lambda i: i.rank)
    return out


def procedures_by_system() -> dict[str, list[Procedure]]:
    out: dict[str, list[Procedure]] = {}
    for p in PROCEDURES.values():
        out.setdefault(p.system, []).append(p)
    return out


def specs_by_system() -> dict[str, list[Spec]]:
    out: dict[str, list[Spec]] = {}
    for s in SPECS:
        out.setdefault(s.system, []).append(s)
    return out


def find_issue_for_dtc(code: str) -> Optional[Issue]:
    code = code.upper()
    for issue in ISSUES.values():
        if code in [c.upper() for c in issue.related_dtcs]:
            return issue
    return None


def search(query: str) -> list[dict]:
    """Full-text-ish search across issues, procedures, specs, parts."""
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for issue in ISSUES.values():
        hay = " ".join([issue.name, issue.system, issue.notes,
                        " ".join(issue.symptoms), " ".join(issue.causes),
                        " ".join(issue.related_dtcs)]).lower()
        if q in hay:
            results.append({"type": "issue", "slug": issue.slug, "name": issue.name,
                            "system": issue.system})
    for p in PROCEDURES.values():
        hay = " ".join([p.name, p.system, " ".join(p.tools)]).lower()
        if q in hay:
            results.append({"type": "procedure", "slug": p.slug, "name": p.name,
                            "system": p.system})
    for s in SPECS:
        if q in (s.item + s.value + s.unit + s.system + s.notes).lower():
            results.append({"type": "spec", "item": s.item, "value": s.value,
                            "unit": s.unit, "system": s.system})
    for slug, p in PARTS.items():
        if q in (p.name + p.system + (p.oem or "") + " ".join(p.aftermarket.values())).lower():
            results.append({"type": "part", "slug": slug, "name": p.name,
                            "system": p.system})
    return results


# ── CLI command (quick lookup) ─────────────────────────────────────────
def main():
    import argparse, json, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="Search all knowledge")
    ap.add_argument("--issue", help="Show details for issue slug")
    ap.add_argument("--procedure", help="Show details for procedure slug")
    ap.add_argument("--stats", action="store_true", help="Show knowledge base stats")
    args = ap.parse_args()

    if args.stats:
        print(f"Issues: {len(ISSUES)}")
        print(f"Procedures: {len(PROCEDURES)}")
        print(f"Specs: {len(SPECS)}")
        print(f"Maintenance intervals: {len(MAINTENANCE)}")
        print(f"TSBs: {len(TSBS)}")
        print(f"Recalls: {len(RECALLS)}")
        print(f"Parts: {len(PARTS)}")
        print(f"Baselines: {len(BASELINES)}")
        print(f"Systems: {sorted({i.system for i in ISSUES.values()})}")
        return

    if args.search:
        for r in search(args.search):
            print(f"  [{r['type']:10}] {r.get('slug') or r.get('item')} — {r.get('name') or r.get('value')}")
        return

    if args.issue:
        i = ISSUES.get(args.issue)
        if not i:
            print(f"no such issue: {args.issue}"); return
        print(json.dumps({**i.__dict__, "related_parts": list(i.related_parts)},
                          indent=2, default=str))
        return

    if args.procedure:
        p = PROCEDURES.get(args.procedure)
        if not p:
            print(f"no such procedure: {args.procedure}"); return
        print(json.dumps(p.__dict__, indent=2, default=str))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
