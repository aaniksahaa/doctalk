#!/usr/bin/env python3
"""
Script to generate an example dataset by selecting top N videos with the most patient calls.

Steps:
1. Scan the dataset folder for videos that have a parsed conversation.json
2. Count patient_call entries in each conversation
3. Sort by patient call count descending, take top N
4. Copy those video folders to example_dataset/
5. Download audio for each video via yt-dlp into <video_id>/audio/<video_id>_audio.mp3

Usage:
    python generate_example_dataset.py [--n 10] [--folder saved-data] [--output example_dataset] [--parse-model gemini-3-flash-preview]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


YOUTUBE_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"


def find_conversation_file(video_folder: Path, parse_model: str) -> Path | None:
    """Return path to _conversation.json for the given parse model, or None."""
    model_dir = parse_model.replace("/", "-").replace(":", "-")
    conv_file = (
        video_folder / "transcribed" / "yt-auto" / "parsed" / model_dir
        / f"{video_folder.name}_conversation.json"
    )
    return conv_file if conv_file.exists() else None


def count_patient_calls(conv_file: Path) -> int:
    """Count the number of patient_call entries in a conversation JSON file."""
    try:
        with open(conv_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return sum(1 for entry in data if entry.get("type") == "patient_call")
    except Exception:
        return 0


def collect_candidates(dataset_path: Path, parse_model: str) -> list[dict]:
    """
    Scan dataset folder and collect videos that have a conversation file with
    at least one patient_call. Returns list of dicts sorted by patient_call_count desc.
    """
    candidates = []
    for video_dir in sorted(dataset_path.iterdir()):
        if not video_dir.is_dir():
            continue
        conv_file = find_conversation_file(video_dir, parse_model)
        if conv_file is None:
            continue
        count = count_patient_calls(conv_file)
        if count > 0:
            candidates.append({
                "video_id": video_dir.name,
                "video_folder": video_dir,
                "patient_call_count": count,
            })

    candidates.sort(key=lambda x: x["patient_call_count"], reverse=True)
    return candidates


def copy_video_folder(src: Path, dst: Path) -> None:
    """Copy video folder to destination, skipping if already exists."""
    if dst.exists():
        print(f"  [skip copy] {dst.name} already exists at destination")
        return
    shutil.copytree(src, dst)


def download_audio(video_id: str, audio_dir: Path) -> bool:
    """
    Download audio for a YouTube video using yt-dlp.
    Saves as <audio_dir>/<video_id>_audio.mp3.
    Returns True on success, False on failure.
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(audio_dir / f"{video_id}_audio.%(ext)s")
    url = YOUTUBE_URL_TEMPLATE.format(video_id=video_id)

    # Check if already downloaded
    expected_file = audio_dir / f"{video_id}_audio.mp3"
    if expected_file.exists():
        print(f"  [skip download] Audio already exists: {expected_file.name}")
        return True

    print(f"  Downloading audio: {url}")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--no-playlist",
        "-o", output_template,
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  [ok] Saved to: {expected_file.name}")
            return True
        else:
            print(f"  [error] yt-dlp failed for {video_id}:")
            print(f"    {result.stderr.strip()[:300]}")
            return False
    except FileNotFoundError:
        print("  [error] yt-dlp not found. Please install it: pip install yt-dlp")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate an example dataset from the top N videos by patient call count."
    )
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Number of videos to include in the example dataset (default: 10)",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="saved-data",
        help="Path to folder containing the dataset directory (default: saved-data)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="example_dataset",
        help="Output folder name for the example dataset (default: example_dataset)",
    )
    parser.add_argument(
        "--parse-model",
        type=str,
        default="gemini-3-flash-preview",
        help="Model name used for parsing conversations (default: gemini-3-flash-preview)",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip audio download (useful for dry runs)",
    )

    args = parser.parse_args()

    # Resolve paths
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path

    dataset_path = folder_path / "dataset"
    output_path = folder_path / args.output

    if not dataset_path.exists():
        print(f"Error: dataset folder not found: {dataset_path}")
        return 1

    print(f"Dataset folder : {dataset_path}")
    print(f"Output folder  : {output_path}")
    print(f"Parse model    : {args.parse_model}")
    print(f"Top N videos   : {args.n}")
    print()

    # Step 1: Collect candidates
    print("Scanning for videos with patient calls...")
    candidates = collect_candidates(dataset_path, args.parse_model)
    print(f"Found {len(candidates)} videos with at least one patient_call.")

    if not candidates:
        print("No eligible videos found. Exiting.")
        return 1

    selected = candidates[: args.n]
    print(f"\nTop {len(selected)} selected:")
    for i, c in enumerate(selected, 1):
        print(f"  {i:2}. {c['video_id']}  ({c['patient_call_count']} patient calls)")

    # Step 2: Create output folder
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 3: Copy folders and download audio
    print(f"\nCopying folders and downloading audio into: {output_path}")
    audio_success = 0
    audio_failed = 0

    for c in selected:
        video_id = c["video_id"]
        src_folder = c["video_folder"]
        dst_folder = output_path / video_id

        print(f"\n[{video_id}]  patient_calls={c['patient_call_count']}")

        # Copy the video folder
        copy_video_folder(src_folder, dst_folder)

        # Download audio
        if args.skip_audio:
            print("  [skip audio] --skip-audio flag set")
        else:
            audio_dir = dst_folder / "audio"
            ok = download_audio(video_id, audio_dir)
            if ok:
                audio_success += 1
            else:
                audio_failed += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"Example dataset generated at: {output_path}")
    print(f"Videos included : {len(selected)}")
    if not args.skip_audio:
        print(f"Audio downloads : {audio_success} ok, {audio_failed} failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
