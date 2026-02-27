#!/usr/bin/env python3
"""
Standalone metrics recalculation script.

Re-computes detailed diarization metrics from already-saved prediction CSVs
and ground-truth annotation CSVs — WITHOUT re-running inference.

Reads inference_time from existing per-file metrics CSVs and audio duration
from the .wav files to compute RTF. Overwrites the metrics CSVs with the
extended field set.

Usage:
    python recalc_metrics.py --data_root dataset
    python recalc_metrics.py --data_root dataset --models "3ds;pyan"
"""
import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from metrics import (
    compute_detailed_metrics,
    compute_rtf,
    get_audio_duration,
    write_metrics_csv,
    METRICS_FIELDNAMES,
)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def find_evaluation_pairs(
    data_root: Path,
    models: List[str] | None = None,
) -> List[Dict]:
    """
    Walk the dataset directory and find all triplets of:
      (ground-truth annotation CSV, prediction annotation CSV, audio WAV)

    Returns a list of dicts, each with keys:
      model, audio_path, ref_csv, hyp_csv, metrics_csv
    """
    pairs = []

    for root, dirs, _ in os.walk(data_root):
        root_path = Path(root)

        # Look for dirs that have both audio/ and annotation/ subdirs
        audio_dir = root_path / "audio"
        annot_dir = root_path / "annotation"
        pred_dir = root_path / "prediction"

        if not (audio_dir.is_dir() and annot_dir.is_dir() and pred_dir.is_dir()):
            continue

        # List model subdirs under prediction/
        model_dirs = sorted([
            d for d in pred_dir.iterdir()
            if d.is_dir() and (models is None or d.name in models)
        ])

        for model_dir in model_dirs:
            model_name = model_dir.name
            hyp_annot_dir = model_dir / "annotation"
            metrics_dir = model_dir / "metrics"

            if not hyp_annot_dir.is_dir():
                continue

            # For each prediction CSV, find matching audio + reference
            for hyp_csv in sorted(hyp_annot_dir.glob("*.csv")):
                stem = hyp_csv.stem
                ref_csv = annot_dir / f"{stem}.csv"
                audio_path = audio_dir / f"{stem}.wav"
                metrics_csv = metrics_dir / f"{stem}.csv"

                if not ref_csv.exists():
                    eprint(f"  SKIP {model_name}/{stem}: no reference annotation")
                    continue

                if not audio_path.exists():
                    eprint(f"  WARN {model_name}/{stem}: audio not found, RTF will be N/A")

                pairs.append({
                    "model": model_name,
                    "stem": stem,
                    "audio_path": audio_path,
                    "ref_csv": ref_csv,
                    "hyp_csv": hyp_csv,
                    "metrics_csv": metrics_csv,
                    "parent_dir": root_path,
                })

    return pairs


def read_existing_inference_time(metrics_csv: Path) -> float:
    """Read inference_time from an existing per-file metrics CSV, if available."""
    if not metrics_csv.exists():
        return 0.0
    try:
        with open(metrics_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                return float(row.get("inference_time", 0))
    except Exception:
        pass
    return 0.0


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Re-compute detailed diarization metrics from saved predictions. "
            "Does NOT re-run inference."
        )
    )
    parser.add_argument(
        "--data_root", "-d",
        required=True,
        help="Root directory to search for audio/annotation/prediction triples",
    )
    parser.add_argument(
        "--models", "-m",
        default=None,
        help="Only recalculate for these models (semicolon-separated, e.g. '3ds;pyan'). Default: all.",
    )
    parser.add_argument(
        "--collar",
        type=float,
        default=0.0,
        help="Collar (seconds) for DER computation (default: 0.0)",
    )
    parser.add_argument(
        "--skip_overlap",
        action="store_true",
        help="Ignore overlap regions when computing DER",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Show what would be processed without writing anything",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root).resolve()
    if not data_root.exists():
        eprint(f"Data root not found: {data_root}")
        sys.exit(1)

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(";") if m.strip()]

    # Find all evaluation pairs
    pairs = find_evaluation_pairs(data_root, models)

    if not pairs:
        eprint(f"No evaluation pairs found in {data_root}")
        sys.exit(1)

    print("=" * 70)
    print("DIARIZATION METRICS RECALCULATION")
    print("=" * 70)
    print(f"Data root: {data_root}")
    print(f"Models: {', '.join(models) if models else 'all'}")
    print(f"Pairs found: {len(pairs)}")
    print()

    if args.dry_run:
        for p in pairs:
            print(f"  [{p['model']}] {p['stem']}")
        print("\n[DRY RUN] No metrics computed.")
        return

    # Process each pair
    success_count = 0
    error_count = 0

    for i, p in enumerate(pairs, 1):
        model = p["model"]
        stem = p["stem"]
        ref_csv = p["ref_csv"]
        hyp_csv = p["hyp_csv"]
        metrics_csv = p["metrics_csv"]
        audio_path = p["audio_path"]

        print(f"[{i}/{len(pairs)}] {model}/{stem} ... ", end="", flush=True)

        # Read existing inference_time
        inference_time = read_existing_inference_time(metrics_csv)

        # Get audio duration
        if audio_path.exists():
            audio_duration = get_audio_duration(str(audio_path))
        else:
            audio_duration = -1.0

        # Compute RTF
        if inference_time > 0 and audio_duration > 0:
            rtf = inference_time / audio_duration
        else:
            rtf = -1.0

        # Compute detailed metrics
        try:
            metrics = compute_detailed_metrics(
                str(ref_csv),
                str(hyp_csv),
                collar=args.collar,
                skip_overlap=args.skip_overlap,
            )
        except Exception as ex:
            eprint(f"FAILED ({ex})")
            error_count += 1

            # Write error metrics
            metrics_csv.parent.mkdir(parents=True, exist_ok=True)
            error_metrics = {
                "der": -1.0,
                "false_alarm": -1.0,
                "missed_detection": -1.0,
                "confusion": -1.0,
                "correct": -1.0,
            }
            try:
                rel_audio = audio_path.relative_to(data_root.parent)
            except ValueError:
                rel_audio = audio_path
            write_metrics_csv(
                str(metrics_csv), model, error_metrics,
                rtf=-1.0, inference_time=inference_time,
                audio_duration=audio_duration, filepath=str(rel_audio),
            )
            continue

        # Write extended metrics CSV
        metrics_csv.parent.mkdir(parents=True, exist_ok=True)
        try:
            rel_audio = audio_path.relative_to(data_root.parent)
        except ValueError:
            rel_audio = audio_path

        write_metrics_csv(
            str(metrics_csv), model, metrics,
            rtf=rtf, inference_time=inference_time,
            audio_duration=audio_duration, filepath=str(rel_audio),
        )

        der_pct = metrics["der"] * 100
        fa_pct = metrics["false_alarm"] * 100
        miss_pct = metrics["missed_detection"] * 100
        conf_pct = metrics["confusion"] * 100
        correct_pct = metrics["correct"] * 100

        print(
            f"DER={der_pct:.1f}% "
            f"(FA={fa_pct:.1f}% Miss={miss_pct:.1f}% Conf={conf_pct:.1f}%) "
            f"Correct={correct_pct:.1f}% "
            f"RTF={rtf:.4f}" if rtf >= 0 else f"RTF=N/A"
        )
        success_count += 1

    # Summary
    print()
    print("=" * 70)
    print(f"Done. Success: {success_count}, Errors: {error_count}")
    print()
    print("Run 'python collect_metrics.py --data_root <path>' to aggregate results.")


if __name__ == "__main__":
    main()
