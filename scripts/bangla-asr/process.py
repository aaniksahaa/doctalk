#!/usr/bin/env python3
"""
Process Raw ASR Data

Converts raw data from long_asr format to batch inference format.

Raw format (long_asr):
  {split}/audio/{name}.webm
  {split}/text/{name}.txt

Output format:
  {split}/{id}/audio/{name}.webm
  {split}/{id}/gt/{name}.txt

Usage:
  python process.py --raw-data-dir ./long_asr --output-dir ./data
"""

import argparse
import os
import shutil
from pathlib import Path


def process_data(raw_data_dir: Path, output_dir: Path, copy_files: bool = True):
    """Process raw data and convert to batch inference format."""
    
    raw_data_dir = Path(raw_data_dir)
    output_dir = Path(output_dir)
    
    if not raw_data_dir.exists():
        print(f"Error: Raw data directory does not exist: {raw_data_dir}")
        return False
    
    # Find all splits (e.g., test, train, val)
    splits = [d for d in raw_data_dir.iterdir() if d.is_dir()]
    
    if not splits:
        print(f"Error: No splits found in {raw_data_dir}")
        return False
    
    print(f"Found {len(splits)} split(s): {[s.name for s in splits]}")
    
    total_processed = 0
    
    for split_dir in splits:
        split_name = split_dir.name
        
        audio_dir = split_dir / "audio"
        text_dir = split_dir / "text"
        
        if not audio_dir.exists():
            print(f"  Warning: No audio directory in {split_dir}")
            continue
        
        # Find all audio files
        audio_files = list(audio_dir.iterdir())
        audio_files = [f for f in audio_files if f.is_file()]
        
        print(f"\nProcessing split: {split_name}")
        print(f"  Found {len(audio_files)} audio file(s)")
        
        for i, audio_file in enumerate(sorted(audio_files), 1):
            basename = audio_file.stem  # e.g., "test_001"
            
            # Create output structure: {split}/{id}/audio/ and {split}/{id}/gt/
            # Use the basename as the ID for simplicity
            sample_dir = output_dir / split_name / basename
            out_audio_dir = sample_dir / "audio"
            out_gt_dir = sample_dir / "gt"
            
            out_audio_dir.mkdir(parents=True, exist_ok=True)
            out_gt_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy/link audio file
            out_audio_file = out_audio_dir / audio_file.name
            if not out_audio_file.exists():
                if copy_files:
                    shutil.copy2(audio_file, out_audio_file)
                else:
                    # Create symlink for faster processing
                    out_audio_file.symlink_to(audio_file.resolve())
            
            # Copy/link text file (ground truth)
            text_file = text_dir / f"{basename}.txt"
            if text_file.exists():
                out_gt_file = out_gt_dir / f"{basename}.txt"
                if not out_gt_file.exists():
                    if copy_files:
                        shutil.copy2(text_file, out_gt_file)
                    else:
                        out_gt_file.symlink_to(text_file.resolve())
            else:
                print(f"  Warning: No transcript for {basename}")
            
            total_processed += 1
            
            # Progress
            if i % 10 == 0 or i == len(audio_files):
                print(f"  Progress: {i}/{len(audio_files)}")
    
    print(f"\n✅ Processed {total_processed} samples")
    print(f"   Output directory: {output_dir}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Process raw ASR data to batch inference format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--raw-data-dir", type=str, required=True,
                        help="Path to raw data directory (e.g., ./long_asr)")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Path to output directory (e.g., ./data)")
    parser.add_argument("--symlink", action="store_true",
                        help="Use symlinks instead of copying files (faster, saves space)")
    
    args = parser.parse_args()
    
    success = process_data(
        raw_data_dir=args.raw_data_dir,
        output_dir=args.output_dir,
        copy_files=not args.symlink
    )
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
