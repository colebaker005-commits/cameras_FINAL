"""
04_placebo_test.py
------------------
Re-runs the core analysis with each camera's install date shifted back by
exactly one year. This is the most important validity check in the pipeline.
 
The logic: if the apparent before/after effect is really caused by the
camera, then pretending the camera was installed in a year when it didn't
yet exist should produce a result close to zero. If the placebo result
looks similar to the real result, the effect was already happening at
those sites before the camera went up -- not because of the camera.
 
How the distance check works:
    Same as script 03. geopy.distance.distance() takes two GPS coordinate
    pairs and returns the real-world distance in meters. We keep any crash
    within 200m of the camera.
 
Input:
    data/processed/crashes_clean.pkl
    data/processed/cameras_eligible.pkl
 
Output:
    data/processed/placebo_results.pkl
    outputs/step_outputs/04_placebo_results.xlsx
"""
 
from pathlib import Path
import pandas as pd
from geopy.distance import distance as geo_distance
 
REPO_ROOT    = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
CAMERAS_PATH = REPO_ROOT / "data" / "processed" / "cameras_eligible.pkl"
OUT_PATH     = REPO_ROOT / "data" / "processed" / "placebo_results.pkl"
 
BUFFER_M          = 200
WINDOW_DAYS       = 365
PLACEBO_SHIFT_DAYS = 365   # how far back to shift the install date
OUTCOMES          = ["all", "injury", "serious", "fatal", "speeding"]
 
 
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
    print(f"  This will take a few minutes.\n")
 
    results = []
 
    for cam_num, (_, cam) in enumerate(cameras.iterrows(), start=1):
        cam_lat      = cam["CAMERA_LATITUDE"]
        cam_lon      = cam["CAMERA_LONGITUDE"]
        real_install = cam["START_DATE"]
 
        # --- Shift the install date back by one year.
        #     Everything else is identical to script 03 -- same windows,
        #     same distance check, same outcome counts. The only difference
        #     is this fake install date.
        fake_install = real_install - pd.Timedelta(days=PLACEBO_SHIFT_DAYS)
 
        pre_start  = fake_install - pd.Timedelta(days=WINDOW_DAYS)
        pre_end    = fake_install
        post_start = fake_install + pd.Timedelta(days=1)
        post_end   = fake_install + pd.Timedelta(days=WINDOW_DAYS)
 
        # --- Filter crashes to each window (citywide).
        pre_crashes  = crashes[(crashes["REPORTDATE"] >= pre_start) &
                               (crashes["REPORTDATE"] <  pre_end)]
        post_crashes = crashes[(crashes["REPORTDATE"] >= post_start) &
                               (crashes["REPORTDATE"] <= post_end)]
 
        # --- Measure distance from each crash to this camera.
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
 
        # --- Keep only crashes within 200m.
        pre_nearby  = pre_crashes[pre_distances  <= BUFFER_M]
        post_nearby = post_crashes[post_distances <= BUFFER_M]
 
        # --- Build this camera's result row.
        rec = {
            "camera_code":   cam["ENFORCEMENT_SPACE_CODE"],
            "location":      cam["LOCATION_DESCRIPTION"],
            "type":          cam["ENFORCEMENT_TYPE"],
            "real_install":  real_install.date(),
            "fake_install":  fake_install.date(),
            "ward":          cam["WARD"],
        }
 
        # --- Counts near the camera (placebo windows).
        for outcome in OUTCOMES:
            rec[f"placebo_nearby_{outcome}_pre"]  = crashes_matching(pre_nearby,  outcome)
            rec[f"placebo_nearby_{outcome}_post"] = crashes_matching(post_nearby, outcome)
 
        # --- Citywide counts for the same placebo windows.
        for outcome in OUTCOMES:
            rec[f"placebo_city_{outcome}_pre"]  = crashes_matching(pre_crashes,  outcome)
            rec[f"placebo_city_{outcome}_post"] = crashes_matching(post_crashes, outcome)
 
        results.append(rec)
 
        if cam_num % 10 == 0:
            print(f"  {cam_num}/{len(cameras)} cameras done ...")
 
    print(f"  All {len(cameras)} cameras processed.\n")
 
    res = pd.DataFrame(results)
 
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.to_pickle(OUT_PATH)
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
 
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "04_placebo_results.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")
 
    # --- Preview: placebo DiD by camera type, injury crashes.
    #     If the real analysis captures a genuine camera effect, these
    #     numbers should be close to zero.
    print("\nPlacebo preview: 200m buffer, INJURY crashes")
    print(f"  {'Type':20s} {'n':>3s}  {'nearby%':>8s} {'city%':>7s}  {'placebo DiD':>11s}")
    for t in res["type"].unique():
        sub  = res[res["type"] == t]
        pre  = sub["placebo_nearby_injury_pre"].sum()
        post = sub["placebo_nearby_injury_post"].sum()
        cpre  = sub["placebo_city_injury_pre"].sum()
        cpost = sub["placebo_city_injury_post"].sum()
        zpct = (post - pre) / pre * 100 if pre else float("nan")
        cpct = (cpost - cpre) / cpre * 100 if cpre else float("nan")
        print(f"  {t:20s} {len(sub):3d}  {zpct:+7.1f}% {cpct:+6.1f}%  {zpct - cpct:+9.1f}")
 
 
if __name__ == "__main__":
    main()