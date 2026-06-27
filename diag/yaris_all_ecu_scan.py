#!/usr/bin/env python3
"""
Multi-ECU DTC scanner — walks every reasonable 11-bit CAN address, sends
standard mode-03 "read stored DTCs" to each, logs any responder.

READ-ONLY. Mode 03/07/0A are SAE-defined DTC reads. No writes, no actuator
tests, no security access, no session changes beyond the default.

The broadcast address 0x7DF only wakes ISO-15031-compliant modules (i.e. the
ECM on this car). Other Toyota modules listen on their own physical addresses.
This script walks likely Toyota CAN IDs and notes who talks back.

Usage:
  python3 yaris_all_ecu_scan.py [--port /dev/rfcomm0]
"""
import serial, time, sys, os, argparse, json
from datetime import datetime

REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))

# Module request addresses to try. Response is typically req+8.
# Standard OBD2: 7E0..7E7 map to powertrain (engine, trans). 7E8..7EF responses.
# Toyota-specific additions (non-standard but widely seen on Toyota CAN):
#   750 / 768   ABS / VSC / skid control
#   7B0 / 7B8   airbag (SRS)
#   7C0 / 7C8   body ECU
#   7F0 / 7F1   EPS (electric power steering)
#   784 / 78C   A/C
#   740 / 748   brake
#   7A0 / 7A8   cluster
# We probe the requests; responses come back on req+8 (standard CAN req/resp pairing).
ADDRS = [
    ('7DF', 'Functional broadcast'),
    ('7E0', 'ECM (phys)'),
    ('7E1', 'TCM (phys)'),
    ('7E2', 'phys 0x7E2'),
    ('7E3', 'phys 0x7E3'),
    ('740', 'Brake ECU'),
    ('750', 'ABS / VSC / Skid control'),
    ('768', 'ABS alt'),
    ('784', 'A/C'),
    ('7A0', 'Cluster / combination meter'),
    ('7B0', 'SRS / airbag'),
    ('7C0', 'Body ECU'),
    ('7C4', 'Body alt'),
    ('7F0', 'EPS / steering'),
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
    """Return dict {header: [bytes]} with ISO-TP reassembly."""
    ecus = {}; cf = {}
    for line in resp.splitlines():
        line = line.strip().replace(' ', '')
        if not line: continue
        if any(x in line for x in ('NODATA','SEARCHING','OK','?','STOPPED','ERROR','UNABLE','CAN')):
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

def decode_dtcs(data):
    """Mode 43/47/4A payload: first byte = count, then 2 bytes per code."""
    if len(data) < 1: return []
    n = data[0]
    codes = []
    for i in range(n):
        off = 1 + 2*i
        if off+1 >= len(data): break
        b1, b2 = data[off], data[off+1]
        letter = ['P','C','B','U'][(b1 >> 6) & 0x3]
        codes.append(f"{letter}{(b1>>4)&0x3}{b1&0x0F:X}{(b2>>4)&0x0F:X}{b2&0x0F:X}")
    return codes

def probe(ser, req_id, label):
    """Send mode 03 to a specific request address. Returns dict of findings."""
    result = {'req': req_id, 'label': label, 'responded': False, 'dtcs': {}, 'info': {}}
    # Set header to this request address
    send(ser, f'ATSH{req_id}', 1.0)

    for mode, key in [('03', 'stored'), ('07', 'pending'), ('0A', 'permanent')]:
        resp = send(ser, mode, 3.0)
        ecus = parse_can(resp)
        expected = int(mode, 16) + 0x40
        codes_by_hdr = {}
        for hdr, data in ecus.items():
            if not data: continue
            if data[0] == expected:
                result['responded'] = True
                codes = decode_dtcs(data[1:])
                codes_by_hdr[hdr] = codes
            elif data[0] == 0x7F and len(data) >= 3:
                result['responded'] = True
                result.setdefault('neg_resp', {})[f"{mode}@{hdr}"] = f"NRC 0x{data[2]:02X}"
        if codes_by_hdr:
            result['dtcs'][key] = codes_by_hdr

    # If any responder appeared, also grab VIN (09 02) + ECU name (09 0A)
    if result['responded']:
        for pid, ident in [('0902', 'VIN'), ('090A', 'ECU name')]:
            resp = send(ser, pid, 3.0)
            ecus = parse_can(resp)
            for hdr, data in ecus.items():
                if len(data) >= 3 and data[0] == 0x49:
                    ascii_val = ''.join(chr(c) if 32<=c<127 else '.' for c in data[2:])
                    result['info'].setdefault(ident, {})[hdr] = ascii_val

    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/rfcomm0')
    ap.add_argument('--baud', type=int, default=38400)
    args = ap.parse_args()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = f"{REPORT_DIR}/all_ecu_scan_{ts}.txt"
    json_path = f"{REPORT_DIR}/all_ecu_scan_{ts}.json"

    print(f"═══ Multi-ECU DTC scan — {ts} ═══\n")
    ser = serial.Serial(args.port, args.baud, timeout=3)
    time.sleep(0.2)
    init(ser)

    results = []
    for req_id, label in ADDRS:
        print(f"[→] {req_id}  {label:35}", end='  ', flush=True)
        r = probe(ser, req_id, label)
        if r['responded']:
            n_dtc = sum(len(v) for d in r['dtcs'].values() for v in d.values())
            print(f"✓ responded, {n_dtc} DTC(s)")
        else:
            print("· silent")
        results.append(r)

    # Restore default header for safety
    send(ser, 'ATSH7DF', 1.0)
    ser.close()

    # Build text report
    report = [f"Multi-ECU DTC scan — {ts}", ""]
    any_resp = [r for r in results if r['responded']]
    report.append(f"Modules that responded: {len(any_resp)} / {len(results)}")
    report.append("")
    for r in results:
        if not r['responded']: continue
        report.append(f"── {r['req']}  {r['label']} ──")
        if r.get('info'):
            for k, v in r['info'].items():
                for hdr, val in v.items():
                    report.append(f"   {k:10} [{hdr}] = {val!r}")
        for bucket in ('stored', 'pending', 'permanent'):
            codes_by_hdr = r['dtcs'].get(bucket, {})
            if not codes_by_hdr:
                report.append(f"   {bucket:10} : —")
            else:
                for hdr, codes in codes_by_hdr.items():
                    shown = codes if codes else ['(clean)']
                    report.append(f"   {bucket:10} [{hdr}] : {', '.join(shown)}")
        if r.get('neg_resp'):
            for k, v in r['neg_resp'].items():
                report.append(f"   NRC        {k} : {v}")
        report.append("")

    report.append("── Silent addresses (no response) ──")
    for r in results:
        if not r['responded']:
            report.append(f"   {r['req']}  {r['label']}")

    with open(txt_path, 'w') as f: f.write('\n'.join(report))
    with open(json_path, 'w') as f: json.dump(results, f, indent=2)
    print(f"\n[+] Text : {txt_path}")
    print(f"[+] JSON : {json_path}")
    print()
    print('\n'.join(report))

if __name__ == '__main__':
    main()
