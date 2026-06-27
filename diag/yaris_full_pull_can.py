#!/usr/bin/env python3
"""Comprehensive OBD2 + Toyota enhanced pull for 2011 Yaris (CAN 11b 500k)."""
import serial, time, json, os
from datetime import datetime

PORT = "/dev/rfcomm0"
BAUD = 38400
REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

def send(ser, cmd, wait=3.0):
    ser.reset_input_buffer()
    ser.write(cmd.encode() + b'\r')
    t0 = time.time(); buf = b''
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if buf.endswith(b'>'): break
        time.sleep(0.04)
    txt = buf.decode('ascii', 'replace')
    return txt.replace('\r', '\n').replace('>', '').strip()

# Parse a response into per-ECU byte streams, handling ISO-TP multi-frame
def parse_can(resp):
    """Return dict {header: [bytes]} reassembling multi-frame ISO-TP."""
    ecus = {}  # header -> assembled bytes
    cf = {}    # header -> expected len for CF accumulation
    for line in resp.splitlines():
        line = line.strip()
        if not line or line in ('SEARCHING...', 'NO DATA', 'OK', '?', 'STOPPED', 'CAN ERROR', 'BUS INIT: ERROR', 'UNABLE TO CONNECT'):
            continue
        line = line.replace(' ', '')
        if len(line) < 6: continue
        hdr = line[:3]
        pci = line[3:4]
        try:
            first = int(line[3:5], 16)
        except: continue
        if pci == '0':  # Single frame: 0 L DD..
            L = first & 0x0F
            data = bytes.fromhex(line[5:5+2*L])
            ecus.setdefault(hdr, b'')
            ecus[hdr] += data
        elif pci == '1':  # First frame: 1 L LLL DD..
            L = int(line[3:7], 16) & 0x0FFF
            data = bytes.fromhex(line[7:])
            ecus[hdr] = data
            cf[hdr] = L - len(data)
        elif pci == '2':  # Consecutive frame: 2 N DD..
            data = bytes.fromhex(line[5:])
            if hdr in ecus:
                need = cf.get(hdr, len(data))
                ecus[hdr] += data[:need]
                cf[hdr] = max(0, need - len(data))
    return ecus

def init(ser):
    out = []
    for c in ['ATZ','ATE0','ATL0','ATH1','ATS0','ATCAF1','ATSP6','ATST96','ATAT1']:
        out.append(f"{c}: {send(ser, c, 2.0)!r}")
    return out

def mode01_supported(ser):
    """Walk 0100, 0120, 0140... to get all supported PIDs."""
    supported = []
    for base in range(0x00, 0xE0, 0x20):
        cmd = f"01{base:02X}"
        resp = send(ser, cmd, 3.0)
        ecus = parse_can(resp)
        any_next = False
        for hdr, data in ecus.items():
            if len(data) < 6: continue
            if data[0] != 0x41 or data[1] != base: continue
            mask = int.from_bytes(data[2:6], 'big')
            for i in range(32):
                if mask & (1 << (31 - i)):
                    pid = base + 1 + i
                    if pid == base + 0x20: any_next = True
                    supported.append(pid)
        if not any_next: break
    return sorted(set(supported))

def decode_pid(pid, data):
    """Decode common PIDs. data is raw bytes after mode+pid echo."""
    if not data: return None
    A = data[0] if len(data)>0 else 0
    B = data[1] if len(data)>1 else 0
    C = data[2] if len(data)>2 else 0
    D = data[3] if len(data)>3 else 0
    dec = {
        0x01: lambda: ("MIL/DTC/Readiness", f"MIL={'ON' if A&0x80 else 'OFF'}, DTCs={A&0x7F}, B={B:02X} C={C:02X} D={D:02X}"),
        0x03: lambda: ("Fuel sys status", f"FS1={A:02X} FS2={B:02X}"),
        0x04: lambda: ("Calc load %", f"{A*100/255:.1f}%"),
        0x05: lambda: ("Coolant °C", f"{A-40}"),
        0x06: lambda: ("ST FT B1 %", f"{(A-128)*100/128:.1f}"),
        0x07: lambda: ("LT FT B1 %", f"{(A-128)*100/128:.1f}"),
        0x08: lambda: ("ST FT B2 %", f"{(A-128)*100/128:.1f}"),
        0x09: lambda: ("LT FT B2 %", f"{(A-128)*100/128:.1f}"),
        0x0A: lambda: ("Fuel press kPa", f"{A*3}"),
        0x0B: lambda: ("MAP kPa", f"{A}"),
        0x0C: lambda: ("RPM", f"{(A*256+B)/4:.0f}"),
        0x0D: lambda: ("Speed km/h", f"{A}"),
        0x0E: lambda: ("Timing adv °", f"{(A-128)/2}"),
        0x0F: lambda: ("IAT °C", f"{A-40}"),
        0x10: lambda: ("MAF g/s", f"{(A*256+B)/100:.2f}"),
        0x11: lambda: ("Throttle %", f"{A*100/255:.1f}"),
        0x13: lambda: ("O2 sensors present", f"{A:08b}"),
        0x14: lambda: ("O2 B1S1 V/STFT", f"V={A*0.005:.3f} FT={(B-128)*100/128:.1f}%"),
        0x15: lambda: ("O2 B1S2 V/STFT", f"V={A*0.005:.3f} FT={(B-128)*100/128:.1f}%"),
        0x1C: lambda: ("OBD std", f"{A}"),
        0x1F: lambda: ("Runtime since start s", f"{A*256+B}"),
        0x21: lambda: ("Dist MIL on km", f"{A*256+B}"),
        0x2E: lambda: ("Cmd evap purge %", f"{A*100/255:.1f}"),
        0x2F: lambda: ("Fuel level %", f"{A*100/255:.1f}"),
        0x30: lambda: ("Warm-ups since clear", f"{A}"),
        0x31: lambda: ("Dist since clear km", f"{A*256+B}"),
        0x33: lambda: ("Baro kPa", f"{A}"),
        0x34: lambda: ("O2WR B1S1 λ/mA", f"λ={(A*256+B)*2/65536:.3f} I={(C*256+D-32768)/256:.2f}mA"),
        0x3C: lambda: ("Cat temp B1S1 °C", f"{(A*256+B)/10 - 40:.1f}"),
        0x42: lambda: ("CtlMod V", f"{(A*256+B)/1000:.3f}V"),
        0x43: lambda: ("Abs load %", f"{(A*256+B)*100/255:.1f}"),
        0x44: lambda: ("Cmd equiv ratio", f"{(A*256+B)*2/65536:.4f}"),
        0x45: lambda: ("Rel throttle %", f"{A*100/255:.1f}"),
        0x46: lambda: ("Ambient °C", f"{A-40}"),
        0x47: lambda: ("Abs throttle B %", f"{A*100/255:.1f}"),
        0x49: lambda: ("Accel pos D %", f"{A*100/255:.1f}"),
        0x4A: lambda: ("Accel pos E %", f"{A*100/255:.1f}"),
        0x4C: lambda: ("Cmd throttle %", f"{A*100/255:.1f}"),
        0x51: lambda: ("Fuel type", f"{A}"),
    }
    fn = dec.get(pid)
    return fn() if fn else (f"PID {pid:02X}", data.hex())

def decode_dtcs(data):
    """Mode 03/07/0A payload: first byte = count, then pairs of 2 bytes per DTC."""
    if len(data) < 1: return []
    n = data[0]
    codes = []
    for i in range(n):
        off = 1 + 2*i
        if off+1 >= len(data): break
        b1, b2 = data[off], data[off+1]
        letter = ['P','C','B','U'][(b1 >> 6) & 0x3]
        d1 = (b1 >> 4) & 0x3
        d2 = b1 & 0x0F
        d3 = (b2 >> 4) & 0x0F
        d4 = b2 & 0x0F
        codes.append(f"{letter}{d1}{d2:X}{d3:X}{d4:X}")
    return codes

def main():
    report = {'timestamp': TS, 'port': PORT, 'sections': {}}
    lines = [f"═══ 2011 Yaris Comprehensive OBD2 Pull — {TS} ═══\n"]

    ser = serial.Serial(PORT, BAUD, timeout=4)
    time.sleep(0.2)

    # ── Init ──
    lines.append("── Init ──")
    init_out = init(ser)
    for l in init_out: lines.append(f"  {l}")
    report['sections']['init'] = init_out

    # ── Adapter info ──
    rv = send(ser, 'ATRV', 1.5)
    dpn = send(ser, 'ATDPN', 1.5)
    dp = send(ser, 'ATDP', 1.5)
    adapter_i = send(ser, 'ATI', 1.5)
    lines += [f"\n── Adapter ──", f"  ID      : {adapter_i}", f"  Proto#  : {dpn}", f"  Proto   : {dp}", f"  OBD V   : {rv}"]
    report['sections']['adapter'] = {'id': adapter_i, 'proto_n': dpn, 'proto': dp, 'vbatt_obd': rv}

    # ── Supported PIDs ──
    lines.append("\n── Supported Mode 01 PIDs ──")
    sup = mode01_supported(ser)
    lines.append(f"  {len(sup)} PIDs: " + ", ".join(f"{p:02X}" for p in sup))
    report['sections']['supported_pids'] = [f"{p:02X}" for p in sup]

    # ── All live PIDs ──
    lines.append("\n── Live Mode 01 data ──")
    live = {}
    for pid in sup:
        resp = send(ser, f"01{pid:02X}", 2.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if len(data) < 2 or data[0] != 0x41 or data[1] != pid: continue
            payload = data[2:]
            name, val = decode_pid(pid, payload)
            key = f"{hdr}/01{pid:02X}"
            live[key] = {'name': name, 'value': val, 'raw': payload.hex()}
            lines.append(f"  [{hdr}] 01{pid:02X} {name:22} = {val}   ({payload.hex()})")
    report['sections']['live'] = live

    # ── DTCs ──
    lines.append("\n── DTCs ──")
    dtc = {}
    for mode, label in [('03','stored'), ('07','pending'), ('0A','permanent')]:
        resp = send(ser, mode, 4.0)
        ecus = parse_can(resp)
        found = {}
        for hdr, data in ecus.items():
            if not data: continue
            expected = int(mode, 16) + 0x40
            # Mode 03/07/0A: first byte is 0x43/0x47/0x4A
            if data[0] == expected:
                codes = decode_dtcs(data[1:])
                found[hdr] = codes
        dtc[label] = found
        lines.append(f"  {label:10}: {found if found else 'none'}")
    report['sections']['dtcs'] = dtc

    # ── Freeze frame (mode 02) ──
    lines.append("\n── Freeze Frame (mode 02) ──")
    ff = {}
    for pid in [0x02, 0x04, 0x05, 0x0C, 0x0D, 0x0F, 0x10, 0x11, 0x03]:
        resp = send(ser, f"02{pid:02X}00", 2.5)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if len(data) < 3 or data[0] != 0x42 or data[1] != pid: continue
            payload = data[3:] if len(data) > 3 else b''  # skip frame# byte
            if pid == 0x02:
                # DTC that caused freeze
                codes = decode_dtcs(bytes([1]) + payload[:2]) if len(payload) >= 2 else []
                ff[f"02{pid:02X}"] = {'name': 'DTC that caused freeze', 'value': codes, 'raw': payload.hex()}
                lines.append(f"  02{pid:02X} DTC-caused-freeze     = {codes} ({payload.hex()})")
            else:
                name, val = decode_pid(pid, payload)
                ff[f"02{pid:02X}"] = {'name': name, 'value': val, 'raw': payload.hex()}
                lines.append(f"  02{pid:02X} {name:22} = {val}   ({payload.hex()})")
    report['sections']['freeze_frame'] = ff

    # ── Mode 09 identifiers ──
    lines.append("\n── Mode 09 Identifiers ──")
    mode9 = {}
    for pid, name in [(0x00,'Supported'),(0x02,'VIN'),(0x04,'CalID'),(0x06,'CVN'),(0x08,'IPT'),(0x0A,'ECU name'),(0x0B,'IUPR')]:
        resp = send(ser, f"09{pid:02X}", 4.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if len(data) < 3 or data[0] != 0x49 or data[1] != pid: continue
            # 3rd byte is usually item-count; payload after
            payload = data[2:]
            ascii_val = ''.join(chr(c) if 32<=c<127 else '.' for c in payload)
            mode9[f"09{pid:02X}"] = {'name': name, 'hex': payload.hex(), 'ascii': ascii_val}
            lines.append(f"  [{hdr}] 09{pid:02X} {name:12} hex={payload.hex()}")
            lines.append(f"                     ascii={ascii_val!r}")
    report['sections']['mode9'] = mode9

    # ── Readiness (mode 01 PID 01 bit detail) ──
    lines.append("\n── Readiness Monitors (PID 01 bytes B/C/D) ──")
    resp = send(ser, '0101', 2.0)
    ecus = parse_can(resp)
    readiness = {}
    for hdr, data in ecus.items():
        if len(data) >= 6 and data[0] == 0x41 and data[1] == 0x01:
            A, B, C, D = data[2], data[3], data[4], data[5]
            r = {
                'MIL': bool(A & 0x80), 'DTC_count': A & 0x7F,
                'Misfire_sup': bool(B & 0x01), 'Misfire_rdy_notdone': bool(B & 0x10),
                'Fuel_sup': bool(B & 0x02), 'Fuel_rdy_notdone': bool(B & 0x20),
                'Comp_sup': bool(B & 0x04), 'Comp_rdy_notdone': bool(B & 0x40),
                'Cat_sup': bool(C & 0x01), 'Cat_rdy_notdone': bool(D & 0x01),
                'HtdCat_sup': bool(C & 0x02), 'HtdCat_rdy_notdone': bool(D & 0x02),
                'Evap_sup': bool(C & 0x04), 'Evap_rdy_notdone': bool(D & 0x04),
                'SecAir_sup': bool(C & 0x08), 'SecAir_rdy_notdone': bool(D & 0x08),
                'AC_sup': bool(C & 0x10), 'AC_rdy_notdone': bool(D & 0x10),
                'O2_sup': bool(C & 0x20), 'O2_rdy_notdone': bool(D & 0x20),
                'O2Htr_sup': bool(C & 0x40), 'O2Htr_rdy_notdone': bool(D & 0x40),
                'EGR_sup': bool(C & 0x80), 'EGR_rdy_notdone': bool(D & 0x80),
            }
            readiness[hdr] = r
            for k, v in r.items():
                lines.append(f"  [{hdr}] {k:26} = {v}")
    report['sections']['readiness'] = readiness

    # ── Mode 06 on-board monitor results (just list supported MID 00) ──
    lines.append("\n── Mode 06 Supported MIDs (0600) ──")
    resp = send(ser, '0600', 3.0)
    ecus = parse_can(resp)
    m06 = {}
    for hdr, data in ecus.items():
        if len(data) >= 6 and data[0] == 0x46 and data[1] == 0x00:
            m06[hdr] = data[2:].hex()
            lines.append(f"  [{hdr}] 0600 mask = {data[2:].hex()}")
    report['sections']['mode06_00'] = m06

    # ── Toyota Enhanced mode 21 (common PIDs) ──
    lines.append("\n── Toyota Mode 21 Enhanced (probe a few) ──")
    tenh = {}
    for pid in [0x01, 0x02, 0x03, 0x08, 0x09, 0x0A, 0x10, 0x15, 0x20, 0x30]:
        resp = send(ser, f"21{pid:02X}", 3.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if data and (data[0] == 0x61 or data[0] == 0x7F):
                tenh[f"21{pid:02X}"] = {'header': hdr, 'raw': data.hex()}
                lines.append(f"  [{hdr}] 21{pid:02X} -> {data.hex()}")
                break
    report['sections']['toyota_mode21'] = tenh

    # ── UDS 22 (alt Toyota ECU data identifier read) ──
    lines.append("\n── UDS 22 Read-DID (probe) ──")
    uds22 = {}
    for did in [0xF190, 0xF18C, 0xF181, 0xF195, 0xF1A0]:
        cmd = f"22{did:04X}"
        resp = send(ser, cmd, 3.0)
        ecus = parse_can(resp)
        for hdr, data in ecus.items():
            if data and (data[0] == 0x62 or data[0] == 0x7F):
                uds22[cmd] = {'header': hdr, 'raw': data.hex()}
                ascii_val = ''.join(chr(c) if 32<=c<127 else '.' for c in data[3:]) if data[0]==0x62 else ''
                lines.append(f"  [{hdr}] {cmd} -> {data.hex()}  ascii={ascii_val!r}")
                break
    report['sections']['uds_22'] = uds22

    ser.close()

    txt_path = os.path.join(REPORT_DIR, f"yaris_full_pull_{TS}.txt")
    json_path = os.path.join(REPORT_DIR, f"yaris_full_pull_{TS}.json")
    with open(txt_path, 'w') as f: f.write('\n'.join(lines))
    with open(json_path, 'w') as f: json.dump(report, f, indent=2)
    print(f"[+] Wrote {txt_path}")
    print(f"[+] Wrote {json_path}")
    print("\n" + '\n'.join(lines))

if __name__ == '__main__':
    main()
