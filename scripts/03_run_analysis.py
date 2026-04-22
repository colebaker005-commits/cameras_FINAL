"""
03_run_analysis.py
------------------
The core analysis. For every eligible camera, counts crashes within a
200-meter radius in the 365 days before installation and the 365 days after.
Also records citywide crash counts for the same windows so we can compute
the difference-in-differences (DiD).
 
How the distance check works:
    geopy.distance.distance() takes two GPS coordinate pairs and returns
    the real-world distance between them. We give it the camera's lat/lon
    and each crash's lat/lon, ask for the result in meters, and check if
    it's under 200. That's it.
 
Input:
    data/processed/crashes_clean.pkl
    data/processed/cameras_eligible.pkl
 
Output:
    data/processed/per_camera_results.pkl
    outputs/step_outputs/03_per_camera_results.xlsx
"""
 
from pathlib import Path
import pandas as pd
import numpy as np
from geopy.distance import distance as geo_distance
 
REPO_ROOT = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
CAMERAS_PATH = REPO_ROOT / "data" / "processed" / "cameras_eligible.pkl"
OUT_PATH     = REPO_ROOT / "data" / "processed" / "per_camera_results.pkl"
 
BUFFER_M   = 200
WINDOW_DAYS = 365
OUTCOMES   = ["all", "injury", "serious", "fatal", "speeding"]
 
 
def crashes_matching(crash_subset, outcome):
    """Return the number of crashes in crash_subset that match the outcome."""
    if outcome == "all":
        return len(crash_subset)
    return int(crash_subset[f"is_{outcome}"].sum())
 
 
def main():
    print("Loading data ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    cameras = pd.read_pickle(CAMERAS_PATH)
    print(f"  {len(crashes):,} crashes, {len(cameras)} cameras")
    print(f"  This will take a few minutes -- checking every crash against every camera.\n")
 
    results = []
 
    for cam_num, (_, cam) in enumerate(cameras.iterrows(), start=1):
        cam_lat      = cam["CAMERA_LATITUDE"]
        cam_lon      = cam["CAMERA_LONGITUDE"]
        install_date = cam["START_DATE"]
 
        # --- Define the before and after date windows.
        #     Pre:  the 365 days leading up to (but not including) install day
        #     Post: the 365 days starting the day after install
        pre_start  = install_date - pd.Timedelta(days=WINDOW_DAYS)
        pre_end    = install_date
        post_start = install_date + pd.Timedelta(days=1)
        post_end   = install_date + pd.Timedelta(days=WINDOW_DAYS)
 
        # --- Filter the crash dataset to each window (citywide for now).
        pre_crashes  = crashes[(crashes["REPORTDATE"] >= pre_start) &
                               (crashes["REPORTDATE"] <  pre_end)]
        post_crashes = crashes[(crashes["REPORTDATE"] >= post_start) &
                               (crashes["REPORTDATE"] <= post_end)]
 
        # --- Measure how far each crash is from this camera.
        #     geo_distance((lat1, lon1), (lat2, lon2)).meters returns
        #     the real-world distance in meters.
        pre_distances  = pre_crashes.apply(
            lambda row: geo_distance(
                (cam_lat, cam_lon),
                (row["LATITUDE"], row["LONGITUDE"])
            ).meters, axis=1)
 
        post_distances = post_crashes.apply(
            lambda row: geo_distance(
                (cam_lat, cam_lon),
                (row["LATITUDE"], row["LONGITUDE"])
            ).meters, axis=1)
 
        # --- Keep only crashes within the 200m buffer.
        pre_nearby  = pre_crashes[pre_distances   <= BUFFER_M]
        post_nearby = post_crashes[post_distances <= BUFFER_M]
 
        # --- Build this camera's result row.
        rec = {
            "camera_code":  cam["ENFORCEMENT_SPACE_CODE"],
            "location":     cam["LOCATION_DESCRIPTION"],
            "type":         cam["ENFORCEMENT_TYPE"],
            "install_date": install_date.date(),
            "ward":         cam["WARD"],
            "lat":          cam_lat,
            "lon":          cam_lon,
        }
 
        # --- Count crashes near the camera by outcome type.
        for outcome in OUTCOMES:
            rec[f"nearby_{outcome}_pre"]  = crashes_matching(pre_nearby,  outcome)
            rec[f"nearby_{outcome}_post"] = crashes_matching(post_nearby, outcome)
 
        # --- Count crashes citywide for the same windows.
        #     These give us the city trend to compare against.
        for outcome in OUTCOMES:
            rec[f"citywide_{outcome}_pre"]  = crashes_matching(pre_crashes,  outcome)
            rec[f"citywide_{outcome}_post"] = crashes_matching(post_crashes, outcome)
 
        results.append(rec)
 
        if cam_num % 10 == 0:
            print(f"  {cam_num}/{len(cameras)} cameras done ...")
 
    print(f"  All {len(cameras)} cameras processed.\n")
 
    res = pd.DataFrame(results)
 
    # --- Compute percent change for nearby and citywide counts.
    def pct_change(pre, post):
        return np.where(pre > 0, (post - pre) / pre * 100, np.nan)
 
    for outcome in OUTCOMES:
        res[f"nearby_{outcome}_pct"]   = pct_change(
            res[f"nearby_{outcome}_pre"],   res[f"nearby_{outcome}_post"])
        res[f"citywide_{outcome}_pct"] = pct_change(
            res[f"citywide_{outcome}_pre"], res[f"citywide_{outcome}_post"])
 
    # --- DiD: nearby % change minus citywide % change.
    #     Negative = crashes near camera fell more than citywide trend.
    for outcome in OUTCOMES:
        res[f"did_{outcome}"] = (res[f"nearby_{outcome}_pct"]
                                 - res[f"citywide_{outcome}_pct"])
 
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.to_pickle(OUT_PATH)
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
 
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "03_per_camera_results.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")
 
    # --- Headline preview.
    print("\nHeadline: 200m buffer, INJURY crashes")
    print(f"  {'Type':20s} {'n':>3s}  {'pre':>5s} {'post':>5s}  {'nearby%':>8s} {'city%':>7s}  {'DiD':>6s}")
    for t in res["type"].unique():
        sub  = res[res["type"] == t]
        pre  = sub["nearby_injury_pre"].sum()
        post = sub["nearby_injury_post"].sum()
        cpre  = sub["citywide_injury_pre"].sum()
        cpost = sub["citywide_injury_post"].sum()
        zpct = (post - pre) / pre * 100 if pre else float("nan")
        cpct = (cpost - cpre) / cpre * 100 if cpre else float("nan")
        print(f"  {t:20s} {len(sub):3d}  {pre:5d} {post:5d}"
              f"  {zpct:+7.1f}% {cpct:+6.1f}%  {zpct - cpct:+5.1f}")
 
 
if __name__ == "__main__":
    main()
 