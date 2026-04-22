#!/bin/bash
# run_pipeline.sh — run the full analysis end-to-end.
# Usage:  bash run_pipeline.sh
set -e    # stop on first error

cd "$(dirname "$0")"

echo "=== 01: Clean crash data ==="
python scripts/01_clean_crashes.py
echo

echo "=== 02: Filter eligible cameras ==="
python scripts/02_filter_cameras.py
echo

echo "=== 03: Run spatial + DiD analysis ==="
python scripts/03_run_analysis.py
echo

echo "=== 04: Placebo test ==="
python scripts/04_placebo_test.py
echo

echo "=== 05: Make figures ==="
python scripts/05_make_figures.py
echo

echo "=== 06: Build Excel workbook ==="
python scripts/06_build_workbook.py
echo

echo "=== Pipeline complete ==="
echo "Outputs in: outputs/"
