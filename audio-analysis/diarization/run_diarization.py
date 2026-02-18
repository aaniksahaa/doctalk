#!/usr/bin/env python3
"""
Runner script for batch speaker diarization inference and evaluation.

Recursively searches for paired audio/annotation directories, runs diarization
with specified models, and computes DER metrics.

Usage:
    python run_diarization.py --data_root dataset --models "nemo;pyan;3ds"
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Model configurations: model_name -> (conda_env, script_name)
MODEL_CONFIG = {
    "nemo": ("nemo", "dianemo.py"),
    "pyan": ("pyan", "diapyan.py"),
    "3ds": ("s3d_clean", "dia3ds.py"),
}

# ntfy.sh notification topic
NTFY_TOPIC = "anik-asr"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def send_notification(title: str, message: str, priority: str = "default"):
    """Send notification via ntfy.sh using curl."""
    try:
        cmd = [
            "curl", "-s",
            "-H", f"Title: {title}",
            "-H", f"Priority: {priority}",
            "-d", message,
            f"https://ntfy.sh/{NTFY_TOPIC}"
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        pass  # Silently ignore notification failures


def notify_metrics(model: str, file_path: str, der: float, inference_time: float, success: bool = True):
    """Send notification about completed metrics."""
    if success:
        title = f"✅ {model.upper()} completed"
        message = (
            f"File: {file_path}\n"
            f"─────────────────\n"
            f"model,der,inference_time,filepath\n"
            f"{model},{der:.6f},{inference_time:.2f},{file_path}"
        )
        priority = "default"
    else:
        title = f"❌ {model.upper()} failed"
        message = f"File: {file_path}\nInference or DER computation failed."
        priority = "high"
    
    send_notification(title, message, priority)


def find_paired_files(data_root: Path) -> List[Tuple[Path, Path, Path]]:
    """
    Recursively find paired audio/annotation directories and their matching files.
    
    Returns list of tuples: (audio_file, annotation_file, parent_dir)
    where parent_dir is the directory containing audio/ and annotation/
    """
    paired_files = []
    
    # Walk through all directories
    for root, dirs, _ in os.walk(data_root):
        root_path = Path(root)
        
        # Check if this directory has both audio and annotation subdirs
        audio_dir = root_path / "audio"
        annot_dir = root_path / "annotation"
        
        if audio_dir.is_dir() and annot_dir.is_dir():
            # Find all wav files in audio/
            wav_files = sorted(audio_dir.glob("*.wav"))
            
            for wav_file in wav_files:
                # Look for matching csv in annotation/
                csv_file = annot_dir / f"{wav_file.stem}.csv"
                
                if csv_file.exists():
                    paired_files.append((wav_file, csv_file, root_path))
    
    return paired_files


def ensure_prediction_dirs(parent_dir: Path, models: List[str]) -> Dict[str, Tuple[Path, Path]]:
    """
    Create prediction directory structure for each model.
    
    Returns dict: model_name -> (annotation_dir, metrics_dir)
    """
    dirs = {}
    pred_root = parent_dir / "prediction"
    
    for model in models:
        annot_dir = pred_root / model / "annotation"
        metrics_dir = pred_root / model / "metrics"
        
        annot_dir.mkdir(parents=True, exist_ok=True)
        metrics_dir.mkdir(parents=True, exist_ok=True)
        
        dirs[model] = (annot_dir, metrics_dir)
    
    return dirs


def run_inference(model: str, audio_path: Path, output_csv: Path, 
                  script_dir: Path, log_file: Path) -> Tuple[bool, float]:
    """
    Run diarization inference for a single model.
    
    Returns: (success, inference_time_seconds)
    """
    if model not in MODEL_CONFIG:
        eprint(f"Unknown model: {model}")
        return False, 0.0
    
    conda_env, script_name = MODEL_CONFIG[model]
    script_path = script_dir / script_name
    
    if not script_path.exists():
        eprint(f"Script not found: {script_path}")
        return False, 0.0
    
    # Build command using conda run
    cmd = [
        "conda", "run", "-n", conda_env, "--no-capture-output",
        "python", str(script_path),
        "-i", str(audio_path),
        "-o", str(output_csv),
    ]
    
    # For dia3ds, we need to specify out_dir to avoid temp dir issues
    if model == "3ds":
        work_dir = output_csv.parent.parent / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--out_dir", str(work_dir)])
    
    start_time = time.time()
    
    try:
        with open(log_file, "w", encoding="utf-8") as log_f:
            result = subprocess.run(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=3600,  # 1 hour timeout
            )
        
        inference_time = time.time() - start_time
        success = result.returncode == 0 and output_csv.exists()
        
        return success, inference_time
        
    except subprocess.TimeoutExpired:
        eprint(f"  Timeout for {model} on {audio_path.name}")
        return False, time.time() - start_time
    except Exception as ex:
        eprint(f"  Error running {model}: {ex}")
        return False, time.time() - start_time


def compute_der(reference_csv: Path, hypothesis_csv: Path, 
                script_dir: Path) -> Tuple[bool, float]:
    """
    Compute DER between reference and hypothesis.
    
    Returns: (success, der_value)
    """
    der_script = script_dir / "der.py"
    
    if not der_script.exists():
        eprint(f"DER script not found: {der_script}")
        return False, -1.0
    
    # DER script uses pyannote.metrics which is available in der_eval or pyan env
    # Try with pyan first, fallback to der_eval
    for env in ["pyan", "der_eval"]:
        cmd = [
            "conda", "run", "-n", env, "--no-capture-output",
            "python", str(der_script),
            "--reference_csv", str(reference_csv),
            "--hypothesis_csv", str(hypothesis_csv),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode == 0:
                # Parse DER from output: "DER=0.123456"
                match = re.search(r"DER=(\d+\.?\d*)", result.stdout)
                if match:
                    return True, float(match.group(1))
        except Exception:
            continue
    
    return False, -1.0


def write_metrics_csv(metrics_path: Path, model: str, der: float, 
                      inference_time: float, audio_path: Path):
    """Write single-row metrics CSV."""
    with open(metrics_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "der", "inference_time", "filepath"])
        writer.writerow([model, f"{der:.6f}", f"{inference_time:.2f}", str(audio_path)])


def main():
    parser = argparse.ArgumentParser(
        description="Batch speaker diarization inference and evaluation"
    )
    parser.add_argument(
        "--data_root", "-d",
        required=True,
        help="Root directory to search for audio/annotation pairs"
    )
    parser.add_argument(
        "--models", "-m",
        default="nemo;pyan;3ds",
        help="Models to run, semicolon-separated (default: nemo;pyan;3ds)"
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Only show what would be processed, don't run inference"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Re-run inference even if output already exists (default: skip existing)"
    )
    args = parser.parse_args()
    
    # Parse models
    models = [m.strip() for m in args.models.split(";") if m.strip()]
    invalid_models = [m for m in models if m not in MODEL_CONFIG]
    if invalid_models:
        eprint(f"Invalid models: {invalid_models}")
        eprint(f"Valid options: {list(MODEL_CONFIG.keys())}")
        sys.exit(1)
    
    # Get script directory (where this script and dia*.py live)
    script_dir = Path(__file__).parent.resolve()
    
    # Find all paired files
    data_root = Path(args.data_root).resolve()
    if not data_root.exists():
        eprint(f"Data root not found: {data_root}")
        sys.exit(1)
    
    paired_files = find_paired_files(data_root)
    
    if not paired_files:
        eprint(f"No paired audio/annotation files found in {data_root}")
        sys.exit(1)
    
    # Group by parent directory for display
    by_parent = {}
    for audio, annot, parent in paired_files:
        if parent not in by_parent:
            by_parent[parent] = []
        by_parent[parent].append((audio, annot))
    
    # Show summary
    print("=" * 70)
    print("DIARIZATION BATCH RUNNER")
    print("=" * 70)
    print(f"Data root: {data_root}")
    print(f"Models: {', '.join(models)}")
    print(f"Total files to process: {len(paired_files)}")
    print()
    
    for parent, files in by_parent.items():
        rel_parent = parent.relative_to(data_root) if parent != data_root else Path(".")
        print(f"  {rel_parent}/")
        for audio, annot in files:
            print(f"    - {audio.stem}")
    print()
    
    if args.dry_run:
        print("[DRY RUN] No inference performed.")
        return
    
    # Process each file
    total = len(paired_files)
    completed = 0
    errors = []
    
    for audio_path, annot_path, parent_dir in paired_files:
        completed += 1
        file_stem = audio_path.stem
        
        # Compute relative path for metrics output
        try:
            rel_audio_path = audio_path.relative_to(data_root.parent)
        except ValueError:
            rel_audio_path = audio_path
        
        print("-" * 70)
        print(f"[{completed}/{total}] Processing: {file_stem}")
        print(f"  Audio: {audio_path}")
        print(f"  Reference: {annot_path}")
        
        # Create prediction directories
        pred_dirs = ensure_prediction_dirs(parent_dir, models)
        
        for model in models:
            annot_dir, metrics_dir = pred_dirs[model]
            pred_csv = annot_dir / f"{file_stem}.csv"
            metrics_csv = metrics_dir / f"{file_stem}.csv"
            log_file = annot_dir / f"{file_stem}.log"
            
            # Check if prediction already exists
            if pred_csv.exists() and not args.fresh:
                print(f"\n  [{model}] SKIPPED (output exists: {pred_csv.name})")
                continue
            
            print(f"\n  [{model}] Running inference...")
            
            # Run inference
            success, inf_time = run_inference(
                model, audio_path, pred_csv, script_dir, log_file
            )
            
            if not success:
                eprint(f"  [{model}] Inference FAILED (see {log_file})")
                errors.append((file_stem, model, "inference"))
                # Write error metrics
                write_metrics_csv(metrics_csv, model, -1.0, inf_time, rel_audio_path)
                notify_metrics(model, str(rel_audio_path), -1.0, inf_time, success=False)
                continue
            
            print(f"  [{model}] Inference OK ({inf_time:.1f}s)")
            
            # Compute DER
            print(f"  [{model}] Computing DER...")
            der_ok, der_val = compute_der(annot_path, pred_csv, script_dir)
            
            if not der_ok:
                eprint(f"  [{model}] DER computation FAILED")
                errors.append((file_stem, model, "der"))
                write_metrics_csv(metrics_csv, model, -1.0, inf_time, rel_audio_path)
                notify_metrics(model, str(rel_audio_path), -1.0, inf_time, success=False)
                continue
            
            print(f"  [{model}] DER={der_val:.4f}")
            
            # Write metrics
            write_metrics_csv(metrics_csv, model, der_val, inf_time, rel_audio_path)
            notify_metrics(model, str(rel_audio_path), der_val, inf_time, success=True)
            print(f"  [{model}] Metrics saved to {metrics_csv.relative_to(data_root)}")
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Processed: {total} files")
    print(f"Models: {', '.join(models)}")
    
    if errors:
        print(f"Errors: {len(errors)}")
        for stem, model, stage in errors:
            print(f"  - {stem} / {model} / {stage}")
    else:
        print("All completed successfully!")
    
    print()
    print("Run 'python collect_metrics.py --data_root <path>' to aggregate results.")


if __name__ == "__main__":
    main()
