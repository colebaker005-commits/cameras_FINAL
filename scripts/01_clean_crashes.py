"""
01_clean_crashes.py
-------------------
Reads the raw DDOT crash data from the source xlsx, filters to usable rows,
and flags each crash by severity. Saves the result as a pickle for later
scripts.

Input:  data/raw/Midterm_Memo.xlsx  (sheet: Crash_Raw)
Output: data/processed/crashes_clean.pkl

Filters applied:
  - REPORTDATE must be a valid datetime in 2021-01-01 through 2026-12-31
  - LATITUDE and LONGITUDE must fall inside the DC bounding box
  - Injury/fatal/speeding columns are coerced to numeric (missing -> 0)

Severity flags added:
  - is_fatal     : any fatality recorded (driver/pedestrian/bicyclist/passenger/other)
  - is_major     : any major injury recorded
  - is_minor     : any minor injury recorded
  - is_injury    : fatal OR major OR minor (the headline metric)
  - is_serious   : fatal OR major
  - is_speeding  : SPEEDING_INVOLVED flag is set
"""

from pathlib import Path
import pandas as pd

# --- Paths. Resolved relative to the repo root, not the script location,
#     so running `python scripts/01_clean_crashes.py` works from either place.
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "data" / "raw" / "Midterm_Memo.xlsx"
OUT_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"

# --- DC bounding box. Anything outside these lat/lon bounds is
#     either bad geocoding or a crash logged from outside the district.
# Source: https://gist.github.com/jakebathman/719e8416191ba14bb6e700fc2d5fccc5
DC_LAT_MIN, DC_LAT_MAX = 38.79, 39.00
DC_LON_MIN, DC_LON_MAX = -77.12, -76.91
DC_LAT_MIN, DC_LAT_MAX = 38.79, 39.00
DC_LON_MIN, DC_LON_MAX = -77.12, -76.91

# --- Date window for the analysis.
DATE_MIN = pd.Timestamp("2021-01-01")
DATE_MAX = pd.Timestamp("2026-12-31")

# --- The columns we actually need from the 66-column raw sheet.
USECOLS = [
    "REPORTDATE", "LATITUDE", "LONGITUDE", "WARD", "SPEEDING_INVOLVED",
    "FATAL_DRIVER", "FATAL_PEDESTRIAN", "FATAL_BICYCLIST",
    "FATALPASSENGER", "FATALOTHER",
    "MAJORINJURIES_DRIVER", "MAJORINJURIES_PEDESTRIAN", "MAJORINJURIES_BICYCLIST",
    "MAJORINJURIESPASSENGER", "MAJORINJURIESOTHER",
    "MINORINJURIES_DRIVER", "MINORINJURIES_PEDESTRIAN", "MINORINJURIES_BICYCLIST",
    "MINORINJURIESPASSENGER", "MINORINJURIESOTHER",
]

FATAL_COLS = ["FATAL_DRIVER", "FATAL_PEDESTRIAN", "FATAL_BICYCLIST",
              "FATALPASSENGER", "FATALOTHER"]
MAJOR_COLS = ["MAJORINJURIES_DRIVER", "MAJORINJURIES_PEDESTRIAN", "MAJORINJURIES_BICYCLIST",
              "MAJORINJURIESPASSENGER", "MAJORINJURIESOTHER"]
MINOR_COLS = ["MINORINJURIES_DRIVER", "MINORINJURIES_PEDESTRIAN", "MINORINJURIES_BICYCLIST",
              "MINORINJURIESPASSENGER", "MINORINJURIESOTHER"]


def main():
    print(f"Reading {RAW_PATH.name} ...")
    df = pd.read_excel(RAW_PATH, sheet_name="Crash_Raw", usecols=USECOLS)
    print(f"  Raw rows loaded: {len(df):,}")

    # --- Coerce types. Excel is loose with types; we force everything we
    #     expect to be numeric to be numeric, with bad values becoming NaN
    #     (and then 0 for the count columns). Dates get parsed and normalized
    #     to midnight so we can compare against window start/end dates cleanly.
    df["REPORTDATE"] = pd.to_datetime(df["REPORTDATE"], errors="coerce").dt.normalize()
    df["LATITUDE"] = pd.to_numeric(df["LATITUDE"], errors="coerce")
    df["LONGITUDE"] = pd.to_numeric(df["LONGITUDE"], errors="coerce")
    for col in FATAL_COLS + MAJOR_COLS + MINOR_COLS + ["SPEEDING_INVOLVED"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- Apply the two main filters: valid date window + inside DC.
    mask_date = df["REPORTDATE"].between(DATE_MIN, DATE_MAX)
    mask_box = (
        df["LATITUDE"].between(DC_LAT_MIN, DC_LAT_MAX)
        & df["LONGITUDE"].between(DC_LON_MIN, DC_LON_MAX)
    )
    print(f"  Valid date:    {mask_date.sum():,}")
    print(f"  Inside DC box: {mask_box.sum():,}")
    print(f"  Both:          {(mask_date & mask_box).sum():,}")

    df = df[mask_date & mask_box].copy()

    # --- Build the severity flags. A crash counts as an "injury crash"
    #     if any of its fatal/major/minor injury columns is non-zero.
    df["is_fatal"] = df[FATAL_COLS].sum(axis=1) > 0
    df["is_major"] = df[MAJOR_COLS].sum(axis=1) > 0
    df["is_minor"] = df[MINOR_COLS].sum(axis=1) > 0
    df["is_injury"] = df["is_fatal"] | df["is_major"] | df["is_minor"]
    df["is_serious"] = df["is_fatal"] | df["is_major"]
    df["is_speeding"] = df["SPEEDING_INVOLVED"] > 0

    # --- Drop the now-redundant per-role columns; keep only what downstream
    #     scripts need. This also shrinks the pickle substantially.
    keep = [
        "REPORTDATE", "LATITUDE", "LONGITUDE", "WARD",
        "is_fatal", "is_major", "is_minor",
        "is_injury", "is_serious", "is_speeding",
    ]
    df = df[keep].reset_index(drop=True)

    # --- Quick summary so the terminal output tells us what happened.
    print()
    print(f"Cleaned crashes:       {len(df):,}")
    print(f"  Date range:          {df['REPORTDATE'].min().date()} to {df['REPORTDATE'].max().date()}")
    print(f"  Injury crashes:      {df['is_injury'].sum():,}")
    print(f"  Serious (fatal+maj): {df['is_serious'].sum():,}")
    print(f"  Fatal crashes:       {df['is_fatal'].sum():,}")
    print(f"  Speeding-involved:   {df['is_speeding'].sum():,}")

    # --- Save.
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(OUT_PATH)
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}")

    # --- Also save a human-readable xlsx so reporters/editors can inspect
    #     the cleaned crash data without needing Python.
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "01_crashes_clean.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
