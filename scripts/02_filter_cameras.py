"""
02_filter_cameras.py
--------------------
Reads the raw camera metadata from the source xlsx and filters to the set
of cameras eligible for analysis: Live status, with a full 365-day pre-install
window AND a full 365-day post-install window inside the available crash data.

Input:
    data/raw/Midterm_Memo.xlsx  (sheet: Camera_CLEAN)
    data/processed/crashes_clean.pkl  (to determine eligible install window)

Output:
    data/processed/cameras_eligible.pkl

Eligibility rules:
    - CAMERA_STATUS == "Live"  (drops Warning, Test)
    - START_DATE within [min_crash_date + 365 days, max_crash_date - 365 days]
    - Valid CAMERA_LATITUDE and CAMERA_LONGITUDE
"""

from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "data" / "raw" / "Midterm_Memo.xlsx"
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
OUT_PATH = REPO_ROOT / "data" / "processed" / "cameras_eligible.pkl"

# --- The subset of Camera_CLEAN columns the downstream scripts use.
USECOLS = [
    "ENFORCEMENT_SPACE_CODE", "LOCATION_DESCRIPTION", "SITE_CODE",
    "CAMERA_STATUS", "START_DATE", "ENFORCEMENT_TYPE", "SPEED_LIMIT",
    "CAMERA_LATITUDE", "CAMERA_LONGITUDE", "WARD",
]


def main():
    # --- Load crashes first so we can read their date range. The camera's
    #     eligible install window depends on what crash data we actually have.
    print(f"Reading {CRASHES_PATH.name} to get crash date range ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    min_crash = crashes["REPORTDATE"].min()
    max_crash = crashes["REPORTDATE"].max()
    print(f"  Crash data spans: {min_crash.date()} to {max_crash.date()}")

    # --- A camera is eligible only if BOTH its 365-day pre window and its
    #     365-day post window fall entirely inside the crash data. That means
    #     the install date has to be at least 365 days after the earliest
    #     crash AND at least 365 days before the latest crash.
    earliest_install = min_crash + pd.Timedelta(days=365)
    latest_install = max_crash - pd.Timedelta(days=365)
    print(f"  Eligible install window: {earliest_install.date()} to {latest_install.date()}")

    print(f"\nReading {RAW_PATH.name} (Camera_CLEAN sheet) ...")
    cam = pd.read_excel(RAW_PATH, sheet_name="Camera_CLEAN", usecols=USECOLS)
    print(f"  Total cameras: {len(cam)}")

    # --- Coerce types.
    cam["START_DATE"] = pd.to_datetime(cam["START_DATE"], errors="coerce").dt.normalize()
    cam["CAMERA_LATITUDE"] = pd.to_numeric(cam["CAMERA_LATITUDE"], errors="coerce")
    cam["CAMERA_LONGITUDE"] = pd.to_numeric(cam["CAMERA_LONGITUDE"], errors="coerce")

    # --- Report what gets dropped and why. Doing this as separate masks
    #     (rather than one combined filter) means the terminal output tells
    #     us exactly which rule filtered out which cameras.
    is_live = cam["CAMERA_STATUS"] == "Live"
    in_window = cam["START_DATE"].between(earliest_install, latest_install)
    has_coords = cam["CAMERA_LATITUDE"].notna() & cam["CAMERA_LONGITUDE"].notna()

    print(f"  Dropped — not Live status:         {(~is_live).sum()}")
    print(f"  Dropped — outside eligible window: {(~in_window).sum()}")
    print(f"  Dropped — missing coordinates:     {(~has_coords).sum()}")

    eligible = cam[is_live & in_window & has_coords].copy().reset_index(drop=True)
    print(f"\nEligible cameras: {len(eligible)}")
    print("  By enforcement type:")
    for etype, count in eligible["ENFORCEMENT_TYPE"].value_counts().items():
        print(f"    {etype:20s} {count}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    eligible.to_pickle(OUT_PATH)
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}")

    # --- Human-readable xlsx of the eligible camera list.
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "02_cameras_eligible.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    eligible.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
