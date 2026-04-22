"""
04_placebo_test.py
------------------
Re-runs the core analysis with each camera's install date shifted back by
exactly one year. This is the single most important validity check in the
whole pipeline.

The logic: if the apparent before/after effect is really caused by the
camera, then pretending the camera was installed in a year when it didn't
yet exist should produce a null result (DiD ~ 0). If the placebo DiD looks
similar to the real DiD, the effect was already happening at those sites —
regression to the mean, not the camera.

Input:
    data/processed/crashes_clean.pkl
    data/processed/cameras_eligible.pkl

Output:
    data/processed/placebo_results.pkl

Design note: we use only the 200m buffer here. The placebo's job is to
validate or invalidate the headline 200m finding; the sensitivity checks
at 150m and 250m are a separate concern handled in the main analysis.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

REPO_ROOT = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
CAMERAS_PATH = REPO_ROOT / "data" / "processed" / "cameras_eligible.pkl"
OUT_PATH = REPO_ROOT / "data" / "processed" / "placebo_results.pkl"

BUFFER_M = 200
WINDOW_DAYS = 365
PLACEBO_SHIFT_DAYS = 365        # how far back to shift the install date
OUTCOMES = ["all", "injury", "serious", "fatal", "speeding"]
R_EARTH_M = 6_371_000.0


def meters_to_radians(m):
    return m / R_EARTH_M


def outcome_mask(df, outcome):
    if outcome == "all":
        return np.ones(len(df), dtype=bool)
    return df[f"is_{outcome}"].values


def main():
    print("Loading cleaned data ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    cameras = pd.read_pickle(CAMERAS_PATH)

    # --- Only cameras whose PLACEBO windows fit inside the crash data can
    #     participate. The placebo "pre" window starts 2 years before the
    #     real install date, so the camera's real install date needs to be
    #     at least 2 years after the earliest crash.
    min_crash = crashes["REPORTDATE"].min()
    placebo_needs = pd.Timedelta(days=PLACEBO_SHIFT_DAYS + WINDOW_DAYS)
    eligible = cameras[cameras["START_DATE"] - placebo_needs >= min_crash].copy().reset_index(drop=True)
    print(f"  {len(cameras)} cameras total, {len(eligible)} eligible for placebo")

    # --- Spatial index (same as script 03).
    crash_rad = np.radians(crashes[["LATITUDE", "LONGITUDE"]].values)
    tree = BallTree(crash_rad, metric="haversine")
    crash_dates = crashes["REPORTDATE"].values.astype("datetime64[D]")

    print("\nRunning placebo analysis (install dates shifted back 1 year) ...")
    results = []
    for i, cam in eligible.iterrows():
        lat = cam["CAMERA_LATITUDE"]
        lon = cam["CAMERA_LONGITUDE"]
        real_install = cam["START_DATE"]
        fake_install = real_install - pd.Timedelta(days=PLACEBO_SHIFT_DAYS)

        # --- Same window structure as the real analysis, just centered on the
        #     fake install date.
        pre_start = np.datetime64((fake_install - pd.Timedelta(days=WINDOW_DAYS)).date(), "D")
        pre_end = np.datetime64(fake_install.date(), "D")
        post_start = np.datetime64((fake_install + pd.Timedelta(days=1)).date(), "D")
        post_end = np.datetime64((fake_install + pd.Timedelta(days=WINDOW_DAYS)).date(), "D")

        mask_pre = (crash_dates >= pre_start) & (crash_dates < pre_end)
        mask_post = (crash_dates >= post_start) & (crash_dates <= post_end)

        rec = {
            "camera_code": cam["ENFORCEMENT_SPACE_CODE"],
            "type": cam["ENFORCEMENT_TYPE"],
        }

        cam_point = np.radians([[lat, lon]])
        nearby_idx = tree.query_radius(cam_point, r=meters_to_radians(BUFFER_M))[0]

        if len(nearby_idx) == 0:
            for outcome in OUTCOMES:
                rec[f"placebo_{outcome}_pre"] = 0
                rec[f"placebo_{outcome}_post"] = 0
        else:
            # --- With just one buffer to check, we can use the tree's exact-
            #     radius result directly; no need to compute distances.
            neigh_pre = mask_pre[nearby_idx]
            neigh_post = mask_post[nearby_idx]
            for outcome in OUTCOMES:
                om = outcome_mask(crashes, outcome)[nearby_idx]
                rec[f"placebo_{outcome}_pre"] = int((neigh_pre & om).sum())
                rec[f"placebo_{outcome}_post"] = int((neigh_post & om).sum())

        # --- Citywide counts for the placebo windows (needed to compute DiD).
        for outcome in OUTCOMES:
            om = outcome_mask(crashes, outcome)
            rec[f"placebo_city_{outcome}_pre"] = int((mask_pre & om).sum())
            rec[f"placebo_city_{outcome}_post"] = int((mask_post & om).sum())

        results.append(rec)

    res = pd.DataFrame(results)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.to_pickle(OUT_PATH)
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}  ({len(res)} rows)")

    # --- Human-readable xlsx of the placebo result matrix.
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "04_placebo_results.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")

    # --- Preview: placebo DiD by camera type, injury crashes.
    #     If the real analysis is capturing a genuine camera effect, these
    #     numbers should be close to zero. Where they aren't, the real finding
    #     is partly or fully regression to the mean.
    print("\nPlacebo preview: 200m buffer, INJURY crashes")
    print(f"  {'Type':20s} {'n':>3s}  {'zone%':>7s} {'city%':>7s}  {'plac.DiD':>8s}")
    for t in res["type"].unique():
        sub = res[res["type"] == t]
        pre, post = sub["placebo_injury_pre"].sum(), sub["placebo_injury_post"].sum()
        cpre, cpost = sub["placebo_city_injury_pre"].sum(), sub["placebo_city_injury_post"].sum()
        zpct = (post - pre) / pre * 100 if pre else float("nan")
        cpct = (cpost - cpre) / cpre * 100 if cpre else float("nan")
        print(f"  {t:20s} {len(sub):3d}  {zpct:+6.1f}% {cpct:+6.1f}%  {zpct - cpct:+6.1f}")


if __name__ == "__main__":
    main()
