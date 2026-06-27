# DTC Full Database — 2011 Toyota Yaris XP90
## Fault Code Reference: 1KR-FE / 2NZ-FE / 1NR-FE Engines

> All codes include full diagnosis, causes, fixes, parts, and DIY difficulty.
> Prices are approximate USD retail. OEM vs aftermarket varies.

---

## POWERTRAIN (P) CODES

---

### P0010
**Description:** "A" Camshaft Position Actuator Circuit (Bank 1) — Open or short in VVT-i Oil Control Valve (OCV) solenoid circuit

**Symptoms:**
- Check Engine Light (CEL) on
- Rough idle or hunting idle
- Poor fuel economy
- Reduced power/throttle response
- Possible stalling at idle

**Causes (ranked):**
- Failed VVT-i OCV solenoid (most common)
- Wiring damage to solenoid — chafed, corroded, or broken connector
- Poor ground connection at engine
- ECM fault (rare)

**Fixes:**
1. Inspect solenoid connector for corrosion or damage
2. Measure resistance across solenoid terminals — spec 6.9–7.9 Ω at 20°C
3. Check wiring continuity from ECM to solenoid (should be <1 Ω resistance)
4. Clean solenoid connector with electrical contact cleaner
5. If electrically failed: replace OCV solenoid
6. Clear codes and retest

**Parts:** VVT-i OCV Solenoid — OEM (Toyota/Denso) $80–$120, Aftermarket (Dorman/BWD) $30–$60
**DIY Difficulty:** Easy

---

### P0011
**Description:** "A" Camshaft Position — Timing Over-Advanced or System Performance (Bank 1)

**Symptoms:**
- CEL on
- Rough idle, especially when warm
- Rattling noise on cold start (chain slack from over-advance)
- Reduced fuel economy
- Hard starting when warm

**Causes (ranked):**
- Sludged VVT-i solenoid screen — partial blockage causes over-advance
- Low oil level or pressure
- Wrong oil viscosity (too thick or too thin)
- Sludge in VVT-i passages inside cam sprocket
- Stuck/faulty OCV solenoid
- Timing chain stretched (false advance reading)

**Fixes:**
1. Check oil level — top up if low
2. Ensure correct oil viscosity is used (5W-30)
3. Remove and clean VVT-i solenoid (see ENGINE_REPAIR.md Section 8)
4. Perform oil flush if sludge is present
5. Replace solenoid if cleaning does not resolve
6. If chain stretched, replace timing chain assembly

**Parts:** VVT-i Solenoid $30–$120; Engine flush fluid $10–$20
**DIY Difficulty:** Easy–Medium

---

### P0012
**Description:** "A" Camshaft Position — Timing Over-Retarded (Bank 1)

**Symptoms:**
- CEL on
- Reduced power
- Poor cold-start performance
- Rough idle

**Causes (ranked):**
- VVT-i solenoid stuck in retarded position
- Low oil pressure (oil pump wear, low level)
- Sludge in VVT-i oil passages
- Faulty OCV solenoid
- Timing chain/VVT sprocket issue

**Fixes:**
1. Check and correct oil level
2. Verify oil pressure (spec: 29 psi / 200 kPa at idle when warm)
3. Clean or replace OCV solenoid
4. Inspect timing chain for stretch

**Parts:** OCV Solenoid $30–$120; Oil pressure gauge $20–$60
**DIY Difficulty:** Easy–Medium

---

### P0016
**Description:** Crankshaft Position — Camshaft Position Correlation (Bank 1, Sensor A) — cam and crank timing do not match

**Symptoms:**
- CEL on
- Engine rattles (especially on cold start)
- Poor power and fuel economy
- Possible no-start or rough start

**Causes (ranked):**
- Stretched timing chain
- Weak or failed chain tensioner
- Worn cam or crank sprocket teeth
- Incorrect cam timing after engine repair
- Low oil pressure causing tensioner failure

**Fixes:**
1. Verify oil level and pressure
2. Remove valve cover and inspect chain slack and cam timing marks
3. Test tensioner function
4. If chain stretched >1 cam tooth: replace timing chain, tensioner, and guides
5. Verify cam timing marks at TDC after replacement

**Parts:** Timing chain kit (chain + tensioner + guides) $80–$200; Labour intensive
**DIY Difficulty:** Hard

---

### P0017
**Description:** Crankshaft Position — Camshaft Position Correlation (Bank 1, Sensor B) — exhaust cam correlation fault

**Symptoms:**
- Same as P0016
- May appear with P0016 simultaneously

**Causes (ranked):**
- Stretched timing chain (bank 1 exhaust cam)
- Worn VVT-i sprocket
- Failed cam position sensor (exhaust side)
- Timing incorrectly set after repair

**Fixes:**
1. Same diagnostic as P0016
2. Specifically inspect exhaust camshaft sensor and its reluctor ring
3. Replace exhaust cam sensor if signal is erratic

**Parts:** Cam position sensor $25–$60; Timing chain kit $80–$200
**DIY Difficulty:** Hard

---

### P0097
**Description:** Intake Air Temperature Sensor 2 Circuit Low Input

**Symptoms:**
- CEL on
- Possible rough idle
- ECM uses substituted IAT value — fuel trims may be off

**Causes (ranked):**
- Shorted IAT sensor or wiring (short to ground)
- Damaged sensor connector
- Failed ECM input circuit (rare)

**Fixes:**
1. Inspect IAT sensor wiring for shorts to ground
2. Measure IAT sensor resistance (should change with temperature — approximately 2–3 kΩ at 20°C)
3. Replace IAT sensor if failed
4. Repair wiring if shorted

**Parts:** IAT Sensor $15–$40
**DIY Difficulty:** Easy

---

### P0098
**Description:** Intake Air Temperature Sensor 2 Circuit High Input

**Symptoms:**
- CEL on
- Possible overly rich or lean fueling (ECM reads incorrect IAT)

**Causes (ranked):**
- Open circuit in IAT sensor or wiring
- Disconnected connector
- Failed IAT sensor (reading max temperature)

**Fixes:**
1. Inspect and reconnect IAT sensor connector
2. Test sensor resistance — if open (infinite resistance): replace sensor
3. Repair open in wiring harness if present

**Parts:** IAT Sensor $15–$40
**DIY Difficulty:** Easy

---

### P0100
**Description:** Mass Air Flow (MAF) Sensor Circuit Malfunction

**Symptoms:**
- CEL on
- Engine may not start or stall
- Severe power loss
- Rich or lean running

**Causes (ranked):**
- Disconnected MAF sensor connector
- Failed MAF sensor
- Wiring open circuit
- Air leak downstream of MAF

**Fixes:**
1. Check connector is fully seated
2. Inspect wiring for damage
3. Clean MAF sensor with MAF cleaner (do not touch wire)
4. Replace MAF sensor if failed

**Parts:** MAF Sensor (1KR-FE/2NZ-FE) $40–$120 OEM; $20–$60 aftermarket
**DIY Difficulty:** Easy

---

### P0101
**Description:** MAF Sensor Circuit Range/Performance

**Symptoms:**
- CEL on
- Rough idle
- Poor fuel economy
- Hesitation under load

**Causes (ranked):**
- Dirty/contaminated MAF sensor (most common)
- Air leak between MAF and throttle body
- Restricted air filter
- Failing MAF sensor

**Fixes:**
1. Replace air filter
2. Inspect all intake hoses for cracks or loose clamps
3. Clean MAF sensor with dedicated MAF cleaner spray — 10 short bursts, let dry 10 minutes
4. Clear code and test drive — monitor short-term fuel trims
5. If STFT > +10%: vacuum leak or weak MAF — trace each

**Parts:** MAF Cleaner $8–$15; MAF Sensor $20–$120
**DIY Difficulty:** Easy

---

### P0102
**Description:** MAF Sensor Circuit Low Input

**Symptoms:**
- CEL on
- Rich running (ECM compensates with more fuel)
- Black smoke from exhaust

**Causes (ranked):**
- Short circuit in MAF wiring to ground
- Failed MAF sensor (very low signal output)
- Dirty sensor element

**Fixes:**
1. Check for shorts in MAF wiring
2. Clean sensor
3. Replace MAF sensor

**Parts:** MAF Sensor $20–$120
**DIY Difficulty:** Easy

---

### P0103
**Description:** MAF Sensor Circuit High Input

**Symptoms:**
- CEL on
- Lean running (ECM sees too much air, reduces fuel)
- Possible misfires

**Causes (ranked):**
- Open circuit in MAF wiring (signal wire disconnected)
- Failed MAF sensor (high signal)
- Loose or disconnected vacuum line affecting MAF signal

**Fixes:**
1. Inspect MAF connector and wiring
2. Repair open circuit if found
3. Replace MAF sensor

**Parts:** MAF Sensor $20–$120
**DIY Difficulty:** Easy

---

### P0105
**Description:** Manifold Absolute Pressure (MAP) Sensor Circuit Malfunction

**Symptoms:**
- CEL on
- Poor idle quality
- Rough acceleration

**Causes (ranked):**
- Failed MAP sensor
- Disconnected sensor or vacuum hose to MAP
- Open/short in wiring

**Fixes:**
1. Inspect vacuum hose to MAP sensor for cracks or disconnection
2. Check connector
3. Test MAP sensor voltage (should be 0.5V at vacuum, ~4.5V at atmospheric pressure)
4. Replace MAP sensor if failed

**Parts:** MAP Sensor $20–$80
**DIY Difficulty:** Easy

---

### P0106
**Description:** MAP Sensor Circuit Range/Performance

**Symptoms:**
- CEL on
- Hesitation
- Poor idle

**Causes (ranked):**
- Vacuum leak near MAP sensor port
- Partially clogged or blocked MAP port
- Intermittent MAP sensor failure

**Fixes:**
1. Inspect and clean MAP sensor vacuum port
2. Check for vacuum leaks
3. Replace MAP sensor

**Parts:** MAP Sensor $20–$80
**DIY Difficulty:** Easy

---

### P0107
**Description:** MAP Sensor Circuit Low Input (signal too low / short to ground)

**Symptoms:**
- CEL on
- Engine may run very rich

**Causes (ranked):**
- Short to ground in MAP sensor signal wire
- Failed MAP sensor

**Fixes:**
1. Test wiring for short to ground
2. Replace MAP sensor

**Parts:** MAP Sensor $20–$80
**DIY Difficulty:** Easy

---

### P0108
**Description:** MAP Sensor Circuit High Input (signal too high / open circuit)

**Symptoms:**
- CEL on
- Engine may run lean

**Causes (ranked):**
- Open circuit in MAP signal wire
- Failed MAP sensor

**Fixes:**
1. Check for open circuit in wiring
2. Replace MAP sensor

**Parts:** MAP Sensor $20–$80
**DIY Difficulty:** Easy

---

### P0110
**Description:** Intake Air Temperature Sensor Circuit Malfunction

**Symptoms:**
- CEL on
- May affect cold-start fueling

**Causes (ranked):**
- Failed IAT sensor
- Damaged wiring
- Loose connector

**Fixes:**
1. Check connector
2. Measure IAT resistance (~2.5 kΩ at 20°C; lower at higher temps)
3. Replace IAT sensor

**Parts:** IAT Sensor $10–$40
**DIY Difficulty:** Easy

---

### P0112
**Description:** IAT Sensor Circuit Low Input

**Symptoms:**
- CEL on
- ECM reads very high temperature (short to ground causes low voltage = high temp reading)

**Causes (ranked):**
- Short to ground in IAT signal wire
- Failed IAT sensor

**Fixes:**
1. Inspect wiring for short
2. Replace sensor

**Parts:** IAT Sensor $10–$40
**DIY Difficulty:** Easy

---

### P0113
**Description:** IAT Sensor Circuit High Input

**Symptoms:**
- CEL on
- ECM reads very cold temperature (open circuit = high voltage = cold reading)
- Can cause excessive fuel enrichment on cold start

**Causes (ranked):**
- Open circuit in IAT wiring
- Disconnected sensor
- Failed IAT sensor

**Fixes:**
1. Check connector and wiring
2. Replace IAT sensor

**Parts:** IAT Sensor $10–$40
**DIY Difficulty:** Easy

---

### P0115
**Description:** Engine Coolant Temperature (ECT) Sensor Circuit Malfunction

**Symptoms:**
- CEL on
- Possible fan running constantly
- Possible hard cold start
- Temperature gauge may read incorrectly

**Causes (ranked):**
- Failed ECT sensor
- Damaged connector/wiring
- Air bubble near sensor (overheating can damage sensor)

**Fixes:**
1. Check coolant level (air bubbles near sensor cause heat damage)
2. Inspect ECT connector for corrosion
3. Test ECT resistance (~2.5 kΩ at 20°C, ~0.3 kΩ at 80°C)
4. Replace ECT sensor

**Parts:** ECT Sensor $15–$50
**DIY Difficulty:** Easy

---

### P0116
**Description:** ECT Sensor Circuit Range/Performance

**Symptoms:**
- CEL on
- Engine temperature readings erratic

**Causes (ranked):**
- ECT sensor slow to respond (aging sensor)
- Thermostat stuck open (engine doesn't reach proper temp — sensor reads low forever)
- Air pocket at sensor location

**Fixes:**
1. Check thermostat operation (see COOLING_GUIDE.md)
2. Bleed air from cooling system
3. Replace ECT sensor if thermostat is OK

**Parts:** ECT Sensor $15–$50; Thermostat $15–$40
**DIY Difficulty:** Easy

---

### P0117
**Description:** ECT Sensor Circuit Low Input

**Symptoms:**
- CEL on
- Fan may run at high speed
- Engine appears to "overheat" per ECM even when cold

**Causes (ranked):**
- Short to ground in ECT signal wire
- Failed ECT sensor (shorted)
- Coolant contamination on sensor connector

**Fixes:**
1. Inspect wiring for short
2. Replace ECT sensor

**Parts:** ECT Sensor $15–$50
**DIY Difficulty:** Easy

---

### P0118
**Description:** ECT Sensor Circuit High Input

**Symptoms:**
- CEL on
- Engine may run rich on cold start indefinitely
- Temperature gauge reads cold permanently

**Causes (ranked):**
- Open circuit in ECT wiring
- Disconnected ECT sensor
- Failed ECT sensor (open)

**Fixes:**
1. Reconnect or repair wiring
2. Replace ECT sensor

**Parts:** ECT Sensor $15–$50
**DIY Difficulty:** Easy

---

### P0120
**Description:** Throttle/Pedal Position Sensor A Circuit Malfunction

**Symptoms:**
- CEL on
- Possible failsafe/reduced power mode
- Erratic acceleration
- Engine may idle but not rev

**Causes (ranked):**
- Failed TPS/ETC sensor (built into throttle body on 1KR-FE ETC)
- Wiring damage
- Carbon buildup affecting throttle plate movement
- ECM fault

**Fixes:**
1. Inspect throttle body for binding plate
2. Clean throttle body (see ENGINE_REPAIR.md)
3. Check TPS wiring
4. Perform TPS/ETC relearn with scanner
5. Replace throttle body/TPS assembly if sensor failed

**Parts:** Throttle Body Assembly $120–$300 OEM; $60–$150 aftermarket
**DIY Difficulty:** Medium

---

### P0121
**Description:** TPS Circuit Range/Performance

**Symptoms:**
- Hesitation and jerky throttle response
- CEL on

**Causes (ranked):**
- Dirty throttle body (plate not moving smoothly)
- Worn TPS
- Intermittent wiring

**Fixes:**
1. Clean throttle body
2. Perform ETC relearn
3. Inspect wiring
4. Replace throttle body if TPS signal erratic

**Parts:** Throttle Body $60–$300
**DIY Difficulty:** Medium

---

### P0122
**Description:** TPS Circuit Low Input

**Symptoms:**
- CEL on
- Failsafe mode engaged
- Very limited power

**Causes (ranked):**
- Short to ground in TPS signal wire
- Failed TPS sensor

**Fixes:**
1. Check wiring for short
2. Replace throttle body/TPS

**Parts:** Throttle Body $60–$300
**DIY Difficulty:** Medium

---

### P0123
**Description:** TPS Circuit High Input

**Symptoms:**
- CEL on
- Engine may not start
- Failsafe mode

**Causes (ranked):**
- Open circuit in TPS signal wire
- Failed TPS sensor (high signal)

**Fixes:**
1. Check wiring for open
2. Replace throttle body/TPS

**Parts:** Throttle Body $60–$300
**DIY Difficulty:** Medium

---

### P0125
**Description:** Insufficient Coolant Temperature for Closed Loop Fuel Control

**Symptoms:**
- CEL on
- Poor fuel economy
- Engine stays in open-loop fueling too long

**Causes (ranked):**
- Thermostat stuck open (engine never reaches operating temp)
- ECT sensor fault
- Very cold ambient temperatures (not a fault)

**Fixes:**
1. Check thermostat — if engine takes >15 minutes to reach operating temp: replace thermostat
2. Verify ECT sensor reading with scanner live data

**Parts:** Thermostat $15–$40
**DIY Difficulty:** Easy

---

### P0128
**Description:** Coolant Temperature Below Thermostat Regulating Temperature

**Symptoms:**
- CEL on
- Heater may not get hot
- Poor fuel economy
- Long warm-up time

**Causes (ranked):**
- Thermostat stuck open (most common cause)
- ECT sensor reading incorrectly low

**Fixes:**
1. Replace thermostat (Toyota spec: 82°C opening temperature)
2. If new thermostat doesn't resolve: check ECT sensor

**Parts:** Thermostat $15–$40
**DIY Difficulty:** Easy

---

### P0130
**Description:** O2 Sensor Circuit Malfunction (Bank 1, Sensor 1 — upstream)

**Symptoms:**
- CEL on
- Poor fuel economy
- Engine runs in open loop

**Causes (ranked):**
- Failed upstream O2 sensor
- Wiring damage or disconnected connector
- Contaminated sensor (oil, coolant, silicone)

**Fixes:**
1. Check O2 sensor connector
2. Test sensor signal with scanner — should oscillate 0.1–0.9V at idle
3. Replace upstream O2 sensor

**Parts:** Upstream O2 Sensor $30–$100
**DIY Difficulty:** Easy–Medium (may require O2 sensor socket)

---

### P0131
**Description:** O2 Sensor Circuit Low Voltage (Bank 1, Sensor 1)

**Symptoms:**
- CEL on
- Lean indication from sensor
- Possible lean fueling

**Causes (ranked):**
- Lean exhaust (vacuum leak, low fuel pressure)
- Failed O2 sensor stuck low
- Short to ground in O2 signal wire

**Fixes:**
1. Check for vacuum leaks first (lean condition)
2. Test O2 sensor operation
3. Replace sensor if stuck low

**Parts:** O2 Sensor $30–$100
**DIY Difficulty:** Easy–Medium

---

### P0132
**Description:** O2 Sensor Circuit High Voltage (Bank 1, Sensor 1)

**Symptoms:**
- CEL on
- Rich exhaust indication
- Black smoke possible

**Causes (ranked):**
- Rich fuel condition
- O2 sensor contaminated (reads rich constantly)
- Short to voltage in signal wire

**Fixes:**
1. Check fuel system for over-rich condition
2. Replace O2 sensor if contaminated

**Parts:** O2 Sensor $30–$100
**DIY Difficulty:** Easy–Medium

---

### P0133
**Description:** O2 Sensor Circuit Slow Response (Bank 1, Sensor 1)

**Symptoms:**
- CEL on
- Poor fuel economy
- Sluggish closed-loop control

**Causes (ranked):**
- Aging/worn O2 sensor (most common at >100k km)
- Exhaust leak upstream of sensor (introducing outside air)
- Contaminated sensor

**Fixes:**
1. Replace upstream O2 sensor — this code almost always means a worn sensor
2. Check for exhaust leaks at manifold

**Parts:** O2 Sensor $30–$100
**DIY Difficulty:** Easy–Medium

---

### P0136
**Description:** O2 Sensor Circuit Malfunction (Bank 1, Sensor 2 — downstream)

**Symptoms:**
- CEL on
- Catalytic converter efficiency cannot be monitored

**Causes (ranked):**
- Failed downstream O2 sensor
- Disconnected connector
- Wiring damage

**Fixes:**
1. Check connector at downstream sensor (under car, after cat)
2. Replace downstream O2 sensor

**Parts:** Downstream O2 Sensor $25–$80
**DIY Difficulty:** Easy–Medium

---

### P0137
**Description:** O2 Sensor Circuit Low Voltage (Bank 1, Sensor 2)

**Symptoms:**
- CEL on
- Sensor reads lean constantly after catalytic converter

**Causes (ranked):**
- Failed downstream O2 sensor
- Exhaust leak after catalytic converter
- Short to ground in signal wire

**Fixes:**
1. Inspect for exhaust leaks after cat
2. Replace downstream O2 sensor

**Parts:** Downstream O2 Sensor $25–$80
**DIY Difficulty:** Easy–Medium

---

### P0138
**Description:** O2 Sensor Circuit High Voltage (Bank 1, Sensor 2)

**Symptoms:**
- CEL on
- Sensor reads rich constantly

**Causes (ranked):**
- Failed O2 sensor stuck high
- Rich exhaust condition bypassing cat
- Short to voltage in signal wire

**Fixes:**
1. Check cat efficiency and condition
2. Replace downstream O2 sensor

**Parts:** Downstream O2 Sensor $25–$80
**DIY Difficulty:** Easy–Medium

---

### P0141
**Description:** O2 Sensor Heater Circuit Malfunction (Bank 1, Sensor 2)

**Symptoms:**
- CEL on
- Slow closed-loop entry on cold start
- Slightly poorer cold start emissions

**Causes (ranked):**
- Failed heater element in downstream O2 sensor
- Open circuit in heater wiring
- Blown fuse for O2 sensor heater circuit

**Fixes:**
1. Check fuse for O2 sensor heater circuit
2. Measure heater circuit resistance (typically 5–20 Ω)
3. Replace O2 sensor if heater failed

**Parts:** Downstream O2 Sensor $25–$80
**DIY Difficulty:** Easy

---

### P0171
**Description:** System Too Lean (Bank 1)

**Symptoms:**
- CEL on
- Rough idle
- Hesitation and stumble
- Poor fuel economy
- Possible misfire codes

**Causes (ranked):**
- Vacuum leak (intake hose, brake booster line, PCV hose)
- Dirty MAF sensor
- Clogged fuel injectors
- Low fuel pressure (weak pump)
- Clogged fuel filter
- Failed O2 sensor (reads lean constantly)
- EGR stuck open introducing excess air

**Fixes:**
1. Inspect all intake hoses and connections — look for cracks
2. Spray carburetor cleaner around intake manifold gasket joints at idle — listen for RPM change
3. Clean MAF sensor
4. Check fuel pressure: spec ~300–400 kPa
5. Replace fuel filter if >60,000 km since last change
6. Run injector cleaner; replace injectors if clogged
7. Replace upstream O2 sensor if >100k km

**Parts:** MAF cleaner $10; O2 sensor $30–$100; Fuel pump $80–$200
**DIY Difficulty:** Easy–Medium (finding leak) / Hard (fuel pump)

---

### P0172
**Description:** System Too Rich (Bank 1)

**Symptoms:**
- CEL on
- Black smoke from exhaust
- Smell of fuel from exhaust
- Fouled spark plugs
- Poor fuel economy

**Causes (ranked):**
- Leaking fuel injector (stuck open)
- Failed MAP or ECT sensor (sending incorrect data)
- Faulty fuel pressure regulator
- Rich fuel trims from EVAP purge valve stuck open
- Failed upstream O2 sensor (reads rich)

**Fixes:**
1. Check fuel pressure with regulator vacuum disconnected
2. Inspect for leaking injectors (cylinder-cut-off test or fuel pressure drop test)
3. Check ECT sensor reading
4. Inspect EVAP purge valve

**Parts:** Fuel injector $30–$100 each; O2 sensor $30–$100
**DIY Difficulty:** Medium

---

### P0201
**Description:** Injector Circuit/Open — Cylinder 1

**Symptoms:**
- CEL on
- Misfire on cylinder 1
- Rough idle
- Reduced power

**Causes (ranked):**
- Failed fuel injector (open circuit in solenoid)
- Wiring open or short to injector 1
- Damaged injector connector
- ECM output failure (rare)

**Fixes:**
1. Check injector connector for damage
2. Measure injector resistance (spec: 13.4–14.2 Ω for low-impedance injectors; ~12–17 Ω typical)
3. Check wiring from ECM to injector pin 1
4. Replace injector if failed

**Parts:** Fuel Injector (per cylinder) $25–$80 aftermarket; $60–$130 OEM
**DIY Difficulty:** Medium

---

### P0202
**Description:** Injector Circuit/Open — Cylinder 2

**Symptoms:** Same as P0201 but cylinder 2
**Causes (ranked):** Same as P0201
**Fixes:** Same diagnostic as P0201, applied to cylinder 2 injector
**Parts:** Fuel Injector $25–$130
**DIY Difficulty:** Medium

---

### P0203
**Description:** Injector Circuit/Open — Cylinder 3

**Symptoms:** Same as P0201 but cylinder 3
**Causes (ranked):** Same as P0201
**Fixes:** Same diagnostic as P0201, applied to cylinder 3 injector
**Parts:** Fuel Injector $25–$130
**DIY Difficulty:** Medium

---

### P0204
**Description:** Injector Circuit/Open — Cylinder 4 (2NZ-FE / 1NR-FE engines only)

**Symptoms:** Misfire on cylinder 4, rough idle
**Causes (ranked):** Same as P0201
**Fixes:** Same diagnostic as P0201, applied to cylinder 4 injector
**Parts:** Fuel Injector $25–$130
**DIY Difficulty:** Medium

---

### P0300
**Description:** Random/Multiple Cylinder Misfire Detected

**Symptoms:**
- CEL on (may flash — indicates catalyst damage risk)
- Rough idle
- Power loss
- Shaking

**Causes (ranked):**
- Multiple worn spark plugs
- Multiple ignition coil failure
- Fuel delivery problem (pump, filter, pressure)
- Vacuum leak causing lean misfire
- Low compression (worn engine)
- Contaminated fuel

**Fixes:**
1. Replace all spark plugs as a set (NGK ILKAR7L11, 18 Nm, 1.0mm gap)
2. Check and replace ignition coils if any are failed (test with known-good swap)
3. Compression test all cylinders
4. Check fuel pressure

**Parts:** Plug set $40–$80; Coil set $60–$150
**DIY Difficulty:** Easy–Medium

---

### P0301
**Description:** Cylinder 1 Misfire Detected

**Symptoms:**
- CEL on (may flash)
- Rough running, especially at idle
- Power loss biased toward cylinder 1 firing event

**Causes (ranked):**
- Worn/fouled spark plug cylinder 1
- Failed ignition coil cylinder 1
- Oil in plug well (valve cover gasket)
- Fuel injector issue cylinder 1
- Low compression cylinder 1

**Fixes:**
1. Swap spark plug cylinder 1 with known good cylinder — if misfire follows plug: replace plug
2. Swap ignition coil — if misfire follows coil: replace coil
3. Check plug well for oil — replace valve cover gasket if present
4. Compression test cylinder 1

**Parts:** Spark plug $8–$20; Ignition coil $20–$60
**DIY Difficulty:** Easy

---

### P0302
**Description:** Cylinder 2 Misfire Detected
**Symptoms:** Same as P0301, cylinder 2
**Causes (ranked):** Same as P0301
**Fixes:** Same as P0301 swapping for cylinder 2
**Parts:** Spark plug $8–$20; Ignition coil $20–$60
**DIY Difficulty:** Easy

---

### P0303
**Description:** Cylinder 3 Misfire Detected
**Symptoms:** Same as P0301, cylinder 3
**Causes (ranked):** Same as P0301
**Fixes:** Same as P0301 swapping for cylinder 3
**Parts:** Spark plug $8–$20; Ignition coil $20–$60
**DIY Difficulty:** Easy

---

### P0325
**Description:** Knock Sensor Circuit Malfunction (Bank 1)

**Symptoms:**
- CEL on
- Possible slight power reduction (ECM retards timing as precaution)
- May hear engine knock if spark advance not corrected

**Causes (ranked):**
- Failed knock sensor
- Damaged wiring to knock sensor
- Poor ground connection
- Loose knock sensor (not torqued correctly)

**Fixes:**
1. Locate knock sensor (mounted on engine block, typically under intake manifold)
2. Check connector and wiring
3. Measure resistance of sensor (non-resonance type: should read OL/open; resonance: 120 kΩ–280 kΩ)
4. Ensure sensor is torqued properly (20 Nm)
5. Replace sensor if failed

**Parts:** Knock Sensor $20–$60
**DIY Difficulty:** Medium (access may require intake removal)

---

### P0327
**Description:** Knock Sensor Circuit Low Input (Bank 1)

**Symptoms:**
- CEL on
- ECM may over-advance timing (dangerous if engine is knock-prone)

**Causes (ranked):**
- Short to ground in knock sensor wiring
- Failed sensor
- Damaged connector

**Fixes:**
1. Check for short to ground in signal wire
2. Replace knock sensor

**Parts:** Knock Sensor $20–$60
**DIY Difficulty:** Medium

---

### P0335
**Description:** Crankshaft Position Sensor "A" Circuit Malfunction

**Symptoms:**
- CEL on
- Engine may not start (no crank signal = no injection/ignition)
- Engine stalls suddenly
- Hard starting

**Causes (ranked):**
- Failed CKP sensor
- Damaged sensor wiring (high vibration area)
- Tone wheel damage (cracks or missing teeth on flywheel ring gear)
- Connector corrosion

**Fixes:**
1. Check CKP connector at front lower of engine (near crank pulley)
2. Inspect wiring for chafing against belts or chassis
3. Check tone wheel / reluctor ring for damage
4. Measure CKP sensor resistance (~985–1600 Ω for passive type; varies)
5. Replace CKP sensor

**Parts:** CKP Sensor $20–$70
**DIY Difficulty:** Easy–Medium

---

### P0340
**Description:** Camshaft Position Sensor "A" Circuit Malfunction (Bank 1, Intake Cam)

**Symptoms:**
- CEL on
- Hard starting or no-start
- Rough running
- VVT-i may be disabled

**Causes (ranked):**
- Failed CMP sensor (intake cam side)
- Broken/chafed sensor wiring
- Reluctor wheel damage on cam sprocket
- Oil contamination at sensor air gap

**Fixes:**
1. Check CMP sensor connector at front of head, intake cam side
2. Inspect wiring for damage
3. Test sensor operation with oscilloscope (should produce clean square wave at cranking)
4. Replace CMP sensor (Toyota Part: 90919-05040 or equivalent)

**Parts:** CMP Sensor $25–$70
**DIY Difficulty:** Easy

---

### P0351
**Description:** Ignition Coil "A" Primary/Secondary Circuit Malfunction (Cylinder 1)

**Symptoms:**
- CEL on
- Cylinder 1 misfire
- Rough idle

**Causes (ranked):**
- Failed ignition coil (coil-on-plug for cylinder 1)
- Wiring open/short to coil
- Damaged coil connector
- ECM driver failure (rare)

**Fixes:**
1. Inspect coil connector
2. Measure coil resistance: Primary 0.5–0.9 Ω; Secondary 10–16 kΩ
3. Swap with another coil — if misfire moves: replace coil
4. Check wiring from ECM to coil

**Parts:** Ignition Coil $20–$60 each; Set of 3: $50–$120
**DIY Difficulty:** Easy

---

### P0352
**Description:** Ignition Coil "B" Primary/Secondary Circuit (Cylinder 2)
**Symptoms:** Cylinder 2 misfire
**Causes (ranked):** Same as P0351
**Fixes:** Same as P0351 for cylinder 2
**Parts:** Ignition Coil $20–$60
**DIY Difficulty:** Easy

---

### P0353
**Description:** Ignition Coil "C" Primary/Secondary Circuit (Cylinder 3)
**Symptoms:** Cylinder 3 misfire
**Causes (ranked):** Same as P0351
**Fixes:** Same as P0351 for cylinder 3
**Parts:** Ignition Coil $20–$60
**DIY Difficulty:** Easy

---

### P0354
**Description:** Ignition Coil "D" Primary/Secondary Circuit (Cylinder 4 — 2NZ-FE/1NR-FE)
**Symptoms:** Cylinder 4 misfire
**Causes (ranked):** Same as P0351
**Fixes:** Same as P0351 for cylinder 4
**Parts:** Ignition Coil $20–$60
**DIY Difficulty:** Easy

---

### P0401
**Description:** EGR Flow Insufficient Detected

**Symptoms:**
- CEL on
- Increased NOx emissions
- Slight reduction in fuel economy
- May experience light knock under load

**Causes (ranked):**
- Clogged EGR valve (carbon buildup)
- Clogged EGR passage in intake manifold
- Failed EGR solenoid
- Vacuum hose to EGR cracked or disconnected

**Fixes:**
1. Locate EGR valve (typically on intake manifold, 2NZ-FE has EGR; 1KR-FE may not on all markets)
2. Remove EGR valve and inspect — heavy carbon deposits are common
3. Clean valve passages with EGR cleaner
4. Inspect vacuum lines to EGR solenoid
5. Replace EGR valve if stuck or solenoid failed

**Parts:** EGR Valve $60–$180 OEM; $30–$80 aftermarket
**DIY Difficulty:** Medium

---

### P0402
**Description:** EGR Flow Excessive Detected

**Symptoms:**
- Rough idle
- Stalling at idle
- CEL on

**Causes (ranked):**
- EGR valve stuck open (most common)
- EGR solenoid failed in open position
- Carbon debris holding valve open

**Fixes:**
1. Remove and clean EGR valve
2. Test EGR solenoid operation
3. Replace EGR valve if stuck open

**Parts:** EGR Valve $30–$180
**DIY Difficulty:** Medium

---

### P0420
**Description:** Catalyst System Efficiency Below Threshold (Bank 1)

**Symptoms:**
- CEL on
- No driveability symptoms typically
- Failing emissions test

**Causes (ranked):**
- Worn/depleted catalytic converter (most common at >150k km)
- Oil or coolant burning contaminating cat
- Exhaust leaks near cat causing false lean reading
- Failed downstream O2 sensor

**Fixes:**
1. Check for exhaust leaks at manifold and upstream of cat
2. Test both O2 sensors — replace if lazy or stuck
3. Fix any oil or coolant burning issues first
4. Replace catalytic converter if confirmed depleted

**Parts:** Downstream O2 sensor $25–$80; Catalytic converter $150–$600
**DIY Difficulty:** Easy (O2 sensor) / Medium (cat replacement)

---

### P0440
**Description:** EVAP Emission Control System Malfunction

**Symptoms:**
- CEL on
- Fuel smell may be present
- No driveability symptoms

**Causes (ranked):**
- Loose or missing fuel cap (most common)
- Leak in EVAP system hoses
- Failed EVAP purge valve
- Failed charcoal canister

**Fixes:**
1. Check fuel cap — tighten until it clicks, or replace if damaged (seal cracked)
2. Inspect EVAP hoses from fuel tank to canister
3. Test purge valve (12V signal — should open with power applied)
4. Smoke test EVAP system

**Parts:** Fuel cap $10–$25; Purge valve $20–$60
**DIY Difficulty:** Easy (cap/purge valve) / Hard (full system)

---

### P0441
**Description:** EVAP Emission Control System Incorrect Purge Flow

**Symptoms:**
- CEL on
- Possible slight rough idle when purging

**Causes (ranked):**
- EVAP purge valve stuck closed or open
- Restricted/kinked vacuum line to purge valve
- Failed purge solenoid

**Fixes:**
1. Test purge valve with 12V direct — valve should click open
2. Check vacuum/hose connections
3. Replace purge valve

**Parts:** EVAP Purge Valve $20–$60
**DIY Difficulty:** Easy

---

### P0442
**Description:** EVAP System Small Leak Detected

**Symptoms:**
- CEL on
- No driveability symptoms
- Faint fuel smell occasionally

**Causes (ranked):**
- Loose or damaged fuel cap (most common)
- Small crack in EVAP hose
- Failed purge valve (leaking)
- Charcoal canister vent valve stuck

**Fixes:**
1. Replace fuel cap first (cheap and very common cause)
2. Smoke test EVAP system
3. Inspect all EVAP hoses for micro-cracks

**Parts:** Fuel cap $10–$25; EVAP hose $5–$30
**DIY Difficulty:** Easy

---

### P0446
**Description:** EVAP System Vent Control Circuit Malfunction

**Symptoms:**
- CEL on
- Difficulty filling fuel tank (slow fill / tank pressurized)

**Causes (ranked):**
- Failed canister vent valve solenoid
- Clogged charcoal canister
- Blocked vent hose
- Wiring fault to vent valve

**Fixes:**
1. Locate canister vent valve (near fuel tank or canister)
2. Test valve electrically
3. Inspect canister for saturation (from running out of fuel repeatedly or overfilling)
4. Replace vent valve or canister

**Parts:** Canister vent valve $20–$50; Charcoal canister $60–$150
**DIY Difficulty:** Medium

---

### P0455
**Description:** EVAP System Large Leak Detected

**Symptoms:**
- CEL on
- Strong fuel smell
- Possible fuel vapor in cabin

**Causes (ranked):**
- Missing or very loose fuel cap
- Large crack in fuel filler neck hose
- Cracked or split EVAP hose
- Failed purge valve (large leak)
- Cracked charcoal canister

**Fixes:**
1. Check and replace fuel cap
2. Visually inspect all EVAP hoses
3. Smoke test system
4. Repair or replace failed components

**Parts:** Fuel cap $10–$25; Canister $60–$150
**DIY Difficulty:** Easy–Medium

---

### P0500
**Description:** Vehicle Speed Sensor "A" Circuit Malfunction

**Symptoms:**
- CEL on
- Speedometer may not work
- ABS light may come on
- Transmission may not shift correctly

**Causes (ranked):**
- Failed VSS sensor
- Damaged wiring
- ABS wheel speed sensor fault (VSS is derived from ABS on modern systems)
- Failed instrument cluster speedometer input

**Fixes:**
1. Check wheel speed sensor at each wheel — inspect for damage
2. Check VSS signal with scanner in live data
3. Replace faulty wheel speed sensor

**Parts:** Wheel Speed Sensor $20–$60 each
**DIY Difficulty:** Easy

---

### P0505
**Description:** Idle Control System Malfunction

**Symptoms:**
- CEL on
- Rough or hunting idle
- Idle too high or too low
- Stalling at idle

**Causes (ranked):**
- Dirty throttle body (most common)
- Failed ISC (Idle Speed Control) — built into ETC on drive-by-wire 1KR-FE
- Vacuum leak
- Carbon buildup preventing proper idle plate control

**Fixes:**
1. Clean throttle body (see ENGINE_REPAIR.md Section 5)
2. Perform throttle body / idle relearn procedure
3. Check for vacuum leaks
4. On cable-throttle models: clean ISC valve

**Parts:** Throttle body cleaning service; Throttle body $60–$300 if failed
**DIY Difficulty:** Easy

---

### P0506
**Description:** Idle Control System RPM Too Low

**Symptoms:**
- CEL on
- Idle drops below target (usually ~750 RPM)
- Stalling
- Shaking at idle

**Causes (ranked):**
- Dirty throttle body
- Vacuum leak (lean-induced low idle)
- MAF sensor dirty
- Carbon buildup on throttle plate

**Fixes:**
1. Clean throttle body
2. Check for vacuum leaks
3. Perform idle relearn

**Parts:** Throttle body cleaning; if replacement needed: $60–$300
**DIY Difficulty:** Easy

---

### P0507
**Description:** Idle Control System RPM Too High

**Symptoms:**
- CEL on
- High idle (above ~1000 RPM warm)
- Engine revs when put in gear causing harsh engagement

**Causes (ranked):**
- Vacuum leak (air bypassing throttle raises idle)
- Throttle plate not fully closing (dirty or worn)
- EVAP purge valve stuck open (introducing vapor)
- ETC not calibrated

**Fixes:**
1. Inspect for vacuum leaks
2. Clean throttle body
3. Perform throttle position relearn
4. Check EVAP purge valve

**Parts:** Idle relearn procedure (free); vacuum hose $5–$20 if leaked
**DIY Difficulty:** Easy

---

### P0560
**Description:** System Voltage Malfunction

**Symptoms:**
- CEL on
- Multiple warning lights
- Electrical accessories acting erratically
- Battery discharging

**Causes (ranked):**
- Weak/failing alternator
- Corroded battery terminals
- Bad battery
- Poor chassis ground
- Failing voltage regulator (internal to alternator)

**Fixes:**
1. Test battery: load test, check voltage (12.6V fully charged)
2. Test alternator output: should be 13.8–14.4V at idle with accessories on
3. Clean battery terminals
4. Inspect chassis ground straps
5. Replace alternator or battery as needed

**Parts:** Battery $80–$150; Alternator $120–$300
**DIY Difficulty:** Easy (battery) / Medium (alternator)

---

### P0600
**Description:** Serial Communication Link Malfunction

**Symptoms:**
- CEL and possibly multiple other lights
- Scanner may show communication errors
- Erratic gauge behavior

**Causes (ranked):**
- CAN bus wiring fault
- Faulty ECM
- Power supply issue to ECM
- Failed module on CAN bus causing bus load issues

**Fixes:**
1. Check ECM fuse and relay
2. Check battery voltage and charging system
3. Scan for other module codes
4. Check CAN bus wiring for shorts/opens
5. If ECM failed: replacement and programming required

**Parts:** ECM $200–$600 (requires programming)
**DIY Difficulty:** Hard

---

### P0705
**Description:** Transmission Range Sensor Circuit Malfunction (PRNDL Input) — Automatic Transmission

**Symptoms:**
- CEL on
- Transmission may not shift
- Reverse lights may not work
- Start inhibitor may fail (car starts in gear)

**Causes (ranked):**
- Faulty neutral safety switch / transmission range sensor
- Wiring damage to range sensor
- Misadjusted shift cable causing incorrect range reading

**Fixes:**
1. Inspect shift cable adjustment
2. Check range sensor connector under car (on transmission case)
3. Test range sensor resistance in each gear position
4. Replace range sensor if failed (Toyota Part: 84542-52020 or equivalent)

**Parts:** Neutral Safety Switch/Range Sensor $30–$100
**DIY Difficulty:** Medium

---

### P0710
**Description:** Transmission Fluid Temperature Sensor Circuit Malfunction (U340E automatic)

**Symptoms:**
- CEL on
- Transmission may be in failsafe
- Erratic shift points

**Causes (ranked):**
- Failed ATF temperature sensor
- Wiring fault
- Low ATF level

**Fixes:**
1. Check ATF level
2. Test ATF temp sensor resistance (varies with temperature)
3. Replace sensor if failed

**Parts:** ATF Temp Sensor $20–$60
**DIY Difficulty:** Medium

---

### P0715
**Description:** Input/Turbine Speed Sensor Circuit Malfunction (U340E)

**Symptoms:**
- CEL on
- Transmission may not shift or shifts harshly
- Speedometer error possible

**Causes (ranked):**
- Failed input speed sensor
- Damaged wiring to speed sensor
- Debris on sensor reluctor wheel

**Fixes:**
1. Check sensor connector at transmission
2. Test sensor resistance (~560 Ω typical)
3. Replace speed sensor

**Parts:** Transmission Speed Sensor $30–$80
**DIY Difficulty:** Medium

---

### P0720
**Description:** Output Speed Sensor Circuit Malfunction (U340E)

**Symptoms:**
- CEL on
- Incorrect speedometer reading
- Transmission won't shift correctly
- Possible ABS faults

**Causes (ranked):**
- Failed output speed sensor
- Damaged wiring

**Fixes:**
1. Inspect output speed sensor connector
2. Test resistance (~560 Ω)
3. Replace sensor

**Parts:** Output Speed Sensor $30–$80
**DIY Difficulty:** Medium

---

### P0730
**Description:** Incorrect Gear Ratio (U340E)

**Symptoms:**
- CEL on
- Transmission slipping
- Harsh or erratic shifts
- Limp mode

**Causes (ranked):**
- Low ATF level
- Worn ATF (degraded friction characteristics)
- Faulty shift solenoid
- Worn clutch packs inside transmission
- Speed sensor fault giving false ratio calculation

**Fixes:**
1. Check and top up ATF (Toyota WS ATF only)
2. Drain and refill ATF if never changed (U340E holds ~3.7L drain/refill)
3. Scan for solenoid codes
4. If solenoids fail: transmission service or overhaul

**Parts:** ATF (Toyota WS, 4L) $30–$60; Solenoid $30–$100
**DIY Difficulty:** Medium (fluid) / Hard (solenoid)

---

### P0741
**Description:** Torque Converter Clutch Circuit Performance or Stuck Off

**Symptoms:**
- CEL on
- Shudder at highway speeds (TCC engaging/disengaging)
- Poor fuel economy at cruising speed

**Causes (ranked):**
- Degraded ATF causing TCC slip
- Failed TCC solenoid
- Worn torque converter
- Dirty valve body

**Fixes:**
1. Drain and refill ATF with fresh Toyota WS
2. Test TCC solenoid resistance (spec: 5.0–5.6 Ω)
3. If solenoid and fluid OK: torque converter or overhaul needed

**Parts:** ATF $30–$60; TCC Solenoid $30–$80
**DIY Difficulty:** Medium (fluid) / Hard (converter)

---

### P1135
**Description:** Air/Fuel Sensor Response Malfunction (Bank 1, Sensor 1) — Wide-band upstream sensor

**Symptoms:**
- CEL on
- Poor fuel economy
- Slow closed-loop response

**Causes (ranked):**
- Aging A/F sensor (>120k km)
- Exhaust leak near sensor
- Sensor contaminated by oil or coolant burning

**Fixes:**
1. Replace upstream A/F sensor (wide-band O2 sensor)
2. Check for exhaust leaks

**Parts:** A/F Sensor (upstream) $60–$150 OEM; $40–$100 aftermarket (Denso recommended)
**DIY Difficulty:** Easy–Medium

---

### P1155
**Description:** Air/Fuel Sensor Response Malfunction (Bank 1, Sensor 2)

**Symptoms:**
- CEL on
- Catalyst monitoring impaired

**Causes (ranked):**
- Aging downstream O2 sensor
- Weak catalytic converter affecting downstream reading
- Sensor heater issue

**Fixes:**
1. Replace downstream O2 sensor
2. Check catalyst efficiency

**Parts:** O2 Sensor $25–$80
**DIY Difficulty:** Easy

---

### P1300
**Description:** Igniter Circuit Malfunction — No. 1 (Cylinder 1 Ignition)

**Symptoms:**
- CEL on
- Cylinder 1 misfire
- Rough running

**Causes (ranked):**
- Failed ignition coil module (cylinder 1)
- Wiring fault to coil 1
- ECM ignition driver fault

**Fixes:**
1. Swap coil to another cylinder and test
2. Check wiring from ECM ignition output to coil 1
3. Replace ignition coil

**Parts:** Ignition Coil $20–$60
**DIY Difficulty:** Easy

---

### P1310
**Description:** Igniter Circuit Malfunction — No. 2 (Cylinder 2 Ignition)

**Symptoms:** Same as P1300 but cylinder 2
**Causes (ranked):** Same as P1300
**Fixes:** Same as P1300 for cylinder 2
**Parts:** Ignition Coil $20–$60
**DIY Difficulty:** Easy

---

### P1349
**Description:** VVT-i System Malfunction (Bank 1)

**Symptoms:**
- CEL on
- Rough idle
- Reduced power
- Rattling on cold start
- Poor fuel economy

**Causes (ranked):**
- Sludged VVT-i solenoid (very common — poor oil maintenance)
- Low engine oil level
- Wrong oil viscosity
- Sludge blocking internal VVT passages in cam sprocket
- Failed OCV solenoid electrically
- Timing chain stretched (cam can't advance)

**Fixes:**
1. Check oil level immediately
2. Remove and clean VVT-i solenoid + screen (see ENGINE_REPAIR.md)
3. Verify oil pressure
4. If cleaning doesn't resolve: replace solenoid
5. If solenoid OK and codes persist: inspect timing chain and VVT sprocket

**Parts:** VVT-i Solenoid $30–$120; Engine flush $15; Chain kit $80–$200
**DIY Difficulty:** Easy (solenoid) / Hard (chain)

---

## BODY (B) CODES

---

### B0100
**Description:** Driver SRS Airbag Squib Circuit Malfunction

**Symptoms:**
- Airbag / SRS warning light on
- Airbag may not deploy in collision

**Causes (ranked):**
- Failed clockspring / spiral cable (most common — intermittent contact with steering rotation)
- Faulty driver airbag module
- Wiring fault in steering column
- Airbag SRS module failure

**Fixes:**
1. **CAUTION: Disable SRS system before working — disconnect battery, wait 90 seconds minimum**
2. Test clockspring resistance (should be near 0 Ω continuity, no open circuit)
3. Replace clockspring/spiral cable if open (see SUSPENSION_GUIDE.md)
4. Replace driver airbag if connector is damaged

**Parts:** Clockspring $30–$100; Airbag module (professional reset required) $200+
**DIY Difficulty:** Medium (clockspring) / Hard (airbag — SRS safety critical)

---

### B1000
**Description:** SRS Control Module Malfunction / Collision Data Stored

**Symptoms:**
- SRS warning light on
- Multiple airbag codes possible

**Causes (ranked):**
- Airbag deployed and crash data stored in module
- Module voltage fluctuation
- Internal module failure
- Wiring fault at module connector

**Fixes:**
1. If airbags deployed: SRS module and all deployed components must be replaced
2. If no deployment: check module power and ground
3. Check all SRS wiring connectors (yellow connectors in SRS circuit)
4. Replace SRS control module if internally failed (programming may be required)

**Parts:** SRS Module $150–$400
**DIY Difficulty:** Hard (SRS safety critical — dealer recommended)

---

## CHASSIS (C) CODES

---

### C0200
**Description:** Right Front Wheel Speed Sensor Circuit Malfunction

**Symptoms:**
- ABS warning light on
- TRACTION (VSC) warning light on
- ABS disabled
- Possible speedometer fault

**Causes (ranked):**
- Failed RF wheel speed sensor (most common)
- Damaged sensor wiring (chafing against wheel/suspension)
- Damaged tone ring on CV axle or hub
- Air gap too large (bearing worn — sensor moves away from ring)

**Fixes:**
1. Inspect RF wheel speed sensor connector and wiring (route near caliper — check for chafing)
2. Check tone ring for cracks or missing teeth
3. Measure sensor resistance (~1.0–1.5 kΩ for passive type)
4. Replace wheel speed sensor (bolts to steering knuckle — 1 bolt, 10mm)

**Parts:** Wheel Speed Sensor RF $25–$60
**DIY Difficulty:** Easy

---

### C0205
**Description:** Right Front Wheel Speed Sensor Circuit Range/Performance

**Symptoms:**
- ABS light on
- Erratic ABS activation at low speed

**Causes (ranked):**
- Debris on tone ring (mud, metal shavings)
- Tone ring runout (bent or eccentric)
- Intermittent sensor signal
- Worn wheel bearing causing excessive runout

**Fixes:**
1. Clean tone ring and sensor tip
2. Check wheel bearing play (max 0.05mm axial play)
3. Replace bearing if worn (see SUSPENSION_GUIDE.md)
4. Replace sensor if intermittent

**Parts:** Wheel Speed Sensor $25–$60; Wheel bearing $40–$100
**DIY Difficulty:** Easy–Hard (bearing)

---

### C0210
**Description:** Right Rear Wheel Speed Sensor Circuit Malfunction

**Symptoms:**
- ABS light on
- ABS disabled RR

**Causes (ranked):**
- Failed RR wheel speed sensor
- Wiring damage
- Corroded connector (rear sensors exposed to water/salt)

**Fixes:**
1. Inspect RR sensor connector — clean corrosion if present
2. Check wiring to rear axle
3. Replace sensor

**Parts:** Wheel Speed Sensor RR $25–$60
**DIY Difficulty:** Easy

---

### C0215
**Description:** Right Rear Wheel Speed Sensor Circuit Range/Performance

**Symptoms:**
- ABS light on
- Intermittent ABS activation

**Causes (ranked):**
- Debris on tone ring
- Worn rear wheel bearing
- Intermittent sensor

**Fixes:**
1. Clean sensor and tone ring
2. Check bearing
3. Replace as needed

**Parts:** Sensor $25–$60; Bearing $40–$100
**DIY Difficulty:** Easy–Medium

---

### C0236
**Description:** Yaw Rate Sensor Circuit Malfunction (VSC system)

**Symptoms:**
- VSC / Stability Control warning light on
- VSC system disabled
- ABS may also be limited

**Causes (ranked):**
- Failed yaw rate sensor
- Low vehicle speed input error
- Wiring fault to yaw sensor
- Contamination or impact damage to sensor

**Fixes:**
1. Locate yaw rate sensor (typically under center console or floor)
2. Check connector
3. Perform zero-point calibration with scanner
4. Replace yaw rate sensor if failed

**Parts:** Yaw Rate Sensor $80–$200
**DIY Difficulty:** Medium

---

### C0245
**Description:** Wheel Speed Sensor Frequency Error

**Symptoms:**
- ABS light on
- ABS non-functional

**Causes (ranked):**
- Air gap error on any wheel speed sensor
- Partially broken tone ring
- Bearing wear changing sensor position

**Fixes:**
1. Check all 4 wheel speed sensors
2. Measure air gaps
3. Replace worn bearings or damaged tone rings

**Parts:** Sensor set $100–$240; Bearings $40–$100 each
**DIY Difficulty:** Easy–Hard

---

### C1201
**Description:** Engine Control System Malfunction (from ABS/VSC perspective)

**Symptoms:**
- ABS/VSC light on simultaneously with CEL
- System integration fault

**Causes (ranked):**
- Engine misfire causing traction control intervention
- Engine ECM fault sending bad data on CAN bus
- CAN communication error between ECM and ABS module

**Fixes:**
1. Resolve all engine codes first (P codes)
2. Clear all codes and retest
3. If C1201 persists without engine codes: CAN bus or ABS module issue

**Parts:** Variable depending on root cause
**DIY Difficulty:** Medium

---

### C1300
**Description:** ABS Control Module Internal Malfunction

**Symptoms:**
- ABS warning light on
- ABS disabled

**Causes (ranked):**
- Failed ABS control module
- Power supply or ground issue to ABS module
- Water intrusion into module

**Fixes:**
1. Check ABS module fuse and relay
2. Check power and ground at module connector
3. Inspect module for physical damage or water intrusion
4. Replace ABS module (may require programming/bleeding)

**Parts:** ABS Module $150–$500
**DIY Difficulty:** Hard

---

## NETWORK/COMMUNICATION (U) CODES

---

### U0001
**Description:** High Speed CAN Communication Bus Malfunction

**Symptoms:**
- Multiple warning lights simultaneously
- Multiple modules failing to communicate
- Scanner may show multiple module errors

**Causes (ranked):**
- CAN bus wiring fault (short, open, or high resistance)
- Failed module dragging down the CAN bus
- Battery/charging system fault (insufficient voltage for CAN)
- Damaged CAN termination resistor

**Fixes:**
1. Check battery voltage and charging system first
2. Measure CAN bus resistance between CAN-H and CAN-L (should be ~60 Ω with both terminators in)
3. Disconnect modules one at a time to find faulty node
4. Inspect CAN wiring in main harness for damage

**Parts:** CAN wiring repair; Module replacement if failed $100–$500+
**DIY Difficulty:** Hard

---

### U0100
**Description:** Lost Communication with ECM/PCM

**Symptoms:**
- Multiple warning lights
- Instrument cluster may go blank
- Engine may stall or not start

**Causes (ranked):**
- ECM power supply or ground fault
- Blown ECM fuse
- Failed ECM
- CAN bus fault at ECM node
- Damaged ECM wiring connector

**Fixes:**
1. Check ECM fuses (typically in engine bay fuse box)
2. Check ECM ground strap at engine and chassis
3. Check ECM connector for bent pins or corrosion
4. If power/ground are good: replace ECM (requires VIN programming)

**Parts:** ECM $200–$600
**DIY Difficulty:** Hard

---

### U0121
**Description:** Lost Communication with ABS Control Module

**Symptoms:**
- ABS light on
- VSC/TRAC light on
- No ABS, no traction control, no stability control

**Causes (ranked):**
- Failed ABS control module
- ABS module fuse blown
- CAN bus wiring fault between ABS and ECM
- Poor ABS module ground

**Fixes:**
1. Check ABS fuse in engine bay fuse box
2. Check ABS module ground connections
3. Check CAN wiring between ABS module and main bus
4. Replace ABS module if failed

**Parts:** ABS Module $150–$500
**DIY Difficulty:** Hard

---

*End of DTC Full Database — 2011 Toyota Yaris XP90*
*For engine repair procedures referenced above, see ENGINE_REPAIR.md*
*For electrical system diagnosis, see ELECTRICAL_GUIDE.md*
