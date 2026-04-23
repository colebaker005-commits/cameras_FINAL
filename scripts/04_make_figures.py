"""
05_make_figures.py
------------------
Generates three figures from the analysis results.

Figure 1 — DC map: every eligible camera as a dot, colored by its DiD
    for injury crashes. Green = fewer crashes than citywide trend.
    Red = more crashes than citywide trend.

Figure 2 — Pre vs post scatter: one dot per camera, x = crashes before
    install, y = crashes after install. Dots below the diagonal line
    mean fewer crashes after the camera went in.

Figure 3 — DiD bar chart: headline DiD by camera type for injury crashes.

Input:
    data/processed/crashes_clean.pkl
    data/processed/per_camera_results.pkl

Output:
    outputs/figures/fig_map.png
    outputs/figures/fig_scatter.png
    outputs/figures/fig_did_bars.png
    outputs/step_outputs/05_figure_did_summary.xlsx
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

REPO_ROOT    = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
RESULTS_PATH = REPO_ROOT / "data" / "processed" / "per_camera_results.pkl"
FIG_DIR      = REPO_ROOT / "outputs" / "figures"

# --- Shared color palette
CREAM  = "#F8F4EC"
INK    = "#1a1f2e"
NAVY   = "#2C3E50"
RED    = "#C9483A"
GREEN  = "#2D6A4F"
GOLD   = "#D4A548"
TEAL   = "#4A7C7E"

TYPES_ORDER  = ["Stop Sign", "Truck Restriction", "Red Light", "Speed"]
TYPE_COLORS  = {"Stop Sign": GREEN, "Red Light": GOLD,
                "Speed": RED, "Truck Restriction": TEAL}
TYPE_MARKERS = {"Speed": ("o", 60), "Red Light": ("s", 60),
                "Stop Sign": ("^", 75), "Truck Restriction": ("D", 65)}


def style_axes(ax):
    ax.set_facecolor(CREAM)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(INK)
    ax.tick_params(colors=INK, labelsize=9)


def compute_did(sub):
    pre   = sub["nearby_injury_pre"].sum()
    post  = sub["nearby_injury_post"].sum()
    cpre  = sub["citywide_injury_pre"].sum()
    cpost = sub["citywide_injury_post"].sum()
    zone  = (post - pre)  / pre  * 100 if pre  else float("nan")
    city  = (cpost - cpre) / cpre * 100 if cpre else float("nan")
    return zone - city


def fig_map(crashes, res):
    """Figure 1 — DC map, cameras colored by injury DiD."""
    fig, ax = plt.subplots(figsize=(9, 9.5), facecolor=CREAM)
    style_axes(ax)

    ax.scatter(crashes["LONGITUDE"], crashes["LATITUDE"],
               s=0.4, color=INK, alpha=0.045, zorder=1)

    cmap = LinearSegmentedColormap.from_list(
        "editorial", [GREEN, "#C8D5B9", "#F7E9D0", "#E8A878", RED])

    res = res.copy()
    res["cam_did"] = (res["nearby_injury_pct"] - res["citywide_injury_pct"]).fillna(0)

    sc = None
    for t, (marker, size) in TYPE_MARKERS.items():
        sub = res[res["type"] == t]
        sc  = ax.scatter(sub["lon"], sub["lat"],
                         c=sub["cam_did"].clip(-40, 40),
                         cmap=cmap, vmin=-40, vmax=40,
                         marker=marker, s=size,
                         edgecolor=INK, linewidth=0.5,
                         label=f"{t}  ({len(sub)})", zorder=3)

    ax.set_xlim(-77.12, -76.91)
    ax.set_ylim(38.79, 39.00)
    ax.set_aspect(1 / np.cos(np.radians(38.9)))
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    leg = ax.legend(loc="lower left", fontsize=9, framealpha=0.95,
                    edgecolor=INK, facecolor="white",
                    title="Camera type (count)", title_fontsize=9)
    leg.get_title().set_fontweight("bold")

    cbar_ax = fig.add_axes([0.88, 0.35, 0.018, 0.3])
    cbar    = plt.colorbar(sc, cax=cbar_ax)
    cbar.set_label("DiD (injury crashes)", fontsize=8, color=INK)
    cbar.ax.tick_params(labelsize=7, colors=INK)
    cbar.outline.set_visible(False)

    out = FIG_DIR / "fig_map.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_scatter(res):
    """Figure 2 — pre vs post injury crashes, one dot per camera, by type."""
    fig, axes = plt.subplots(1, 4, figsize=(13.5, 3.8), facecolor=CREAM)
    for ax, t in zip(axes, TYPES_ORDER):
        style_axes(ax)
        sub   = res[res["type"] == t]
        pre   = sub["nearby_injury_pre"]
        post  = sub["nearby_injury_post"]
        max_v = max(pre.max(), post.max(), 1) + 1

        ax.plot([0, max_v], [0, max_v], "--", color=INK, alpha=0.4, linewidth=0.8)
        ax.scatter(pre, post, s=35, alpha=0.55,
                   edgecolor=INK, linewidth=0.3, color=TYPE_COLORS[t])
        ax.set_title(f"{t}\n(n={len(sub)})", fontsize=10,
                     color=INK, fontweight="bold")
        ax.set_xlim(-0.5, max_v)
        ax.set_ylim(-0.5, max_v)
        ax.set_xlabel("Crashes before install", fontsize=9, color=INK)
        ax.set_ylabel("Crashes after install",  fontsize=9, color=INK)
        ax.grid(True, alpha=0.2, linewidth=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_scatter.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_did_bars(res):
    """Figure 3 — DiD by camera type, injury crashes."""
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=CREAM)
    style_axes(ax)

    dids   = [compute_did(res[res["type"] == t]) for t in TYPES_ORDER]
    colors = [TYPE_COLORS[t] for t in TYPES_ORDER]
    y      = np.arange(len(TYPES_ORDER))

    bars = ax.barh(y, dids, color=colors, edgecolor=INK, linewidth=0.5)
    ax.axvline(0, color=INK, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(TYPES_ORDER, fontsize=11, color=INK)
    ax.set_xlabel("DiD — nearby % change minus citywide % change",
                  fontsize=10, color=INK)
    ax.grid(True, alpha=0.25, axis="x", linestyle="--", linewidth=0.4)

    for bar, val in zip(bars, dids):
        ax.text(val + (0.6 if val >= 0 else -0.6),
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}", va="center",
                ha="left" if val >= 0 else "right",
                fontsize=10, color=INK, fontweight="bold")

    plt.tight_layout()
    out = FIG_DIR / "fig_did_bars.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def main():
    print("Loading data ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    res     = pd.read_pickle(RESULTS_PATH)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("\nRendering figures ...")
    fig_map(crashes, res)
    fig_scatter(res)
    fig_did_bars(res)

    print("\nWriting DiD summary xlsx ...")
    rows = []
    for t in TYPES_ORDER:
        sub = res[res["type"] == t]
        rows.append({
            "camera_type":     t,
            "n":               len(sub),
            "did_injury":      round(compute_did(sub), 2),
        })
    summary = pd.DataFrame(rows)
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "05_figure_did_summary.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_excel(xlsx_path, index=False)
    print(f"  {xlsx_path.relative_to(REPO_ROOT)}")
    print("\nDone.")


if __name__ == "__main__":
    main()