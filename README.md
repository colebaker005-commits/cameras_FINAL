# DC Traffic Camera Safety Impact Data

Measuring the difference in crash rates within 200 meters of every active DC traffic camera, using a difference-in-differences analysis

## Whaat's in this repo

- `scripts/` — the scripts that brought raw data to the analysis level, made with aid from Claude
- `data/raw/` — the original Excel workbook (public DDOT crash and camera data).
- `outputs/` — results (analysis, figures). 

## Data sources

- **Crashes in DC** — [DDOT open data](https://opendata.dc.gov/datasets/crashes-in-dc), filtered to 2021–2026.
- **Traffic Cameras** — [DDOT open data](https://opendata.dc.gov/datasets/DCGIS::traffic-camera/about), all camera locations and start dates.
- **Lat and Lon bounds for DC** - [Github data](https://gist.github.com/jakebathman/719e8416191ba14bb6e700fc2d5fccc5)

The raw file in `data/raw/Midterm_Memo.xlsx` is a snapshot of both datasets combined into one workbook for this analysis.

## Brief Method

For each of the 283 eligible cameras, this analysis compares crashes within a 200 meter range of the camera 365 days before the cameras installation and 365 days after the installation. Both pre and post crash data is compared to the citywide trend of crash data during the same period of time to gauge how it compares to the general crash trend in that time. using `(zone % change) − (citywide % change)`.

## How to run it

- Have Python 3.10
```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/dc-camera-analysis.git
cd dc-camera-analysis

# Install Python packages
pip install -r requirements.txt
```

### Run the pipeline

The scripts are numbered so they run in order. You can run them one at a time:

```bash
python scripts/01_clean_crashes.py
python scripts/02_filter_cameras.py
python scripts/03_run_analysis.py
python scripts/04_make_figures.py
python scripts/05_build_workbook.py
```

Or all at once:

```bash
bash run_pipeline.sh
```

## Project structure

```
dc-camera-analysis/
├── data/
│   ├── raw/                       source spreadsheet
│   └── processed/                 intermediate pickles (generated)
├── scripts/                       the 5-step pipeline
└── outputs/                       final results (generated)
    ├── figures/                   the charts
    ├── step_outputs/              one spreadsheet per step
    └── camera_analysis_results.xlsx    the full analysis 
```

### Outputs from each script

| Script | Output file |
|---|---|
| 01 clean crashes | `outputs/step_outputs/01_crashes_clean.xlsx` |
| 02 filter cameras | `outputs/step_outputs/02_cameras_eligible.xlsx` |
| 03 run analysis | `outputs/step_outputs/03_per_camera_results.xlsx` |
| 04 make figures | `outputs/figures/*.png` + `outputs/step_outputs/05_figure_did_summary.xlsx` |
| 05 build workbook | `outputs/camera_analysis_results.xlsx` |

## Limitations

This is journalism analysis, not peer-reviewed research. 

The data does not capture if the cameras actually CAUSE the reduced crashes and do not take into account if other factors, such as police presence, speed limits, or general public interest played a role in reduced or increased crash rates.

## License

Data is public domain (DDOT open data). Code is MIT-licensed.
