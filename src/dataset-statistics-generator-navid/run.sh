#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================================="
echo " 🚀 INITIALIZING TELEMEDBN STATISTICS PIPELINE 🚀 "
echo "=========================================================="
echo ""

# ==========================================
# ⚙️ CONFIGURATION: SET YOUR FOLDERS HERE
# ==========================================

# --- INPUT LOCATIONS ---
CORE_DATASET_DIR="../../../dataset"
DOWNSTREAM_DATASET_DIR="../../../downstream-datasets-v1/downstream-datasets"

# --- OUTPUT LOCATIONS ---
CORE_CSV_OUT="statistics-results"
CORE_SUMMARY_OUT="."
DOWNSTREAM_CSV_OUT="downstream_results"

# ==========================================
# 🚀 PIPELINE EXECUTION ENGINE
# ==========================================

echo "▶️  STEP 1: Extracting Core Dataset Statistics"
echo "💻 Executing: python dataset_stats_generator.py"
python dataset_stats_generator.py --data-dir "$CORE_DATASET_DIR" --output-dir "$CORE_CSV_OUT"
echo "----------------------------------------------------------"

echo "▶️  STEP 2: Generating Core Summary Tables (.txt & .tex)"
echo "💻 Executing: python generate_core_summary.py"
python generate_core_summary.py --input-dir "$CORE_CSV_OUT" --output-dir "$CORE_SUMMARY_OUT"
echo "----------------------------------------------------------"

echo "▶️  STEP 3: Plotting Core Dataset Figures"
echo "💻 Executing: python plot_datasets_stats.py"
python plot_datasets_stats.py
echo "----------------------------------------------------------"

echo "▶️  STEP 4: Extracting Downstream Benchmark Statistics"
echo "💻 Executing: python generate_downstream_summary.py"
python generate_downstream_summary.py --downstream-dir "$DOWNSTREAM_DATASET_DIR" --output-dir "$DOWNSTREAM_CSV_OUT"
echo "----------------------------------------------------------"

echo "▶️  STEP 5: Plotting Downstream Appendix Figures"
echo "💻 Executing: python plot_downstream_stats.py"
python plot_downstream_stats.py
echo "----------------------------------------------------------"

echo ""
echo "🎉 🎉 🎉 PIPELINE COMPLETE! ALL DATA, TABLES, AND PLOTS ARE READY! 🎉 🎉 🎉"
echo ""