# Yaris OBD2 Toolkit

**Target:** 2011 Toyota Yaris, VIN `JTDEXAMPLE0000000`, 1NR-FE 1.3L
**Adapter:** ELM327 v2.1 clone (BT `AA:BB:CC:DD:EE:FF`, PIN `1234`, SPP channel **2**)
**Protocol:** ISO 15765-4 CAN 11-bit 500 kbps

## Quick reference

All subcommands are reachable through the `yaris-diag` launcher in the parent
tools directory (`../yaris-diag <subcommand>`):

| Subcommand    | What it does                                                                             |
|---------------|------------------------------------------------------------------------------------------|
| `connect`     | Verify BT + rfcomm + adapter liveness                                                    |
| `pull`        | Full state dump (mode 01/03/07/0A/02/06/09/21/22) → `reports/yaris_full_pull_*.{txt,json}` |
| `dash`        | Live dashboard + CSV logging (use while driving or at idle)                             |
| `scan`        | Multi-ECU DTC scan — walks 14 likely CAN addresses                                      |
| `sniff`       | Passive CAN bus monitor (ATMA). Note: this car's OBD2 CAN is request-response only      |
| `tpms`        | TPMS probe — DTCs + DIDs + mode 21 subfunctions                                          |
| `clear`       | **Audited** code clear: before snapshot → 04 → after snapshot → diff                     |
| `readiness`   | Monitor-completion tracker (`--once` or continuous watch)                                |
| `analyze`     | Analyze a dash CSV for MAF / LTFT health                                                 |
| `verify`      | Compare two dash CSVs (before / after a repair) with pass/fail verdict                   |
| `coldstart`   | Guided cold-start warm-up analyzer                                                       |
| `cat`         | Catalyst efficiency monitor (upstream vs downstream O2 dynamics)                         |
| `healthcheck` | "Is my car OK?" one-shot — DTC DB + live ranges + ranked priority list                   |
| `mode06`      | Full walk of mode 06 on-board monitor results (cat eff %, O2 response ms, EGR flow)     |
| `enhanced`    | Toyota mode 21 enhanced data probe with byte-auto-correlation against known PIDs         |
| `drive`       | **Guided drive-cycle runner** — auto-advances phases from live data (no ENTER presses) |
| `web`         | Live dashboard (`127.0.0.1:8080`) + `/compare` overlay page for before/after CSVs |
| `history`     | Query longitudinal SQLite history — sessions, LTFT trends, MAF ratio trends, DTC counts |
| `kline`       | ISO 9141-2 / KWP2000 scan of non-CAN modules (ABS/SRS/TPMS/Body/Cluster)                 |
| `plot`        | Matplotlib PNG exports — MAF scatter, trim overlay, before/after, LTFT history           |
| `economy`     | Fuel economy estimator from MAF — L/100km, MPG, per-session trend, before/after delta    |
| `dtc <CODE>`  | Look up DTCs in the local knowledge base (with cross-links to `YarisRepair/` procedures) |

## Longitudinal data store

Every `dash` run writes to both CSV (point-in-time) and `reports/yaris_history.db`
(cross-session queries). Explore with:

```bash
./yaris-diag history                  # overview across 30 days
./yaris-diag history --sessions 20    # recent sessions
./yaris-diag history --ltft 30        # LTFT trend (bar chart)
./yaris-diag history --maf 30         # MAF ratio trend (✓/~/✗ per session)
./yaris-diag history --dtcs           # DTC occurrences
./yaris-diag history --session 42     # full detail for one session
./yaris-diag history --import <CSV>   # ingest an existing CSV into history
```

## Multi-vehicle profiles

Vehicle-specific constants (VIN, MAC, engine, expected ranges) live in
`yaris/vehicles/<VIN>.toml`. To add a new car:

```bash
cp yaris/vehicles/_template.toml yaris/vehicles/<NEW_VIN>.toml
# Edit the new file
YARIS_VIN=<NEW_VIN> ./yaris-diag healthcheck
```

## Reliability

All tools for long-running operations use `ResilientElm` — wraps the raw
`Elm` class and auto-recovers from BT link drops by re-binding rfcomm and
re-running the ELM init sequence. Up to 3 retries per command, 2 rebinds
per open.

## Testing

```bash
python3 -m unittest discover yaris/tests
```

62 tests covering: CAN parser, DTC decoder, PID decoders, readiness bits,
expected-MAF physics model, DTC knowledge base, profile loader, resilient
wrapper reconnect logic, SQLite store schema + queries.

## Safety model

**Read-only services used everywhere except `clear`:**
- 01 (live data), 02 (freeze frame), 03/07/0A (DTCs), 06 (monitor results),
  09 (vehicle info), 21 (Toyota enhanced), 22 (UDS read DID)

**Write / command services `NEVER` used:**
- 04 (clear) — only inside `clear` subcommand, with audit trail
- 08 (actuator tests), 10 (session change), 27 (security access),
  2E (write DID), 2F (I/O control), 31 (routine), 34/36/37 (flash), 3B (write)

You cannot brick the car with this toolkit. Worst case from any script is a
negative response code (`7F xx 11` etc.) or a timeout.

## Package layout

```
yaris/
├── __init__.py          # version, doc
├── vehicle.py           # VIN, engine params, expected ranges, paths
├── elm.py               # ELM327 serial I/O wrapper (init, send, monitor)
├── obd.py               # CAN parser, ISO-TP reassembly, PID/DTC decoders
├── connect.py           # BT + rfcomm state / rebind / health-probe
├── dtc_db.py            # XP90 / 1NR-FE code DB (symptoms, causes, fixes, parts)
├── readiness.py         # `yaris-diag readiness`
├── clear.py             # `yaris-diag clear`  (audited)
├── verify.py            # `yaris-diag verify`
├── coldstart.py         # `yaris-diag coldstart`
├── cat_efficiency.py    # `yaris-diag cat`
├── healthcheck.py       # `yaris-diag healthcheck`
└── cli.py               # top-level launcher dispatcher
```

The older standalone scripts (`yaris_full_pull_can.py`, `yaris_live_dash.py`,
`yaris_all_ecu_scan.py`, `yaris_can_sniff.py`, `yaris_tpms_probe.py`,
`yaris_maf_analysis.py`) still work on their own and are wired into the CLI
via subprocess. Gradual migration to the `yaris/` package is fine but not
required — these tools are battle-tested.

## Connection recovery (copy-paste)

If the BT link is dead and the adapter needs re-pairing from scratch:

```bash
# 1. Agent in background (pair-response handler)
sudo python3 ./bt_pair_agent.py \
    --pin 1234 --mac AA:BB:CC:DD:EE:FF &

# 2. Cache the device in bluez
( printf 'scan bredr\n'; sleep 12 ) | sudo bluetoothctl

# 3. Trigger pair via D-Bus (avoids bluetoothctl's agent-hijack)
sudo dbus-send --system --print-reply \
    --dest=org.bluez /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF \
    org.bluez.Device1.Pair

# 4. Bind + permissions
sudo rfcomm bind rfcomm0 AA:BB:CC:DD:EE:FF 2
sudo chmod 666 /dev/rfcomm0

# 5. Sanity-check
./yaris-diag connect
```

If already paired, steps 1–3 can be skipped — step 4 alone is enough.

## Deprecated

Files in `../deprecated_2001_iso9141/` were written for a 2001 Yaris on
ISO 9141-2 K-Line. They do not apply to this CAN-protocol 2011 car. Kept
only for reference if we ever need to reach the body / ABS / SRS modules
(which may live on the K-Line bus on pin 7).
