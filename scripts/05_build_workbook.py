"""
06_build_workbook.py
--------------------
Assembles the final Excel workbook from the analysis results.

Tabs produced:
    1. Summary     — headline DiD numbers by camera type and outcome
    2. Per_Camera  — one row per camera with all computed columns

Input:
    data/processed/per_camera_results.pkl

Output:
    outputs/camera_analysis_results.xlsx
"""

from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

REPO_ROOT    = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "data" / "processed" / "per_camera_results.pkl"
OUT_PATH     = REPO_ROOT / "outputs" / "camera_analysis_results.xlsx"

TYPES    = ["Speed", "Red Light", "Stop Sign", "Truck Restriction"]
OUTCOMES = [
    ("all",     "All crashes"),
    ("injury",  "Injury crashes"),
    ("serious", "Serious (fatal + major)"),
    ("fatal",   "Fatal only"),
]

HEADER_FILL = PatternFill("solid", start_color="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=11)
GREEN_FILL  = PatternFill("solid", start_color="C6EFCE")
RED_FILL    = PatternFill("solid", start_color="FFC7CE")
YELLOW_FILL = PatternFill("solid", start_color="FFF2CC")


def style_header(ws, row=1):
    for cell in ws[row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def autosize(ws, min_w=10, max_w=30):
    for col in ws.columns:
        cells = [c for c in col if c.column_letter]
        if not cells:
            continue
        length = max(len(str(c.value)) if c.value is not None else 0 for c in cells)
        ws.column_dimensions[cells[0].column_letter].width = min(max(length + 2, min_w), max_w)


def compute_did(sub, outcome_key):
    pre   = sub[f"nearby_{outcome_key}_pre"].sum()
    post  = sub[f"nearby_{outcome_key}_post"].sum()
    cpre  = sub[f"citywide_{outcome_key}_pre"].sum()
    cpost = sub[f"citywide_{outcome_key}_post"].sum()
    zone  = (post - pre)  / pre  * 100 if pre  else None
    city  = (cpost - cpre) / cpre * 100 if cpre else None
    if zone is None or city is None:
        return None
    return round(zone - city, 1)


def build_summary(wb, res):
    ws = wb.active
    ws.append(["Headline results by camera type — 200m buffer"])
    ws.append([])
    ws.append(["Camera Type", "N", "Outcome",
               "Nearby pre", "Nearby post", "Nearby %",
               "Citywide %", "DiD"])

    for outcome_key, outcome_label in OUTCOMES:
        for t in TYPES:
            sub = res[res["type"] == t]

            npre  = sub[f"nearby_{outcome_key}_pre"].sum()
            npost = sub[f"nearby_{outcome_key}_post"].sum()
            cpre  = sub[f"citywide_{outcome_key}_pre"].sum()
            cpost = sub[f"citywide_{outcome_key}_post"].sum()
            npct  = round((npost - npre) / npre * 100, 1) if npre else None
            cpct  = round((cpost - cpre) / cpre * 100, 1) if cpre else None
            did   = compute_did(sub, outcome_key)

            ws.append([t, len(sub), outcome_label,
                       npre, npost, npct, cpct, did])
        ws.append([])

    style_header(ws, 3)
    ws["A1"].font = Font(bold=True, size=13)

    # Color code the DiD column (col 8)
    for row_idx in range(4, ws.max_row + 1):
        cell = ws.cell(row=row_idx, column=8)
        if cell.value is None:
            continue
        try:
            v = float(cell.value)
            if v <= -5:
                cell.fill = GREEN_FILL
            elif v >= 5:
                cell.fill = RED_FILL
            else:
                cell.fill = YELLOW_FILL
        except (ValueError, TypeError):
            pass

    autosize(ws, min_w=12, max_w=25)


def build_per_camera(wb, res):
    ws = wb.create_sheet("Per_Camera")

    cols = [
        "camera_code", "location", "type", "install_date", "ward", "lat", "lon",
        "nearby_all_pre",     "nearby_all_post",     "nearby_all_pct",
        "nearby_injury_pre",  "nearby_injury_post",  "nearby_injury_pct",
        "nearby_serious_pre", "nearby_serious_post", "nearby_serious_pct",
        "nearby_fatal_pre",   "nearby_fatal_post",   "nearby_fatal_pct",
        "citywide_all_pct",   "citywide_injury_pct",
        "did_all", "did_injury", "did_serious", "did_fatal", "did_speeding",
    ]
    out = res[cols].copy()
    for c in out.columns:
        if out[c].dtype == float:
            out[c] = out[c].round(2)

    ws.append(list(out.columns))
    for _, row in out.iterrows():
        ws.append([None if pd.isna(v) else v for v in row.values])

    style_header(ws)
    ws.freeze_panes = "D2"
    autosize(ws)


def main():
    print("Loading results ...")
    res = pd.read_pickle(RESULTS_PATH)
    print(f"  {len(res)} cameras in results")

    wb = Workbook()
    wb.active.title = "Summary"
    build_summary(wb, res)
    build_per_camera(wb, res)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_PATH)
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()