# Toyota Yaris XP90 — Fuel System Guide

**Applies to:** 2006–2012 Toyota Yaris Sedan (XP90)

---

## SECTION 1: FUEL FILTER LOCATION & REPLACEMENT

**Location:** In-tank fuel filter (integrated into fuel pump assembly)  
**Service interval:** 60,000 km (37,000 mi) or 5 years  
**Cost:** Filter element only ~$5–10 if serviceable; pump assembly ~$80–150 if pump needed too

**Note:** Unlike older Yaris, the XP90 uses an in-tank design — no separate engine bay filter on most markets.

### Replacement procedure:

**Tools needed:** Socket set, fuel line clamps/plugs, drain pan  
**Difficulty:** ⭐⭐⭐ (requires fuel tank removal or access)

**Procedure (with tank removal):**
1. Drain fuel from tank (siphon out through filler cap tube)
2. Disconnect fuel pump electrical connector (under rear seats or in trunk)
3. Raise vehicle, remove rear wheel (passenger or driver side, depending on access)
4. Remove fuel tank straps (2× bolts, 10mm)
5. Disconnect fuel fill hose and vent hose from tank
6. Carefully lower tank to ground
7. Remove fuel pump assembly (4–6 bolts in top of tank)
8. Remove filter screen/element from pump
9. Rinse screen with diesel fuel (not water) to clean debris
10. Install new filter element if type is separate; many pumps have sealed elements
11. Reinstall pump assembly with new gasket
12. Reinstall tank, reconnect hoses, install straps
13. Reconnect pump electrical connector
14. Fill fuel tank, test for leaks

**Note:** If fuel pump fails during tank removal, replace it now (~$100–150 saves future labor)

---

## SECTION 2: FUEL PUMP REPLACEMENT

**Symptoms of failing pump:**
- Engine dies at highway speeds (fuel starvation)
- Difficulty starting (weak fuel pressure)
- No priming sound when turning ignition ON
- Whining/grinding noise from fuel tank area

**Fuel pump type:** Submerged electric pump in tank (not externally mounted)  
**Pressure spec:** 270–310 kPa (39–45 psi) at idle  
**OEM pump:** Toyota 23300-21050 (~$100–150)

**Tools needed:** Socket set, fuel pressure gauge (to test), drain pan  
**Labor time:** 1.5 hrs DIY (with tank access) | 2–3 hrs shop  
**Difficulty:** ⭐⭐⭐⭐

### Testing before replacement:

1. Turn ignition ON (engine off) — listen near fuel filler for priming pump sound (brief whine)
2. Connect fuel pressure gauge to fuel line test point (under hood, near fuel filter/rail)
3. With key ON: pressure should read 270–310 kPa
4. If pressure low (<200 kPa): 
   - Check fuel filter first (may be clogged)
   - Check fuel line for kink or damage
   - If line/filter OK: pump failing
5. If no pressure at all: pump not running (check fuse F16 in engine bay fuse box, or pump wiring)

### Replacement:

See section 1 above (fuel filter removal also requires tank drop). Pump is accessed from top of tank.

1. After tank is on ground, locate fuel pump access hole (metal ring with bolts, center of tank top)
2. Remove bolts (4–6 total) — may require special spoon wrench if no bolt heads accessible
3. Lift pump assembly straight up — may stick from sludge/rust
4. Disconnect electrical connector
5. Install new pump with new gasket/seal ring (critical — prevents fuel leaks)
6. Reconnect connector
7. Lower pump back into tank, install bolts
8. Torque bolts: **13–18 N·m (10–13 ft·lb)** — do NOT overtighten (can crack pump)
9. Reinstall tank, refill, test for leaks and pressure

---

## SECTION 3: FUEL INJECTOR CLEANING & TESTING

**Symptoms requiring cleaning:**
- Rough idle, hesitation on throttle
- P0171 (lean code) with high short-term fuel trim
- Misfires under load (one or more cylinders lazy)
- Poor fuel economy

**Testing (simple check):**
1. With engine running, listen near each injector (front of engine, mounted on intake rail)
2. Should hear a clicking sound from all three injectors (1KR-FE) or four (2NZ-FE)
3. If one silent: that injector likely stuck

**Testing (electrical):**
1. Remove fuel injector connectors
2. Measure resistance across injector pins: should be 13.4–14.2 Ω
3. If open circuit (∞ ohms) or very low (<1 Ω): injector failed — replace

**Service options:**
- **DIY cleaning:** In-tank cleaner additive (~$10–15) — poured into fuel tank; helps but not guaranteed
- **Professional cleaning:** Send injectors to injector cleaning service (~$50 per set) — ultrasonic cleaning restores flow
- **Replacement:** New injectors ~$30–50 each (OEM cheaper than aftermarket)

### Injector replacement procedure:

**Tools needed:** Socket set, fuel line disconnect tool, O-ring pick  
**Difficulty:** ⭐⭐

1. Disconnect battery negative
2. Relieve fuel pressure: turn ignition ON (no crank) for 10 seconds, then OFF
3. Disconnect fuel injector connectors (3 or 4, depending on engine)
4. Remove fuel rail bolts (2–4 bolts holding common fuel rail)
5. Carefully lift fuel rail off (fuel rails have O-rings at injector seats)
6. Injectors should pull straight up out of intake manifold
7. Remove old O-ring from injector seat (usually stuck — use small pick)
8. Install new O-ring on new injector (coat lightly with clean engine oil)
9. Insert new injector into manifold seat, ensure seated fully
10. Position fuel rail, start bolts by hand
11. Torque fuel rail bolts: **10–14 N·m (7–10 ft·lb)** in crossing pattern
12. Reconnect injector connectors
13. Reconnect battery, turn ignition ON to pressurize fuel rail
14. Check for leaks at injector O-rings and fuel rail connection
15. Start engine, verify no rough idle or codes

---

## SECTION 4: IDLE SPEED ADJUSTMENT

**XP90 uses drive-by-wire (electronic throttle):** There is **NO manual idle adjustment screw**

**If idle is too high or too low:**
1. Clean throttle body (see ENGINE_REPAIR.md section 1.8)
2. Check for vacuum leaks (PCV hose, intake gaskets)
3. Verify ECT sensor function (thermostat cold start enrichment requires working ECT)
4. If idle still erratic after above: use Techstream to perform ETCS calibration
   - ETCS = Electronic Throttle Control System
   - Procedure relearns throttle pedal and spring positions
   - Typical dealer cost: $100–150 labor

**Normal idle specs:**
- Cold idle (below 80°C): 1,000–1,200 rpm
- Warm idle (above 80°C): 700–750 rpm
- With A/C ON: may increase 50–100 rpm (normal)

---

## SECTION 5: FUEL SYSTEM PRESSURE TEST PROCEDURE

**Purpose:** Diagnose weak fuel pressure or lack thereof  
**Tools needed:** Fuel pressure gauge (0–600 kPa / 0–90 psi range), fuel line disconnect tool  
**Test points:** Fuel rail test port (if equipped) or fuel line junction near filter

**Procedure:**

1. **Connect gauge:**
   - Locate fuel test port on fuel rail (small Schrader valve)
   - OR: Disconnect fuel line after pump, install gauge with tee fitting
   - Aim gauge away from engine (fuel spray possible)

2. **Key ON, engine OFF:**
   - Ignition ON for 3 seconds
   - Pressure should spike to 270–310 kPa, then drop to 200–250 kPa
   - Should hold steady (minimal drop)
   - If pressure drops: check-valve failure (fuel returns backward after pump shuts off)

3. **Engine at idle (warm):**
   - Pressure should be 270–310 kPa steady
   - Should not drop below 250 kPa
   - If bouncy/oscillating: fuel regulator issue

4. **2,500 rpm cruise:**
   - Pressure may rise slightly (100–150 kPa higher) — normal
   - Should remain in spec range

5. **Vacuum applied to fuel regulator:**
   - Pull off fuel regulator vacuum hose
   - Pressure should drop 50–100 kPa
   - If no change: regulator diaphragm ruptured

**Interpreting results:**

| Pressure Reading | Diagnosis | Fix |
|-----------------|-----------|-----|
| 0 kPa | No fuel pressure | Check pump fuse, pump not running, kinked line |
| 100–200 kPa | Too low | Clogged fuel filter, weak pump, bad regulator |
| 310+ kPa steady | Too high | Stuck fuel regulator, check valve stuck |
| Bouncy (±50 kPa) | Regulator hunting | Vacuum leak to regulator, regulator damaged |

---

## SECTION 6: EVAP SYSTEM COMPONENTS & COMMON LEAKS

**EVAP = Evaporative Emission Control System** — captures fuel vapors from tank

**Components:**
- Charcoal canister (under vehicle, rear driver's side)
- Purge valve (under hood, intake manifold area)
- Vent valve (on canister)
- Fuel cap (must seal — common fault)
- Hoses connecting all above

**Common EVAP fault codes:**
- P0440: EVAP malfunction (usually loose fuel cap)
- P0441: Incorrect purge flow (purge valve stuck)
- P0442: Small leak (cap not sealing, small hose crack)
- P0455: Large leak (major hose disconnect, damaged canister)

### Diagnosis:

1. **Fuel cap:** Remove, inspect rubber seal for hardening/cracks
   - Try tightening cap 3 clicks past first resistance
   - Clear code, test drive 50 km
   - If code returns: replace fuel cap (~$10–15)

2. **Hoses:** Inspect all EVAP hoses under vehicle for:
   - Cracks or splits
   - Disconnected joints
   - Pinched or kinked lines

3. **Purge valve:** Listen for clicking when engine warms at idle
   - No click = valve stuck or solenoid failed
   - Valve location: near intake manifold, one solenoid and hose connection
   - Replace valve: ~$25–40

4. **Charcoal canister:** If code persists after cap + hose checks:
   - Canister may be internally cracked or saturated with fuel
   - Replacement: ~$80–150 part, 1 hr labor to unbolt and relocate hoses

---

## SECTION 7: FUEL TANK REMOVAL & ACCESS

**When required:** Fuel pump replacement, fuel tank repair, fuel tank cleaning  
**Time:** 1.5–2 hrs  
**Difficulty:** ⭐⭐⭐⭐

### Procedure:

1. Drain fuel using siphon (into approved fuel container)
2. Disconnect battery negative (safety — no spark risk near fuel)
3. Remove rear seats or access trim to expose fuel pump electrical connector
   - Pull connector straight off
4. Raise vehicle on jack stands (entire rear end up)
5. Remove both rear wheels (better clearance)
6. Locate fuel filler cap area (top of rear quarter panel)
7. Disconnect fuel fill hose: loosen clamp, wiggle hose off tank fitting
8. Disconnect vent hose (typically near fill hose)
9. Locate fuel feed line leaving tank (from pump inside)
   - Pinch line with fuel line clamp or wrap with rag (prevent spill)
   - Disconnect at junction toward engine
10. Locate fuel return line (if equipped, on older XP90 models)
11. Remove fuel tank straps:
    - Two or three straps holding tank up
    - 10mm bolts; use jack to support tank as you unbolt straps
12. Carefully lower tank to ground (heavy — ~30 kg when empty, ~50 kg full)
13. Once on ground: remove fuel pump assembly bolts, access interior components

**Reinstall (reverse):**
- Use new fuel line clamps if old ones stretched
- Ensure vent hose is not kinked (prevents proper pressure regulation)
- Ensure fill hose is not pinched under tank during seating
- Torque tank straps: **37–44 N·m (27–32 ft·lb)**

---

## SECTION 8: FUEL SYSTEM SPECIFICATIONS

| Parameter | Specification |
|-----------|---------------|
| Fuel type | 87 RON minimum (regular unleaded) |
| Fuel tank capacity | 42 L (11.1 US gal) |
| Fuel pump outlet pressure | 270–310 kPa (39–45 psi) at idle |
| Fuel rail pressure | Same as pump (no additional regulation) |
| Fuel injector flow | ~2.0–2.5 cc/min per injector |
| Fuel pump amperage | 3–5 A at runtime |
| Fuel line material | Metal (engine to tank), rubber hose (connection points) |
| Fuel line ID | 6 mm (primary feed), 4 mm (return, if equipped) |
| Fuel filter | In-tank element (not externally serviceable easily) |

---

*For fuel system electrical fuses, see ELECTRICAL_GUIDE.md (F16 = fuel pump fuse). For P0171 and fuel-related fault codes, see DTC_FULL_DATABASE.md.*
