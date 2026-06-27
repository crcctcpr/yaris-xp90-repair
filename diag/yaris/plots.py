"""Matplotlib PNG exports for diagnostic reports.

Optional dependency — if matplotlib isn't available, functions return None
and callers should fall back to their ASCII/text reports.

Uses the non-interactive Agg backend (no display needed).

Usage:
  python3 -m yaris.plots --csv reports/drive_live_*.csv
  python3 -m yaris.plots --compare <before.csv> <after.csv>
  python3 -m yaris.plots --history 30
"""
import argparse
import csv
import os
from datetime import datetime

from .vehicle import REPORT_DIR, expected_maf

# Optional matplotlib — keep the rest of the toolkit usable without it
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


STYLE = {
    "bg": "#0d1117",
    "fg": "#c9d1d9",
    "grid": "#30363d",
    "ok": "#3fb950",
    "warn": "#d29922",
    "err": "#f85149",
    "blue": "#58a6ff",
    "maf_expected": "#d29922",
    "maf_actual": "#58a6ff",
}


def _style_ax(ax):
    ax.set_facecolor(STYLE["bg"])
    ax.tick_params(colors=STYLE["fg"])
    for spine in ax.spines.values():
        spine.set_color(STYLE["grid"])
    ax.xaxis.label.set_color(STYLE["fg"])
    ax.yaxis.label.set_color(STYLE["fg"])
    ax.title.set_color(STYLE["fg"])
    ax.grid(True, color=STYLE["grid"], linewidth=0.5, alpha=0.5)


def _load_csv(path: str) -> list[dict]:
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "t":       r.get("timestamp", ""),
                    "rpm":     float(r.get("rpm") or 0),
                    "speed":   float(r.get("speed_kmh") or 0),
                    "maf":     float(r.get("maf_gs") or 0),
                    "stft":    float(r.get("stft_b1_pct") or 0),
                    "ltft":    float(r.get("ltft_b1_pct") or 0),
                    "load":    float(r.get("load_pct") or 0),
                    "throttle":float(r.get("throttle_pct") or 0),
                    "coolant": float(r.get("coolant_c") or 0),
                })
            except (ValueError, TypeError):
                continue
    return [r for r in rows if r["rpm"] > 0]


def plot_maf_scatter(csv_path: str, out_path: str | None = None) -> str | None:
    """MAF actual vs RPM scatter, with expected curve overlay."""
    if not HAS_MPL:
        return None
    rows = _load_csv(csv_path)
    if not rows:
        return None
    live = [r for r in rows if r["rpm"] > 400]
    rpm = [r["rpm"] for r in live]
    maf = [r["maf"] for r in live]
    # Expected curve using throttle mode
    for r in live:
        r["expected"] = expected_maf(r["rpm"], throttle_pct=r["throttle"], mode="throttle")
    rpm_sorted = sorted(live, key=lambda r: r["rpm"])
    exp_x = [r["rpm"] for r in rpm_sorted]
    exp_y = [r["expected"] for r in rpm_sorted]

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=STYLE["bg"])
    _style_ax(ax)
    # Scatter of actuals
    ax.scatter(rpm, maf, c=STYLE["maf_actual"], s=8, alpha=0.7,
               label="actual MAF")
    ax.plot(exp_x, exp_y, color=STYLE["maf_expected"], linewidth=1.4,
            linestyle="--", alpha=0.7, label="expected (throttle model)")
    ax.set_xlabel("RPM")
    ax.set_ylabel("MAF (g/s)")
    ax.set_title(f"MAF vs RPM — {os.path.basename(csv_path)}")
    leg = ax.legend(facecolor=STYLE["bg"], edgecolor=STYLE["grid"])
    for t in leg.get_texts():
        t.set_color(STYLE["fg"])

    out = out_path or csv_path.replace(".csv", "_maf.png")
    fig.savefig(out, dpi=120, bbox_inches="tight",
                facecolor=STYLE["bg"])
    plt.close(fig)
    return out


def plot_trim_over_time(csv_path: str, out_path: str | None = None) -> str | None:
    """STFT + LTFT over time — shows saturation pattern."""
    if not HAS_MPL:
        return None
    rows = _load_csv(csv_path)
    if not rows:
        return None
    idx = list(range(len(rows)))
    stft = [r["stft"] for r in rows]
    ltft = [r["ltft"] for r in rows]
    rpm = [r["rpm"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                    facecolor=STYLE["bg"])
    _style_ax(ax1); _style_ax(ax2)

    ax1.plot(idx, stft, color=STYLE["blue"], linewidth=0.8, label="STFT B1")
    ax1.plot(idx, ltft, color=STYLE["err"], linewidth=1.2, label="LTFT B1")
    ax1.axhspan(-7, 7, color=STYLE["ok"], alpha=0.08, label="healthy ±7%")
    ax1.axhline(25, color=STYLE["err"], linestyle="--", alpha=0.5,
                label="P0171 threshold +25%")
    ax1.axhline(-25, color=STYLE["err"], linestyle="--", alpha=0.5)
    ax1.set_ylabel("Fuel trim (%)")
    ax1.set_title(f"Fuel trims over time — {os.path.basename(csv_path)}")
    leg = ax1.legend(facecolor=STYLE["bg"], edgecolor=STYLE["grid"], loc="best")
    for t in leg.get_texts():
        t.set_color(STYLE["fg"])

    ax2.plot(idx, rpm, color=STYLE["ok"], linewidth=0.8)
    ax2.set_ylabel("RPM")
    ax2.set_xlabel("sample #")

    out = out_path or csv_path.replace(".csv", "_trims.png")
    fig.savefig(out, dpi=120, bbox_inches="tight",
                facecolor=STYLE["bg"])
    plt.close(fig)
    return out


def plot_compare(before_path: str, after_path: str,
                 out_path: str | None = None) -> str | None:
    """Before/after comparison chart — MAF ratio distribution + LTFT overlay."""
    if not HAS_MPL:
        return None
    b = _load_csv(before_path)
    a = _load_csv(after_path)
    if not (b and a):
        return None

    # Compute ratios
    def ratios(rows):
        out = []
        for r in rows:
            exp = expected_maf(r["rpm"], throttle_pct=r["throttle"], mode="throttle")
            if exp > 0:
                out.append(r["maf"] / exp)
        return out

    b_ratios = ratios(b)
    a_ratios = ratios(a)
    b_ltft = [r["ltft"] for r in b]
    a_ltft = [r["ltft"] for r in a]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor=STYLE["bg"])
    _style_ax(ax1); _style_ax(ax2)

    # Histograms of MAF ratio
    bins = [i / 20 for i in range(31)]  # 0 .. 1.5
    ax1.hist(b_ratios, bins=bins, alpha=0.55, color=STYLE["err"], label="before")
    ax1.hist(a_ratios, bins=bins, alpha=0.55, color=STYLE["ok"],  label="after")
    ax1.axvline(0.85, color=STYLE["warn"], linestyle="--", alpha=0.7,
                label="healthy ≥0.85×")
    ax1.set_xlabel("MAF actual / expected ratio")
    ax1.set_ylabel("sample count")
    ax1.set_title("MAF ratio distribution")
    leg = ax1.legend(facecolor=STYLE["bg"], edgecolor=STYLE["grid"])
    for t in leg.get_texts():
        t.set_color(STYLE["fg"])

    # LTFT overlay
    ax2.plot(range(len(b_ltft)), b_ltft, color=STYLE["err"], linewidth=0.8,
             alpha=0.7, label="before")
    ax2.plot(range(len(a_ltft)), a_ltft, color=STYLE["ok"], linewidth=0.8,
             alpha=0.7, label="after")
    ax2.axhspan(-7, 7, color=STYLE["ok"], alpha=0.08, label="healthy")
    ax2.axhline(25, color=STYLE["err"], linestyle="--", alpha=0.5, label="P0171")
    ax2.set_xlabel("sample #")
    ax2.set_ylabel("LTFT B1 (%)")
    ax2.set_title("LTFT trajectory")
    leg = ax2.legend(facecolor=STYLE["bg"], edgecolor=STYLE["grid"])
    for t in leg.get_texts():
        t.set_color(STYLE["fg"])

    fig.suptitle("Before vs After — repair comparison",
                 color=STYLE["fg"], fontsize=14)
    out = out_path or f"{REPORT_DIR}/compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    fig.savefig(out, dpi=120, bbox_inches="tight",
                facecolor=STYLE["bg"])
    plt.close(fig)
    return out


def plot_history_ltft(db_path: str | None = None,
                      days: int = 30,
                      out_path: str | None = None) -> str | None:
    """LTFT avg across sessions over time."""
    if not HAS_MPL:
        return None
    from .store import Store, DEFAULT_DB
    from .vehicle import VIN

    with Store(db_path or DEFAULT_DB) as s:
        rows = s.ltft_history(vin=VIN, days=days)
    if not rows:
        return None

    # Reverse so oldest first on X axis
    rows = list(reversed(rows))
    ts = [r["started_ts"] for r in rows]
    labels = [t.split("T")[0] + "\n" + t.split("T")[1][:5] for t in ts]
    ltft_avg = [r["ltft_avg"] for r in rows]
    ltft_max = [r["ltft_max"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=STYLE["bg"])
    _style_ax(ax)
    x = list(range(len(rows)))
    ax.bar(x, ltft_avg, color=STYLE["blue"], alpha=0.7, label="avg")
    ax.plot(x, ltft_max, color=STYLE["err"], marker="o", linewidth=1.2,
            label="peak")
    ax.axhspan(-7, 7, color=STYLE["ok"], alpha=0.12, label="healthy ±7%")
    ax.axhline(25, color=STYLE["err"], linestyle="--", alpha=0.5,
               label="P0171")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("LTFT B1 (%)")
    ax.set_title(f"LTFT history — last {days} days — {VIN}")
    leg = ax.legend(facecolor=STYLE["bg"], edgecolor=STYLE["grid"])
    for t in leg.get_texts():
        t.set_color(STYLE["fg"])

    out = out_path or f"{REPORT_DIR}/history_ltft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    fig.savefig(out, dpi=120, bbox_inches="tight", facecolor=STYLE["bg"])
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="CSV to chart")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="Plot before/after comparison")
    ap.add_argument("--history", type=int, metavar="DAYS",
                    help="Plot LTFT history from SQLite store")
    ap.add_argument("--out", help="Output PNG path")
    args = ap.parse_args()

    if not HAS_MPL:
        print("[!] matplotlib not installed — run:  pip install matplotlib")
        return 1

    if args.csv:
        maf_out = plot_maf_scatter(args.csv,
                                    args.out and args.out.replace(".png", "_maf.png"))
        trim_out = plot_trim_over_time(args.csv,
                                        args.out and args.out.replace(".png", "_trim.png"))
        print(f"[+] MAF scatter:  {maf_out}")
        print(f"[+] Trim overlay: {trim_out}")
    elif args.compare:
        out = plot_compare(args.compare[0], args.compare[1], args.out)
        print(f"[+] Compare: {out}")
    elif args.history:
        out = plot_history_ltft(days=args.history, out_path=args.out)
        print(f"[+] History: {out}")
    else:
        print("Pass --csv, --compare, or --history. Use --help for details.")


if __name__ == "__main__":
    main()
