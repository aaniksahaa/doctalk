#!/usr/bin/env python3
"""
Speaker diarization wrapper for 3D-Speaker.
Provides a compatible interface (-i, -o) and outputs CSV format.
"""
import argparse
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def seconds_to_hhmmss(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format (truncated, no milliseconds)."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_rttm(rttm_path: str):
    """
    Parse RTTM file from 3D-Speaker.
    Format: SPEAKER <file-id> 0 <start> <duration> <NA> <NA> <speaker> <NA> <NA>
    """
    segments = []
    with open(rttm_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8 or parts[0].upper() != "SPEAKER":
                continue
            start = float(parts[3])
            dur = float(parts[4])
            spk = parts[7]
            segments.append((start, start + dur, spk))
    segments.sort(key=lambda x: x[0])
    return segments


def write_csv(csv_path: str, segments):
    """Write segments to CSV in the expected format."""
    # Build speaker ID mapping (0 -> 1, 1 -> 2, etc.)
    speaker_labels = sorted(set(spk for _, _, spk in segments), key=lambda x: int(x) if x.isdigit() else x)
    speaker_to_id = {label: idx + 1 for idx, label in enumerate(speaker_labels)}
    
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)) or ".", exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start_time", "end_time", "speaker_id"])
        for start, end, speaker in segments:
            writer.writerow([
                seconds_to_hhmmss(start),
                seconds_to_hhmmss(end),
                speaker_to_id[speaker],
            ])
    return len(speaker_labels)


def main():
    # Get script directory to locate 3D-Speaker
    script_dir = Path(__file__).parent.resolve()
    infer_script = script_dir / "3D-Speaker" / "speakerlab" / "bin" / "infer_diarization.py"
    
    ap = argparse.ArgumentParser(
        description="Speaker diarization with 3D-Speaker (CSV output)"
    )
    ap.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input audio (e.g., .wav)"
    )
    ap.add_argument(
        "-o", "--output",
        help="Path to output CSV (default: <input_stem>.csv in same folder)"
    )
    ap.add_argument(
        "--out_dir",
        default=None,
        help="Working directory for intermediate files (default: temp dir)"
    )
    ap.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU inference (default: use GPU if available)"
    )
    args = ap.parse_args()

    in_path = Path(args.input).resolve()
    if not in_path.exists():
        eprint(f"ERROR: input file not found: {in_path}")
        sys.exit(2)

    out_csv = Path(args.output) if args.output else in_path.with_suffix(".csv")
    
    # Use temp dir if out_dir not specified
    if args.out_dir:
        work_dir = Path(args.out_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup_work_dir = False
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="dia3ds_"))
        cleanup_work_dir = True

    # Check if 3D-Speaker script exists
    if not infer_script.exists():
        eprint(f"ERROR: 3D-Speaker inference script not found at: {infer_script}")
        eprint("Make sure 3D-Speaker is cloned in the same directory as this script.")
        sys.exit(2)

    # Build command
    cmd = [
        sys.executable,
        str(infer_script),
        "--wav", str(in_path),
        "--out_dir", str(work_dir),
        "--out_type", "rttm",
    ]
    
    if args.cpu:
        cmd.extend(["--device", "cpu"])

    print(f"Running 3D-Speaker diarization...")
    print(f"Input: {in_path}")
    
    try:
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as ex:
        eprint(f"ERROR: 3D-Speaker diarization failed with exit code {ex.returncode}")
        sys.exit(2)
    except FileNotFoundError:
        eprint(f"ERROR: Could not run Python. Check your environment.")
        sys.exit(2)

    # Find the RTTM output
    rttm_path = work_dir / f"{in_path.stem}.rttm"
    if not rttm_path.exists():
        eprint(f"ERROR: Expected RTTM not found at: {rttm_path}")
        eprint(f"Check {work_dir} for outputs.")
        sys.exit(2)

    # Parse RTTM and write CSV
    segments = parse_rttm(str(rttm_path))
    num_speakers = write_csv(str(out_csv), segments)

    print(f"\nCSV written to: {out_csv}")
    print(f"Detected {num_speakers} speakers, {len(segments)} segments.")

    # Cleanup temp dir if we created it
    if cleanup_work_dir:
        import shutil
        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass  # Best effort cleanup


if __name__ == "__main__":
    main()
