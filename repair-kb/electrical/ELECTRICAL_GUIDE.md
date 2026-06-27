# Electrical Guide — 2011 Toyota Yaris XP90

---

## 1. ENGINE BAY FUSE BOX LAYOUT

The engine bay fuse box is located on the left side of the engine bay (driver's side, near battery). It is a black plastic box with a snap-off lid that has a fuse diagram printed inside.

> Note: Exact fuse ratings may vary by market (JDM, AUS, EUR, NA). The following reflects the common XP90 configuration. Always verify against the inside of your fuse box lid.

| Fuse # | Rating | Circuit Protected |
|--------|--------|-------------------|
| 1  | 120A | Main fuse (battery to fuse box) |
| 2  | 80A  | Engine management / EFI main relay power |
| 3  | 60A  | Body electrical / ALT output |
| 4  | 40A  | Cooling fan (electric main fan) |
| 5  | 30A  | ABS / VSC pump motor |
| 6  | 30A  | Power steering (EPS — electronic) |
| 7  | 20A  | EFI main (fuel injectors, fuel pump relay) |
| 8  | 20A  | AM1 — ignition switch power |
| 9  | 15A  | Ignition (IGN) coils / sensors |
| 10 | 15A  | ECM main power |
| 11 | 15A  | ABS module power |
| 12 | 15A  | Headlight relay (low beam supply) |
| 13 | 10A  | Cooling fan relay control |
| 14 | 10A  | VSC / stability control module |
| 15 | 10A  | Alternator field / charge warning |
| 16 | 10A  | Starter relay / neutral safety input |
| 17 | 7.5A | EVAP system solenoids |
| 18 | 7.5A | O2 sensor heater circuit |
| 19 | 7.5A | Throttle body / ETC motor |
| 20 | 7.5A | MAF / IAT sensor power |
| 21 | 7.5A | CKP / CMP sensors |
| 22 | 7.5A | VVT-i solenoid circuit |
| 23 | 40A  | Window / door lock relay (some markets) |
| 24 | 20A  | Headlights — driver side |
| 25 | 20A  | Headlights — passenger side |

### Relay Locations (Engine Bay)
- **EFI main relay:** Engine bay fuse box, labeled "EFI" or "Fuel Pump"
- **Cooling fan relay:** Engine bay fuse box or mounted separately on fan shroud
- **Starter relay:** Engine bay fuse box or main relay block
- **Horn relay:** Engine bay fuse box

---

## 2. INTERIOR FUSE BOX LAYOUT

The interior (cabin) fuse box is located on the driver's side lower dashboard, behind a removable panel (pull-off or screwed cover). A fuse chart is printed on the inside of the lid.

| Fuse # | Rating | Circuit Protected |
|--------|--------|-------------------|
| 1  | 30A | Power windows (all 4) |
| 2  | 20A | Rear window defogger (heated) |
| 3  | 20A | Cigarette lighter / accessory socket |
| 4  | 15A | Instrument cluster / gauges |
| 5  | 15A | Audio system (radio/CD) |
| 6  | 15A | HVAC / Climate control blower relay |
| 7  | 15A | Horn |
| 8  | 15A | Interior lighting (dome light, map light) |
| 9  | 10A | Airbag / SRS system |
| 10 | 10A | ABS warning light circuit |
| 11 | 10A | Reverse lights |
| 12 | 10A | Brake lights |
| 13 | 10A | Daytime running lights (DRL) — if equipped |
| 14 | 10A | Tail lights / parking lights |
| 15 | 10A | Front fog lights — if equipped |
| 16 | 10A | Central door locking / remote entry |
| 17 | 10A | Keyless entry module / body ECU |
| 18 | 10A | Instrument cluster warning lights / CAN |
| 19 | 7.5A | Clock / radio memory |
| 20 | 7.5A | Stop lights (brake switch circuit) |
| 21 | 7.5A | Backup camera / parking sensors |
| 22 | 7.5A | Hazard flashers |
| 23 | 7.5A | Turn signal flasher |
| 24 | 7.5A | Wipers (front) |
| 25 | 7.5A | Wiper (rear) — if equipped |
| 26 | 7.5A | OBD-II port power |

---

## 3. BATTERY REPLACEMENT

### Battery Specification
- **Group:** 55B24L (common JDM/AUS) or equivalent group 35 (North America)
- **Voltage:** 12V
- **CCA:** Minimum 400 CCA (500 CCA recommended for reliability)
- **Ah:** Approximately 45–55 Ah

### Notes
- The Toyota Yaris XP90 does **NOT** require BMS (Battery Management System) registration after battery replacement — unlike BMW/Mercedes vehicles. Simply swap the battery.
- However, the throttle body will require a relearn idle procedure after power is disconnected (see ENGINE_REPAIR.md).

### Tools Required
- 10mm socket and wrench
- Battery terminal puller (optional)

### Procedure
1. **Safety first:** Turn off ignition and all accessories.
2. **Disconnect NEGATIVE terminal first** (black, marked "–") — prevents short circuits.
   - Loosen 10mm nut on negative clamp
   - Wiggle clamp free (do not pry with screwdriver against battery — can crack casing)
3. Disconnect POSITIVE terminal (red, marked "+") — same process.
4. Remove battery hold-down clamp (typically one 10mm or 12mm bolt/nut securing a bracket across the battery top or bottom).
5. Lift battery out — batteries are heavy (~14–18 kg). Lift with knees, not back.
6. Inspect battery tray for acid corrosion — clean with baking soda and water if corroded, rinse and dry.
7. Place new battery in tray — ensure correct orientation (positive terminal toward engine bay fuse box).
8. Install hold-down clamp — snug, do not overtighten (can crack battery case).
9. Connect POSITIVE terminal first — tighten firmly.
10. Connect NEGATIVE terminal — tighten firmly.
11. Apply terminal grease (dielectric or petroleum jelly) to terminals to prevent future corrosion.
12. Start engine — verify charging voltage is 13.8–14.4V.
13. **Perform idle relearn:** Turn ignition ON for 15 sec, OFF for 15 sec, start and idle for 3 minutes.

---

## 4. ALTERNATOR — TESTING AND REPLACEMENT

### Voltage Specifications
| Condition | Expected Voltage |
|-----------|-----------------|
| Battery at rest (engine off) | 12.4–12.7V |
| Engine idling (no accessories) | 13.5–14.5V |
| Engine at 2000 RPM (AC + headlights on) | 13.2–14.0V |
| Charging system fault | <13.0V or >15.0V |

### Testing Procedure

#### Voltage Test
1. Set multimeter to DC voltage, 20V range.
2. With engine running, measure across battery terminals.
3. Idle: should read 13.5–14.5V.
4. If below 13.0V: alternator not charging sufficiently → test further or replace.
5. If above 15.0V: voltage regulator failed high — replace alternator.

#### Load Test
1. Start engine.
2. Turn on all accessories: headlights high beam, rear defroster, fan speed max, A/C.
3. Measure battery voltage — should remain above 13.0V.
4. If voltage drops below 12.5V under load: alternator is undersized or failing.

#### Testing Alternator Diodes (ripple test)
1. Set multimeter to AC voltage.
2. Measure across battery terminals with engine running.
3. AC ripple should be <0.1V AC.
4. If ripple is >0.5V AC: failed diode(s) inside alternator — replace alternator.

### Alternator Replacement Procedure

**Location:** 1KR-FE: Right (passenger) side of engine, accessible from top or through wheel well.

1. Disconnect battery negative terminal.
2. Remove engine cover if applicable.
3. Slacken accessory drive belt by rotating tensioner (14mm) — slip belt off alternator pulley.
4. Disconnect alternator wiring:
   - Main output cable (large nut, 10mm — often 12mm nut on battery terminal stud)
   - Field/sense connector (small push-tab connector)
5. Remove alternator mounting bolts (typically 2–3 bolts, 12–14mm).
6. Maneuver alternator out of bracket (may require tipping/rotating to clear hoses).
7. Install new alternator in bracket.
8. Torque mounting bolts to 38 Nm (long bolt) / 21 Nm (short bolt) — or per spec.
9. Reconnect wiring — main cable nut torque 8 Nm, field connector clicks in.
10. Reinstall drive belt — verify it seats in all pulley grooves.
11. Reconnect battery. Start engine and verify charging voltage.

**Toyota Part:** 27060-40050 (1KR-FE alternator) — OEM ~$300–$500; Remanufactured $80–$150

---

## 5. STARTER MOTOR — TESTING AND REPLACEMENT

### Starter Motor Test

#### No-Crank Test
1. When key is turned to START:
   - **Nothing happens:** Check battery, fuse, relay, neutral safety switch
   - **Click sound:** Dead battery or starter solenoid failing
   - **Grinding:** Starter drive gear not engaging ring gear — worn starter or flywheel
   - **Long crank, eventually starts:** Weak battery or worn starter

#### Direct Test
1. Locate starter motor (on transmission bellhousing, driver's side).
2. With battery connected:
3. Use a remote starter switch or short momentarily between the battery terminal on the solenoid and the small trigger terminal on the solenoid.
4. **Warning:** Engine will crank — ensure car is in Neutral/Park and parking brake is on.
5. If starter spins: starter motor is OK — fault is in trigger circuit (relay, switch, neutral safety switch)
6. If starter does not spin: starter or solenoid failed

#### Circuit Test
1. With DVOM, check for 12V at the starter trigger terminal when the ignition key is in START position.
2. If 12V present and starter doesn't operate: starter failed — replace.
3. If no 12V: trace back through neutral safety switch, relay, and ignition switch.

### Starter Motor Replacement

**Location:** Lower driver's side of engine, attached to transmission bellhousing.

1. Disconnect battery negative terminal.
2. Raise and support vehicle.
3. Disconnect starter wiring:
   - Main power cable (12mm nut)
   - Small trigger wire (push clip)
4. Remove 2 starter mounting bolts (14mm, long bolts through bellhousing).
5. Pull starter motor out.
6. Install new starter — align spigot into bellhousing correctly.
7. Torque mounting bolts to 37 Nm.
8. Reconnect wiring — main nut torque 8 Nm.
9. Reconnect battery. Test operation.

**Toyota Part:** 28100-40050 (1KR-FE) — OEM ~$200–$350; Remanufactured $60–$120

---

## 6. POWER WINDOW MOTOR REPLACEMENT

### Symptoms of Failure
- Window moves very slowly or stops partway
- Window moves in only one direction
- Window doesn't move but switch clicks
- Grinding or clicking noise from door

### Tools Required
- Door panel removal tools (plastic trim tools)
- T20/T25 Torx screwdriver
- 8mm, 10mm sockets
- Drill with appropriate bit (for riveted regulators)

### Procedure

1. **Remove door panel** (see BODY_GUIDE.md for full door panel removal):
   - Remove door pull handle screws
   - Remove mirror triangle trim
   - Unclip power window switch panel
   - Remove all perimeter clips

2. Peel back the plastic vapor barrier — use a heat gun or hair dryer to soften the adhesive sealant. Save the barrier for reuse.

3. Disconnect the window glass from the regulator:
   - Lower window partially using a 12V power source connected to the window motor
   - Locate the glass-to-regulator clip(s) at the bottom of the glass — typically 2 plastic or metal retainers
   - Carefully slide glass up and tape it to the door frame with masking tape to hold it in place

4. Disconnect the window motor electrical connector.

5. Remove the regulator assembly:
   - Typically 3–4 bolts (10mm) securing the regulator to the door inner panel
   - Note the orientation before removing
   - If riveted: drill out rivets (5mm drill bit) to remove

6. The motor may be integral with the regulator (common in Yaris) — replace as complete assembly.

7. If motor-only replacement:
   - Remove 3 bolts securing motor to regulator arm plate
   - Unclip motor — motor shaft disengages from regulator gears
   - Install new motor — ensure shaft engages correctly

8. Install new regulator/motor assembly:
   - Bolt or rivet in place
   - Connect electrical connector
   - Lower glass onto regulator clips and secure

9. Test window operation before reinstalling vapor barrier.

10. Re-adhesive vapor barrier (automotive seam sealer or butyl tape).

11. Reinstall door panel.

**Window Motor Part:** Toyota Part: 85720-0D091 (varies by door/side) — $50–$150 OEM; $20–$60 aftermarket

---

## 7. CENTRAL LOCKING — TROUBLESHOOTING

### System Overview
The XP90 Yaris uses a body ECU / multiplex system for central locking. The ECU receives input from:
- Key fob (remote)
- Door lock switches
- Key in door lock cylinder (driver's door has a lock barrel connected to actuator)

### Common Faults

#### All Doors Don't Lock/Unlock
1. Check central locking fuse (interior fuse box, typically 10A)
2. Check central locking relay (interior fuse box)
3. Check body ECU power and ground
4. Test fob battery (CR1632 or CR2032)

#### One Door Doesn't Lock/Unlock
1. Disconnect that door's actuator connector in the door
2. Apply 12V directly between the actuator wires (swap polarity to lock/unlock)
3. If actuator moves with direct power: wiring problem between ECU and door actuator
4. If actuator doesn't move: actuator failed → replace

#### Lock Actuator Replacement
1. Remove door panel (see BODY_GUIDE.md)
2. Locate actuator inside door — typically bolted to lock mechanism
3. Disconnect electrical connector
4. Remove 2–3 bolts securing actuator
5. Disconnect actuator rod from lock linkage
6. Install new actuator and reconnect linkage

**Actuator Part:** $15–$50 per door

### Key Fob (Remote) Synchronization Procedure

If the key fob has lost sync (e.g., after battery replacement or excessive range misuse):

1. Sit in driver's seat with all doors closed.
2. Insert key into ignition.
3. Turn ignition ON and back OFF rapidly **5 times** within 5 seconds — end in the OFF position.
4. The door locks will cycle (lock then unlock) to confirm you are in programming mode.
5. Within 40 seconds, press any button on the remote to be programmed. Door locks will cycle to confirm.
6. If programming multiple remotes, repeat step 5 for each remote within 40 seconds.
7. Turn ignition ON to exit programming mode — locks will cycle again.
8. Test all remotes.

> Note: Procedure may vary by market. If above doesn't work, consult dealer or Toyota TECHSTREAM software.

---

## 8. HEADLIGHT BULB REPLACEMENT

### Bulb Specification
- **Standard:** H4 (Hi/Lo dual filament) — most XP90 markets (Japan, Australia, Europe, some Asia)
- **North America:** May use H11 (low beam) + HB3/9005 (high beam) depending on trim
- **Verify:** Check inside fuse box lid or owner's manual for your specific market

### H4 Replacement Procedure

**Access:** The H4 bulb is accessed from the engine bay. The headlight unit is fixed and does not need to be removed for bulb replacement on most variants.

1. Open the hood.
2. Locate the back of the headlight housing — the bulb access is a large rubber boot/seal covering the rear of the housing.
3. Twist or pull the rubber boot off (rotates approximately 1/4 turn or pulls straight off).
4. Unclip the spring retainer holding the bulb in place — it is a thin wire clip that pivots to release the bulb. Note how it is clipped before releasing.
5. Pull the old H4 bulb out toward you.
6. **IMPORTANT — Handle halogen bulb by the base ONLY.** Skin oil on the glass causes hot spots → bulb failure. Use clean gloves or a clean cloth.
7. Disconnect the wiring connector from the old bulb (3-pin connector — Hi, Lo, Ground).
8. Connect the same 3-pin connector to the new H4 bulb.
9. Insert new bulb into housing — the tab/key on the bulb flange only fits one way (aligns correctly oriented).
10. Re-clip the spring retainer over the bulb flange.
11. Reinstall rubber boot — ensure it seals fully against the housing (moisture intrusion = premature bulb failure).
12. Test both high and low beam.

### Headlight Aiming
After bulb replacement, check headlight aim on a flat wall at 5m. The hot spot of the dipped beam should not be higher than the center of the headlights. Adjust with the aim adjustment screws (usually 1 per headlight for vertical, 1 for horizontal — accessible from engine bay above the headlight).

---

## 9. DASHBOARD WARNING LIGHTS

The following warning lights are present on the 2011 Toyota Yaris XP90 instrument cluster:

---

### 🔴 ENGINE OIL PRESSURE WARNING (Red oil can icon)
**Meaning:** Engine oil pressure has dropped below safe threshold.
**Immediate Action:**
- **STOP THE ENGINE IMMEDIATELY** — driving with low oil pressure will destroy the engine within minutes.
- Check oil level with dipstick — add oil if low.
- If oil level is correct and light remains: do not restart — tow to workshop.
- Possible causes: low oil, failed oil pump, failed oil pressure switch, serious internal wear.

---

### 🔴 BATTERY / CHARGING SYSTEM WARNING (Red battery icon)
**Meaning:** Charging system not maintaining battery voltage.
**Immediate Action:**
- Reduce electrical load (turn off AC, heated rear window).
- Plan to get to a workshop — battery may have 30–60 minutes of driving time remaining.
- Check drive belt is present and not broken.
- Possible causes: failed alternator, slipped/broken drive belt, failed battery.

---

### 🔴 ENGINE TEMPERATURE WARNING (Red thermometer icon)
**Meaning:** Engine coolant temperature is too high — overheating.
**Immediate Action:**
- Turn off A/C immediately.
- Turn heater to maximum (helps dissipate heat).
- Pull over safely as soon as possible.
- **Do NOT open the radiator cap when hot** — serious burn risk.
- Turn engine off and wait at least 30 minutes before inspecting coolant.
- Possible causes: low coolant, thermostat failure, water pump failure, blocked radiator, head gasket failure.

---

### 🟡 CHECK ENGINE / MIL (Yellow/Amber engine outline)
**Meaning:** The engine management system has detected a fault and stored a DTC.
**Immediate Action:**
- If light is **solid:** Non-urgent — schedule inspection, read codes with OBD-II scanner.
- If light is **flashing:** Active severe misfire causing catalytic converter damage — reduce load, avoid high RPM, get to workshop promptly.

---

### 🔴 BRAKE SYSTEM WARNING (Red "!" in circle or "BRAKE" text)
**Meaning:** Parking brake is applied, OR brake fluid level is low.
**Immediate Action:**
- First: check if parking brake is released.
- If parking brake is off and light is on: check brake fluid level immediately.
- Low brake fluid may indicate: leaking brake lines, worn brake pads (fluid level drops as pistons extend), or internal master cylinder fault.
- If fluid is critically low: do not drive until inspected — risk of brake failure.

---

### 🟡 ABS WARNING LIGHT (Amber "ABS" text)
**Meaning:** ABS system has detected a fault — ABS is disabled.
**Immediate Action:**
- Normal brakes still function — you have braking, but no anti-lock protection.
- Avoid aggressive braking on slippery surfaces.
- Read codes with scanner to diagnose (usually a wheel speed sensor).
- Not an emergency but schedule repair.

---

### 🟡 AIRBAG / SRS WARNING (Amber person-with-circles icon)
**Meaning:** Airbag system has detected a fault — airbags may not deploy in a collision.
**Immediate Action:**
- The vehicle is less safe in a crash.
- Do not attempt to work on airbag system yourself without proper training.
- Take to dealer or qualified shop for diagnosis.
- Very common cause: failed clockspring from wheel impact or age.

---

### 🟡 VSC / TRACTION CONTROL OFF LIGHT (Amber with skidding car)
**Meaning:** VSC/Traction Control has been disabled (either manually pressed off, or system fault).
**Immediate Action:**
- If you pressed the VSC OFF button: this is normal — press again to re-enable.
- If light came on by itself: VSC system fault — read codes. ABS may also be affected.

---

### 🟡 TPMS WARNING (Amber tire cross-section with exclamation — if equipped)
**Meaning:** One or more tires has significantly low pressure (typically >5 psi below recommendation).
**Immediate Action:**
- Check all four tire pressures at next opportunity.
- Do not ignore — driving on underinflated tires increases blowout risk and reduces fuel economy.
- Recommended pressure: typically 30–33 psi (check door jamb sticker for your specific vehicle).
- Note: XP90 Yaris in some markets does NOT have TPMS — check if equipped.

---

### 🟡 FUEL LOW WARNING (Amber fuel pump icon or light)
**Meaning:** Fuel level is low — approximately 5–8 liters remaining.
**Immediate Action:**
- Refuel soon.
- Fuel tank capacity is 42 liters.

---

### 🔵 HIGH BEAM INDICATOR (Blue double-beam icon)
**Meaning:** High beam headlights are active. Informational only.

---

### 🟢 TURN SIGNAL INDICATORS (Green arrow — left and right)
**Meaning:** Turn signal is active. If flashing rapidly: a turn signal bulb has failed.

---

### 🟡 DOOR AJAR WARNING (Car outline with open door — some markets)
**Meaning:** One or more doors is not fully closed.
**Immediate Action:** Check all doors and boot are fully closed.

---

### 🟡 SEATBELT WARNING (Red seatbelt icon + chime)
**Meaning:** Driver (and sometimes passenger) seatbelt is not fastened with ignition on.
**Action:** Fasten seatbelt.

---

*End of Electrical Guide*
