#!/usr/bin/env python3
"""
Live dashboard for 2011 Yaris (CAN 11b 500k) — MAF-diagnosis-focused.
Colors: green=ok, yellow=watch, red=warning.
CSV logging: pass --log reports/drive_YYYYMMDD_HHMMSS.csv
Ctrl+C to exit cleanly.
"""
import serial, time, sys, os, signal, argparse
from datetime import datetime

# ── ANSI ──
C = {
    'reset':'\033[0m', 'bold':'\033[1m', 'dim':'\033[2m',
    'red':'\033[91m', 'grn':'\033[92m', 'ylw':'\033[93m',
    'blu':'\033[94m', 'mag':'\033[95m', 'cyn':'\033[96m',
    'clr':'\033[2J\033[H', 'hide':'\033[?25l', 'show':'\033[?25h',
}
def c(col, s): return f"{C[col]}{s}{C['reset']}"

# ── ISO-TP aware CAN response parser ──
def parse_can(resp):
    ecus = {}; cf = {}
    for line in resp.splitlines():
        line = line.strip().replace(' ', '')
        if not line or line in ('NODATA','SEARCHING...','OK','?','STOPPED','CANERROR'):
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
        except ValueError:
            continue
    return ecus

def send(ser, cmd, wait=1.0):
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

def read_pid(ser, pid_hex, wait=0.8):
    """Return payload bytes (after mode+pid echo), or None."""
    resp = send(ser, pid_hex, wait)
    ecus = parse_can(resp)
    mode_resp = int(pid_hex[:2], 16) + 0x40
    pid = int(pid_hex[2:], 16)
    for hdr, data in ecus.items():
        if len(data) >= 2 and data[0] == mode_resp and data[1] == pid:
            return data[2:]
    return None

# ── decoders ──
def dec_rpm(d): return (d[0]*256 + d[1]) / 4 if len(d)>=2 else 0
def dec_speed(d): return d[0] if len(d)>=1 else 0
def dec_maf(d): return (d[0]*256 + d[1]) / 100 if len(d)>=2 else 0
def dec_temp(d): return d[0] - 40 if len(d)>=1 else 0
def dec_pct255(d): return d[0] * 100 / 255 if len(d)>=1 else 0
def dec_ft(d): return (d[0] - 128) * 100 / 128 if len(d)>=1 else 0
def dec_o2v(d): return d[0] * 0.005 if len(d)>=1 else 0
def dec_timing(d): return (d[0] - 128) / 2 if len(d)>=1 else 0
def dec_lambda(d): return (d[0]*256 + d[1]) * 2 / 65536 if len(d)>=2 else 0
def dec_cat_t(d): return (d[0]*256 + d[1]) / 10 - 40 if len(d)>=2 else 0
def dec_ctlv(d): return (d[0]*256 + d[1]) / 1000 if len(d)>=2 else 0
def dec_fs(d): return d[0] if len(d)>=1 else 0

def color_val(val, warn_low=None, warn_high=None, crit_low=None, crit_high=None):
    """Pick color based on thresholds."""
    if crit_low is not None and val <= crit_low: return 'red'
    if crit_high is not None and val >= crit_high: return 'red'
    if warn_low is not None and val <= warn_low: return 'ylw'
    if warn_high is not None and val >= warn_high: return 'ylw'
    return 'grn'

def ft_color(ft):
    a = abs(ft)
    if a >= 20: return 'red'
    if a >= 10: return 'ylw'
    return 'grn'

FUEL_SYS = {0:'off',1:'OL-eng',2:'CL',4:'OL-drv',8:'OL-fault',16:'CL-fault'}

def fmt_duration(s):
    h = s // 3600; m = (s % 3600) // 60; sec = s % 60
    return f"{h:d}:{m:02d}:{sec:02d}"

# ── main loop ──
class Dash:
    def __init__(self, port, baud, log_path=None, use_store=True, store_note=None):
        self.ser = serial.Serial(port, baud, timeout=2)
        self.log = None
        if log_path:
            self.log = open(log_path, 'w')
            self.log.write("timestamp,rpm,speed_kmh,maf_gs,stft_b1_pct,ltft_b1_pct,load_pct,throttle_pct,coolant_c,iat_c,o2_b1s2_v,o2wr_lambda,cat_temp_c,timing_deg,ctlmod_v,fuel_sys,mil,dtc_count\n")
            self.log.flush()

        # SQLite store — optional, best-effort (never crash the dashboard)
        self.store = None
        self.session_id = None
        if use_store:
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from yaris.store import Store
                from yaris.vehicle import VIN
                self.store = Store()
                note = store_note or (os.path.basename(log_path) if log_path else "dash")
                self.session_id = self.store.start_session(vin=VIN, source="dash", note=note)
            except Exception as e:
                print(f"[warn] SQLite store unavailable: {e}", file=sys.stderr)
                self.store = None
                self.session_id = None

        self.init_elm()
        self.start_ts = time.time()
        self.counters = {'loops':0, 'errs':0, 'new_dtcs':set()}
        self.last_dtc_count = 0
        self.ltft_hist = []  # (time, value) for trend
        self.maf_hist = []
        self.last = {}  # persist values across partial reads

    def init_elm(self):
        for c_ in ['ATZ','ATE0','ATL0','ATH1','ATS0','ATSP6','ATST32','ATAT1']:
            send(self.ser, c_, 2.0)

    def read_all(self):
        """Read a batch of PIDs. Returns dict."""
        d = {}
        pids_fast = [
            ('rpm','010C',dec_rpm),
            ('speed','010D',dec_speed),
            ('maf','0110',dec_maf),
            ('stft','0106',dec_ft),
            ('ltft','0107',dec_ft),
            ('load','0104',dec_pct255),
            ('throttle','0111',dec_pct255),
            ('coolant','0105',dec_temp),
            ('iat','010F',dec_temp),
            ('timing','010E',dec_timing),
            ('fs','0103',dec_fs),
        ]
        pids_slow = [
            ('o2_b1s2','0115', lambda x: dec_o2v(x)),
            ('o2wr','0134', dec_lambda),
            ('cat_t','013C', dec_cat_t),
            ('ctlv','0142', dec_ctlv),
        ]
        for name, pid, fn in pids_fast:
            p = read_pid(self.ser, pid, 0.7)
            if p is not None:
                try:
                    d[name] = fn(p)
                    self.last[name] = d[name]
                except: self.counters['errs'] += 1
            else:
                self.counters['errs'] += 1
        # slow PIDs every 3rd loop
        if self.counters['loops'] % 3 == 0:
            for name, pid, fn in pids_slow:
                p = read_pid(self.ser, pid, 0.7)
                if p is not None:
                    try:
                        d[name] = fn(p)
                        self.last[name] = d[name]
                    except: self.counters['errs'] += 1
            # MIL/DTC status every 3rd loop
            p = read_pid(self.ser, '0101', 0.7)
            if p and len(p) >= 1:
                d['mil'] = bool(p[0] & 0x80)
                d['dtc_count'] = p[0] & 0x7F
                self.last['mil'] = d['mil']
                self.last['dtc_count'] = d['dtc_count']
        # fill gaps from last-known
        for k, v in self.last.items():
            d.setdefault(k, v)
        return d

    def render(self, d):
        elapsed = int(time.time() - self.start_ts)
        now = datetime.now().strftime("%H:%M:%S")

        buf = [C['clr']]
        buf.append(c('bold', c('cyn', "╔════════════════════════════════════════════════════════════════╗")))
        buf.append(c('bold', c('cyn', f"║  2011 YARIS LIVE DASHBOARD (VIN …{'BL009931'})  {now}  t+{fmt_duration(elapsed)}   ║")))
        buf.append(c('bold', c('cyn', "╠════════════════════════════════════════════════════════════════╣")))

        # Row: RPM + Speed + Load
        rpm = d.get('rpm', 0)
        speed = d.get('speed', 0)
        load = d.get('load', 0)
        throttle = d.get('throttle', 0)
        timing = d.get('timing', 0)
        fs_val = int(d.get('fs', 0))
        fs_lbl = FUEL_SYS.get(fs_val, '?')
        rpm_col = color_val(rpm, warn_low=500, warn_high=5500, crit_low=300, crit_high=6500) if rpm > 0 else 'dim'
        rpm_s = c(rpm_col, f"{rpm:7.0f}")
        speed_s = c('grn', f"{speed:3.0f} km/h")
        load_s = c('grn', f"{load:4.1f}%")
        thr_s = c('grn', f"{throttle:5.1f}%")
        tim_s = c('grn', f"{timing:+5.1f}")
        fs_s = c('grn', fs_lbl)
        buf.append(f"║  RPM {rpm_s}   Speed {speed_s}   Load {load_s}          ║")
        buf.append(f"║  Throttle {thr_s}   Timing {tim_s}°   Fuel sys {fs_s}       ║")

        # Row: MAF (the star of the show)
        maf = d.get('maf', 0)
        maf_col = 'red' if (rpm > 600 and maf < 1.5) or (rpm > 2000 and maf < 10) else ('ylw' if maf < 2.0 and rpm > 700 else 'grn')
        buf.append("╟────────────────────────────────────────────────────────────────╢")
        buf.append(c('bold', f"║  MAF      {c(maf_col, f'{maf:6.2f} g/s')}   "))
        # expected MAF for diagnostic hint
        exp = self.expected_maf(rpm, load)
        if rpm > 400:
            ratio = maf / exp if exp > 0 else 0
            ratio_col = 'red' if ratio < 0.6 else ('ylw' if ratio < 0.85 else 'grn')
            buf[-1] += f"expected ~{c('dim', f'{exp:.1f}')} g/s   ratio {c(ratio_col, f'{ratio:.2f}'):>4} ║"
        else:
            buf[-1] += f"                        (engine off)           ║"

        # Row: fuel trims (the diagnostic smoking gun)
        stft = d.get('stft', 0)
        ltft = d.get('ltft', 0)
        buf.append(c('bold', f"║  STFT B1  {c(ft_color(stft), f'{stft:+6.1f}%')}   "
                              f"LTFT B1  {c(ft_color(ltft), f'{ltft:+6.1f}%')}   "
                              f"sum {c(ft_color(stft+ltft), f'{stft+ltft:+5.1f}%')}                 ║"))

        # O2 sensors
        buf.append("╟────────────────────────────────────────────────────────────────╢")
        o2b = d.get('o2_b1s2', 0)
        o2w = d.get('o2wr', 0)
        o2_col = 'ylw' if o2b > 0.8 or o2b < 0.1 else 'grn'
        buf.append(f"║  O2 post-cat B1S2 {c(o2_col, f'{o2b:4.2f} V')}   Wideband λ {c('grn', f'{o2w:.3f}')}              ║")

        # Temps & voltage
        coolant = d.get('coolant', 0)
        iat = d.get('iat', 0)
        cat_t = d.get('cat_t', 0)
        ctlv = d.get('ctlv', 0)
        cool_col = color_val(coolant, warn_low=70, warn_high=100, crit_low=50, crit_high=108)
        ctlv_col = 'red' if ctlv < 12.5 and rpm > 600 else ('ylw' if ctlv < 13.4 and rpm > 600 else 'grn')
        buf.append("╟────────────────────────────────────────────────────────────────╢")
        buf.append(f"║  Coolant {c(cool_col, f'{coolant:4.0f}°C')}   IAT {c('grn', f'{iat:4.0f}°C')}   Cat {c('grn', f'{cat_t:5.0f}°C')}   Batt {c(ctlv_col, f'{ctlv:5.2f}V')}   ║")

        # MIL / DTC status
        buf.append("╟────────────────────────────────────────────────────────────────╢")
        mil = d.get('mil', None)
        dtcs = d.get('dtc_count', None)
        mil_str = c('red', 'ON ') if mil else (c('grn', 'OFF') if mil is False else c('dim', '...'))
        dtc_str = c('red', f'{dtcs} DTC') if dtcs else (c('grn', '0 DTC') if dtcs == 0 else c('dim', '…'))
        alert = ''
        if dtcs is not None and dtcs > self.last_dtc_count:
            alert = c('red', '  !!! NEW DTC !!!')
        if dtcs is not None: self.last_dtc_count = dtcs
        buf.append(f"║  MIL {mil_str}   Stored {dtc_str}{alert:<32}      ║")

        # Footer
        buf.append("╟────────────────────────────────────────────────────────────────╢")
        buf.append(f"║  loops {self.counters['loops']:5d}   errs {c('ylw' if self.counters['errs'] else 'grn', str(self.counters['errs']))}   log {c('grn', 'on') if self.log else c('dim', 'off')}   {c('dim', 'Ctrl+C to exit'):<28}   ║")
        buf.append(c('bold', c('cyn', "╚════════════════════════════════════════════════════════════════╝")))

        # Diagnostic hint line
        hint = self.hint(d)
        if hint:
            buf.append("  " + hint)

        sys.stdout.write('\n'.join(buf) + '\n')
        sys.stdout.flush()

    def expected_maf(self, rpm, load_pct):
        """Rough expected MAF for 1.3L.
        Physical: (disp/2) * rpm/60 * VE * air_density_g_per_L.
        VE: ~0.30 at idle, scales with load up to ~0.95 WOT.
        NB: OBD 'load' is ECU-computed from MAF itself, so if MAF under-reads,
        load under-reads too. This makes 'expected' here actually *low* when the
        sensor is bad — real underreporting is worse than the ratio suggests."""
        if rpm < 300: return 0
        disp = 1.329  # 1NR-FE actual displacement L
        ve = 0.30 + 0.65 * max(0.0, min(1.0, load_pct / 100.0))
        air_density = 1.20  # g/L at sea level, 20°C
        return max(0.5, (disp / 2.0) * (rpm / 60.0) * ve * air_density)

    def hint(self, d):
        rpm = d.get('rpm', 0)
        maf = d.get('maf', 0)
        ltft = d.get('ltft', 0)
        if rpm < 400: return ""
        notes = []
        if ltft > 15:
            notes.append(c('red', f"LTFT +{ltft:.0f}% → ECU over-fueling, MAF under-reporting"))
        elif ltft > 7:
            notes.append(c('ylw', f"LTFT +{ltft:.0f}% rising"))
        elif ltft < -10:
            notes.append(c('ylw', f"LTFT {ltft:.0f}% → over-reporting MAF or rich injector"))
        if rpm > 1800 and maf < 8:
            notes.append(c('red', f"MAF {maf:.1f} g/s at {rpm:.0f} RPM way low"))
        return "  ".join(notes)

    def log_row(self, d):
        if self.log:
            row = [datetime.now().isoformat(timespec='seconds')]
            for k in ['rpm','speed','maf','stft','ltft','load','throttle','coolant','iat','o2_b1s2','o2wr','cat_t','timing','ctlv','fs']:
                v = d.get(k, '')
                if isinstance(v, float): row.append(f"{v:.3f}")
                else: row.append(str(v))
            row.append('1' if d.get('mil') else ('0' if d.get('mil') is False else ''))
            row.append(str(d.get('dtc_count', '')))
            self.log.write(','.join(row) + '\n')
            self.log.flush()
        # Best-effort SQLite write — swallow all errors so BT drops/etc never break logging
        if self.store and self.session_id is not None:
            try:
                self.store.record_sample(self.session_id, {
                    "timestamp": datetime.now().isoformat(timespec='seconds'),
                    "rpm": d.get('rpm'), "speed_kmh": d.get('speed'),
                    "maf_gs": d.get('maf'),
                    "stft_b1_pct": d.get('stft'), "ltft_b1_pct": d.get('ltft'),
                    "load_pct": d.get('load'), "throttle_pct": d.get('throttle'),
                    "coolant_c": d.get('coolant'), "iat_c": d.get('iat'),
                    "o2_b1s2_v": d.get('o2_b1s2'), "o2wr_lambda": d.get('o2wr'),
                    "cat_temp_c": d.get('cat_t'), "timing_deg": d.get('timing'),
                    "ctlmod_v": d.get('ctlv'), "fuel_sys": d.get('fs'),
                    "mil": 1 if d.get('mil') else (0 if d.get('mil') is False else None),
                    "dtc_count": d.get('dtc_count'),
                })
                if self.counters.get('loops', 0) % 20 == 0:
                    self.store.flush()
            except Exception:
                pass

    def run(self):
        sys.stdout.write(C['hide'])
        try:
            while True:
                self.counters['loops'] += 1
                try:
                    d = self.read_all()
                    self.render(d)
                    self.log_row(d)
                except Exception as e:
                    self.counters['errs'] += 1
                    sys.stdout.write(f"\n[err] {e}\n")
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            sys.stdout.write(C['show'] + C['reset'] + '\n')
            if self.log: self.log.close()
            if self.store and self.session_id is not None:
                try:
                    self.store.end_session(self.session_id)
                    self.store.close()
                except Exception:
                    pass
            self.ser.close()
            print(f"Exited. {self.counters['loops']} loops, {self.counters['errs']} errors.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/rfcomm0')
    ap.add_argument('--baud', type=int, default=38400)
    ap.add_argument('--log', default=None, help='CSV log path (default: reports/drive_TS.csv)')
    ap.add_argument('--nolog', action='store_true')
    args = ap.parse_args()

    log_path = None
    if not args.nolog:
        log_path = args.log or f"./reports/drive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    Dash(args.port, args.baud, log_path).run()

if __name__ == '__main__':
    main()
