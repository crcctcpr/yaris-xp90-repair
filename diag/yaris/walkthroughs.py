"""Interactive diagnostic walkthroughs.

Each walkthrough is a state machine: nodes are info/action/question/measurement,
edges are conditional transitions. The web UI renders one step at a time and
transitions based on user input.

Node types:
  - "info"        : explain something, advance on click
  - "action"      : "do this". advance on click.
  - "question"    : yes/no → different next nodes
  - "measurement" : user enters a number; range check branches
  - "choice"      : N options each with its own next node
  - "result"      : terminal — shows conclusion + linked actions
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    id: str
    type: str            # "info", "action", "question", "measurement", "choice", "result"
    title: str
    body: str = ""
    next_id: str = ""                         # info/action: next step
    yes_id: str = ""                          # question: yes path
    no_id: str = ""                           # question: no path
    measurement_pid: str = ""                 # for display
    measurement_units: str = ""
    measurement_low: float = 0                # if value is below/within/above range
    measurement_high: float = 0               # if not set (both 0), skip range check
    pass_id: str = ""                         # measurement: within [low, high]
    fail_low_id: str = ""                     # measurement: below low
    fail_high_id: str = ""                    # measurement: above high
    choices: list[dict] = field(default_factory=list)  # choice: [{label, next_id}]
    # Result-only:
    result_status: str = ""                   # "fixed", "replace_part", "inconclusive"
    linked_issue: str = ""                    # related Issue slug
    linked_procedure: str = ""                # related Procedure slug
    linked_shopping: str = ""                 # shopping list slug


@dataclass
class Walkthrough:
    slug: str
    name: str
    summary: str
    symptom_triggers: list[str] = field(default_factory=list)  # from symptoms.py
    dtc_triggers: list[str] = field(default_factory=list)
    start_id: str = ""
    steps: dict[str, Step] = field(default_factory=dict)

    def add(self, step: Step):
        self.steps[step.id] = step
        if not self.start_id:
            self.start_id = step.id


# ── P0101 MAF diagnosis ─────────────────────────────────────────────────
_p0101 = Walkthrough(
    slug="p0101-diag",
    name="P0101 / MAF sensor diagnosis",
    summary="Step-by-step walkthrough to diagnose a MAF fault: clean, verify, replace.",
    dtc_triggers=["P0101", "P0102", "P0103"],
    symptom_triggers=["poor-mpg", "hesitation-accel", "rough-idle"],
)
_p0101.add(Step(
    id="start", type="info",
    title="P0101 walkthrough — start",
    body="This walkthrough diagnoses a MAF Sensor Range/Performance fault. "
         "You'll need: OBD adapter (paired), CRC 05110 MAF cleaner (~$8), "
         "T20 Torx, 10mm wrench for battery. ~20 minutes.",
    next_id="check-engine-running",
))
_p0101.add(Step(
    id="check-engine-running", type="question",
    title="Is the engine warm and running?",
    body="For accurate MAF readings, the engine must be at operating temperature "
         "(coolant ≥80°C) and idling in Park/Neutral with A/C off.",
    yes_id="measure-idle-maf", no_id="warm-up",
))
_p0101.add(Step(
    id="warm-up", type="action",
    title="Warm the engine",
    body="Start the engine. Let it idle for 5–10 minutes until coolant reads ≥80°C. "
         "Then return to the walkthrough.",
    next_id="measure-idle-maf",
))
_p0101.add(Step(
    id="measure-idle-maf", type="measurement",
    title="Measure MAF at warm idle",
    body="Read PID 0110 (MAF g/s) via live dashboard or yaris-diag dash. "
         "Expected range for a healthy 1.3L at warm idle: 2.5–3.5 g/s.",
    measurement_pid="0110", measurement_units="g/s",
    measurement_low=2.0, measurement_high=4.5,
    pass_id="check-ltft", fail_low_id="maf-reading-low", fail_high_id="maf-reading-high",
))
_p0101.add(Step(
    id="maf-reading-low", type="info",
    title="MAF under-reading at idle",
    body="Your MAF is below 2.0 g/s at warm idle. Two main causes: (1) contaminated "
         "element — common fix, cleaning works ~70% of the time; (2) vacuum leak "
         "causing low actual airflow — check for hissing sounds near the intake.",
    next_id="check-vacuum-leak",
))
_p0101.add(Step(
    id="check-vacuum-leak", type="question",
    title="Any visible cracks or hissing from intake?",
    body="Inspect the intake boot (between MAF and throttle body) for cracks, splits, "
         "or loose clamps. Listen near PCV hose and intake manifold gaskets.",
    yes_id="fix-vacuum", no_id="clean-maf",
))
_p0101.add(Step(
    id="fix-vacuum", type="result",
    title="Vacuum leak detected — fix that first",
    body="Repair the leak before touching the MAF. Common parts: intake boot, "
         "PCV valve, valve cover gasket.",
    result_status="replace_part",
    linked_issue="p0171-lean",
    linked_shopping="p0171-lean",
))
_p0101.add(Step(
    id="clean-maf", type="action",
    title="Clean the MAF sensor",
    body="Disconnect battery (90 s), pull MAF (T20 Torx, 2 screws), spray element "
         "with CRC 05110 from 6 inches away, 10–15 short bursts. Let dry 5+ min. "
         "DO NOT TOUCH the element. Reinstall, reconnect battery, start, idle 30 s.",
    next_id="remeasure-maf",
))
_p0101.add(Step(
    id="remeasure-maf", type="measurement",
    title="Re-measure MAF at warm idle after cleaning",
    body="Drive ~5 minutes first to let ECM relearn, then re-read PID 0110 at idle.",
    measurement_pid="0110", measurement_units="g/s",
    measurement_low=2.5, measurement_high=3.5,
    pass_id="maf-fixed", fail_low_id="maf-still-bad", fail_high_id="maf-still-bad",
))
_p0101.add(Step(
    id="maf-fixed", type="result",
    title="✓ MAF cleaned successfully",
    body="MAF now reads in the healthy range. Clear codes (mode 04) and drive 2 full "
         "cycles to let the permanent code self-clear. LTFT should drift back toward "
         "±5% within 1-2 drive cycles.",
    result_status="fixed",
    linked_issue="p0101-maf-fault",
))
_p0101.add(Step(
    id="maf-still-bad", type="info",
    title="MAF still out of range after cleaning",
    body="Cleaning didn't restore function. Sensor element is likely damaged or aged. "
         "Replacement is indicated. Use Denso 22204-21010 (OEM) or a direct replacement.",
    next_id="replace-maf",
))
_p0101.add(Step(
    id="replace-maf", type="result",
    title="Replace MAF sensor",
    body="Shop for Denso 22204-21010 (~$60 aftermarket, $120 OEM). "
         "Install: 2× T20 Torx, reconnect connector, battery, start. ECM auto-adapts "
         "LTFT over 2-3 drive cycles.",
    result_status="replace_part",
    linked_issue="p0101-maf-fault",
    linked_procedure="maf-clean",
    linked_shopping="p0101-maf-fault",
))
_p0101.add(Step(
    id="maf-reading-high", type="result",
    title="MAF over-reading — unusual",
    body="MAF above 4.5 g/s at warm idle is unusual for 1.3L. Check: (a) engine NOT "
         "at idle, (b) aftermarket air filter with oil contamination, (c) calibration "
         "drift. Try: replace air filter with OEM paper type, re-measure.",
    result_status="inconclusive",
))
_p0101.add(Step(
    id="check-ltft", type="measurement",
    title="MAF is in healthy range. Now check LTFT",
    body="If MAF is OK but code still fires: check LTFT B1 (PID 0107). Healthy: ±5%.",
    measurement_pid="0107", measurement_units="%",
    measurement_low=-7, measurement_high=7,
    pass_id="maf-and-ltft-ok", fail_low_id="rich-trim", fail_high_id="lean-trim",
))
_p0101.add(Step(
    id="maf-and-ltft-ok", type="result",
    title="✓ MAF & LTFT both healthy",
    body="P0101 may be historical. Clear codes and drive 2 cycles. If it doesn't "
         "return, you're done. If it returns: intermittent sensor fault — worth "
         "replacing the MAF proactively.",
    result_status="fixed",
))
_p0101.add(Step(
    id="rich-trim", type="result",
    title="LTFT negative — ECM reducing fuel",
    body="ECU is pulling fuel, meaning something is running rich: leaky injector, "
         "fuel pressure too high, or MAF over-reading intermittently. Investigate "
         "fuel system.",
    result_status="inconclusive",
    linked_issue="p0171-lean",
))
_p0101.add(Step(
    id="lean-trim", type="result",
    title="LTFT positive — vacuum leak or lean-running",
    body="LTFT >+7% despite MAF being OK means unmetered air (vacuum leak) or weak "
         "fuel delivery. Smoke-test intake. Follow P0171 walkthrough next.",
    result_status="inconclusive",
    linked_issue="p0171-lean",
))


# ── Overheating diagnosis ───────────────────────────────────────────────
_overheat = Walkthrough(
    slug="overheating-diag",
    name="Overheating diagnosis",
    summary="Diagnose a car that's running hot — thermostat, water pump, coolant, fan.",
    symptom_triggers=["temp-light", "coolant-drip", "slow-warmup"],
)
_overheat.add(Step(
    id="start", type="info",
    title="Overheating / temperature walkthrough",
    body="⚠ SAFETY: if the engine is currently overheating, stop driving and let it "
         "cool for 30+ minutes. Do NOT open the radiator cap on a hot engine — "
         "scalding coolant spray.",
    next_id="check-coolant-level",
))
_overheat.add(Step(
    id="check-coolant-level", type="question",
    title="Is coolant level at MAX in the overflow tank?",
    body="With engine COLD, open the hood. The overflow reservoir is on the passenger "
         "side near the radiator. Check level against the MAX line.",
    yes_id="check-fan", no_id="low-coolant",
))
_overheat.add(Step(
    id="low-coolant", type="result",
    title="Low coolant — top up first",
    body="Top up with Toyota SLLC 50/50. If level drops again within 1-2 weeks: "
         "you have a leak. Inspect hoses, water pump weep hole, radiator, "
         "thermostat housing.",
    result_status="replace_part",
    linked_issue="water-pump-seep",
    linked_procedure="coolant-flush",
))
_overheat.add(Step(
    id="check-fan", type="question",
    title="Does the cooling fan run when coolant reaches ~95°C?",
    body="Start engine, let it warm up. When coolant hits 95°C (PID 0105), "
         "the radiator cooling fan should cycle on.",
    yes_id="check-live-temp", no_id="fan-not-running",
))
_overheat.add(Step(
    id="fan-not-running", type="result",
    title="Cooling fan not running — electrical diagnosis",
    body="Cooling fan failure causes rapid overheating in stop-and-go. Check: "
         "(1) 30A RDI FAN fuse in engine bay fuse box, (2) fan relay, "
         "(3) temperature switch, (4) fan motor itself. Test each with a DMM.",
    result_status="replace_part",
))
_overheat.add(Step(
    id="check-live-temp", type="measurement",
    title="What's the coolant temp during normal driving?",
    body="Healthy range: 85–98°C. Fan cycles at ~95°C.",
    measurement_pid="0105", measurement_units="°C",
    measurement_low=80, measurement_high=100,
    pass_id="temps-ok", fail_low_id="thermostat-stuck-open", fail_high_id="real-overheat",
))
_overheat.add(Step(
    id="thermostat-stuck-open", type="result",
    title="Thermostat stuck open — slow warm-up / runs cold",
    body="Coolant <80°C = thermostat stuck open. Replace with OEM 90916-03084. "
         "Poor MPG and weak heat are the main symptoms.",
    result_status="replace_part",
    linked_issue="thermostat-stuck-open",
    linked_procedure="thermostat-replace",
    linked_shopping="thermostat-stuck-open",
))
_overheat.add(Step(
    id="real-overheat", type="result",
    title="Real overheat — investigate further",
    body="Coolant >100°C under normal load. Check: water pump weep hole, "
         "radiator airflow obstruction, head gasket (white smoke from exhaust, "
         "oil in coolant or coolant in oil).",
    result_status="inconclusive",
    linked_issue="water-pump-seep",
))
_overheat.add(Step(
    id="temps-ok", type="result",
    title="✓ Temps healthy",
    body="Cooling system is behaving normally. If you got here by chasing a P-code, "
         "it may be historical. Clear codes and monitor.",
    result_status="fixed",
))


# ── No-start diagnosis ──────────────────────────────────────────────────
_nostart = Walkthrough(
    slug="no-start-diag",
    name="No-start diagnosis",
    summary="Car won't crank or won't start? Walk through battery → starter → fuel → spark.",
    symptom_triggers=["no-crank", "slow-crank", "hard-start"],
)
_nostart.add(Step(
    id="start", type="choice",
    title="What happens when you turn the key?",
    body="Pick the closest match.",
    choices=[
        {"label": "Nothing — no sound at all", "next_id": "check-battery-click"},
        {"label": "Single click, no cranking", "next_id": "check-battery-click"},
        {"label": "Cranks slowly", "next_id": "weak-crank"},
        {"label": "Cranks fine but won't fire", "next_id": "crank-no-fire"},
        {"label": "Starts briefly then stalls", "next_id": "stall-after-start"},
    ],
))
_nostart.add(Step(
    id="check-battery-click", type="measurement",
    title="Check battery voltage",
    body="Measure battery voltage with DMM (key off).",
    measurement_pid="battery_v", measurement_units="V",
    measurement_low=12.2, measurement_high=13.5,
    pass_id="check-starter", fail_low_id="dead-battery", fail_high_id="check-starter",
))
_nostart.add(Step(
    id="dead-battery", type="result",
    title="Battery depleted",
    body="Battery <12.2V won't crank reliably. Jump start, drive 30+ min, recheck. "
         "If battery drops again after sitting overnight — replace it, or chase a "
         "parasitic drain (use the fuse-box battery-drain procedure).",
    result_status="replace_part",
    linked_issue="battery-drain",
))
_nostart.add(Step(
    id="check-starter", type="action",
    title="Measure voltage at starter solenoid while cranking",
    body="Battery is OK. Now check if the starter is getting 12V when you turn the "
         "key. Place DMM on the small solenoid wire (S terminal) while an assistant "
         "holds the key in START.",
    next_id="starter-v",
))
_nostart.add(Step(
    id="starter-v", type="question",
    title="Did voltage reach 10V+ at the S terminal?",
    yes_id="starter-bad", no_id="ignition-circuit-issue",
))
_nostart.add(Step(
    id="starter-bad", type="result",
    title="Starter motor is the fault",
    body="Power reaches the solenoid but starter doesn't crank = internal failure "
         "(brush wear, armature, solenoid contacts). Replace the starter. "
         "Aftermarket units ~$60-100.",
    result_status="replace_part",
    linked_issue="starter-failure",
))
_nostart.add(Step(
    id="ignition-circuit-issue", type="result",
    title="Ignition circuit issue",
    body="No voltage at starter solenoid when key turned = ignition switch, neutral "
         "safety switch (auto) or clutch interlock (manual) is blocking the signal. "
         "Check fuses: ST (7.5A), AM1 (30A), IGN (7.5A).",
    result_status="inconclusive",
))
_nostart.add(Step(
    id="weak-crank", type="result",
    title="Weak cranking — battery or cables",
    body="Slow cranking = insufficient current. Load-test battery (parts store will "
         "do this free). Clean battery terminals with wire brush. If battery tests "
         "good: starter is pulling excessive current — replace it.",
    result_status="inconclusive",
    linked_issue="battery-drain",
))
_nostart.add(Step(
    id="crank-no-fire", type="question",
    title="Do you smell fuel after extended cranking?",
    body="Fuel smell = injectors firing. No fuel smell = fuel delivery issue.",
    yes_id="check-spark", no_id="fuel-issue",
))
_nostart.add(Step(
    id="fuel-issue", type="result",
    title="Fuel delivery problem",
    body="No fuel at injectors. Check: EFI fuse (15A), EFI MAIN fuse (20A), "
         "fuel pump relay, fuel pump. Listen for 2-second pump prime when key "
         "turned to ON. No prime hum = bad pump or relay.",
    result_status="inconclusive",
))
_nostart.add(Step(
    id="check-spark", type="action",
    title="Check for spark",
    body="Remove a spark plug, connect it to the coil, rest the plug shell on engine "
         "ground, and crank. Helper watches for spark. Or use an inline spark tester "
         "(~$15 at AutoZone).",
    next_id="spark-q",
))
_nostart.add(Step(
    id="spark-q", type="question",
    title="Do you see spark at any of the 3 plugs?",
    yes_id="spark-ok-but-no-start", no_id="no-spark",
))
_nostart.add(Step(
    id="no-spark", type="result",
    title="No spark — ignition circuit",
    body="Check: IGN fuse, all 3 ignition coils, CKP sensor (P0335). "
         "Swap a coil with a known-good cylinder to isolate.",
    result_status="inconclusive",
))
_nostart.add(Step(
    id="spark-ok-but-no-start", type="result",
    title="Spark and fuel present — compression or timing",
    body="Mechanically something's wrong. Do a compression test: 150-180 psi healthy, "
         "<130 is a problem. If one cylinder is zero = bent valve (check timing "
         "chain). If all low: aged engine or timing chain jumped.",
    result_status="inconclusive",
    linked_issue="timing-chain-rattle",
    linked_procedure="compression-test",
))
_nostart.add(Step(
    id="stall-after-start", type="result",
    title="Starts and stalls",
    body="Check: idle-air-control / throttle body (carbon), fuel pressure regulator, "
         "CKP intermittent, vacuum leak. Run yaris-diag dash and watch: does RPM "
         "drop progressively (fuel) or drop suddenly (ignition)?",
    result_status="inconclusive",
    linked_issue="throttle-carbon",
))


# ── Misfire P0300-P0304 diagnosis ───────────────────────────────────────
_misfire = Walkthrough(
    slug="misfire-diag",
    name="Misfire / P0300 diagnosis",
    summary="Rough idle or P030X codes? Isolate which cylinder and find root cause.",
    dtc_triggers=["P0300", "P0301", "P0302", "P0303", "P0304"],
    symptom_triggers=["rough-idle", "stumble-cold", "power-loss"],
)
_misfire.add(Step(
    id="start", type="question",
    title="Is MIL flashing (not solid)?",
    body="A flashing MIL during misfires = catalyst damage imminent. Stop driving.",
    yes_id="stop-driving", no_id="pull-codes",
))
_misfire.add(Step(
    id="stop-driving", type="result",
    title="⚠ STOP DRIVING — catalyst damage imminent",
    body="Flashing MIL = severe misfire damaging the catalytic converter with "
         "unburned fuel. Pull over, have it towed. Continuing to drive will destroy "
         "the cat (~$500-1500 part).",
    result_status="inconclusive",
))
_misfire.add(Step(
    id="pull-codes", type="choice",
    title="Which specific misfire code was set?",
    body="P030X codes identify the cylinder. P0300 = random, multiple cylinders.",
    choices=[
        {"label": "P0300 (random / multiple)", "next_id": "p0300-path"},
        {"label": "P0301 (cyl 1)", "next_id": "single-cyl-1"},
        {"label": "P0302 (cyl 2)", "next_id": "single-cyl-2"},
        {"label": "P0303 (cyl 3)", "next_id": "single-cyl-3"},
        {"label": "Don't know — pull codes first", "next_id": "pull-first"},
    ],
))
_misfire.add(Step(
    id="pull-first", type="action",
    title="Pull DTCs first",
    body="Run yaris-diag pull or /live to read stored DTCs. Note which specific "
         "misfire codes are active, then return here.",
    next_id="pull-codes",
))
_misfire.add(Step(
    id="p0300-path", type="info",
    title="Random / multiple misfire — broader cause",
    body="P0300 means misfires aren't isolated to one cylinder. Likely causes: "
         "(1) vacuum leak, (2) weak spark from aged coil pack affecting multiple, "
         "(3) fuel pressure low, (4) timing chain jumped a tooth, (5) bad fuel.",
    next_id="check-vacuum-leak-misfire",
))
_misfire.add(Step(
    id="check-vacuum-leak-misfire", type="question",
    title="LTFT at idle reads above +7%?",
    body="Check PID 0107. Lean running from a vacuum leak causes random misfires.",
    yes_id="vacuum-leak-misfire", no_id="check-fuel-pressure",
))
_misfire.add(Step(
    id="vacuum-leak-misfire", type="result",
    title="Vacuum leak → lean misfire",
    body="Smoke test intake, fix leaks, retest. Usually intake boot or PCV.",
    result_status="replace_part",
    linked_issue="p0171-lean",
))
_misfire.add(Step(
    id="check-fuel-pressure", type="action",
    title="Check fuel pressure",
    body="Need a fuel pressure gauge on the Schrader valve (if equipped) or inline. "
         "Static: 41-43 psi. Running: 35-38 psi.",
    next_id="fuel-pressure-q",
))
_misfire.add(Step(
    id="fuel-pressure-q", type="question",
    title="Fuel pressure within spec?",
    yes_id="swap-coils", no_id="fuel-delivery-fail",
))
_misfire.add(Step(
    id="fuel-delivery-fail", type="result",
    title="Fuel delivery problem",
    body="Check fuel pump, filter (tank-internal on Yaris), regulator. Common "
         "failure at 150k+ km.",
    result_status="replace_part",
))
_misfire.add(Step(
    id="swap-coils", type="action",
    title="Coil swap test",
    body="If you have any single-cylinder misfire code, swap that cylinder's coil "
         "with a neighbor. Drive 10 min, re-read codes. If the misfire follows the "
         "coil → coil is bad. If it stays on the same cylinder → plug, injector, "
         "or compression.",
    next_id="swap-result",
))
_misfire.add(Step(
    id="swap-result", type="question",
    title="Did the misfire follow the coil to the other cylinder?",
    yes_id="replace-coil", no_id="check-spark-plug",
))
_misfire.add(Step(
    id="replace-coil", type="result",
    title="Replace the faulty coil pack",
    body="Denso 90919-02240 (~$40-60). Replace just the bad one, or all 3 if high "
         "mileage for peace of mind.",
    result_status="replace_part",
))
_misfire.add(Step(
    id="check-spark-plug", type="action",
    title="Pull the spark plug on that cylinder",
    body="Inspect for: (a) oil fouling = ring/valve seal issue, (b) fuel fouling "
         "(black wet) = injector stuck open, (c) burned electrode = lean, "
         "(d) physical damage.",
    next_id="plug-conclusion",
))
_misfire.add(Step(
    id="plug-conclusion", type="choice",
    title="What does the plug look like?",
    choices=[
        {"label": "Normal tan/gray — compression test next",
         "next_id": "compression-check"},
        {"label": "Oil-fouled (wet brown)", "next_id": "oil-fouling"},
        {"label": "Fuel-fouled (wet black)", "next_id": "injector-bad"},
        {"label": "Burned or cracked", "next_id": "replace-plug"},
    ],
))
_misfire.add(Step(
    id="replace-plug", type="result",
    title="Replace plug(s)",
    body="NGK ILKAR7L11 or Denso VCH16. Replace all 3 (they're only $8 each). "
         "Gap is pre-set — don't adjust iridium.",
    result_status="replace_part",
    linked_procedure="spark-plug-replace",
))
_misfire.add(Step(
    id="oil-fouling", type="result",
    title="Oil-fouled plug — engine oil consumption",
    body="Oil getting past rings or valve stem seals. Do a compression test. "
         "On pre-2014 1NR-FE this is TSB EG-0095T territory.",
    result_status="inconclusive",
    linked_issue="oil-consumption-1nrfe",
))
_misfire.add(Step(
    id="injector-bad", type="result",
    title="Injector stuck open / leaking",
    body="Fuel-soaked plug = injector dumping fuel. Replace the injector on that "
         "cylinder. Can also try an injector-cleaner treatment first.",
    result_status="replace_part",
))
_misfire.add(Step(
    id="compression-check", type="measurement",
    title="Compression test on that cylinder",
    body="Healthy 1NR-FE: 150-180 psi. Minimum: 130 psi. Max cyl-to-cyl variation: 14 psi.",
    measurement_pid="compression", measurement_units="psi",
    measurement_low=130, measurement_high=220,
    pass_id="comp-ok", fail_low_id="comp-low", fail_high_id="comp-ok",
))
_misfire.add(Step(
    id="comp-ok", type="result",
    title="Compression healthy — check wiring",
    body="Plug, coil, compression all good. Misfire likely electrical — check "
         "injector wiring, CKP/CMP reluctor ring, ground strap.",
    result_status="inconclusive",
))
_misfire.add(Step(
    id="comp-low", type="result",
    title="Low compression — head gasket or valves",
    body="Wet test: add 15 ml oil, re-measure. If pressure rises → worn rings. "
         "If stays low → valve leak, head gasket, or burned valve. Major repair.",
    result_status="replace_part",
))
_misfire.add(Step(
    id="single-cyl-1", type="info", title="Cylinder 1 misfire",
    body="Focus diagnosis on cylinder 1. Run the coil swap test next.",
    next_id="swap-coils",
))
_misfire.add(Step(
    id="single-cyl-2", type="info", title="Cylinder 2 misfire",
    body="Focus diagnosis on cylinder 2.",
    next_id="swap-coils",
))
_misfire.add(Step(
    id="single-cyl-3", type="info", title="Cylinder 3 misfire",
    body="Focus diagnosis on cylinder 3.",
    next_id="swap-coils",
))


# ── Registry ────────────────────────────────────────────────────────────
WALKTHROUGHS: dict[str, Walkthrough] = {
    w.slug: w for w in [_p0101, _overheat, _nostart, _misfire]
}


def get(slug: str) -> Optional[Walkthrough]:
    return WALKTHROUGHS.get(slug)


def list_all() -> list[dict]:
    return [{"slug": w.slug, "name": w.name, "summary": w.summary,
             "n_steps": len(w.steps),
             "dtc_triggers": w.dtc_triggers,
             "symptom_triggers": w.symptom_triggers}
            for w in WALKTHROUGHS.values()]
