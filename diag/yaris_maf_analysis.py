#!/usr/bin/env python3
"""
Analyze a yaris_live_dash CSV log to produce a MAF-health report.
Computes per-RPM-band expected MAF, actual vs expected ratio, LTFT drift,
and writes a text report + ASCII plot.

Usage:
  python3 yaris_maf_analysis.py [--csv path] [--label tag]
"""
import csv, sys, os, argparse
from collections import defaultdict
from datetime import datetime
from math import sqrt

REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))

# Physical model for 1NR-FE 1.3L (actual displacement 1.329L).
# Expected MAF = (disp/2) * (rpm/60) * VE * air_density_g_per_L
# VE scales from ~0.30 (idle) to ~0.95 (WOT) roughly linearly with load.
DISPLACEMENT_L = 1.329
AIR_DENSITY_G_L = 1.20  # 20°C sea level

def expected_maf(rpm, load_pct):
    if rpm < 300: return 0.0
    ve = 0.30 + 0.65 * max(0.0, min(1.0, load_pct/100.0))
    return (DISPLACEMENT_L/2.0) * (rpm/60.0) * ve * AIR_DENSITY_G_L

def load_csv(path):
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append({
                    't': row['timestamp'],
                    'rpm': float(row['rpm']),
                    'speed': float(row['speed_kmh']),
                    'maf': float(row['maf_gs']),
                    'stft': float(row['stft_b1_pct']),
                    'ltft': float(row['ltft_b1_pct']),
                    'load': float(row['load_pct']),
                    'throttle': float(row['throttle_pct']),
                    'coolant': float(row['coolant_c']),
                    'iat': float(row['iat_c']),
                    'fs': row['fuel_sys'],
                })
            except (ValueError, KeyError): continue
    return rows

def stats(values):
    if not values: return None
    n = len(values)
    mean = sum(values)/n
    var = sum((v-mean)**2 for v in values)/n
    return {'n': n, 'min': min(values), 'max': max(values),
            'mean': mean, 'std': sqrt(var)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=f"{REPORT_DIR}/driveway_test_20260421.csv")
    ap.add_argument('--label', default='baseline')
    args = ap.parse_args()

    rows = load_csv(args.csv)
    if not rows:
        print(f"No data in {args.csv}")
        sys.exit(1)

    # Filter: only engine-running samples (rpm > 400)
    live = [r for r in rows if r['rpm'] > 400]
    print(f"Loaded {len(rows)} rows, {len(live)} with engine running.")

    # Compute actual vs expected for each sample
    for r in live:
        r['expected'] = expected_maf(r['rpm'], r['load'])
        r['ratio'] = r['maf'] / r['expected'] if r['expected'] > 0 else 0

    # RPM bands
    bands = [
        ('Idle',       400,  800),
        ('Low',        800, 1500),
        ('Low-mid',   1500, 2100),
        ('Mid',       2100, 2700),
        ('Mid-high',  2700, 3200),
    ]

    rep = []
    rep.append(f"═══ MAF Health Analysis — {args.label} ═══")
    rep.append(f"Source: {args.csv}")
    rep.append(f"Samples: {len(rows)} total, {len(live)} with engine on")
    rep.append("")

    # Overall trim stats
    ltft = [r['ltft'] for r in live]
    stft = [r['stft'] for r in live]
    ltft_s = stats(ltft); stft_s = stats(stft)
    rep.append("── Fuel Trim (engine-on samples) ──")
    rep.append(f"  STFT B1: mean {stft_s['mean']:+6.2f}%  range [{stft_s['min']:+6.2f}, {stft_s['max']:+6.2f}]  σ={stft_s['std']:.2f}")
    rep.append(f"  LTFT B1: mean {ltft_s['mean']:+6.2f}%  range [{ltft_s['min']:+6.2f}, {ltft_s['max']:+6.2f}]  σ={ltft_s['std']:.2f}")
    rep.append(f"  Sum mean: {(stft_s['mean']+ltft_s['mean']):+6.2f}%   (healthy car: ±5%, this car: well over)")
    rep.append("")

    # Per-band MAF analysis
    rep.append("── MAF Actual vs Expected, by RPM band ──")
    rep.append(f"{'Band':10}  {'RPM range':12}  {'n':>4}  {'MAF act':>8}  {'MAF exp':>8}  {'ratio':>6}  {'STFT':>7}  {'LTFT':>7}")
    rep.append("-"*80)
    band_summary = []
    for name, lo, hi in bands:
        in_band = [r for r in live if lo <= r['rpm'] < hi]
        if not in_band:
            rep.append(f"{name:10}  {lo}-{hi:<6}  {0:4d}  (no samples)")
            continue
        maf_s = stats([r['maf'] for r in in_band])
        exp_s = stats([r['expected'] for r in in_band])
        ratio = maf_s['mean'] / exp_s['mean'] if exp_s['mean'] > 0 else 0
        stft_b = stats([r['stft'] for r in in_band])
        ltft_b = stats([r['ltft'] for r in in_band])
        rep.append(f"{name:10}  {lo}-{hi:<6}  {maf_s['n']:4d}  {maf_s['mean']:6.2f} g/s  {exp_s['mean']:6.2f} g/s  {ratio:5.2f}×  {stft_b['mean']:+6.2f}%  {ltft_b['mean']:+6.2f}%")
        band_summary.append((name, ratio, stft_b['mean'], ltft_b['mean'], maf_s['n']))
    rep.append("")

    # Scatter plot: MAF vs RPM (ASCII)
    rep.append("── MAF vs RPM scatter (ASCII) ──")
    rep.append("   MAF g/s")
    W, H = 60, 18
    max_rpm = max(r['rpm'] for r in live)
    max_maf = max(max(r['maf'] for r in live), max(r['expected'] for r in live)) * 1.1
    grid = [[' ']*W for _ in range(H)]
    # Plot expected as '.'
    for rpm in range(500, int(max_rpm)+1, 50):
        # Use average load to estimate expected; use average load in that rpm band
        in_band = [r for r in live if abs(r['rpm']-rpm) < 100]
        if in_band:
            avg_load = sum(r['load'] for r in in_band)/len(in_band)
        else:
            avg_load = 40
        ex = expected_maf(rpm, avg_load)
        x = int((rpm/max_rpm)*(W-1))
        y = H-1 - int((ex/max_maf)*(H-1))
        if 0 <= x < W and 0 <= y < H and grid[y][x] == ' ':
            grid[y][x] = '.'
    # Plot actual as 'x' or 'o' (darker for overlap)
    for r in live:
        x = int((r['rpm']/max_rpm)*(W-1))
        y = H-1 - int((r['maf']/max_maf)*(H-1))
        if 0 <= x < W and 0 <= y < H:
            grid[y][x] = '#' if grid[y][x] in '#*' else '*'
    # Y-axis labels
    for yi in range(H):
        val = max_maf * (1 - yi/(H-1))
        prefix = f"{val:5.1f} |" if yi % 3 == 0 else "      |"
        rep.append(prefix + ''.join(grid[yi]))
    rep.append("      +" + "-"*W)
    rep.append("       0" + f"{max_rpm:>{W-5}.0f} RPM")
    rep.append("   legend: * = actual MAF reading    . = expected (physical model)")
    rep.append("")

    # Ratio over time (LTFT saturation check)
    rep.append("── LTFT over time (check for saturation / drift) ──")
    times = [i for i,_ in enumerate(live)]
    if times:
        step = max(1, len(live)//40)
        for i in range(0, len(live), step):
            r = live[i]
            bar_len = max(0, int(r['ltft'] * 1.5))
            bar = '▮' * min(bar_len, 40)
            rep.append(f"  t+{i:4d}  rpm {r['rpm']:4.0f}  ltft {r['ltft']:+6.2f}%  |{bar}")
    rep.append("")

    # Diagnosis
    rep.append("── Diagnosis ──")
    ratios = [r['ratio'] for r in live if r['ratio'] > 0]
    if ratios:
        avg_ratio = sum(ratios)/len(ratios)
        ratio_s = stats(ratios)
        rep.append(f"  Overall MAF ratio: {avg_ratio:.2f}× expected (σ={ratio_s['std']:.2f})")
        if avg_ratio < 0.6 and ratio_s['std'] < 0.15:
            rep.append(f"  → Proportional under-read across RPM range (σ low). Signature of a CONTAMINATED element.")
        elif avg_ratio < 0.6:
            rep.append(f"  → Under-read with high variance — could be intermittent sensor or wiring.")
        elif avg_ratio > 1.4:
            rep.append(f"  → Over-reading — calibration or gain issue.")
        else:
            rep.append(f"  → Ratio in healthy range.")

    # Write
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(REPORT_DIR, exist_ok=True)
    out_path = f"{REPORT_DIR}/maf_analysis_{args.label}_{ts}.txt"
    with open(out_path, 'w') as f: f.write('\n'.join(rep))
    print(f"[+] Written: {out_path}\n")
    print('\n'.join(rep))

if __name__ == '__main__':
    main()
