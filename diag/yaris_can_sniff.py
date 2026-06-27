#!/usr/bin/env python3
"""
Passive CAN bus sniffer via ELM327 ATMA (Monitor All).
READ-ONLY: enables ELM's passive monitor mode, receives frames, never transmits.
Produces: (a) per-arbitration-ID frame count + rate, (b) example payloads, (c) raw log.

Known limitation: ELM327 @ 38400 BT serial CANNOT keep up with a busy 500k CAN bus.
Expect buffer overruns ("BUFFER FULL" from ELM) and dropped frames. We still get
useful info: a census of which IDs are actually broadcasting + sample payloads.

Usage:
  python3 yaris_can_sniff.py [--dur 30] [--port /dev/rfcomm0]
"""
import serial, time, sys, os, argparse
from collections import defaultdict
from datetime import datetime

REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))

def send(ser, cmd, wait=1.5):
    ser.reset_input_buffer()
    ser.write(cmd.encode() + b'\r')
    t0 = time.time(); buf = b''
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if buf.endswith(b'>'): break
        time.sleep(0.03)
    return buf.decode('ascii', 'replace').replace('\r','\n').replace('>','').strip()

def init_monitor(ser, can_filter=None, can_mask=None, can_rx_addr=None, silent=False):
    """Set up ELM327 for passive monitoring. Never sends a request, just listens.

    Optional filters (massively reduce buffer overruns on busy 500k buses):
      can_rx_addr : str   — ATCRA hhh, receive ONLY this arbitration ID
      can_filter  : str   — ATCF hhh, receive pattern (combined with mask)
      can_mask    : str   — ATCM hhh, bits that must match
      silent      : bool  — ATCSM1, silent monitoring (don't ACK the bus)
    """
    steps = [
        ('ATZ',     'Reset'),
        ('ATE0',    'Echo off'),
        ('ATL0',    'Linefeed off'),
        ('ATH1',    'Headers on (show arb ID)'),
        ('ATS1',    'Spaces on (readable)'),
        ('ATSP6',   'Protocol: ISO 15765 CAN 11b 500k'),
        ('ATCAF0',  'Formatting OFF (raw CAN frames, no ISO-TP assembly)'),
        ('ATAL',    'Allow long messages'),
    ]
    # Optional filter steps BEFORE monitoring
    if silent:
        steps.append(('ATCSM1', 'Silent monitoring (no ACK)'))
    if can_rx_addr:
        steps.append((f'ATCRA{can_rx_addr.upper()}',
                      f'Receive only arb ID {can_rx_addr.upper()}'))
    if can_mask:
        steps.append((f'ATCM{can_mask.upper()}', f'CAN mask {can_mask.upper()}'))
    if can_filter:
        steps.append((f'ATCF{can_filter.upper()}', f'CAN filter {can_filter.upper()}'))

    for cmd, note in steps:
        r = send(ser, cmd, 1.5)
        print(f"  {cmd:10}  {note:38}  -> {r[:40]!r}")

def monitor(ser, duration):
    """Enter ATMA and read frames for duration seconds. Returns list of raw lines."""
    print(f"\n[*] Entering passive monitor mode for {duration}s. No frames transmitted.")
    ser.reset_input_buffer()
    ser.write(b'ATMA\r')
    t0 = time.time()
    buf = b''
    lines = []
    last_report = t0
    try:
        while time.time() - t0 < duration:
            n = ser.in_waiting
            if n:
                chunk = ser.read(n)
                buf += chunk
                # Split on CR
                while b'\r' in buf:
                    line, buf = buf.split(b'\r', 1)
                    s = line.decode('ascii', 'replace').strip()
                    if s:
                        lines.append((time.time() - t0, s))
            # Periodic progress
            if time.time() - last_report > 2.0:
                print(f"  [{time.time()-t0:5.1f}s] {len(lines)} frames captured")
                last_report = time.time()
            time.sleep(0.01)
    finally:
        # Exit ATMA cleanly — any char sent stops the monitor; we send ESC/newline
        ser.write(b'\r')
        time.sleep(0.3)
        ser.reset_input_buffer()
    return lines

def summarize(lines):
    """Group by CAN ID, compute rates, sample payloads."""
    by_id = defaultdict(list)  # id -> [(t, data), ...]
    skipped = 0
    for t, s in lines:
        parts = s.split()
        # ELM327 format: "<arb_id> <D0> <D1> ..." (hex, space-separated)
        # "BUFFER FULL" / "CAN ERROR" / "STOPPED" are control lines
        if not parts or not all(all(c in '0123456789ABCDEFabcdef' for c in p) for p in parts):
            skipped += 1
            continue
        if len(parts) < 2:
            continue
        arb = parts[0].upper()
        # Standard 11-bit IDs are 3 hex chars
        if len(arb) not in (3, 8):
            skipped += 1
            continue
        data = ' '.join(p.upper() for p in parts[1:])
        by_id[arb].append((t, data))
    return by_id, skipped

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/rfcomm0')
    ap.add_argument('--baud', type=int, default=38400)
    ap.add_argument('--dur', type=float, default=15.0)
    ap.add_argument('--rx', default=None,
                    help='Only receive this CAN arb ID (e.g. 7E8). Uses ATCRA.')
    ap.add_argument('--filter', default=None,
                    help='ATCF filter pattern (3-char hex). Pair with --mask.')
    ap.add_argument('--mask', default=None,
                    help='ATCM mask (3-char hex). Pair with --filter.')
    ap.add_argument('--silent', action='store_true',
                    help='ATCSM1 — receive without acknowledging bus.')
    args = ap.parse_args()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    raw_path = f"{REPORT_DIR}/can_sniff_raw_{ts}.txt"
    sum_path = f"{REPORT_DIR}/can_sniff_summary_{ts}.txt"

    print(f"═══ Passive CAN sniff — {ts} ═══\n")
    ser = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.2)
    init_monitor(ser, can_filter=args.filter, can_mask=args.mask,
                 can_rx_addr=args.rx, silent=args.silent)
    lines = monitor(ser, args.dur)
    ser.close()

    print(f"\n[+] Captured {len(lines)} lines in {args.dur}s")
    with open(raw_path, 'w') as f:
        for t, s in lines:
            f.write(f"{t:7.3f}  {s}\n")
    print(f"[+] Raw: {raw_path}")

    by_id, skipped = summarize(lines)
    print(f"[+] {len(by_id)} distinct CAN IDs, {skipped} control/malformed lines")

    # Sort by frame count, descending
    ranked = sorted(by_id.items(), key=lambda kv: -len(kv[1]))

    report = []
    report.append(f"CAN Bus Summary — {ts} — {args.dur}s window")
    report.append(f"Distinct IDs: {len(by_id)}   Total frames: {sum(len(v) for v in by_id.values())}")
    report.append("")
    report.append(f"{'ARB':>5}  {'count':>6}  {'Hz':>6}  {'sample payload (D0..D7)':38}  {'guess'}")
    report.append("-" * 88)
    for arb, samples in ranked:
        count = len(samples)
        rate = count / args.dur if args.dur > 0 else 0
        sample = samples[len(samples)//2][1] if samples else ''
        guess = guess_id(arb)
        report.append(f"{arb:>5}  {count:6d}  {rate:6.1f}  {sample:38}  {guess}")

    with open(sum_path, 'w') as f:
        f.write('\n'.join(report))
    print(f"[+] Summary: {sum_path}")
    print('\n'.join(report))

def guess_id(arb):
    """Rough guesses for common Toyota CAN IDs. Informational only."""
    a = arb.upper()
    hints = {
        '0B4': 'wheel speeds / VSC',
        '0B6': 'VSC status',
        '0C4': 'yaw rate / long accel',
        '0C6': 'steering angle',
        '1C4': 'brake pressure',
        '1C6': 'ABS / VSC',
        '1D2': 'engine RPM / throttle',
        '1D3': 'engine status',
        '224': 'engine data',
        '228': 'engine live',
        '262': 'transmission',
        '2C1': 'body control',
        '2C4': 'cluster / instrument',
        '3B0': 'cluster',
        '3B1': 'cluster',
        '3B7': 'cluster',
        '3B8': 'cluster',
        '3BB': 'cluster',
        '3BC': 'cluster',
        '423': 'steering / body',
        '620': 'body / door',
        '630': 'body',
        '7E0': 'ECM request',
        '7E1': 'TCM request',
        '7E8': 'ECM response',
        '7E9': 'TCM/ABS response',
        '7EA': 'ECU response',
    }
    return hints.get(a, '')

if __name__ == '__main__':
    main()
