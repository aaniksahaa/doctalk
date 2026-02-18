#!/usr/bin/env python3
"""
Collect and aggregate diarization metrics from prediction directories.

Searches for metrics CSVs created by run_diarization.py and outputs:
1. all_metrics.csv - All individual results (header + all rows)
2. summary.csv - Model-wise averages

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


def find_metrics_files(data_root: Path) -> List[Tuple[Path, str]]:
    """
    Recursively find all metrics CSV files in prediction/*/metrics/ directories.
    
    Returns list of tuples: (metrics_csv_path, model_name)
    """
    metrics_files = []
    
    for root, dirs, _ in os.walk(data_root):
        root_path = Path(root)
        
        # Look for prediction directory
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
    model_stats = defaultdict(lambda: {"der_sum": 0.0, "time_sum": 0.0, "count": 0, "valid_der_count": 0})
    
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
        
        # Add source file info
        data["metrics_file"] = str(rel_path)
        
        all_rows.append(data)
        
        # Accumulate for averages
        try:
            der = float(data.get("der", -1))
            inf_time = float(data.get("inference_time", 0))
            
            model_stats[model]["time_sum"] += inf_time
            model_stats[model]["count"] += 1
            
            if der >= 0:  # Valid DER (not error marker)
                model_stats[model]["der_sum"] += der
                model_stats[model]["valid_der_count"] += 1
        except (ValueError, TypeError):
            pass
    
    if not all_rows:
        print("No valid metrics data found", file=sys.stderr)
        sys.exit(1)
    
    # Sort by model, then by filepath
    all_rows.sort(key=lambda x: (x.get("model", ""), x.get("filepath", "")))
    
    # Write all_metrics.csv
    all_metrics_path = output_dir / "all_metrics.csv"
    fieldnames = ["model", "der", "inference_time", "filepath", "metrics_file"]
    
    with open(all_metrics_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    
    print(f"Wrote {len(all_rows)} rows to {all_metrics_path}")
    
    # Calculate and write summary.csv
    summary_rows = []
    
    for model in sorted(model_stats.keys()):
        stats = model_stats[model]
        count = stats["count"]
        valid_der_count = stats["valid_der_count"]
        
        avg_der = stats["der_sum"] / valid_der_count if valid_der_count > 0 else -1
        avg_time = stats["time_sum"] / count if count > 0 else 0
        
        summary_rows.append({
            "model": model,
            "avg_der": f"{avg_der:.6f}" if avg_der >= 0 else "N/A",
            "avg_inference_time": f"{avg_time:.2f}",
            "total_files": count,
            "valid_der_files": valid_der_count,
        })
    
    summary_path = output_dir / "summary.csv"
    summary_fields = ["model", "avg_der", "avg_inference_time", "total_files", "valid_der_files"]
    
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    
    print(f"Wrote summary to {summary_path}")
    
    # Print summary to console
    print()
    print("=" * 60)
    print("MODEL SUMMARY")
    print("=" * 60)
    print(f"{'Model':<10} {'Avg DER':<12} {'Avg Time (s)':<15} {'Files':<10}")
    print("-" * 60)
    
    for row in summary_rows:
        print(f"{row['model']:<10} {row['avg_der']:<12} {row['avg_inference_time']:<15} {row['total_files']:<10}")
    
    print()


if __name__ == "__main__":
    main()
