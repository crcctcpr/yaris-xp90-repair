#!/usr/bin/env python3
"""
TPMS probe for 2011 Yaris.

2011 Yaris TPMS is direct-type (individual RF sensors in each wheel @315 MHz US /
433 EU). The receiver lives in one of a few candidate CAN modules — we try each,
pull DTCs (TPMS codes are C0xxx), and attempt the commonly-documented read PIDs
for individual tire pressures / statuses.

READ-ONLY. Stays in the default diagnostic session — does NOT send mode 10
(session change), 27 (security access), 2E/2F (write/IO), 31 (routine),
34/36/37 (flash), 04 (clear), 08 (actuator). If a DID requires extended session
we'll report "NRC 0x11/0x12" and stop — we won't auto-escalate.

Usage:
  python3 yaris_tpms_probe.py [--port /dev/rfcomm0]
"""
import serial, time, sys, os, argparse, json
from datetime import datetime

REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))

# Candidate modules that commonly host TPMS on Toyota CAN
TPMS_CANDIDATES = [
    ('750', 'ABS / Skid control (common TPMS host on JDM Toyota)'),
    ('7C0', 'Body ECU (common TPMS host on US-market Toyota)'),
    ('740', 'Brake ECU'),
    ('7B0', 'SRS / airbag'),
    ('7E0', 'ECM (unlikely but cheap to check)'),
    ('7A0', 'Cluster'),
]

# Known Toyota TPMS DIDs / PIDs (documented from multiple Toyota service sources).
# Ranges probed via mode 22 (Read Data By Identifier). No guarantee a given
# platform supports them — we just ask and log whatever comes back.
TPMS_DIDS = [
    # Individual tire pressures (kPa) — Toyota common range
    (0x2100, 'TPMS status block 1 (Toyota common)'),
    (0x2101, 'TPMS status block 2'),
    (0x2102, 'TPMS FL pressure'),
    (0x2103, 'TPMS FR pressure'),
    (0x2104, 'TPMS RL pressure'),
    (0x2105, 'TPMS RR pressure'),
    (0x2108, 'TPMS warning state'),
    # Broader Toyota TPMS DIDs seen on various platforms
    (0x010A, 'TPMS generic block A'),
    (0x011A, 'TPMS generic block B'),
    (0x0160, 'TPMS sensor IDs'),
    (0x0161, 'TPMS sensor IDs alt'),
    (0xF405, 'TPMS tire 1 data (UDS DID)'),
    (0xF406, 'TPMS tire 2 data'),
    (0xF407, 'TPMS tire 3 data'),
    (0xF408, 'TPMS tire 4 data'),
    (0xF40A, 'TPMS bundled data'),
    # Generic UDS identifiers that sometimes carry TPMS
    (0xF190, 'VIN (verify module alive)'),
    (0xF18C, 'ECU serial number'),
]

# Toyota enhanced mode 21 subfunctions that sometimes expose TPMS on Toyota ABS
MODE21_PROBES = [
    (0x01, '21 01 main data'),
    (0x02, '21 02 data page 2'),
    (0x30, '21 30 sensor data'),
    (0x40, '21 40 TPMS (some Toyotas)'),
    (0x41, '21 41 TPMS alt'),
    (0xA0, '21 A0 TPMS (Toyota specific)'),
    (0xB1, '21 B1 TPMS alt'),
]

def send(ser, cmd, wait=2.0):
    ser.reset_input_buffer()
    ser.write(cmd.encode() + b'\r')
    t0 = time.time(); buf = b''
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if buf.endswith(b'>'): break
        time.sleep(0.02)
    return buf.decode('ascii', 'replace').replace('\r','\n').replace('>','').strip()

def init(ser):
    for c in ['ATZ','ATE0','ATL0','ATH1','ATS0','ATSP6','ATCAF1','ATST50','ATAT1']:
        send(ser, c, 1.5)

def parse_can(resp):
    ecus = {}; cf = {}
    for line in resp.splitlines():
        line = line.strip().replace(' ', '')
        if not line: continue
        if any(x in line for x in ('NODATA','SEARCHING','OK','?','STOPPED','ERROR','UNABLE','CAN','BUS')):
            continue
        if len(line) < 6: continue
        hdr = line[:3]
        try: first = int(line[3:5], 16)
        except: continue
        pci = line[3:4]
        try:
            if pci == '0':
                L = first & 0x0F
                ecus[hdr] = ecus.get(hdr, b'') + bytes.fromhex(line[5:5+2*L])
            elif pci == '1':
                L = int(line[3:7], 16) & 0x0FFF
                data = bytes.fromhex(line[7:])
                ecus[hdr] = data; cf[hdr] = L - len(data)
            elif pci == '2':
                data = bytes.fromhex(line[5:])
                if hdr in ecus:
                    need = cf.get(hdr, len(data))
                    ecus[hdr] += data[:need]; cf[hdr] = max(0, need-len(data))
        except ValueError: pass
    return ecus

NRC = {
    0x10: 'general reject',
    0x11: 'service not supported',
    0x12: 'subfunction not supported',
    0x13: 'invalid message length',
    0x22: 'conditions not correct',
    0x31: 'request out of range',
    0x33: 'security access denied',
    0x7E: 'subfunc not in active session',
    0x7F: 'service not in active session',
}

def decode_dtcs(data):
    if len(data) < 1: return []
    n = data[0]; codes = []
    for i in range(n):
        off = 1 + 2*i
        if off+1 >= len(data): break
        b1, b2 = data[off], data[off+1]
        letter = ['P','C','B','U'][(b1 >> 6) & 0x3]
        codes.append(f"{letter}{(b1>>4)&0x3}{b1&0x0F:X}{(b2>>4)&0x0F:X}{b2&0x0F:X}")
    return codes

def plausible_tpms_pressure(b1, b2=None):
    """Return a tire pressure guess in PSI if bytes look like a pressure value."""
    if b2 is None:
        # Single byte: could be PSI direct, or kPa/4 (common Toyota), or 0.25 PSI units
        guesses = []
        if 20 <= b1 <= 60: guesses.append(f"{b1} PSI direct")
        kpa = b1 * 4
        if 140 <= kpa <= 400: guesses.append(f"{kpa} kPa ({kpa*0.145:.0f} PSI)")
        p = b1 * 0.25
        if 20 <= p <= 60: guesses.append(f"{p:.2f} PSI (0.25 units)")
        return guesses
    # Two-byte: big-endian kPa, or big-endian 0.01 kPa
    kpa16 = (b1 << 8) | b2
    out = []
    if 140 <= kpa16 <= 400: out.append(f"{kpa16} kPa")
    if 14000 <= kpa16 <= 40000: out.append(f"{kpa16/100:.1f} kPa ({kpa16/100*0.145:.1f} PSI)")
    return out

def probe_module(ser, req_id, label):
    out = {'req': req_id, 'label': label, 'responded': False,
           'dtcs': {}, 'dids': {}, 'mode21': {}, 'notes': []}
    send(ser, f'ATSH{req_id}', 0.8)

    # DTCs first — cheapest "is it alive" check
    for mode, key in [('03', 'stored'), ('07', 'pending'), ('0A', 'permanent')]:
        resp = send(ser, mode, 2.5)
        ecus = parse_can(resp)
        codes_by_hdr = {}
        for hdr, data in ecus.items():
            if not data: continue
            exp = int(mode, 16) + 0x40
            if data[0] == exp:
                out['responded'] = True
                codes_by_hdr[hdr] = decode_dtcs(data[1:])
            elif data[0] == 0x7F and len(data) >= 3:
                out['responded'] = True
                out['notes'].append(f"{mode}@{hdr} NRC 0x{data[2]:02X} ({NRC.get(data[2],'?')})")
        if codes_by_hdr:
            out['dtcs'][key] = codes_by_hdr

    if not out['responded']:
        return out

    # DID probes (mode 22)
    for did, name in TPMS_DIDS:
        cmd = f"22{did:04X}"
        resp = send(ser, cmd, 2.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if len(data) < 2: continue
            if data[0] == 0x62 and len(data) >= 3:
                # positive response: 62 <DID_hi> <DID_lo> <data...>
                if len(data) >= 4 and (data[1]<<8 | data[2]) == did:
                    payload = data[3:]
                    entry = {'hdr': hdr, 'hex': payload.hex(), 'len': len(payload)}
                    # ASCII view
                    entry['ascii'] = ''.join(chr(c) if 32<=c<127 else '.' for c in payload)
                    # TPMS pressure hint
                    hints = []
                    if len(payload) >= 1:
                        hints += plausible_tpms_pressure(payload[0])
                    if len(payload) >= 2:
                        hints += plausible_tpms_pressure(payload[0], payload[1])
                    if hints:
                        entry['pressure_hint'] = hints
                    out['dids'][f"22{did:04X}"] = {'name': name, 'result': entry}
            elif data[0] == 0x7F and len(data) >= 3 and data[1] == 0x22:
                # NRC — log if security/session related
                if data[2] in (0x11, 0x12, 0x31, 0x7E, 0x7F):
                    # store summary rather than one-per-DID; these fill up fast
                    out.setdefault('_did_rejects', {}).setdefault(f"0x{data[2]:02X}", 0)
                    out['_did_rejects'][f"0x{data[2]:02X}"] += 1

    # Mode 21 enhanced probes
    for sub, name in MODE21_PROBES:
        cmd = f"21{sub:02X}"
        resp = send(ser, cmd, 2.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if len(data) < 2: continue
            if data[0] == 0x61:
                out['mode21'][cmd] = {
                    'name': name,
                    'hdr': hdr,
                    'hex': data[1:].hex(),
                    'ascii': ''.join(chr(c) if 32<=c<127 else '.' for c in data[1:]),
                }
            elif data[0] == 0x7F and len(data) >= 3 and data[1] == 0x21:
                if data[2] in (0x11, 0x12):
                    out.setdefault('_mode21_rejects', {}).setdefault(f"0x{data[2]:02X}", 0)
                    out['_mode21_rejects'][f"0x{data[2]:02X}"] += 1

    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/rfcomm0')
    ap.add_argument('--baud', type=int, default=38400)
    args = ap.parse_args()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = f"{REPORT_DIR}/tpms_probe_{ts}.txt"
    json_path = f"{REPORT_DIR}/tpms_probe_{ts}.json"

    print(f"═══ TPMS probe — {ts} ═══\n")
    ser = serial.Serial(args.port, args.baud, timeout=3)
    time.sleep(0.2)
    init(ser)

    results = []
    for req, label in TPMS_CANDIDATES:
        print(f"[→] {req}  {label:55}", end='  ', flush=True)
        r = probe_module(ser, req, label)
        if r['responded']:
            n_dtc = sum(len(v) for bucket in r['dtcs'].values() for v in bucket.values())
            n_did = len(r['dids'])
            n_m21 = len(r['mode21'])
            print(f"✓ {n_dtc} DTC, {n_did} DID hits, {n_m21} mode21 hits")
        else:
            print("· silent")
        results.append(r)

    send(ser, 'ATSH7DF', 0.8)
    ser.close()

    # Report
    report = [f"TPMS probe — {ts}", ""]
    any_resp = [r for r in results if r['responded']]
    report.append(f"Modules responded: {len(any_resp)} / {len(results)}")
    report.append("")
    for r in results:
        if not r['responded']: continue
        report.append(f"── {r['req']}  {r['label']} ──")
        for bucket in ('stored', 'pending', 'permanent'):
            b = r['dtcs'].get(bucket, {})
            if not b:
                report.append(f"   DTC {bucket:10} : —")
            else:
                for hdr, codes in b.items():
                    report.append(f"   DTC {bucket:10} [{hdr}]: {', '.join(codes) if codes else '(clean)'}")

        if r['dids']:
            report.append("   -- DID responses --")
            for cmd, info in r['dids'].items():
                res = info['result']
                report.append(f"   {cmd}  {info['name']:34}  [{res['hdr']}] len={res['len']} hex={res['hex']}")
                if res.get('ascii', '').strip('.'):
                    report.append(f"           ascii={res['ascii']!r}")
                if 'pressure_hint' in res:
                    report.append(f"           pressure hints: {res['pressure_hint']}")
        if r.get('_did_rejects'):
            report.append(f"   -- DID negative responses: {r['_did_rejects']} --")

        if r['mode21']:
            report.append("   -- Mode 21 responses --")
            for cmd, info in r['mode21'].items():
                report.append(f"   {cmd}  {info['name']:34}  [{info['hdr']}] hex={info['hex']}")
        if r.get('_mode21_rejects'):
            report.append(f"   -- Mode 21 negative: {r['_mode21_rejects']} --")

        if r['notes']:
            for n in r['notes']:
                report.append(f"   note: {n}")
        report.append("")

    report.append("── Silent candidates ──")
    for r in results:
        if not r['responded']:
            report.append(f"   {r['req']}  {r['label']}")

    with open(txt_path, 'w') as f: f.write('\n'.join(report))
    with open(json_path, 'w') as f: json.dump(results, f, indent=2)
    print(f"\n[+] Text : {txt_path}")
    print(f"[+] JSON : {json_path}\n")
    print('\n'.join(report))

if __name__ == '__main__':
    main()
