"""
04_make_figures.py
------------------
Generates three figures from the analysis results.

Figure 1 — DC map: every eligible camera as a dot, colored by its effect
    vs. city trend for injury crashes. Green = fewer crashes than city
    average. Red = more crashes than city average.

Figure 2 — Lollipop chart: headline effect vs. city trend by camera type
    for injury crashes. One dot per camera type, stems showing the
    distance from the city average.

Figure 3 — Small multiples: four panels (all / injury / serious / fatal),
    each showing horizontal bars of effect vs. city trend by camera type.

Input:
    data/processed/crashes_clean.pkl
    data/processed/per_camera_results.pkl

Output:
    outputs/figures/fig_map.png
    outputs/figures/fig_lollipop.png
    outputs/figures/fig_small_multiples.png
    outputs/step_outputs/04_figure_summary.xlsx
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

# --- Shared color palette (matches the workbook and any other figures).
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

OUTCOMES = [
    ("all",     "All crashes"),
    ("injury",  "Injury crashes"),
    ("serious", "Serious (fatal + major)"),
    ("fatal",   "Fatal only"),
]


def style_axes(ax):
    """Apply the shared editorial style to a matplotlib axes."""
    ax.set_facecolor(CREAM)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(INK)
    ax.tick_params(colors=INK, labelsize=9)


def compute_effect(sub, outcome_key):
    """Effect vs. city trend: nearby % change minus citywide % change."""
    pre   = sub[f"nearby_{outcome_key}_pre"].sum()
    post  = sub[f"nearby_{outcome_key}_post"].sum()
    cpre  = sub[f"citywide_{outcome_key}_pre"].sum()
    cpost = sub[f"citywide_{outcome_key}_post"].sum()
    zone  = (post - pre)  / pre  * 100 if pre  else float("nan")
    city  = (cpost - cpre) / cpre * 100 if cpre else float("nan")
    return zone - city


def color_for_value(val):
    """Green if clearly negative, red if clearly positive, gray if near zero."""
    if val is None or np.isnan(val):
        return "#999999"
    if val <= -5:
        return GREEN
    if val >= 5:
        return RED
    return "#999999"


def fig_map(crashes, res):
    """Figure 1 — DC map, cameras colored by effect vs. city trend (injury)."""
    fig, ax = plt.subplots(figsize=(9, 9.5), facecolor=CREAM)
    style_axes(ax)

    # Faint crash dots in the background to show the road network.
    ax.scatter(crashes["LONGITUDE"], crashes["LATITUDE"],
               s=0.4, color=INK, alpha=0.045, zorder=1)

    cmap = LinearSegmentedColormap.from_list(
        "editorial", [GREEN, "#C8D5B9", "#F7E9D0", "#E8A878", RED])

    res = res.copy()
    res["cam_effect"] = (res["nearby_injury_pct"] - res["citywide_injury_pct"]).fillna(0)

    sc = None
    for t, (marker, size) in TYPE_MARKERS.items():
        sub = res[res["type"] == t]
        sc  = ax.scatter(sub["lon"], sub["lat"],
                         c=sub["cam_effect"].clip(-40, 40),
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
    cbar.set_label("Effect vs. city trend (injury crashes)", fontsize=8, color=INK)
    cbar.ax.tick_params(labelsize=7, colors=INK)
    cbar.outline.set_visible(False)

    out = FIG_DIR / "fig_map.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_lollipop(res):
    """Figure 2 — lollipop chart, effect vs. city trend by camera type (injury)."""
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=CREAM)
    style_axes(ax)

    effects = [compute_effect(res[res["type"] == t], "injury") for t in TYPES_ORDER]
    y       = np.arange(len(TYPES_ORDER))

    # --- The zero line is labeled "City average" for readability.
    ax.axvline(0, color=INK, linewidth=1.2, zorder=1)
    ax.text(0, len(TYPES_ORDER) - 0.3, "City average",
            ha="center", va="bottom",
            fontsize=9, color=INK, style="italic")

    # --- Stems (horizontal lines) from the zero line out to each value.
    for yi, val in zip(y, effects):
        ax.plot([0, val], [yi, yi],
                color=color_for_value(val), linewidth=2.5, zorder=2)

    # --- Dots at the end of each stem.
    for yi, val in zip(y, effects):
        ax.scatter(val, yi, s=220, color=color_for_value(val),
                   edgecolor=INK, linewidth=1, zorder=3)

    # --- Value labels just past each dot.
    for yi, val in zip(y, effects):
        offset = 1.5 if val >= 0 else -1.5
        ha     = "left" if val >= 0 else "right"
        ax.text(val + offset, yi, f"{val:+.1f}",
                va="center", ha=ha, fontsize=11,
                color=INK, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(TYPES_ORDER, fontsize=12, color=INK)
    ax.set_xlabel("Effect vs. city trend — injury crashes",
                  fontsize=10, color=INK)
    ax.set_ylim(-0.6, len(TYPES_ORDER) - 0.1)

    # --- Extend x-axis so the labels don't clip at the edges.
    xlim_pad = max(abs(min(effects)), abs(max(effects))) + 6
    ax.set_xlim(-xlim_pad, xlim_pad)
    ax.grid(True, alpha=0.2, axis="x", linestyle="--", linewidth=0.4)

    plt.tight_layout()
    out = FIG_DIR / "fig_lollipop.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=CREAM)
    plt.close()
    print(f"  {out.relative_to(REPO_ROOT)}")


def fig_small_multiples(res):
    """Figure 3 — four panels, effect vs. city trend by crash type."""
    fig, axes = plt.subplots(1, 4, figsize=(14, 4.2), facecolor=CREAM,
                             sharey=True)

    y = np.arange(len(TYPES_ORDER))

    # --- Compute all effects first so we can share a single x-axis scale.
    all_effects = []
    panel_data  = []
    for outcome_key, outcome_label in OUTCOMES:
        effects = [compute_effect(res[res["type"] == t], outcome_key)
                   for t in TYPES_ORDER]
        panel_data.append((outcome_label, effects))
        all_effects.extend([e for e in effects if not np.isnan(e)])

    xlim_pad = max(abs(min(all_effects)), abs(max(all_effects))) + 8

    for ax, (outcome_label, effects) in zip(axes, panel_data):
        style_axes(ax)

        # --- City average line with label only on first panel.
        ax.axvline(0, color=INK, linewidth=1, zorder=1)

        # --- Horizontal bars.
        for yi, val in zip(y, effects):
            ax.barh(yi, val, height=0.55,
                    color=color_for_value(val),
                    edgecolor=INK, linewidth=0.5, zorder=2)

        # --- Value labels at the end of each bar.
        for yi, val in zip(y, effects):
            offset = 0.8 if val >= 0 else -0.8
            ha     = "left" if val >= 0 else "right"
            ax.text(val + offset, yi, f"{val:+.1f}",
                    va="center", ha=ha, fontsize=9,
                    color=INK, fontweight="bold")

        ax.set_title(outcome_label, fontsize=11,
                     color=INK, fontweight="bold", pad=10)
        ax.set_xlim(-xlim_pad, xlim_pad)
        ax.set_ylim(-0.6, len(TYPES_ORDER) - 0.4)
        ax.grid(True, alpha=0.15, axis="x", linestyle="--", linewidth=0.4)

    # --- Only the leftmost panel gets y-axis camera type labels.
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(TYPES_ORDER, fontsize=11, color=INK)

    # --- "City average" label above the zero line in the first panel.
    axes[0].text(0, len(TYPES_ORDER) - 0.3, "City average",
                 ha="center", va="bottom", fontsize=8,
                 color=INK, style="italic")

    fig.suptitle("Effect vs. city trend, by crash type",
                 fontsize=13, color=INK, fontweight="bold", y=1.02)
    fig.supxlabel("Effect vs. city trend (percentage points)",
                  fontsize=10, color=INK, y=-0.02)

    plt.tight_layout()
    out = FIG_DIR / "fig_small_multiples.png"
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
    fig_lollipop(res)
    fig_small_multiples(res)

    # --- Small summary table of the effects shown in the figures.
    print("\nWriting effect summary xlsx ...")
    rows = []
    for t in TYPES_ORDER:
        sub = res[res["type"] == t]
        row = {"camera_type": t, "n": len(sub)}
        for outcome_key, outcome_label in OUTCOMES:
            row[f"effect_{outcome_key}"] = round(compute_effect(sub, outcome_key), 2)
        rows.append(row)
    summary = pd.DataFrame(rows)

    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "04_figure_summary.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_excel(xlsx_path, index=False)
    print(f"  {xlsx_path.relative_to(REPO_ROOT)}")
    print("\nDone.")


if __name__ == "__main__":
    main()