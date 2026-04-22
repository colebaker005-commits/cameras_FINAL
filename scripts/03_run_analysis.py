"""
03_run_analysis.py
------------------
The core analysis. For every eligible camera, counts crashes in the 365-day
window before install and the 365-day window after install, at three buffer
radii (150m, 200m, 250m) and in a 200-500m donut ring, for five outcome
variables (all / injury / serious / fatal / speeding). Also records the
citywide counts in the same windows for the difference-in-differences math.

Input:
    data/processed/crashes_clean.pkl
    data/processed/cameras_eligible.pkl

Output:
    data/processed/per_camera_results.pkl

Why a BallTree? With 283 cameras and 75,400 crashes, a naive pairwise
distance calculation is 21 million comparisons. A spatial index (scikit-learn's
BallTree with haversine distance) brings that down to ~20 seconds by pruning
obvious non-matches — it organizes the crashes into nested spherical regions
so we only check crashes that are plausibly near each camera.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

REPO_ROOT = Path(__file__).resolve().parent.parent
CRASHES_PATH = REPO_ROOT / "data" / "processed" / "crashes_clean.pkl"
CAMERAS_PATH = REPO_ROOT / "data" / "processed" / "cameras_eligible.pkl"
OUT_PATH = REPO_ROOT / "data" / "processed" / "per_camera_results.pkl"

# --- Design constants. Change any of these and re-run the whole pipeline
#     to see how sensitive the results are.
BUFFERS_M = [150, 200, 250]        # three radii for sensitivity
DONUT_INNER_M = 200                # donut ring: everything from 200m...
DONUT_OUTER_M = 500                # ...out to 500m, to detect displacement
WINDOW_DAYS = 365                  # pre and post window length
OUTCOMES = ["all", "injury", "serious", "fatal", "speeding"]

# --- Earth's radius in meters, used to convert between meter distances and
#     the radian distances that haversine math needs.
R_EARTH_M = 6_371_000.0


def meters_to_radians(m):
    """Convert a great-circle distance in meters to radians on a unit sphere."""
    return m / R_EARTH_M


def outcome_mask(df, outcome):
    """Boolean array: which crashes count for this outcome variable."""
    if outcome == "all":
        return np.ones(len(df), dtype=bool)
    return df[f"is_{outcome}"].values


def main():
    print("Loading cleaned crash and camera data ...")
    crashes = pd.read_pickle(CRASHES_PATH)
    cameras = pd.read_pickle(CAMERAS_PATH)
    print(f"  {len(crashes):,} crashes, {len(cameras)} cameras")

    # --- Build the spatial index once. BallTree wants coordinates in radians
    #     for haversine (great-circle) distance.
    print("\nBuilding spatial index (BallTree with haversine metric) ...")
    crash_rad = np.radians(crashes[["LATITUDE", "LONGITUDE"]].values)
    tree = BallTree(crash_rad, metric="haversine")

    # --- Precompute a numpy array of crash dates as datetime64[D].
    #     Comparing datetime64 arrays is orders of magnitude faster than
    #     comparing pandas Timestamps in a Python loop.
    crash_dates = crashes["REPORTDATE"].values.astype("datetime64[D]")

    print("\nRunning per-camera analysis ...")
    results = []
    largest_buffer_m = max(max(BUFFERS_M), DONUT_OUTER_M)

    for i, cam in cameras.iterrows():
        lat = cam["CAMERA_LATITUDE"]
        lon = cam["CAMERA_LONGITUDE"]
        install = cam["START_DATE"]

        # --- Define the two date windows. Both exclude the install day itself
        #     (a crash ON the install day doesn't clearly fit in either side).
        pre_start = np.datetime64((install - pd.Timedelta(days=WINDOW_DAYS)).date(), "D")
        pre_end = np.datetime64(install.date(), "D")                        # exclusive upper bound
        post_start = np.datetime64((install + pd.Timedelta(days=1)).date(), "D")
        post_end = np.datetime64((install + pd.Timedelta(days=WINDOW_DAYS)).date(), "D")

        mask_pre = (crash_dates >= pre_start) & (crash_dates < pre_end)
        mask_post = (crash_dates >= post_start) & (crash_dates <= post_end)

        # --- Start the result row with the camera's metadata.
        rec = {
            "camera_code": cam["ENFORCEMENT_SPACE_CODE"],
            "location": cam["LOCATION_DESCRIPTION"],
            "type": cam["ENFORCEMENT_TYPE"],
            "install_date": install.date(),
            "ward": cam["WARD"],
            "lat": lat,
            "lon": lon,
        }

        # --- Query the tree once, for the largest radius we'll need. Pulling
        #     all crashes within DONUT_OUTER_M (500m) means we can filter down
        #     to 150/200/250m by comparing exact distances, without a second
        #     tree query per buffer.
        cam_point = np.radians([[lat, lon]])
        nearby_idx = tree.query_radius(cam_point, r=meters_to_radians(largest_buffer_m))[0]

        if len(nearby_idx) == 0:
            # --- Rare case: no crashes anywhere near this camera. Fill zeros
            #     but still compute the citywide windows (those don't depend
            #     on the camera's buffer).
            for b in BUFFERS_M:
                for outcome in OUTCOMES:
                    rec[f"b{b}_{outcome}_pre"] = 0
                    rec[f"b{b}_{outcome}_post"] = 0
            for outcome in OUTCOMES:
                rec[f"donut_{outcome}_pre"] = 0
                rec[f"donut_{outcome}_post"] = 0
            for outcome in OUTCOMES:
                om = outcome_mask(crashes, outcome)
                rec[f"citywide_{outcome}_pre"] = int((mask_pre & om).sum())
                rec[f"citywide_{outcome}_post"] = int((mask_post & om).sum())
            results.append(rec)
            continue

        # --- Compute exact haversine distance (in meters) from the camera to
        #     each nearby crash. These are the distances we'll compare against
        #     the various buffer radii.
        neigh_coords = crash_rad[nearby_idx]
        dlat = neigh_coords[:, 0] - np.radians(lat)
        dlon = neigh_coords[:, 1] - np.radians(lon)
        a = (np.sin(dlat / 2) ** 2
             + np.cos(np.radians(lat)) * np.cos(neigh_coords[:, 0]) * np.sin(dlon / 2) ** 2)
        dist_m = 2 * R_EARTH_M * np.arcsin(np.sqrt(a))

        # --- Pre/post flags for just the nearby crashes.
        neigh_pre = mask_pre[nearby_idx]
        neigh_post = mask_post[nearby_idx]

        # --- Buffer counts. For each of the three radii, for each outcome,
        #     count how many nearby crashes fall (a) in-buffer, (b) in-window.
        for b in BUFFERS_M:
            in_buffer = dist_m <= b
            for outcome in OUTCOMES:
                om_all = outcome_mask(crashes, outcome)
                om_near = om_all[nearby_idx]
                rec[f"b{b}_{outcome}_pre"] = int((in_buffer & neigh_pre & om_near).sum())
                rec[f"b{b}_{outcome}_post"] = int((in_buffer & neigh_post & om_near).sum())

        # --- Donut ring: 200m < d <= 500m. If crashes get pushed out of the
        #     200m zone but show up here, that's displacement, not prevention.
        in_donut = (dist_m > DONUT_INNER_M) & (dist_m <= DONUT_OUTER_M)
        for outcome in OUTCOMES:
            om_all = outcome_mask(crashes, outcome)
            om_near = om_all[nearby_idx]
            rec[f"donut_{outcome}_pre"] = int((in_donut & neigh_pre & om_near).sum())
            rec[f"donut_{outcome}_post"] = int((in_donut & neigh_post & om_near).sum())

        # --- Citywide counts for this camera's exact windows. These give us
        #     the denominator for DiD: what was the overall city trend over
        #     the same 730-day span this camera spans?
        for outcome in OUTCOMES:
            om = outcome_mask(crashes, outcome)
            rec[f"citywide_{outcome}_pre"] = int((mask_pre & om).sum())
            rec[f"citywide_{outcome}_post"] = int((mask_post & om).sum())

        results.append(rec)

        # --- Progress indicator every 50 cameras. Handy for the 20-second run.
        if (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{len(cameras)} cameras processed")

    print(f"  Done: {len(results)} cameras processed")

    # --- Convert to DataFrame and compute derived metrics: percent changes
    #     and the DiD itself (at the headline 200m buffer).
    res = pd.DataFrame(results)

    def pct_change(pre, post):
        """Percent change from pre to post. Returns NaN if pre is zero."""
        return np.where(pre > 0, (post - pre) / pre * 100, np.nan)

    # --- Buffer % changes.
    for b in BUFFERS_M:
        for outcome in OUTCOMES:
            res[f"b{b}_{outcome}_pct"] = pct_change(res[f"b{b}_{outcome}_pre"],
                                                   res[f"b{b}_{outcome}_post"])
    # --- Donut % changes.
    for outcome in OUTCOMES:
        res[f"donut_{outcome}_pct"] = pct_change(res[f"donut_{outcome}_pre"],
                                                 res[f"donut_{outcome}_post"])
    # --- Citywide % changes.
    for outcome in OUTCOMES:
        res[f"citywide_{outcome}_pct"] = pct_change(res[f"citywide_{outcome}_pre"],
                                                    res[f"citywide_{outcome}_post"])

    # --- DiD at the headline buffer (200m): zone % minus citywide %.
    #     This is the single most important derived column.
    for outcome in OUTCOMES:
        res[f"did_200m_{outcome}"] = res[f"b200_{outcome}_pct"] - res[f"citywide_{outcome}_pct"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.to_pickle(OUT_PATH)
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}  ({len(res)} rows, {len(res.columns)} cols)")

    # --- Human-readable xlsx of the per-camera result matrix.
    xlsx_path = REPO_ROOT / "outputs" / "step_outputs" / "03_per_camera_results.xlsx"
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_excel(xlsx_path, index=False)
    print(f"Wrote {xlsx_path.relative_to(REPO_ROOT)}")

    # --- Headline preview so we can sanity-check the output immediately.
    print("\nHeadline preview: 200m buffer, INJURY crashes")
    print(f"  {'Type':20s} {'n':>3s}  {'pre':>5s} {'post':>5s}  {'zone%':>7s} {'city%':>7s}  {'DiD':>6s}")
    for t in res["type"].unique():
        sub = res[res["type"] == t]
        pre = sub["b200_injury_pre"].sum()
        post = sub["b200_injury_post"].sum()
        zpct = (post - pre) / pre * 100 if pre else float("nan")
        cpre = sub["citywide_injury_pre"].sum()
        cpost = sub["citywide_injury_post"].sum()
        cpct = (cpost - cpre) / cpre * 100 if cpre else float("nan")
        print(f"  {t:20s} {len(sub):3d}  {pre:5d} {post:5d}  {zpct:+6.1f}% {cpct:+6.1f}%  {zpct - cpct:+5.1f}")


if __name__ == "__main__":
    main()
