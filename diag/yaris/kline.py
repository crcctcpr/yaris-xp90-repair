"""K-Line protocol support — ISO 9141-2 and ISO 14230-4 (KWP2000).

On this 2011 Yaris, only the ECM answers OBD2-CAN. Body/ABS/SRS/Cluster and
the TPMS receiver almost certainly live on K-Line (OBD pin 7, 10.4 kbps)
behind a gateway. This module switches the ELM327 to K-Line, performs the
appropriate init (5-baud or fast init), and provides request/response helpers.

SAFETY: read-only. Uses mode 01/03/07/09/21/22 against K-Line targets. Never
sends 04 (clear), 08 (actuator), 27 (security), 2E (write), 31 (routine),
34/36/37 (flash). K-Line bus timing is forgiving — a bad request times out
with NO DATA, it does not brick modules.

Common Toyota K-Line module source addresses (requests go to these):
   0x01       ECM  (might also be on CAN — we already reach it there)
   0x05/0x06  TCM
   0x09       ABS / Skid control
   0x0A       SRS / airbag
   0x0C       Body ECU
   0x13       Tire pressure monitor
   0x28       A/C
   0x2C       Cluster / combination meter
   0x40       Steering

ELM327 K-Line protocol numbers:
   3 = ISO 9141-2
   4 = ISO 14230-4 (KWP2000) 5-baud init
   5 = ISO 14230-4 (KWP2000) fast init       ← most common on 2008+ Toyota

Caveats:
  - Many ELM327 clones have buggy K-Line implementations. If init fails
    repeatedly, it may be a clone limitation, not a real bus issue.
  - K-Line init can take 2-4 seconds. Be patient.
  - After init, we need to send a keep-alive (3E TP) every ~3s or the bus
    goes to sleep and we have to re-init.

Usage (read-only scan):
  python3 -m yaris.kline                # probe all known Toyota addresses
  python3 -m yaris.kline --proto 5      # force KWP2000 fast init
  python3 -m yaris.kline --addr 0C      # target just body ECU
"""
import argparse
import os
import time
from datetime import datetime

from .elm import Elm
from .obd import decode_dtcs
from .vehicle import DEFAULT_PORT, REPORT_DIR


# Toyota K-Line module address map (best-known references; verify empirically)
KLINE_TARGETS = [
    ("01", "ECM (K-Line)"),
    ("05", "TCM (alt)"),
    ("06", "TCM"),
    ("09", "ABS / Skid control"),
    ("0A", "SRS / Airbag"),
    ("0C", "Body ECU"),
    ("13", "TPMS receiver"),
    ("28", "A/C"),
    ("2C", "Cluster / Combination meter"),
    ("40", "Steering / EPS"),
    ("58", "Immobilizer"),
]

PROTO_NAMES = {
    3: "ISO 9141-2",
    4: "ISO 14230-4 KWP2000 (5-baud init)",
    5: "ISO 14230-4 KWP2000 (fast init)",
}


def kline_init(elm: Elm, proto: int = 5) -> dict:
    """Switch ELM to a K-Line protocol and force a bus-init.

    Returns dict of command/response log.
    """
    out = {}
    for cmd in [
        "ATZ",                # fresh state
        "ATE0", "ATL0", "ATS0",
        f"ATSP{proto}",       # 3=ISO9141, 4=KWP-5baud, 5=KWP-fast
        "ATAT2",              # adaptive timing
        "ATST64",              # timeout 100 x 4ms = 400ms
        "ATH1",               # headers on (source/target addrs visible)
    ]:
        out[cmd] = elm.send(cmd, 1.5)
    # Some clones need a dummy request to trigger bus init
    out["0100"] = elm.send("0100", 5.0)
    return out


def build_kwp_request(target_addr: int, service: int,
                      params: bytes = b"", tester_addr: int = 0xF1) -> str:
    """Build a KWP2000 request formatted for ELM327 (no format byte/checksum — ELM does those).

    ELM327 with ATH1 accepts just source/target/service/params in hex; the
    adapter wraps with the KWP2000 protocol header and checksum.

    But for K-Line, we usually set the header via ATSH and then send just the
    service bytes. For us, use ATSH + raw service payload.
    """
    # For KWP2000, header is: 82 + target + tester = 0x82 TA SA
    # But ELM does this when you ATSH <target_physical> and send the service.
    # Format: ATSH 82 TA F1  then send e.g. 03 (mode 03)
    header = f"82{target_addr:02X}{tester_addr:02X}"
    payload = f"{service:02X}{params.hex()}"
    return header, payload


def query_module(elm: Elm, target_hex: str, label: str,
                 tester: str = "F1") -> dict:
    """Send a series of read-only requests to a K-Line module."""
    target = int(target_hex, 16)
    tester_int = int(tester, 16)
    result = {"addr": target_hex, "label": label, "responded": False, "raw": {}, "dtcs": {}}

    # Header: 82 <target> <tester>  — KWP2000 physical addressing, 1-byte frame length
    header = f"82{target:02X}{tester_int:02X}"
    elm.send(f"ATSH{header}", 1.0)

    # Mode 03: read stored DTCs
    for mode, key in [("03", "stored"), ("07", "pending"), ("0A", "permanent")]:
        resp = elm.send(mode, 3.0)
        result["raw"][mode] = resp
        # K-Line response format: <target> <tester> <service+0x40> <count> <DTCs...> <checksum>
        # Look for 43/47/4A service-response byte
        expected = int(mode, 16) + 0x40
        codes = _parse_kwp_dtcs(resp, expected)
        if codes is not None:
            result["responded"] = True
            result["dtcs"][key] = codes

    # Service 1A: read ECU identification (Toyota uses this a lot on K-Line)
    resp = elm.send("1A80", 3.0)
    if resp and any(x in resp for x in ("5A", "7F1A")):
        result["responded"] = True
        result["raw"]["1A80"] = resp

    return result


def _parse_kwp_dtcs(resp: str, expected_service: int) -> list[str] | None:
    """Parse a KWP2000 response and extract DTCs if present."""
    # Expect lines like: "82 F1 XX 43 01 XX XX ..."
    for line in resp.splitlines():
        line = line.strip().replace(" ", "")
        if len(line) < 6:
            continue
        # Find the service byte — skip non-hex lines
        if not all(c in "0123456789ABCDEFabcdef" for c in line):
            continue
        try:
            data = bytes.fromhex(line)
        except ValueError:
            continue
        # KWP 2000: byte 0 = format/length, 1 = target, 2 = source, 3 = service, ...
        # Or with physical addressing: 82 TA SA LEN SRV DATA CS
        # We scan for the expected service byte
        if expected_service in data:
            idx = data.index(expected_service)
            # Look at next byte for DTC count
            if idx + 1 < len(data):
                payload = data[idx+1:]
                # If this is a DTC response, payload is count + 2-byte pairs
                codes = decode_dtcs(payload)
                if codes is not None:
                    return codes
    return None


def scan_all(elm: Elm, proto: int = 5) -> list[dict]:
    """Scan every known Toyota K-Line module and collect DTCs + IDs."""
    init_log = kline_init(elm, proto)
    print(f"[*] K-Line init via protocol {proto} ({PROTO_NAMES.get(proto, '?')})")
    for k, v in init_log.items():
        snippet = v[:60].replace("\n", " | ")
        print(f"    {k:8} → {snippet}")

    results = []
    for addr, label in KLINE_TARGETS:
        print(f"[→] {addr}  {label:40}", end="  ", flush=True)
        r = query_module(elm, addr, label)
        if r["responded"]:
            n_dtc = sum(len(v) for v in r["dtcs"].values())
            print(f"✓ responded, {n_dtc} DTC(s)")
        else:
            print("· silent / timeout")
        results.append(r)
        # Keep bus alive with a short delay between requests
        time.sleep(0.3)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--proto", type=int, default=5, choices=[3, 4, 5],
                    help="3=ISO9141, 4=KWP 5-baud, 5=KWP fast (default)")
    ap.add_argument("--addr", default=None, help="Target specific 1-byte address (hex)")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = f"{REPORT_DIR}/kline_scan_{ts}.txt"
    os.makedirs(REPORT_DIR, exist_ok=True)

    lines = [f"═══ K-Line scan — {ts} ═══", ""]
    try:
        with Elm(args.port) as e:
            if args.addr:
                kline_init(e, args.proto)
                label = next((l for a, l in KLINE_TARGETS if a.upper() == args.addr.upper()), "(custom)")
                r = query_module(e, args.addr, label)
                results = [r]
            else:
                results = scan_all(e, args.proto)

            responded = [r for r in results if r["responded"]]
            lines.append(f"Responded: {len(responded)} / {len(results)} modules")
            lines.append("")
            for r in results:
                if not r["responded"]:
                    continue
                lines.append(f"── {r['addr']}  {r['label']} ──")
                for bucket in ("stored", "pending", "permanent"):
                    codes = r["dtcs"].get(bucket, [])
                    lines.append(f"   {bucket:10}: {', '.join(codes) if codes else '(none)'}")
                if r["raw"].get("1A80"):
                    lines.append(f"   ECU ID raw: {r['raw']['1A80'][:80]}")
                lines.append("")

            lines.append("── Silent modules ──")
            for r in results:
                if not r["responded"]:
                    lines.append(f"   {r['addr']}  {r['label']}")

    except Exception as ex:
        lines.append(f"[!] K-Line scan failed: {ex}")
        lines.append("    Common causes:")
        lines.append("    - ELM327 clone doesn't fully support K-Line")
        lines.append("    - Car is off — K-Line needs key-on")
        lines.append("    - This vehicle has no K-Line bus at all (all modules on CAN)")

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[+] Report: {txt_path}")


if __name__ == "__main__":
    main()
