#!/bin/bash
# run_pipeline.sh — run the full analysis end-to-end.
# Usage:  bash run_pipeline.sh
set -e    # stop on first error

cd "$(dirname "$0")"

echo "=== 01: Clean crash data ==="
python3 scripts/01_clean_crashes.py
echo

echo "=== 02: Filter eligible cameras ==="
python3 scripts/02_filter_cameras.py
echo

echo "=== 03: Run spatial + DiD analysis ==="
python3 scripts/03_run_analysis.py
echo

echo "=== 04: Placebo test ==="
python3 scripts/04_placebo_test.py
echo

echo "=== 05: Make figures ==="
python3 scripts/05_make_figures.py
echo

echo "=== 06: Build Excel workbook ==="
python3 scripts/06_build_workbook.py
echo

echo "=== Pipeline complete ==="
echo "Outputs in: outputs/"
