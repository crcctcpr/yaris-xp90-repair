# From a $10 ELM327 to a full diagnostics toolkit

*How this project was built — and a practical, vehicle-agnostic guide so you can
build your own tools for **your** car.*

This is the write-up I wish I'd had when I started. It explains what an ELM327
is, where to buy one and which to avoid, what it actually does, and the exact
method used to go from "a dongle in the OBD port" to the Python toolkit in
[`diag/`](../diag/). The generic parts apply to **any** OBD-II vehicle; the
Toyota-specific parts are an example of how to push past generic OBD into your
manufacturer's enhanced data.

> **The goal:** by the end you should understand the moving pieces well enough
> to write your own diagnostics for whatever you drive. Nothing here is
> exotic — it's a serial port, some hex, and patience.

---

## 1. Background: OBD-II and the ELM327

Every petrol car sold in the US since **1996** (and most diesels; EU petrol
since ~2001, diesel ~2004) has a standardized **OBD-II** port — the trapezoidal
16-pin connector usually under the dash near the steering column. Behind it sit
your car's computers (ECUs) speaking one of a handful of low-level protocols.
On anything reasonably modern that protocol is **CAN (ISO 15765-4)**.

You can't just wire a laptop to those pins — the signalling and framing are
specific. That's what the **ELM327** is for. It's a small microcontroller
(originally a PIC from ELM Electronics) that:

- speaks all the OBD-II physical protocols on the car side, and
- exposes a dead-simple **text command interface** on the computer side.

To your computer it looks like a **serial port**. You write ASCII commands, it
writes ASCII back. That's the whole magic — it turns "automotive bus protocol
engineering" into "read/write lines of text," which is why a hobbyist can build
real tools with it.

---

## 2. Buying one: what to get, what to avoid

### Form factors
| Type | Talks to PC via | Good for | Notes |
|------|-----------------|----------|-------|
| **USB** | `/dev/ttyUSB0` (serial) | Most reliable, simplest | No pairing hassle. Great for a laptop in the car. |
| **Bluetooth (Classic / SPP)** | `/dev/rfcomm0` (serial over BT) | Phones, Linux, this project | **What this project used.** Pairs as a serial port. |
| **Bluetooth LE** | GATT, not a serial port | Newer phone apps | Harder to script on Linux; avoid for this style of tool. |
| **WiFi** | TCP socket (usually `192.168.0.10:35000`) | iOS, networked setups | Works, but you talk to a socket instead of a serial port. |

For a **Linux + Python + `pyserial`** workflow like this one, get a
**Bluetooth Classic (SPP)** or **USB** adapter. Avoid "BLE only" dongles unless
you enjoy pain.

### Genuine vs. clone
The original ELM327 firmware is **discontinued and effectively unavailable new**.
Virtually every cheap adapter is a **clone** running cloned/older firmware, and
many lie about their version ("v1.5" / "v2.1" stickers are meaningless). For
**read-only diagnostics** — which is all this toolkit does — the clones are
fine, and that's the point: the whole project was built on a **~$10 Bluetooth
clone**.

If you want reliability (faster, honest chipset, better protocol coverage,
won't drain your battery), step up to a reputable brand:

- **Budget / disposable (~$8–15):** generic "OBD2 ELM327 Bluetooth" off
  Amazon / AliExpress / eBay. Works for reading. Expect occasional flakiness.
  *This is what this project used.*
- **Quality (~$30–70):** **OBDLink SX** (USB) or **OBDLink MX+** (Bluetooth) —
  genuine STN chipset, much faster, well-behaved, supports more protocols. If
  you're going to do this seriously, buy one of these.

### What to check before buying
- **Your car's protocol.** Post-2008-ish = almost certainly CAN (ISO 15765-4).
  Older cars may use ISO 9141-2 / KWP2000 / J1850 — make sure the adapter lists
  it (most "support all protocols").
- **Bluetooth Classic + SPP** (not BLE only) if you want the serial-port path.
- The **PIN** for cheap BT clones is almost always `1234` or `0000`.

### One safety note on the hardware
Cheap adapters can keep the CAN bus awake and **slowly drain your battery** if
left plugged in for days. Unplug it when you're not using it.

---

## 3. What the ELM327 does, concretely

Once it's a serial port, you talk to it with two kinds of commands:

1. **`AT` commands** — configure the *adapter* (reset, echo, protocol, headers…).
   These never reach the car.
2. **OBD commands** — hex like `010C` (mode `01`, PID `0C` = engine RPM) that the
   adapter forwards to the *car* and returns the answer.

A minimal session looks like this (what [`elm.py`](../diag/yaris/elm.py) wraps):

```
ATZ          → reset the adapter           → "ELM327 v1.5"
ATE0         → turn off command echo       → "OK"
ATSP6        → set protocol 6 (CAN 11-bit 500k) → "OK"
010C         → ask the car for RPM         → "41 0C 0B 90"
```

That last line decodes as: `41` = positive response to mode `01`, `0C` = the PID
you asked for, `0B90` = `((0x0B*256)+0x90)/4` = **740 RPM**. Decode rules for
every standard PID are public (SAE J1979 / Wikipedia's "OBD-II PIDs"). The
project's decoders live in [`obd.py`](../diag/yaris/obd.py).

The key `AT` commands this project relies on (see `elm.py::init_can`):

| Command | Effect |
|---------|--------|
| `ATZ` / `ATE0` | reset / echo off |
| `ATSP6` | select ISO 15765-4 CAN, 11-bit, 500 kbps |
| `ATH1` | show CAN headers (so you can tell *which* ECU replied) |
| `ATCAF1/0` | CAN auto-formatting (ISO-TP) on/off |
| `ATSH 7E0` | set the request header (target the engine ECU directly) |
| `ATMA` | **monitor all** — passively dump every frame on the bus |

---

## 4. Getting it talking on Linux (the genuinely fiddly part)

USB adapters "just work" (`/dev/ttyUSB0`). Bluetooth clones are where people get
stuck, because BlueZ and the clone's PIN handshake fight each other. The flow
that works (and the helper in [`bt_pair_agent.py`](../diag/bt_pair_agent.py)):

```bash
# Terminal 1 — auto-answer the PIN prompt (clones use 1234 or 0000)
sudo python3 diag/bt_pair_agent.py --pin 1234

# Terminal 2 — find, pair, and bind it to a serial device
sudo bluetoothctl -- scan on            # ~15s; note the adapter's MAC
sudo bluetoothctl -- pair AA:BB:CC:DD:EE:FF
# if bluetoothctl's own agent hijacks the PIN, pair straight over D-Bus:
sudo dbus-send --system --print-reply --dest=org.bluez \
    /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF org.bluez.Device1.Pair
# bind it to a serial port — NOTE: many clones use SPP channel 2, not 1
sudo rfcomm bind rfcomm0 AA:BB:CC:DD:EE:FF 2
sudo chmod 666 /dev/rfcomm0
```

Now `/dev/rfcomm0` is a serial port and `pyserial` can open it like any other.
That "SPP channel 2, not 1" detail cost hours; it's the single most common reason
a clone pairs but won't open.

---

## 5. How the toolkit was actually developed

This is the part the project is really about. The method, in the order it
happened:

### Step 1 — Prove the link
`ATI` (adapter ID), `ATRV` (battery voltage). If `ATRV` shows ~12–14 V you're
physically connected to a live car. Build *nothing* else until this is solid;
flaky power/Bluetooth will masquerade as "car problems" forever.

### Step 2 — Speak generic OBD-II first (works on every car)
Before any Toyota-specific work, the universal modes give you a lot:

- **Mode 01** — live data (RPM, speed, coolant, MAF, fuel trims, throttle…).
- **Mode 03 / 07 / 0A** — stored / pending / permanent trouble codes.
- **Mode 09** — vehicle info (VIN, calibration IDs).
- **Mode 04** — clear codes (the *only* thing this toolkit ever writes).

Decoding DTCs from raw bytes is a tidy example — two bytes per code, top bits
pick the letter (P/C/B/U). See `obd.py::decode_dtcs`. Everything in this layer
is **vehicle-independent**: it already works on your car, today.

### Step 3 — Reassemble multi-frame responses (ISO-TP)
The ELM hands you text, but longer answers arrive as **multiple CAN frames**
(ISO-TP: a "first frame" with a length, then "consecutive frames"). You have to
stitch them back together before decoding. `obd.py::parse_can` does this:
single-frame, first-frame (`1xxx` = total length), and consecutive-frame (`2x`)
handling, keyed by ECU header. Getting this right is what separates "reads RPM"
from "reads a 40-byte enhanced data block."

### Step 4 — Push past generic OBD into manufacturer data
Generic OBD-II is the floor, not the ceiling. Manufacturers expose far more
through **enhanced services** — for Toyota, service **`21`** (and `22`). The
problem: which sub-functions exist is **undocumented**. So the project *probed
the ECU itself*. [`mode21_sweep.py`](../diag/yaris/mode21_sweep.py) walks all
**256** sub-functions (`2100`…`21FF`) and records, for each:

- a **positive** response (`61 xx …`) → that sub-function exists; log its length
  and raw hex, or
- a **negative** response (`7F 21 <NRC>`) → rejected, with the reason code
  (`0x12` = "sub-function not supported", `0x33` = "security access denied", …).

On the 2011 Yaris ECM, ~5–10 of the 256 respond with real data. That sweep is
how you *discover* what your specific ECU is willing to tell you, without a
factory tool. From there it's detective work: change one thing in the car
(rev it, warm it up), watch which bytes move, and you've mapped a field.

### Step 5 — Turn raw bytes into meaning
Numbers aren't diagnosis. The toolkit pairs each reading with an
**expected-value table** for the engine (idle RPM 650–850, warm coolant 85–98 °C,
fuel trims ±7 %, etc. — in the vehicle profile). That's what powers the original
use case: a chronic **P0101 / MAF** fault, found by watching MAF g/s and
long-term fuel trim drift outside expected ranges, and *confirmed fixed* by
comparing before/after drive logs (`verify`).

### Step 6 — Wrap it in workflows, not one-off scripts
The same primitives compose into the actual user-facing commands: live `dash`
(logging to CSV), `healthcheck`, `economy`/`drive` (fuel economy from speed+MAF),
`readiness` (emissions monitors), `cat` (catalyst efficiency from the two O2
sensors), and before/after `verify`. Each is thin once the link + decode layers
are solid.

### Step 7 — Connect data back to repair knowledge
A code number is useless without "so what do I do?" Every DTC the tool reports
cross-links straight into the Markdown repair wiki in
[`repair-kb/`](../repair-kb/) (127-code database → ranked causes → fixes). The
diagnostics and the repair knowledge are one system.

### Step 8 — Passive CAN sniffing
`ATMA` ("monitor all") dumps every frame on the bus read-only — useful for
spotting broadcast traffic and non-OBD modules. See `yaris_can_sniff.py`.

### The safety model that made all of this OK to run
**Everything is read-only except `clear`** (an audited mode-04: snapshot → clear
→ snapshot). The toolkit deliberately never touches the dangerous UDS services —
security access (`27`), routine control (`31`), write-data (`2E`), or programming
(`34`–`37`). You cannot brick an ECU by *reading* it, and that constraint is what
let development be fearless. **Adopt the same rule for your own tools.**

---

## 6. The stack (and why it's deliberately tiny)

- **Python 3.11+** and **`pyserial`** — that's the only hard dependency.
  `matplotlib` is optional (text fallback), D-Bus libs only for the BT helper.
- **VIN-keyed profiles** (`diag/yaris/vehicles/<VIN>.toml`) hold everything
  car-specific — adapter MAC, protocol, expected-value tables — so the *code*
  stays generic and you describe your car in *data*.
- **62 unit tests** run with **recorded ELM responses** as fixtures, so you can
  develop and refactor the decoders **with no car and no adapter attached**.
  Record a few real responses once, then iterate offline forever. This is the
  highest-leverage habit in the whole project.

---

## 7. Recreate it for YOUR vehicle

1. **Buy the adapter** (Section 2) and **get `/dev/rfcomm0` or `/dev/ttyUSB0`
   talking** (Section 4). Confirm with `ATRV`.
2. **Start with generic OBD-II** (Section 5, Steps 2–3) — live PIDs and DTCs work
   on any OBD-II car with zero customization.
3. **Make a profile.** Copy `diag/yaris/vehicles/_template.toml`, put in your
   VIN, adapter MAC, and engine's normal ranges. (Your real profile stays local —
   it's `.gitignore`d so you never publish your VIN/MAC.)
4. **Discover your enhanced data.** Run the mode-21/22 sweep against your ECU to
   see what it supports. Cross-reference your manufacturer's enhanced PIDs from
   community sources (vehicle forums, the **opendbc** project, RomRaider for
   Subaru, etc.).
5. **Map fields experimentally.** Change one variable in the car, watch which
   bytes move, write a decoder, add an expected range.
6. **Stay read-only.** Log everything, baseline a *healthy* car so you know what
   "normal" looks like before you go chasing a fault.

The Toyota tables won't match your car — but the **method** (link → generic OBD →
ISO-TP → enhanced discovery → expected values → workflows) is identical for a
Honda, a VW, or a truck.

---

## 8. Room for improvement (PRs welcome)

This is a hobbyist project built around one car; there's plenty to do:

- **More vehicle profiles** — the whole point is generalization; every added
  `<VIN>.toml` + enhanced-PID map helps the next owner.
- **BLE adapter support** — talk to BLE-only ELM327s via GATT instead of SPP.
- **DBC-based decoding** — integrate **opendbc** so raw CAN sniffs decode into
  named signals automatically.
- **WiFi adapter transport** — a socket backend alongside the serial one.
- **Mode 06 expansion** — richer on-board test-result (OBDMID) decoding.
- **Async I/O** — replace the blocking `pyserial` loop for smoother live dashes.
- **A real GUI / mobile front-end** over the existing web dashboard.
- **Community DTC contributions** — expand the database beyond the XP90.
- **J2534 / DoIP** for newer vehicles that gate data behind authenticated
  sessions.

If you build any of these — or just add your car — send a PR.

---

## 9. Legal & safety

This is hobbyist tooling, provided as-is, **not affiliated with Toyota or any
manufacturer**. It only *reads* your vehicle (plus the audited mode-04 clear).
Don't clear emissions monitors right before a smog test (you'll fail readiness).
Work on vehicles carries risk — when unsure, consult a professional. You're
responsible for complying with your local emissions and right-to-repair rules.
See [`LICENSE`](../LICENSE) (MIT).
