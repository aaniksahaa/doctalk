#!/usr/bin/env python3
"""
Audio/Video Conversion Script using FFmpeg

Usage:
  # Convert single file (output in same dir with new extension):
  python convert.py --input-filepath input.webm --output-format wav

  # Convert single file to specific output path:
  python convert.py --input-filepath input.webm --output-filepath output.wav

  # Convert all files in a directory:
  python convert.py --input-dir ./videos --output-dir ./audio --output-format wav
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def convert_file(input_path, output_path, output_format=None):
    """Convert a single audio/video file using ffmpeg"""
    input_path = Path(input_path)
    
    if output_path is None:
        # Output in same directory with new extension
        output_path = input_path.with_suffix(f".{output_format}")
    else:
        output_path = Path(output_path)
    
    # Determine format from output extension if not specified
    if output_format is None:
        output_format = output_path.suffix.lstrip('.')
    
    if output_path.exists():
        os.remove(output_path)
    
    # Build ffmpeg command based on output format
    cmd = ["ffmpeg", "-i", str(input_path), "-vn"]  # -vn = no video
    
    if output_format == "wav":
        cmd.extend(["-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"])
    elif output_format == "mp3":
        cmd.extend(["-acodec", "libmp3lame", "-q:a", "2"])
    elif output_format == "mp4":
        cmd.extend(["-acodec", "aac", "-b:a", "192k"])
    elif output_format == "flac":
        cmd.extend(["-acodec", "flac"])
    # For other formats, let ffmpeg decide
    
    cmd.append(str(output_path))
    
    print(f"Converting: {input_path} -> {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error converting {input_path}: {result.stderr}", file=sys.stderr)
        return False
    
    return True


def convert_directory(input_dir, output_dir, output_format):
    """Convert all audio/video files in a directory"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Common audio/video extensions to look for
    extensions = {'.webm', '.mp4', '.mkv', '.avi', '.mov', '.flv', 
                  '.wmv', '.m4a', '.aac', '.ogg', '.flac', '.mp3', '.wav'}
    
    success_count = 0
    fail_count = 0
    
    for input_file in input_dir.iterdir():
        if input_file.is_file() and input_file.suffix.lower() in extensions:
            output_file = output_dir / f"{input_file.stem}.{output_format}"
            if convert_file(input_file, output_file, output_format):
                success_count += 1
            else:
                fail_count += 1
    
    print(f"\nConversion complete: {success_count} succeeded, {fail_count} failed")
    return fail_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Convert audio/video files using FFmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Single file options
    parser.add_argument("--input-filepath", type=str,
                        help="Path to single input file")
    parser.add_argument("--output-filepath", type=str,
                        help="Path to output file (optional if --output-format is given)")
    
    # Directory options
    parser.add_argument("--input-dir", type=str,
                        help="Directory containing input files")
    parser.add_argument("--output-dir", type=str,
                        help="Directory for output files")
    
    # Common options
    parser.add_argument("--output-format", type=str,
                        help="Output format (e.g., wav, mp3, mp4, flac)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.input_filepath and args.input_dir:
        parser.error("Cannot use both --input-filepath and --input-dir")
    
    if not args.input_filepath and not args.input_dir:
        parser.error("Must specify either --input-filepath or --input-dir")
    
    # Single file mode
    if args.input_filepath:
        if not args.output_filepath and not args.output_format:
            parser.error("Must specify --output-filepath or --output-format for single file conversion")
        
        success = convert_file(args.input_filepath, args.output_filepath, args.output_format)
        sys.exit(0 if success else 1)
    
    # Directory mode
    if args.input_dir:
        if not args.output_dir:
            parser.error("--output-dir is required when using --input-dir")
        if not args.output_format:
            parser.error("--output-format is required when using --input-dir")
        
        success = convert_directory(args.input_dir, args.output_dir, args.output_format)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
