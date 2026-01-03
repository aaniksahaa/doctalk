import argparse
import json
import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any

# Import the processing functions
from process_srt_without_timestamp import srt_to_clean_text
from process_srt_with_timestamp import srt_to_clean_text_with_turn_timestamps


def load_json(filepath: str) -> Any:
    """Load JSON data from file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath: str, data: Any):
    """Save JSON data to file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_command(cmd: List[str], cwd: str = None) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except Exception as e:
        return False, str(e)


def load_or_create_state(folder_path: str, filename: str, lang: str) -> Dict:
    """Load existing state or create new one."""
    state_file = Path(folder_path) / "save-state.json"
    
    if state_file.exists():
        state = load_json(str(state_file))
        # Verify the state matches current inputs
        if (state.get("folder_path") == folder_path and 
            state.get("filename") == filename and 
            state.get("language") == lang):
            print(f"Resuming from index {state.get('last_processed_index', -1) + 1}")
            return state
    
    # Create new state
    return {
        "folder_path": folder_path,
        "filename": filename,
        "language": lang,
        "last_processed_index": -1
    }


def save_state(folder_path: str, state: Dict):
    """Save current state to file."""
    state_file = Path(folder_path) / "save-state.json"
    save_json(str(state_file), state)


def load_or_create_metadata(folder_path: str, filename: str, lang: str) -> Dict:
    """Load existing metadata or create new one."""
    metadata_file = Path(folder_path) / "save-metadata.json"
    
    if metadata_file.exists():
        return load_json(str(metadata_file))
    
    # Create new metadata
    return {
        "folder_path": folder_path,
        "filename": filename,
        "language": lang,
        "failures": []
    }


def save_metadata(folder_path: str, metadata: Dict):
    """Save metadata to file."""
    metadata_file = Path(folder_path) / "save-metadata.json"
    save_json(str(metadata_file), metadata)


def add_failure(metadata: Dict, idx: int, video_id: str, reason: str):
    """Add a failure entry to metadata."""
    metadata["failures"].append({
        "index": idx,
        "video_id": video_id,
        "reason": reason
    })


def process_video_with_retry(video_data: Dict, idx: int, dataset_path: Path, lang: str, metadata: Dict, max_retries: int = 5, force_rewrite: bool = False) -> tuple[bool, bool]:
    """
    Process a video with retry logic and exponential backoff.
    Returns (success: bool, was_skipped: bool) - was_skipped is True if lock file was found and video was skipped.
    """
    video_id = video_data["videoId"]
    
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = min(2 ** attempt, 60)  # Exponential backoff, max 60s
            print(f"  ⏳ Retry attempt {attempt + 1}/{max_retries} after {wait_time}s...")
            time.sleep(wait_time)
        
        success, was_skipped = process_video(video_data, idx, dataset_path, lang, metadata, attempt, force_rewrite)
        if success:
            return True, was_skipped
    
    print(f"  ✗ Failed after {max_retries} attempts")
    return False, False


def process_video(video_data: Dict, idx: int, dataset_path: Path, lang: str, metadata: Dict, attempt: int = 0, force_rewrite: bool = False) -> tuple[bool, bool]:
    """
    Process a single video: download metadata, transcription, and process files.
    Returns (success: bool, was_skipped: bool) - was_skipped is True if lock file was found and video was skipped.
    """
    video_id = video_data["videoId"]
    
    if attempt == 0:
        print(f"\n[{idx}] Processing video: {video_id}")
    else:
        print(f"  → Attempting to process video: {video_id}")
    
    # Create video folder
    video_folder = dataset_path / video_id
    lock_file = video_folder / ".lock"
    
    # Check if already processed
    if video_folder.exists():
        if lock_file.exists() and not force_rewrite:
            print(f"  ✓ Video {video_id} already processed (lock file found). Skipping.")
            return True, True  # Success, was skipped
        elif lock_file.exists() and force_rewrite:
            print(f"  ⚠ Force rewrite enabled. Deleting and reprocessing...")
            shutil.rmtree(video_folder)
        else:
            print(f"  ⚠ Folder exists but no lock file. Deleting and reprocessing...")
            shutil.rmtree(video_folder)
    
    # Create folder structure
    video_folder.mkdir(parents=True, exist_ok=True)
    transcribed_folder = video_folder / "transcribed" / "yt-auto"
    transcribed_folder.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Download video metadata
    print(f"  → Downloading metadata...")
    metadata_file = video_folder / f"{video_id}_yt-dlp-metadata.json"
    # Quote video_id with -- to handle IDs starting with dash (e.g., -bdJJXgVlLg)
    cmd = ["yt-dlp", "-j", "--", video_id]
    success, output = run_command(cmd)
    
    if not success:
        print(f"  ✗ Failed to get metadata: {output}")
        add_failure(metadata, idx, video_id, "failed to get metadata")
        shutil.rmtree(video_folder)
        return False, False
    
    # Save metadata
    metadata_json = json.loads(output)
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata_json, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Metadata saved")
    
    # Step 2: Download subtitles
    print(f"  → Downloading {lang} subtitles...")
    srt_temp_file = transcribed_folder / f"file.{lang}.srt"
    srt_final_file = transcribed_folder / f"{video_id}_transcription.srt"
    
    cmd = [
        "yt-dlp",
        "--write-auto-subs",
        "--sub-lang", lang,
        "--convert-subs", "srt",
        "--skip-download",
        "-o", str(transcribed_folder / "file"),
        "--", video_id  # Use -- to handle IDs starting with dash
    ]
    success, output = run_command(cmd)
    
    if not success or not srt_temp_file.exists():
        print(f"  ✗ Failed to get subtitles: {output}")
        add_failure(metadata, idx, video_id, "failed to get srt")
        shutil.rmtree(video_folder)
        return False, False
    
    # Rename subtitle file
    srt_temp_file.rename(srt_final_file)
    print(f"  ✓ Subtitles saved")
    
    # Step 3: Process SRT files
    print(f"  → Processing transcription...")
    try:
        # Read SRT file
        with open(srt_final_file, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # Process with timestamps
        txt_with_timestamp = srt_to_clean_text_with_turn_timestamps(srt_content)
        output_with_ts = transcribed_folder / f"{video_id}_transcription-processed-with-timestamp.txt"
        with open(output_with_ts, 'w', encoding='utf-8') as f:
            f.write(txt_with_timestamp)
        
        # Process without timestamps
        txt_without_timestamp = srt_to_clean_text(srt_content)
        output_without_ts = transcribed_folder / f"{video_id}_transcription-processed-without-timestamp.txt"
        with open(output_without_ts, 'w', encoding='utf-8') as f:
            f.write(txt_without_timestamp)
        
        print(f"  ✓ Transcription processed")
    
    except Exception as e:
        print(f"  ✗ Failed to process: {str(e)}")
        add_failure(metadata, idx, video_id, "failed to process")
        shutil.rmtree(video_folder)
        return False, False
    
    # Step 4: Create lock file
    lock_file.touch()
    print(f"  ✓ Lock file created")
    print(f"  ✓ Video {video_id} processed successfully!")
    
    return True, False  # Success, not skipped (actually processed)


def main():
    parser = argparse.ArgumentParser(
        description="Process YouTube videos: download metadata, transcriptions, and process SRT files"
    )
    parser.add_argument(
        "--folder",
        default="saved-data",
        help="Folder path containing the JSON file (default: saved-data)"
    )
    parser.add_argument(
        "--file",
        default="filtered-results.json",
        help="JSON file name containing video data (default: filtered-results.json)"
    )
    parser.add_argument(
        "--lang",
        default="bn",
        help="Subtitle language code (default: bn)"
    )
    parser.add_argument(
        "--force-rewrite",
        action="store_true",
        help="Force reprocessing even if lock file exists"
    )
    
    args = parser.parse_args()
    
    # Setup paths
    folder_path = Path(args.folder)
    json_file = folder_path / args.file
    dataset_path = folder_path / "dataset"
    
    # Validate input file
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        return
    
    # Create dataset folder
    dataset_path.mkdir(parents=True, exist_ok=True)
    
    # Load video data
    print(f"Loading video data from {json_file}...")
    video_data_list = load_json(str(json_file))
    print(f"Found {len(video_data_list)} videos")
    
    # Load or create state
    state = load_or_create_state(str(folder_path), args.file, args.lang)
    start_index = state.get("last_processed_index", -1) + 1
    
    # Load or create metadata
    metadata = load_or_create_metadata(str(folder_path), args.file, args.lang)
    
    # Process videos
    for idx, video_data in enumerate(video_data_list):
        if idx < start_index:
            continue
        
        success, was_skipped = process_video_with_retry(video_data, idx, dataset_path, args.lang, metadata, max_retries=5, force_rewrite=args.force_rewrite)
        
        # Update state after each video (success or failure)
        state["last_processed_index"] = idx
        save_state(str(folder_path), state)
        save_metadata(str(folder_path), metadata)
        
        # Add delay between videos to avoid bombarding the server (only if video was actually processed)
        if not was_skipped and idx < len(video_data_list) - 1:  # Don't delay after skipped or last video
            print(f"  ⏸ Waiting 5 seconds before next video...")
            time.sleep(5)
    
    # Remove state file after completion
    state_file = folder_path / "save-state.json"
    if state_file.exists():
        state_file.unlink()
        print("\n✓ Removed save-state.json (processing complete)")
    
    # Final summary
    print("\n" + "="*60)
    print("Processing complete!")
    print(f"Total videos: {len(video_data_list)}")
    print(f"Failures: {len(metadata['failures'])}")
    if metadata['failures']:
        print("\nFailed videos:")
        for failure in metadata['failures']:
            print(f"  [{failure['index']}] {failure['video_id']}: {failure['reason']}")
    print("="*60)


if __name__ == "__main__":
    main()