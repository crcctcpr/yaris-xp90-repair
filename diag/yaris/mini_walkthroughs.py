"""Mini R60 N16-specific diagnostic walkthroughs."""
from .walkthroughs import Walkthrough, Step, WALKTHROUGHS


# ── Timing chain rattle ─────────────────────────────────────────────────
_wt_chain = Walkthrough(
    slug="mini-chain-rattle-diag",
    name="MINI: Timing Chain / Death Rattle diagnosis",
    summary="N14/N16 timing chain is the infamous Mini weak point. Diagnose: real chain stretch vs VANOS solenoid vs CKP/CMP sensor.",
    dtc_triggers=["P0016", "P0017", "P0014", "P0015"],
    symptom_triggers=["cold-start-rattle", "persistent-rattle"],
)
_wt_chain.add(Step(
    id="start", type="info",
    title="MINI Timing chain walkthrough",
    body="This is the most famous BMW/MINI N-series issue. The cost of getting it wrong is engine "
         "destruction. Proceed carefully — STOP DRIVING if chain noise is clearly present.",
    next_id="check-oil",
))
_wt_chain.add(Step(
    id="check-oil", type="measurement",
    title="Check oil level + condition FIRST",
    body="Pop hood, check dipstick with engine OFF, cold. Is oil between MIN and MAX?",
    measurement_pid="oil_level_mm", measurement_units="mm",
    measurement_low=50, measurement_high=100,
    pass_id="cold-start-test", fail_low_id="low-oil", fail_high_id="cold-start-test",
))
_wt_chain.add(Step(
    id="low-oil", type="result",
    title="⚠ Low oil — fix this first",
    body="Low oil accelerates chain wear AND hydraulic tensioner can't maintain pressure. "
         "Add BMW LongLife-01 5W-30 to MAX (no other oil). Then investigate rattle.",
    result_status="replace_part",
))
_wt_chain.add(Step(
    id="cold-start-test", type="action",
    title="Cold-start listen test",
    body="Engine off for 4+ hours. Start cold, stand at front fender, listen for metallic "
         "rattle sound from top of engine.",
    next_id="rattle-q",
))
_wt_chain.add(Step(
    id="rattle-q", type="question",
    title="Do you hear a metallic rattle lasting >1 second after start?",
    body="Distinct metal-on-metal rattle, not a clicking injector or accessory noise.",
    yes_id="rattle-duration", no_id="no-rattle",
))
_wt_chain.add(Step(
    id="rattle-duration", type="choice",
    title="How long does the rattle last?",
    choices=[
        {"label": "Under 2 sec, goes away immediately", "next_id": "mild-rattle"},
        {"label": "2-5 sec then fades", "next_id": "moderate-rattle"},
        {"label": "More than 5 sec / never fully stops", "next_id": "severe-rattle"},
    ],
))
_wt_chain.add(Step(
    id="mild-rattle", type="result",
    title="Mild rattle — monitor and service",
    body="Short rattle usually means tensioner is partial-worn but chain not yet stretched badly. "
         "Plan replacement within 5-10,000 km. Use ONLY LL-01 oil. Check oil monthly.",
    result_status="inconclusive",
    linked_issue="mini-timing-chain-rattle",
))
_wt_chain.add(Step(
    id="moderate-rattle", type="result",
    title="Moderate rattle — schedule replacement soon",
    body="Chain is worn. Replace timing chain kit within 2-3 months. "
         "Parts $200-400, labor $800-1500. Don't delay — if chain skips teeth, engine destruction.",
    result_status="replace_part",
    linked_issue="mini-timing-chain-rattle",
    linked_shopping="mini-timing-chain-rattle",
))
_wt_chain.add(Step(
    id="severe-rattle", type="result",
    title="⚠ STOP DRIVING — Severe rattle",
    body="Prolonged rattle = chain has stretched significantly. Engine at risk of chain skipping "
         "or breaking. Tow to shop if possible. Continued driving risks $5000+ catastrophic damage.",
    result_status="replace_part",
    linked_issue="mini-timing-chain-rattle",
))
_wt_chain.add(Step(
    id="no-rattle", type="question",
    title="No rattle but P0016/P0017 still present?",
    yes_id="swap-vanos", no_id="intermittent-fault",
))
_wt_chain.add(Step(
    id="swap-vanos", type="action",
    title="VANOS solenoid swap test",
    body="Before committing to chain: swap intake ↔ exhaust VANOS solenoids. "
         "Unplug connector, 10mm bolt, pull out, swap, reinstall. Drive 10 min. Re-read codes.",
    next_id="swap-result",
))
_wt_chain.add(Step(
    id="swap-result", type="question",
    title="Did the code switch to the other cam?",
    body="If P0016 → P0017 (or vice versa), the solenoid is bad. If code stays on same cam, "
         "it's cam hardware (sensor, phaser, or chain).",
    yes_id="replace-solenoid", no_id="ckp-cmp-test",
))
_wt_chain.add(Step(
    id="replace-solenoid", type="result",
    title="✓ VANOS solenoid is the fault",
    body="Replace that solenoid (BMW 11368610388, ~$30-60). Much cheaper than chain work. "
         "Perform oil change at same time if overdue — sludge causes solenoid clog.",
    result_status="replace_part",
    linked_issue="mini-vanos-solenoid",
    linked_procedure="mini-vanos-replace",
    linked_shopping="mini-vanos-solenoid",
))
_wt_chain.add(Step(
    id="ckp-cmp-test", type="result",
    title="Check CKP/CMP sensors next",
    body="Code is sensor-correlation related. Before touching chain, swap CKP or CMP sensor ($30-60 each). "
         "If sensor replacement doesn't clear, then chain is the last remaining cause.",
    result_status="inconclusive",
    linked_issue="mini-crank-sensor",
))
_wt_chain.add(Step(
    id="intermittent-fault", type="result",
    title="Intermittent P0016 with no rattle — likely sensor drift",
    body="Could be CKP sensor drift with heat. Do a 30-min drive, re-read codes. "
         "If code comes back only when engine is hot: replace CKP sensor first.",
    result_status="inconclusive",
))


# ── Overheating ─────────────────────────────────────────────────────────
_wt_overheat = Walkthrough(
    slug="mini-overheat-diag",
    name="MINI: Overheating / cooling system diagnosis",
    summary="Electric water pump, plastic thermostat housing, coolant leaks. BMW runs hot (105°C normal) — don't panic below 110°C.",
    dtc_triggers=["P2181", "P0128", "P0597", "P0598", "P0599"],
    symptom_triggers=["temp-light", "coolant-drip", "slow-warmup"],
)
_wt_overheat.add(Step(
    id="start", type="info",
    title="MINI Cooling diagnosis",
    body="Remember: BMW runs 100-108°C as NORMAL (map-controlled thermostat). "
         "Only start worrying above 110°C. If temp >115°C, stop immediately.",
    next_id="check-level",
))
_wt_overheat.add(Step(
    id="check-level", type="question",
    title="Is coolant level at MAX in the expansion tank?",
    body="Engine cold. Expansion tank in engine bay. Check against MAX line.",
    yes_id="check-rear-head", no_id="low-coolant-mini",
))
_wt_overheat.add(Step(
    id="low-coolant-mini", type="result",
    title="Low coolant — locate the leak",
    body="Top up BMW Blue coolant 50/50 with distilled. Then pressure-test system at 15 psi. "
         "On N16 the top suspects are: (1) thermostat housing plastic crack at rear of head, "
         "(2) water pump weep, (3) PCV diaphragm pushing oil into coolant.",
    result_status="replace_part",
    linked_issue="mini-thermostat-housing",
))
_wt_overheat.add(Step(
    id="check-rear-head", type="action",
    title="Visual: check rear of cylinder head",
    body="Look at the rear of the cylinder head where the thermostat housing sits. "
         "Look for white crystalline residue or wet spots.",
    next_id="rear-head-q",
))
_wt_overheat.add(Step(
    id="rear-head-q", type="question",
    title="Any white crystalline residue or wetness?",
    yes_id="tstat-crack", no_id="check-pump-rpm",
))
_wt_overheat.add(Step(
    id="tstat-crack", type="result",
    title="Thermostat housing cracked — famous N16 failure",
    body="Replace thermostat housing assembly (BMW 11538674895, ~$60-120). "
         "Integrated electric thermostat + housing — replaces as a unit.",
    result_status="replace_part",
    linked_issue="mini-thermostat-housing",
    linked_procedure="mini-thermostat-replace",
    linked_shopping="mini-thermostat-housing",
))
_wt_overheat.add(Step(
    id="check-pump-rpm", type="action",
    title="Check electric water pump RPM",
    body="This needs the OBD adapter: Mode 22 DID 0x2261 returns water pump RPM. "
         "ATSH 7E0, then '22 2261'. Should be 200-500 at warm idle.",
    next_id="pump-rpm-q",
))
_wt_overheat.add(Step(
    id="pump-rpm-q", type="question",
    title="Is water pump RPM > 0 with engine warm?",
    yes_id="other-cause", no_id="pump-dead",
))
_wt_overheat.add(Step(
    id="pump-dead", type="result",
    title="Electric water pump has failed",
    body="Pierburg pump dies silently at 60-90k mi. Replace (BMW 11537630368 / ~$100-180). "
         "Often the thermostat housing is replaced at the same time (same area, similar age).",
    result_status="replace_part",
    linked_issue="mini-water-pump",
    linked_procedure="mini-water-pump-replace",
    linked_shopping="mini-water-pump",
))
_wt_overheat.add(Step(
    id="other-cause", type="result",
    title="Pump + thermostat OK — investigate further",
    body="Rare: check fan operation, radiator flow, head gasket (oil in coolant or coolant in oil), "
         "PCV diaphragm pushing combustion gases into coolant.",
    result_status="inconclusive",
))


# ── Register ────────────────────────────────────────────────────────────
WALKTHROUGHS[_wt_chain.slug] = _wt_chain
WALKTHROUGHS[_wt_overheat.slug] = _wt_overheat
