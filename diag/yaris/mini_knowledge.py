"""2013 Mini Cooper Countryman R60 N16 — knowledge bundle.

N16 specifics (distinct from N14/N18):
  - Naturally aspirated 1.6L, 122 HP
  - PORT-injected (MPI) — not DI, so carbon buildup less severe
  - Electric water pump + integrated electronic thermostat housing
  - VANOS (variable intake + exhaust cam timing) via 2 oil-control solenoids
  - No HPFP, no turbo — base Countryman / Cooper only (not "S")

Sources: NorthAmericanMotoring R60 forum, Pelican Parts tech articles,
Atlantic Motorcar warranty-extension docs, ClassAction.org, NHTSA bulletins.
"""
from .knowledge import Issue, Procedure, Spec, MaintenanceItem, TSB, Recall, Part, DiagnosticBaseline


# ── Top issues ──────────────────────────────────────────────────────────
MINI_ISSUES: dict[str, Issue] = {
    "mini-timing-chain-rattle": Issue(
        slug="mini-timing-chain-rattle", name="Timing Chain Rattle ('Death Rattle')",
        system="engine", rank=1,
        frequency="Endemic on N14; reduced on N16 but still common at 60k-100k mi",
        typical_mileage="60,000-100,000 mi (>96,000-160,000 km)",
        symptoms=["Metallic rattle 1-3 sec on cold start",
                  "Rattle becomes continuous as wear progresses",
                  "P0016 / P0017 correlation codes latch",
                  "Rough idle after warm-up",
                  "Hard start or no-start if chain jumps teeth"],
        causes=["Chain tensioner spring weakens (primary)",
                "Chain stretch from long-interval oil or wrong oil spec",
                "Low oil level reduces hydraulic tensioner pressure",
                "Non-LL-01 oil accelerates wear",
                "Chain guide wear (plastic guides shed material)"],
        diagnostics=["Cold-start rattle >3 sec = replace chain kit IMMEDIATELY",
                     "P0016/P0017 with stretch-rattle = full chain kit + tensioner",
                     "Check oil level FIRST (low oil accelerates damage)",
                     "Do NOT drive if chain noise present — catastrophic risk"],
        difficulty=5, cost_diy_usd=(200, 400), cost_shop_usd=(1000, 2000),
        related_dtcs=["P0016", "P0017", "P0014", "P0015"],
        kb_links=[],
        tsb_refs=["SI M11 02 13", "SIB 11 03 14"],
        notes="BMW 2016 class-action settlement ($30M) reimbursed some out-of-pocket repairs through 2013 MY. Updated tensioner PN 11318611993 supersedes 11317618943. ALWAYS use BMW LL-01 5W-30 oil after repair.",
    ),

    "mini-vanos-solenoid": Issue(
        slug="mini-vanos-solenoid", name="VANOS Solenoid Contamination / Sticking",
        system="engine", rank=2,
        frequency="Common 45-75k mi, often paired with missed oil changes",
        typical_mileage="45,000-75,000 mi",
        symptoms=["P0010/P0011/P0012 (intake VANOS)",
                  "P0013/P0014 (exhaust VANOS)",
                  "BMW-raw codes 2A82/2A87/2A98/2A99",
                  "Rough idle", "Poor fuel economy",
                  "Hesitation on acceleration"],
        causes=["Oil sludge clogging solenoid oil passages",
                "Solenoid electrical failure (coil open/shorted)",
                "Low oil pressure (check oil level FIRST)",
                "Wrong oil spec (non-LL-01) left sludge deposits"],
        diagnostics=["SWAP TEST: physically swap intake↔exhaust solenoids",
                     "If code follows the solenoid → that solenoid is faulty",
                     "If code stays on same cam → VANOS hardware, not solenoid",
                     "Check oil level + condition before replacing anything"],
        difficulty=2, cost_diy_usd=(30, 90), cost_shop_usd=(200, 400),
        related_dtcs=["P0010", "P0011", "P0012", "P0013", "P0014"],
        related_procedures=["mini-vanos-replace"],
        tsb_refs=["SI B11 08 11"],
        notes="Solenoid OEM PN 11368610388 (updated) or 11367604292. Swap test is diagnostic gold standard.",
    ),

    "mini-thermostat-housing": Issue(
        slug="mini-thermostat-housing", name="Thermostat Housing Crack / Coolant Leak",
        system="cooling", rank=3,
        frequency="~1 in 4 vehicles past 50k mi — plastic housing known weak point",
        typical_mileage="40,000+ mi",
        symptoms=["Coolant puddle at rear of engine",
                  "White crystalline residue around housing",
                  "P0128 (coolant below regulating temp) if stuck open",
                  "P0597/P0598/P0599 if thermostat heater circuit fails",
                  "Slow warm-up, weak heater"],
        causes=["Plastic thermostat housing cracks from thermal cycling",
                "Integrated electronic thermostat is in plastic assembly (11538674895)",
                "Seal degradation around housing-to-head interface"],
        diagnostics=["Visual inspection — look for white residue and wet areas at rear of head",
                     "Pressure test cooling system to 15 psi, listen/feel for leaks",
                     "If P0597/8/9 codes + warmup normal: thermostat heater circuit only"],
        difficulty=3, cost_diy_usd=(60, 120), cost_shop_usd=(200, 350),
        related_dtcs=["P0128", "P0597", "P0598", "P0599"],
        related_procedures=["mini-thermostat-replace"],
        tsb_refs=["SI B17 01 13"],
        notes="Replace entire housing assembly — thermostat is integrated and not separately serviceable.",
    ),

    "mini-water-pump": Issue(
        slug="mini-water-pump", name="Pierburg Electric Water Pump Failure",
        system="cooling", rank=4,
        frequency="1 in 5 vehicles at 80k-100k mi",
        typical_mileage="60,000-90,000 mi",
        symptoms=["Sudden overheat / temperature spike",
                  "No heat from heater",
                  "P2181 cooling system performance",
                  "Mode 22 DID 2261 (water pump RPM) reads 0 when engine warm"],
        causes=["Pierburg electric pump bearing failure (most common)",
                "Pump seal failure allowing coolant into motor",
                "Plastic impeller degradation over time",
                "Wiring harness corrosion at pump connector"],
        diagnostics=["Mode 22 DID 2261: should read 200-500 RPM idle, 500-4000 under load",
                     "If RPM=0 with engine warm → pump dead",
                     "Listen for pump hum 5 sec after cold start (should spin briefly)"],
        difficulty=4, cost_diy_usd=(100, 180), cost_shop_usd=(300, 500),
        related_dtcs=["P2181"],
        related_procedures=["mini-water-pump-replace"],
        tsb_refs=["SI B11 04 13"],
        notes="Pierburg PN 11537630368 (new) supersedes 11537619360. Often replace with thermostat housing as package.",
    ),

    "mini-pcv-valve-cover": Issue(
        slug="mini-pcv-valve-cover", name="PCV Diaphragm / Valve Cover Failure",
        system="engine", rank=5,
        frequency="Common past 60k mi — integrated PCV in valve cover",
        typical_mileage="60,000+ mi",
        symptoms=["Whistling sound at idle (diaphragm tear)",
                  "High crankcase pressure pushing oil past dipstick seal",
                  "Oil leak onto exhaust manifold (burning smell)",
                  "P0171 (lean) from intake vacuum",
                  "P052E / P1093 PCV codes",
                  "Rough idle in cold weather"],
        causes=["PCV diaphragm tears — it's integrated INSIDE the valve cover and not separately serviceable",
                "Plastic valve cover warps from thermal cycling",
                "Cold-weather PCV heater failure (see recall 18V-193)"],
        diagnostics=["Whistle at idle that stops when oil filler cap lifted = PCV diaphragm torn",
                     "Check oil dipstick for oil push-out or bubbling",
                     "Inspect valve cover for oil weeping onto exhaust"],
        difficulty=3, cost_diy_usd=(50, 150), cost_shop_usd=(250, 450),
        related_dtcs=["P0171", "P052E", "P1093", "P1497", "P1498"],
        tsb_refs=["SI B12 10 11"],
        notes="Replace entire valve cover (PN 11127646552 / 11127585907) — PCV not a serviceable item. Replace gasket at the same time. US NHTSA recall 17V-287 and 18V-193 relate to PCV heater fire risk.",
    ),

    "mini-coil-pack": Issue(
        slug="mini-coil-pack", name="Ignition Coil Failure (Red-Top Bosch)",
        system="ignition", rank=6,
        frequency="Common at 60k-100k mi",
        typical_mileage="60,000-100,000 mi",
        symptoms=["P0301-P0304 single cylinder misfire",
                  "Rough idle, shaking",
                  "CEL flashing on acceleration",
                  "Loss of power"],
        causes=["Bosch 'red-top' coil insulation failure (most common)",
                "Spark plug wear loading the coil",
                "Oil contamination of coil boot from valve-cover leak"],
        diagnostics=["Swap test: move coil to different cylinder, see if misfire follows",
                     "Fuel-trim test: pull coil connector on idling engine, listen for RPM drop",
                     "Check for oil in coil boot (valve-cover leak)"],
        difficulty=1, cost_diy_usd=(40, 80), cost_shop_usd=(150, 250),
        related_dtcs=["P0301", "P0302", "P0303", "P0304", "P0351", "P0352", "P0353", "P0354"],
        notes="OEM BMW/MINI 12138647689 (Bosch 0221504470). Aftermarket Delphi GN10328 is known-good alternative. Always replace spark plugs at same time.",
    ),

    "mini-clutch-r60": Issue(
        slug="mini-clutch-r60", name="Clutch Failure (Manual — R60 is heavier)",
        system="drivetrain", rank=7,
        frequency="Common 40k-70k mi on manual R60 — OE clutch undersized for weight",
        typical_mileage="40,000-70,000 mi",
        symptoms=["Slippage under acceleration (tach rises without speed)",
                  "Judder on engagement",
                  "High pedal engagement point",
                  "Burning smell under load"],
        causes=["R60 is ~300 lb heavier than R56 hatch — OE clutch undersized",
                "Aggressive driving wears clutch faster",
                "Oil contamination from rear main seal leak"],
        difficulty=5, cost_diy_usd=(300, 600), cost_shop_usd=(1200, 1800),
        notes="Upgrade to Sachs Performance or SPEC Stage 2 recommended on replacement.",
    ),

    "mini-crank-sensor": Issue(
        slug="mini-crank-sensor", name="Crankshaft Position Sensor Failure",
        system="ignition", rank=8,
        frequency="Moderate past 60k mi — intermittent failure common before total",
        symptoms=["Intermittent no-start (restart works after sit)",
                  "Stall at idle or cruise",
                  "P0335 / P0336 codes",
                  "Tachometer glitches or drops to zero while running"],
        causes=["Sensor magnetic element degrades with heat cycles",
                "Crank trigger wheel debris contamination"],
        diagnostics=["Intermittent faults: heat-test with hair dryer on sensor during idle",
                     "P0335 with temperature correlation is diagnostic",
                     "CKP sensor output should be clean sinusoidal on scope"],
        difficulty=2, cost_diy_usd=(40, 80), cost_shop_usd=(150, 250),
        related_dtcs=["P0335", "P0336"],
    ),

    "mini-coolant-temp-sensor": Issue(
        slug="mini-coolant-temp-sensor", name="Coolant Temp Sensor (CTS) Drift",
        system="cooling", rank=9,
        frequency="Common past 80k mi",
        symptoms=["Intermittent fan activation at wrong times",
                  "LTFT wandering (fueling based on wrong temp)",
                  "Hard cold start",
                  "Temp gauge behaves erratically"],
        causes=["Sensor element drifts with age",
                "Connector corrosion"],
        difficulty=2, cost_diy_usd=(30, 60), cost_shop_usd=(100, 180),
        notes="OEM PN 11537549476.",
    ),

    "mini-oil-pan-gasket": Issue(
        slug="mini-oil-pan-gasket", name="Oil Pan / Oil Pump Solenoid Leak (2011-2013 R60)",
        system="engine", rank=10,
        frequency="Specific 2011-2013 R60 issue",
        symptoms=["Oil drips from bottom of engine",
                  "Oil can seep into nearby wiring harness — potential ECU damage",
                  "Low oil warning if leak progresses"],
        causes=["Oil pan gasket hardens from thermal cycling",
                "Oil pump solenoid seal leaks into loom area"],
        difficulty=4, cost_diy_usd=(80, 150), cost_shop_usd=(400, 700),
        notes="Check wiring loom for oil soak during repair — oil-soaked looms cause electrical faults.",
    ),
}


# ── Procedures ──────────────────────────────────────────────────────────
MINI_PROCEDURES: dict[str, Procedure] = {
    "mini-oil-change": Procedure(
        slug="mini-oil-change", name="Oil + Filter Change (N16)",
        system="engine", difficulty=1, time_minutes=25,
        tools=["36mm oil filter cap wrench", "17mm drain plug socket",
               "Drain pan", "Torque wrench"],
        parts={"oil": "BMW LongLife-01 5W-30 — 4.2L (ONLY LL-01, no substitutes)",
               "filter_cartridge": "BMW 11427622446 (supersedes 11427557012)",
               "drain_plug_washer": "BMW 07119963151"},
        torque_specs=["Drain plug: 25 Nm", "Oil filter cap: 25 Nm"],
        steps=["Warm engine 5 min, shut off",
               "Lift car on jack stands (engine oil pan is at bottom)",
               "Remove drain plug (17mm)",
               "Drain fully (10-15 min — oil is sealed with check valve, slow)",
               "Access filter cap through upper engine bay (36mm)",
               "Remove old filter cartridge, install new with O-rings oiled",
               "Reinstall drain plug with NEW crush washer — torque 25 Nm",
               "Torque filter cap 25 Nm",
               "Fill 4.2 L LL-01 5W-30",
               "Start engine, check dipstick, top if needed"],
        safety="Non-LL-01 oil voids warranty and causes VANOS + timing chain damage. "
               "LL-01 approved brands: Castrol Edge LL-01, Shell Helix Ultra LL-01, "
               "Mobil 1 ESP LL-01.",
        kb_link="",
    ),

    "mini-vanos-replace": Procedure(
        slug="mini-vanos-replace", name="VANOS Solenoid Replacement",
        system="engine", difficulty=2, time_minutes=20,
        tools=["10mm socket (solenoid bolt)", "Small flat screwdriver (connector release)"],
        parts={"solenoid_each": "BMW 11368610388 (updated) or 11367604292",
               "cost": "~$30-60 per solenoid, 2 required if both cams"},
        torque_specs=["Solenoid retainer bolt: 10 Nm"],
        steps=["Disconnect battery (safe practice)",
               "Locate solenoid: intake on front-top of head, exhaust on rear",
               "Unplug electrical connector (press tab, pull)",
               "Remove single 10mm bolt securing retainer",
               "Pull solenoid straight out (have rag ready for oil)",
               "Inspect filter screen on solenoid tip — sludge = clean with brake cleaner",
               "Insert new solenoid, retain with bolt (10 Nm)",
               "Reconnect electrical, reconnect battery",
               "Clear codes, idle 5 min for relearn"],
        safety="Check engine oil level + quality BEFORE replacing. If oil is sludged, "
               "change oil first — a new solenoid in dirty oil clogs quickly.",
    ),

    "mini-water-pump-replace": Procedure(
        slug="mini-water-pump-replace", name="Electric Water Pump Replacement",
        system="cooling", difficulty=4, time_minutes=180,
        tools=["13mm / 10mm sockets", "Torx T30", "Drain pan",
               "Coolant pressure tester (for post-install test)"],
        parts={"water_pump": "Pierburg 11537630368 (new) / BMW 7.02851.20.0",
               "coolant": "BMW Blue coolant 82141467704 — ~6L with distilled water 50/50",
               "thermostat_housing": "CONSIDER replacing together (11538674895)"},
        torque_specs=["Water pump bolts: 10 Nm",
                      "Electrical connector: hand-tight"],
        steps=["Drain coolant via lower radiator hose or petcock",
               "Unbolt under-tray for access",
               "Disconnect hoses at pump inlet + outlet",
               "Remove pump electrical connector",
               "Remove 2-3 retaining bolts (10mm)",
               "Pull pump out with gasket",
               "Clean mating surface",
               "Install new pump with fresh gasket",
               "Torque bolts 10 Nm, reconnect hoses and connector",
               "Refill coolant via expansion tank",
               "Perform air-bleed cycle: engine on with cap off, heater max-hot, "
               "squeeze upper hose repeatedly until bubbling stops",
               "Check for leaks, verify pump RPM via Mode 22 DID 2261"],
        safety="Do not reuse old coolant. BMW thermostat is map-controlled — do not substitute with mechanical t-stat from aftermarket.",
    ),

    "mini-thermostat-replace": Procedure(
        slug="mini-thermostat-replace", name="Thermostat Housing Replacement",
        system="cooling", difficulty=3, time_minutes=90,
        tools=["10mm, 13mm sockets", "Torx T30", "Drain pan"],
        parts={"housing_assembly": "BMW 11538674895 (includes thermostat)",
               "coolant": "BMW Blue 82141467704 — ~4L top-up after",
               "o-rings": "Included in housing kit"},
        torque_specs=["Housing bolts: 10-12 Nm"],
        steps=["Drain sufficient coolant (2-3 L)",
               "Disconnect upper + lower housing coolant hoses",
               "Unplug electrical connector",
               "Remove 3-4 housing bolts",
               "Remove old housing — inspect for cracks and residue",
               "Install new housing assembly (new o-rings pre-fit)",
               "Torque bolts 10-12 Nm",
               "Reconnect hoses + connector",
               "Refill coolant, bleed air same as water pump procedure"],
    ),

    "mini-spark-plugs": Procedure(
        slug="mini-spark-plugs", name="Spark Plug Replacement (4x NGK)",
        system="ignition", difficulty=1, time_minutes=30,
        tools=["14mm spark plug socket w/ rubber insert", "Extension", "Torque wrench"],
        parts={"plugs_4x": "BMW 12122158165 (NGK ILZKBR7B8G) — gap 0.028 in / 0.7 mm pre-gapped",
               "do_not_regap": "DO NOT re-gap iridium — factory set"},
        torque_specs=["Spark plugs: 23 Nm (17 ft-lb)"],
        steps=["Disconnect battery",
               "Remove engine cover (2 screws or push-clips)",
               "Unplug 4 ignition coil connectors",
               "Remove coil retainer clips/screws",
               "Pull coils straight up (twist slightly if stuck)",
               "Using 14mm plug socket with rubber insert, remove each plug",
               "Verify new plugs have correct gap (0.028 in pre-set, don't touch)",
               "Thread plugs by hand first (critical — no cross-thread)",
               "Torque 23 Nm — do NOT over-tighten (breaks electrode)",
               "Reinstall coils, push firmly until click",
               "Reconnect coil connectors",
               "Reconnect battery, test idle"],
        safety="Over-torquing BMW iridium plugs SHATTERS the ceramic. 23 Nm exactly. "
               "Do not adjust gap — iridium factory-set.",
    ),
}


# ── Specs ───────────────────────────────────────────────────────────────
MINI_SPECS: list[Spec] = [
    # Oil
    Spec("Engine oil grade (STRICT)", "BMW LongLife-01 5W-30 ONLY", "grade", "engine",
         "Non-LL-01 causes sludge + timing chain damage"),
    Spec("Engine oil capacity", "4.2", "L", "engine"),
    Spec("Oil drain plug torque", "25", "Nm", "engine"),
    Spec("Oil filter cap torque", "25", "Nm", "engine"),
    Spec("Oil filter cartridge", "BMW 11427622446", "OEM PN", "engine"),

    # Spark plugs
    Spec("Spark plug torque", "23", "Nm", "ignition", "17 ft-lb — over-tightening breaks electrode"),
    Spec("Spark plug PN", "NGK ILZKBR7B8G / BMW 12122158165", "OEM", "ignition"),
    Spec("Spark plug gap", "0.7 (0.028 in) — pre-gapped iridium", "mm", "ignition",
         "DO NOT re-gap"),

    # Cooling
    Spec("Coolant type", "BMW Blue 82141467704", "OEM", "cooling"),
    Spec("Coolant capacity", "~6.0", "L", "cooling", "50/50 with distilled water"),
    Spec("Thermostat housing bolts", "10-12", "Nm", "cooling"),
    Spec("Water pump bolts", "10", "Nm", "cooling"),
    # BMW map-controlled thermostat — NOT like Toyota
    Spec("Thermostat regulating temp (low-load economy map)", "~103", "°C", "cooling",
         "BMW map-controlled — runs hot for efficiency"),
    Spec("Thermostat regulating temp (high-load)", "~88", "°C", "cooling",
         "Drops to 88°C under WOT / high-load"),
    Spec("Cooling fan high-speed trigger", "~108", "°C", "cooling"),

    # VANOS
    Spec("VANOS solenoid torque", "10", "Nm", "engine"),
    Spec("VANOS solenoid PN", "BMW 11368610388 (updated)", "OEM", "engine"),

    # Timing chain (dealer job)
    Spec("Timing chain updated tensioner", "BMW 11318611993", "OEM", "engine"),
    Spec("Timing chain", "BMW 11318648732", "OEM", "engine"),

    # Brakes (front, base R60 — heavier than R56)
    Spec("Front brake pad PN", "BMW 34116858910", "OEM", "brakes"),
    Spec("Front rotor diameter", "294", "mm", "brakes"),
    Spec("Front rotor thickness (nominal)", "22", "mm", "brakes"),
    Spec("Rear brake pad PN", "BMW 34216778327", "OEM", "brakes"),
    Spec("Rear rotor diameter", "280", "mm (solid)", "brakes"),

    # Battery
    Spec("Battery spec", "AGM 70Ah 760A (BMW 61217604516)", "OEM", "electrical",
         "MUST be registered with Carly/BimmerCode/ISTA after replacement — "
         "otherwise wrong charge profile premature-fails battery"),

    # Fluid / electrical
    Spec("Brake fluid", "DOT 4 (BMW spec)", "grade", "brakes"),
    Spec("Transmission fluid (manual)", "BMW MTF LT-3", "OEM", "drivetrain"),
    Spec("Transmission fluid (auto U340E/AW6)", "BMW ATF LT71141 (Esso LT71141)", "OEM", "drivetrain"),

    # Engine baseline
    Spec("Compression nominal", "150-180", "psi", "engine"),
    Spec("Idle RPM spec", "720-780", "RPM", "engine"),
    Spec("Healthy MAF at warm idle", "2.8-3.6", "g/s", "fuel", "N16 1.6L NA"),
    Spec("Fuel rail pressure", "~4", "bar", "fuel", "Port injection — no HPFP"),
]


# ── Parts Cross-Reference additions ─────────────────────────────────────
MINI_PARTS: dict[str, Part] = {
    "mini-oil-filter": Part(
        name="N16 Oil filter cartridge", system="engine",
        oem="BMW 11427622446 (supersedes 11427557012)",
        aftermarket={"Mann": "HU816X", "Mahle": "OX386D", "Hengst": "E340HD129"},
        price_usd=(10, 20)),
    "mini-air-filter": Part(
        name="N16 Air filter (R60 base)", system="engine",
        oem="BMW 13727568728",
        aftermarket={"Mann": "C2774/4", "Mahle": "LX1987"},
        price_usd=(18, 30)),
    "mini-cabin-filter": Part(
        name="Cabin filter (charcoal)", system="hvac",
        oem="BMW 64319127516 / 64319194098",
        aftermarket={"Mann": "CUK2545"},
        price_usd=(20, 40)),
    "mini-spark-plug": Part(
        name="Iridium spark plug (4x)", system="ignition",
        oem="BMW 12122158165 (NGK ILZKBR7B8G)",
        aftermarket={"NGK": "ILZKBR7B8G / 97968", "Bosch": "ZR5TPP33"},
        price_usd=(40, 70),
        notes="Gap 0.028 in pre-set. Do not re-gap."),
    "mini-coil": Part(
        name="Ignition coil (red-top, 4x)", system="ignition",
        oem="BMW 12138647689",
        aftermarket={"Bosch": "0221504470", "Delphi": "GN10328"},
        price_usd=(40, 80)),
    "mini-water-pump": Part(
        name="Electric water pump", system="cooling",
        oem="BMW 11537630368 (new) / 11537619360 (old)",
        aftermarket={"Pierburg": "7.02851.20.0"},
        price_usd=(120, 200),
        notes="Pump RPM visible via Mode 22 DID 2261. Common failure 60-90k mi."),
    "mini-thermostat-housing": Part(
        name="Thermostat housing assembly", system="cooling",
        oem="BMW 11538674895",
        aftermarket={"Mahle": "TH47", "Behr": "BTH010"},
        price_usd=(60, 120),
        notes="Integrated electric thermostat — replace as assembly, not serviceable."),
    "mini-vanos-solenoid": Part(
        name="VANOS solenoid (per cam)", system="engine",
        oem="BMW 11368610388 (updated) / 11367604292",
        aftermarket={"Hella": "OE", "Pierburg": "OE"},
        price_usd=(35, 80)),
    "mini-valve-cover": Part(
        name="Valve cover with integrated PCV", system="engine",
        oem="BMW 11127646552 / 11127585907",
        aftermarket={"Genuine Febi": "47048"},
        price_usd=(120, 200),
        notes="PCV diaphragm integrated in cover — not separately serviceable."),
    "mini-maf": Part(
        name="MAF sensor", system="fuel",
        oem="BMW 13627597085",
        aftermarket={"Bosch": "0280218205"},
        price_usd=(80, 150)),
    "mini-upstream-o2": Part(
        name="Upstream O2 sensor (wideband)", system="emissions",
        oem="BMW 11787576673",
        aftermarket={"Bosch": "17212 / 17017"},
        price_usd=(130, 200)),
    "mini-downstream-o2": Part(
        name="Downstream O2 sensor", system="emissions",
        oem="BMW 11787570481",
        aftermarket={"Bosch": "16795"},
        price_usd=(50, 100)),
    "mini-front-pads": Part(
        name="Front brake pads (R60 base)", system="brakes",
        oem="BMW 34116858910",
        aftermarket={"Akebono": "OE", "Textar": "OE", "Pagid": "OE"},
        price_usd=(45, 90)),
    "mini-front-rotor": Part(
        name="Front brake rotor 294x22mm", system="brakes",
        oem="BMW 34116854999",
        aftermarket={"Zimmermann": "OE", "Brembo": "09.A427.11"},
        price_usd=(60, 130)),
    "mini-timing-chain-kit": Part(
        name="Timing chain kit (chain + tensioner + guides)", system="engine",
        oem="BMW 11318611993 tensioner + 11318648732 chain + 11317607551 upper + 11317583365 lower",
        aftermarket={"Iwis": "OE supplier kit"},
        price_usd=(200, 400),
        notes="N16 supersedes earlier N14 parts — use only updated PNs. Labor $800-1500 at shop."),
    "mini-ckp-sensor": Part(
        name="Crankshaft position sensor", system="ignition",
        oem="BMW 13627548994",
        aftermarket={"Bosch": "0986280470"},
        price_usd=(30, 70)),
    "mini-cts": Part(
        name="Coolant temperature sensor", system="cooling",
        oem="BMW 11537549476",
        aftermarket={"Hella": "6PT009107-571"},
        price_usd=(25, 50)),
}


# ── Additional Mini-specific DTCs ────────────────────────────────────────
MINI_EXTRA_DTCS: list[tuple] = [
    # (code, title, severity, system, description-for-notes)
    ("P0015", "Exhaust Cam Correlation — Timing Chain (BMW 2A99)",
     "critical", "engine", "Exhaust cam timing correlation. On N16, often indicates timing chain stretch OR exhaust VANOS solenoid."),
    ("P0021", "VANOS Exhaust Over-advanced (Bank 1)",
     "warn", "engine", "Exhaust cam over-advanced. Solenoid stuck open or oil pressure high."),
    ("P0022", "VANOS Exhaust Over-retarded (Bank 1)",
     "warn", "engine", "Exhaust cam over-retarded. Solenoid stuck closed or oil pressure low."),
    ("P052E", "PCV Valve / Crankcase Vent Fault",
     "warn", "engine", "On N16 this is PCV diaphragm in valve cover — replace cover."),
    ("P1093", "BMW PCV System Insufficient Flow",
     "warn", "engine", "PCV diaphragm torn — whistle at idle confirms."),
    ("P0597", "Thermostat Heater Circuit Open",
     "warn", "cooling", "BMW map-controlled thermostat heater circuit — replace housing."),
    ("P0598", "Thermostat Heater Circuit Low",
     "warn", "cooling", "Thermostat heater shorted to ground — replace housing."),
    ("P0599", "Thermostat Heater Circuit High",
     "warn", "cooling", "Thermostat heater shorted to power — replace housing."),
    ("P1345", "BMW Camshaft Position / Sync Fault",
     "critical", "engine", "Cam sync lost — often timing chain stretch."),
    ("P1497", "PCV Heater Control Circuit",
     "warn", "engine", "Cold-weather PCV heater. See NHTSA 18V-193 recall."),
    ("P1498", "PCV Heater Control Circuit Open",
     "warn", "engine", "Cold-weather PCV heater — recall item."),
    ("P2181", "Cooling System Performance",
     "critical", "cooling", "Electric water pump failure or thermostat housing crack on N16."),
    ("P2187", "System Too Lean at Idle",
     "warn", "fuel", "Vacuum leak at idle — often PCV diaphragm torn on N16."),
    ("P0234", "Turbocharger Overboost",
     "warn", "fuel", "Base N16 has NO turbo — this code suggests wrong engine family or ECU swap. Verify."),
    ("P0299", "Turbocharger Underboost",
     "warn", "fuel", "Base N16 has NO turbo — same note as P0234."),
]


# ── TSBs ────────────────────────────────────────────────────────────────
MINI_TSBS: list[TSB] = [
    TSB("SI M11 02 13", "Timing chain noise / tensioner replacement",
        "Full timing chain kit replacement for rattle/P0016/P0017 on N-series. "
        "Applies R56/R60 N12/N14/N16 through 2013 MY.",
        fix="Replace tensioner (updated PN 11318611993) + upper/lower guides + chain + seals. "
        "Reset adaptations via ISTA after.",
        source="BMW/MINI TSB"),
    TSB("SI B11 08 11", "VANOS solenoid cleaning/replacement",
        "Procedure for 2A82/2A87/2A9A codes: clean or replace oil control valves."),
    TSB("SI B17 01 13", "Thermostat housing leak",
        "Replace thermostat housing with updated assembly PN 11538674895."),
    TSB("SI B12 10 11", "Crankcase vent (PCV) valve whistling / oil consumption",
        "Replace valve cover (PCV integrated, not separately serviceable)."),
    TSB("SI B11 04 13", "Coolant pump failure",
        "Diagnostic + replacement procedure for electric water pump."),
    TSB("Warranty Extension 2016", "Class-action settlement reimbursement",
        "BMW/MINI $30M class-action settlement covered timing chain failures on "
        "affected N14/N16 VINs through 2013. Reimbursement may still be available to "
        "owners who paid out-of-pocket at authorized dealers.",
        source="Atlantic Motorcar / ClassAction.org"),
]


# ── Recalls ─────────────────────────────────────────────────────────────
MINI_RECALLS: list[Recall] = [
    Recall("14V-540 / 14V-541", "2014", "Footwell Module Water Intrusion",
           "Select build VINs — water can enter footwell module causing electrical faults.",
           remedy="Reroute water drain channel + inspect/replace footwell module.",
           applies_to_vin="verify by VIN at miniusa.com", source="NHTSA"),
    Recall("17V-287", "2017", "PCV Heater Short Circuit Fire Risk",
           "PCV heater internal short can cause thermal event.",
           remedy="Replace PCV heater element.",
           applies_to_vin="verify by VIN", source="NHTSA"),
    Recall("18V-193", "2018", "Crankcase Vent Heater Fire Risk",
           "Crankcase ventilation heater fire risk on multiple MINI models.",
           remedy="Replace crankcase vent heater.",
           applies_to_vin="verify by VIN", source="NHTSA"),
]


# ── Baselines ───────────────────────────────────────────────────────────
MINI_BASELINES: list[DiagnosticBaseline] = [
    DiagnosticBaseline("010C", "RPM (warm idle)", "720-780",
                       warning_range="<600 or >900",
                       notes="BMW spec ±30 RPM from 750."),
    DiagnosticBaseline("0110", "MAF g/s (warm idle)", "2.8-3.6",
                       warning_range="<2.0 or >4.5",
                       notes="N16 NA 1.6L."),
    DiagnosticBaseline("0106", "STFT B1 %", "±0 to ±5", "±10+",
                       notes="Typical BMW narrowband fuel trim."),
    DiagnosticBaseline("0107", "LTFT B1 %", "-7 to +7", "±10 (watch), ±20 (P0171/P0172)",
                       notes="LTFT that climbs under load suggests PCV/boost leak."),
    DiagnosticBaseline("0105", "Coolant °C", "95-108 (normal economy map)",
                       warning_range=">110 or <80 with engine warm",
                       notes="BMW runs HOT by design. 105°C cruise is normal, not overheat."),
    DiagnosticBaseline("0142", "Control module V", "12.6-14.6",
                       notes="BMW IBS may cycle into charge-off mode — 12.6-13.2V at idle NOT a fault."),
    DiagnosticBaseline("0111", "Throttle %", "8-14 at warm idle",
                       notes="ETC base."),
    DiagnosticBaseline("010E", "Timing advance °", "4-12 at idle",
                       notes="N16 conservative map."),
    DiagnosticBaseline("0134", "O2 B1S1 wideband λ", "0.98-1.02",
                       notes="Should cycle around stoich."),
    DiagnosticBaseline("0115", "O2 B1S2 V", "0.6-0.8 steady",
                       notes="Slow cycling = healthy cat."),
    # Mode 22 BMW-specific — need ATSH 7E0 to query
    DiagnosticBaseline("22 2261", "Water pump RPM (Mode 22)", "200-500 idle / 500-4000 load",
                       warning_range="=0 with engine warm → pump dead",
                       notes="Queried via ATSH7E0 then '22 2261'. DID value × 1 = RPM."),
    DiagnosticBaseline("22 223A", "VANOS intake angle (Mode 22)", "0 to +10° at idle",
                       notes="Needs ATSH7E0. Divide raw by 10."),
]


# ── Install hook ────────────────────────────────────────────────────────
def install_into_main_db():
    """Merge Mini data into the central knowledge / DTC / parts stores.

    Called at module import so the web UI sees both Yaris + Mini content.
    Each Mini entry has a prefix (mini-) that distinguishes it from Yaris.
    """
    from . import knowledge, dtc_db
    from .knowledge import Issue, Procedure, Spec, MaintenanceItem, TSB, Recall, Part, DiagnosticBaseline
    from .dtc_db import DtcEntry

    # Issues + procedures + parts
    knowledge.ISSUES.update(MINI_ISSUES)
    knowledge.PROCEDURES.update(MINI_PROCEDURES)
    knowledge.PARTS.update(MINI_PARTS)
    knowledge.SPECS.extend(MINI_SPECS)
    knowledge.TSBS.extend(MINI_TSBS)
    knowledge.RECALLS.extend(MINI_RECALLS)
    knowledge.BASELINES.extend(MINI_BASELINES)

    # DTCs
    for code, title, severity, system, note in MINI_EXTRA_DTCS:
        code = code.upper()
        if code not in dtc_db.DTC_DATABASE:
            dtc_db.DTC_DATABASE[code] = DtcEntry(
                code=code, title=title, severity=severity, system=system,
                notes=note, kb_links=["MINI R60 N16 Service Documentation"],
            )


# Eager install at import so web UI sees everything
install_into_main_db()
