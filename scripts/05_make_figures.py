"""
05_make_figures.py
------------------
Generates the four editorial figures used in both the PDF briefing and the
Excel workbook cover. All four use a shared cream/ink/red palette so they
read as a coherent set.

Input:
    data/processed/crashes_clean.pkl
    data/processed/per_camera_results.pkl
    data/processed/placebo_results.pkl

Output:
    outputs/figures/fig_map.png         — DC map, cameras colored by DiD
    outputs/figures/fig_scatter.png     — pre vs post scatter, per camera type
    outputs/figures/fig_placebo.png     — real vs placebo DiD, horizontal bars
    outputs/figures/fig_sensitivity.png — DiD at 150m / 200m / 250m
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

REPO_ROOT = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
RESULTS_PATH = REPO_ROOT / "data" / "processed" / "per_camera_results.pkl"
PLACEBO_PATH = REPO_ROOT / "data" / "processed" / "placebo_results.pkl"
FIG_DIR = REPO_ROOT / "outputs" / "figures"

# --- Shared palette. Changing any of these here updates all four figures.
CREAM = "#F8F4EC"
INK = "#1a1f2e"
NAVY = "#2C3E50"
RED = "#C9483A"
GREEN = "#2D6A4F"
GOLD = "#D4A548"
TEAL = "#4A7C7E"

TYPES_ORDER_DESC = ["Stop Sign", "Truck Restriction", "Red Light", "Speed"]
TYPE_COLORS = {"Stop Sign": GREEN, "Red Light": GOLD, "Speed": RED, "Truck Restriction": TEAL}
TYPE_MARKERS = {"Speed": ("o", 60), "Red Light": ("s", 60),
                "Stop Sign": ("^", 75), "Truck Restriction": ("D", 65)}


def style_axes(ax, bg=CREAM):
    """Apply the editorial base style to a matplotlib axes."""
    ax.set_facecolor(bg)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(INK)
    ax.tick_params(colors=INK, labelsize=9)


def compute_did(df, pre_col, post_col, city_pre_col, city_post_col):
    """Difference-in-Differences: zone %-change minus citywide %-change."""
    pre, post = df[pre_col].sum(), df[post_col].sum()
    cpre, cpost = df[city_pre_col].sum(), df[city_post_col].sum()
    zone = (post - pre) / pre * 100 if pre else float("nan")
    city = (cpost - cpre) / cpre * 100 if cpre else float("nan")
    return zone - city


def fig_map(crashes, res):
    """Figure 1 — DC map, each camera colored by its injury DiD at 200m."""
    fig, ax = plt.subplots(figsize=(9, 9.5), facecolor=CREAM)
    style_axes(ax)

    # --- Background: faint crash points show the DC road network.
    ax.scatter(crashes["LONGITUDE"], crashes["LATITUDE"],
               s=0.4, color=INK, alpha=0.045, zorder=1)

    # --- Diverging colormap: green = fewer crashes, red = more.
    cmap = LinearSegmentedColormap.from_list(
        "editorial", [GREEN, "#C8D5B9", "#F7E9D0", "#E8A878", RED])

    d = res.copy()
    d["cam_did"] = (d["b200_injury_pct"] - d["citywide_injury_pct"]).fillna(0)

    sc = None
    for t, (marker, size) in TYPE_MARKERS.items():
        sub = d[d["type"] == t]
        sc = ax.scatter(sub["lon"], sub["lat"],
                        c=sub["cam_did"].clip(-40, 40),
                        cmap=cmap, vmin=-40, vmax=40, marker=marker,
                        s=size, edgecolor=INK, linewidth=0.5,
                        label=f"{t}  ({len(sub)})", zorder=3)

    # --- DC roughly fits this bounding box; lock the aspect so it's not stretched.
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
    cbar = plt.colorbar(sc, cax=cbar_ax)
    cbar.set_label("DiD (injury crashes)", fontsize=8, color=INK)
    cbar.ax.tick_params(labelsize=7, colors=INK)
    cbar.outline.set_visible(False)

    out = FIG_DIR / "fig_map.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_placebo(res, placebo):
    """Figure 2 — real DiD vs placebo DiD, horizontal bars, by camera type."""
    fig, ax = plt.subplots(figsize=(9.5, 5.5), facecolor=CREAM)
    style_axes(ax)

    real_dids, placebo_dids = [], []
    for t in TYPES_ORDER_DESC:
        real_dids.append(compute_did(
            res[res["type"] == t],
            "b200_injury_pre", "b200_injury_post",
            "citywide_injury_pre", "citywide_injury_post"))
        placebo_dids.append(compute_did(
            placebo[placebo["type"] == t],
            "placebo_injury_pre", "placebo_injury_post",
            "placebo_city_injury_pre", "placebo_city_injury_post"))

    y = np.arange(len(TYPES_ORDER_DESC))
    h = 0.36
    b1 = ax.barh(y - h / 2, real_dids, h, color=NAVY,
                 edgecolor=INK, linewidth=0.5, label="Actual install date")
    b2 = ax.barh(y + h / 2, placebo_dids, h, color="#BFB7A4",
                 edgecolor=INK, linewidth=0.5, label="Placebo (1 yr earlier)")

    ax.axvline(0, color=INK, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(TYPES_ORDER_DESC, fontsize=11, color=INK)
    ax.set_xlabel("DiD  —  Zone % change minus citywide % change",
                  fontsize=10, color=INK)
    ax.grid(True, alpha=0.25, axis="x", linestyle="--", linewidth=0.4)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.95,
              edgecolor=INK, facecolor="white")

    # --- Value labels next to each bar so readers don't need to eyeball.
    for bar, val in zip(b1, real_dids):
        ax.text(val + (0.6 if val >= 0 else -0.6),
                bar.get_y() + bar.get_height() / 2, f"{val:+.1f}",
                va="center", ha="left" if val >= 0 else "right",
                fontsize=10, color=NAVY, fontweight="bold")
    for bar, val in zip(b2, placebo_dids):
        ax.text(val + (0.6 if val >= 0 else -0.6),
                bar.get_y() + bar.get_height() / 2, f"{val:+.1f}",
                va="center", ha="left" if val >= 0 else "right",
                fontsize=9, color="#6E6856")

    ax.set_xlim(-22, 12)
    plt.tight_layout()
    out = FIG_DIR / "fig_placebo.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_scatter(res):
    """Figure 3 — per-camera pre vs post injury crashes, faceted by type."""
    fig, axes = plt.subplots(1, 4, figsize=(13.5, 3.8), facecolor=CREAM)
    for ax, t in zip(axes, TYPES_ORDER_DESC):
        style_axes(ax)
        sub = res[res["type"] == t]
        pre = sub["b200_injury_pre"]
        post = sub["b200_injury_post"]
        max_v = max(pre.max(), post.max(), 1) + 1
        ax.plot([0, max_v], [0, max_v], "--", color=INK, alpha=0.4, linewidth=0.8)
        ax.scatter(pre, post, s=35, alpha=0.55, edgecolor=INK,
                   linewidth=0.3, color=TYPE_COLORS[t])
        ax.set_title(f"{t}\n(n={len(sub)})",
                     fontsize=10, color=INK, fontweight="bold")
        ax.set_xlim(-0.5, max_v)
        ax.set_ylim(-0.5, max_v)
        ax.set_xlabel("Before", fontsize=9, color=INK)
        ax.set_ylabel("After", fontsize=9, color=INK)
        ax.grid(True, alpha=0.2, linewidth=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_scatter.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_sensitivity(res):
    """Figure 4 — DiD at each buffer radius, grouped by camera type."""
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=CREAM)
    style_axes(ax)

    types = ["Speed", "Red Light", "Stop Sign", "Truck Restriction"]
    buffers = [150, 200, 250]
    colors = ["#3b6e8f", "#5794b9", "#a8c8db"]

    x = np.arange(len(types))
    w = 0.25
    for i, b in enumerate(buffers):
        dids = []
        for t in types:
            sub = res[res["type"] == t]
            dids.append(compute_did(
                sub, f"b{b}_injury_pre", f"b{b}_injury_post",
                "citywide_injury_pre", "citywide_injury_post"))
        bars = ax.bar(x + (i - 1) * w, dids, w, color=colors[i],
                      edgecolor=INK, label=f"{b}m")
        for bar, val in zip(bars, dids):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    val + (0.7 if val >= 0 else -1.7),
                    f"{val:+.1f}", ha="center", fontsize=7)

    ax.axhline(0, color=INK, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(types)
    ax.set_ylabel("DiD: Injury crashes (zone% − citywide%)")
    ax.set_title("Sensitivity: DiD at different buffer radii\n"
                 "(If finding is robust, bars within each group should agree directionally)")
    ax.legend(title="Buffer", fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    out = FIG_DIR / "fig_sensitivity.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def main():
    print("Loading data ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    res = pd.read_pickle(RESULTS_PATH)
    placebo = pd.read_pickle(PLACEBO_PATH)
    # --- Merge placebo type onto placebo rows so figure code can groupby.
    placebo = placebo.merge(res[["camera_code", "type"]].rename(
        columns={"type": "_type"}), on="camera_code", how="left")
    if "type" not in placebo.columns:
        placebo = placebo.rename(columns={"_type": "type"})

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("\nRendering figures ...")
    fig_map(crashes, res)
    fig_placebo(res, placebo)
    fig_scatter(res)
    fig_sensitivity(res)

    # --- Also save the DiD values shown in the figures as a small table.
    #     Useful as caption/chart-notes source for anyone working from the PNGs.
    print("\nWriting figure DiD summary xlsx ...")
    summary_rows = []
    for t in TYPES_ORDER_DESC:
        sub_r = res[res["type"] == t]
        sub_p = placebo[placebo["type"] == t]
        row = {"camera_type": t, "n": len(sub_r)}
        # 200m injury DiD at real vs placebo
        row["real_did_injury_200m"] = compute_did(
            sub_r, "b200_injury_pre", "b200_injury_post",
            "citywide_injury_pre", "citywide_injury_post")
        row["placebo_did_injury_200m"] = compute_did(
            sub_p, "placebo_injury_pre", "placebo_injury_post",
            "placebo_city_injury_pre", "placebo_city_injury_post")
        # Sensitivity DiDs
        for b in [150, 200, 250]:
            row[f"did_injury_{b}m"] = compute_did(
                sub_r, f"b{b}_injury_pre", f"b{b}_injury_post",
                "citywide_injury_pre", "citywide_injury_post")
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows).round(2)

    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "05_figure_did_summary.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_excel(xlsx_path, index=False)
    print(f"  {xlsx_path.relative_to(REPO_ROOT)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
