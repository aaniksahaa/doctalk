#!/usr/bin/env python3
"""
Collect and aggregate diarization metrics from prediction directories.

Searches for metrics CSVs created by run_diarization.py or recalc_metrics.py
and outputs:
  1. all_metrics.csv - All individual results (header + all rows)
  2. summary.csv     - Model-wise averages

Usage:
    python collect_metrics.py --data_root dataset --output_dir results
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


# All metric columns we expect (extended set).
METRIC_COLS = [
    "model", "der", "false_alarm", "missed_detection", "confusion",
    "correct", "rtf", "inference_time", "audio_duration", "filepath",
]

# Numeric columns to average in the summary.
NUMERIC_COLS = [
    "der", "false_alarm", "missed_detection", "confusion",
    "correct", "rtf", "inference_time",
]


def find_metrics_files(data_root: Path) -> List[Tuple[Path, str]]:
    """
    Recursively find all metrics CSV files in prediction/*/metrics/ directories.

    Returns list of tuples: (metrics_csv_path, model_name)
    """
    metrics_files = []

    for root, dirs, _ in os.walk(data_root):
        root_path = Path(root)

        # Look for metrics directory under prediction/<model>/
        if root_path.name == "metrics":
            parent = root_path.parent
            if parent.parent.name == "prediction":
                model_name = parent.name

                for csv_file in sorted(root_path.glob("*.csv")):
                    metrics_files.append((csv_file, model_name))

    return metrics_files


def read_metrics_csv(csv_path: Path) -> Dict:
    """Read a single metrics CSV file and return the data row as dict."""
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                return rows[0]  # Single row expected
    except Exception as ex:
        print(f"Warning: Could not read {csv_path}: {ex}", file=sys.stderr)
    return {}


def safe_float(value, default=-1.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    if value is None or str(value).strip().upper() in ("N/A", ""):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def main():
    parser = argparse.ArgumentParser(
        description="Collect and aggregate diarization metrics"
    )
    parser.add_argument(
        "--data_root", "-d",
        required=True,
        help="Root directory to search for metrics"
    )
    parser.add_argument(
        "--output_dir", "-o",
        default=None,
        help="Output directory for aggregated CSVs (default: data_root)"
    )
    args = parser.parse_args()

    data_root = Path(args.data_root).resolve()
    if not data_root.exists():
        print(f"Data root not found: {data_root}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else data_root
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all metrics files
    metrics_files = find_metrics_files(data_root)

    if not metrics_files:
        print(f"No metrics files found in {data_root}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(metrics_files)} metrics files")

    # Collect all metrics
    all_rows = []
    # model -> column -> { sum, count }
    model_stats = defaultdict(lambda: defaultdict(lambda: {"sum": 0.0, "count": 0}))

    for csv_path, model in metrics_files:
        data = read_metrics_csv(csv_path)

        if not data:
            continue

        # Ensure consistent model name
        if "model" not in data:
            data["model"] = model

        # Extract relative filepath for readability
        try:
            rel_path = csv_path.relative_to(data_root)
        except ValueError:
            rel_path = csv_path

        data["metrics_file"] = str(rel_path)

        all_rows.append(data)

        # Accumulate numeric columns for per-model averages
        for col in NUMERIC_COLS:
            val = safe_float(data.get(col))
            if val >= 0:  # skip error markers (-1)
                model_stats[model][col]["sum"] += val
                model_stats[model][col]["count"] += 1

    if not all_rows:
        print("No valid metrics data found", file=sys.stderr)
        sys.exit(1)

    # Sort by model, then by filepath
    all_rows.sort(key=lambda x: (x.get("model", ""), x.get("filepath", "")))

    # Write all_metrics.csv
    all_metrics_path = output_dir / "all_metrics.csv"
    fieldnames = METRIC_COLS + ["metrics_file"]

    with open(all_metrics_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {all_metrics_path}")

    # Calculate and write summary.csv
    summary_rows = []

    for model in sorted(model_stats.keys()):
        stats = model_stats[model]
        row = {"model": model}

        # File counts
        der_count = stats["der"]["count"]
        total_count = max(
            stats[c]["count"] for c in NUMERIC_COLS if stats[c]["count"] > 0
        ) if any(stats[c]["count"] > 0 for c in NUMERIC_COLS) else 0

        row["total_files"] = total_count
        row["valid_der_files"] = der_count

        for col in NUMERIC_COLS:
            s = stats[col]
            if s["count"] > 0:
                avg = s["sum"] / s["count"]
                row[f"mean_{col}"] = f"{avg:.6f}"
            else:
                row[f"mean_{col}"] = "N/A"

        summary_rows.append(row)

    summary_path = output_dir / "summary.csv"
    summary_fields = (
        ["model"]
        + [f"mean_{c}" for c in NUMERIC_COLS]
        + ["total_files", "valid_der_files"]
    )

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote summary to {summary_path}")

    # Print summary to console
    print()
    print("=" * 100)
    print("MODEL SUMMARY")
    print("=" * 100)
    hdr = (
        f"{'Model':<8} {'DER':>8} {'FA%':>8} {'Miss%':>8} "
        f"{'Conf%':>8} {'Correct%':>9} {'RTF':>8} "
        f"{'Time(s)':>9} {'Files':>6}"
    )
    print(hdr)
    print("-" * 100)

    for row in summary_rows:
        def fmt(key, pct=False):
            v = row.get(key, "N/A")
            if v == "N/A":
                return "N/A"
            val = float(v)
            if pct:
                return f"{val * 100:.2f}%"
            return f"{val:.4f}"

        print(
            f"{row['model']:<8} "
            f"{fmt('mean_der', pct=True):>8} "
            f"{fmt('mean_false_alarm', pct=True):>8} "
            f"{fmt('mean_missed_detection', pct=True):>8} "
            f"{fmt('mean_confusion', pct=True):>8} "
            f"{fmt('mean_correct', pct=True):>9} "
            f"{fmt('mean_rtf'):>8} "
            f"{fmt('mean_inference_time'):>9} "
            f"{row['total_files']:>6}"
        )

    print()


if __name__ == "__main__":
    main()
