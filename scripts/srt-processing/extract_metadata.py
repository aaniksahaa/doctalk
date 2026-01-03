#!/usr/bin/env python3
"""
Script to extract derived metadata (tags, etc.) from healthcare videos using LLM.
Processes videos and saves individual metadata files per video in the dataset folder.
Uses lock files per video to track completion (similar to save.py).
"""

import json
import argparse
import os
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel, field_validator

from llm import get_response
from constants import MEDICAL_TAGS

# Get valid tag names from constants
VALID_TAGS = {tag["tag"] for tag in MEDICAL_TAGS}


class TagsResponse(BaseModel):
    """Structured response for tag extraction."""
    tags: List[str]
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Ensure all tags are from the valid set."""
        validated = [tag for tag in v if tag in VALID_TAGS]
        if not validated:
            validated = ["general-medicine"]  # Default fallback
        return validated[:3]  # Max 3 tags


# Load prompts from files
PROMPTS_DIR = Path(__file__).parent / "prompts" / "metadata-extraction"

def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the metadata-extraction prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")


def load_results(results_path: str) -> List[Dict[str, Any]]:
    """Load results JSON file."""
    with open(results_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_run_metadata(metadata_path: str, folder: str, file: str, model: str) -> Dict[str, Any]:
    """Load or create extraction run metadata."""
    if os.path.exists(metadata_path):
        return json.load(open(metadata_path, 'r', encoding='utf-8'))
    
    return {
        'folder': folder,
        'file': file,
        'model': model,
        'processed_count': 0,
        'skipped_count': 0,
        'failures': []
    }


def save_run_metadata(metadata_path: str, metadata: Dict[str, Any]) -> None:
    """Save extraction run metadata."""
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def save_derived_metadata(video_folder: Path, video_id: str, derived_data: Dict[str, Any]) -> None:
    """
    Save derived metadata for a single video.
    Creates <VIDEO_ID>_derived-metadata.json in the video folder.
    """
    output_file = video_folder / f"{video_id}_derived-metadata.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(derived_data, f, indent=2, ensure_ascii=False)


def is_video_processed(video_folder: Path) -> bool:
    """Check if video has already been processed (lock file exists)."""
    lock_file = video_folder / ".extract-metadata.lock"
    return lock_file.exists()


def create_lock_file(video_folder: Path) -> None:
    """Create lock file to mark video as processed."""
    lock_file = video_folder / ".extract-metadata.lock"
    lock_file.touch()


def add_failure(metadata: Dict[str, Any], index: int, video_id: str, reason: str) -> None:
    """Add a failure entry to metadata."""
    metadata['failures'].append({
        'index': index,
        'video_id': video_id,
        'reason': reason
    })


def load_transcript(video_folder: Path, video_id: str, max_chars: int = 4000) -> str | None:
    """
    Load transcript from the video folder if available.
    Returns first max_chars characters of the transcript, or None if not found.
    """
    transcript_path = video_folder / "transcribed" / "yt-auto" / f"{video_id}_transcription-processed-without-timestamp.txt"
    
    if not transcript_path.exists():
        return None
    
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Return first max_chars characters
        return content[:max_chars] if len(content) > max_chars else content
    except Exception:
        return None


def extract_tags(model: str, title: str, description: str, transcript: str | None = None, max_retries: int = 5) -> List[str]:
    """
    Query LLM to extract medical tags from video content.
    Uses prompts loaded from markdown files.
    Optionally includes transcript context if available.
    Retries up to max_retries times if JSON parsing fails.
    Returns list of tag strings.
    """
    # Build prompt from file-based templates
    if transcript:
        prompt = HEADER_PROMPT + f"""
Title: {title}
Description: {description}
Transcript (partial): {transcript}
"""
        print("\n\nUsing transcript for context...\n\n")
    else:
        prompt = HEADER_PROMPT + f"""
Title: {title}
Description: {description}
"""

    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            response = get_response(
                prompt=prompt,
                model=model,
                system_prompt=SYSTEM_PROMPT,
                format_schema=TagsResponse.model_json_schema(),
            )
            
            # Parse JSON response
            result = TagsResponse.model_validate_json(response.content)
            return result.tags
        
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                print(f"      Retry {attempt}/{max_retries}: JSON parse error - {str(e)}")
            continue
        except Exception as e:
            # Non-retryable errors (network, API, etc.)
            raise Exception(f"Error during LLM inference: {str(e)}")
    
    # All retries exhausted
    raise Exception(f"Failed to parse JSON response after {max_retries} attempts: {str(last_error)}")


def process_video(
    model: str,
    result: Dict[str, Any],
    idx: int,
    dataset_path: Path,
    metadata: Dict[str, Any],
    force_rewrite: bool = False
) -> str:
    """
    Process a single video for metadata extraction.
    Returns: 'success', 'skipped', or 'failed'
    """
    title = result.get('title', '')
    normalized_desc = result.get('normalizedDescription', '')
    video_id = result.get('videoId', 'unknown')
    
    # Create video folder if it doesn't exist
    video_folder = dataset_path / video_id
    if not video_folder.exists():
        video_folder.mkdir(parents=True, exist_ok=True)
    
    # Check if already processed (lock file exists), unless force_rewrite is on
    if not force_rewrite and is_video_processed(video_folder):
        print(f"  [{idx}] {video_id} - ✓ Already processed (lock file found)")
        return 'skipped'
    
    # Try to load transcript for additional context
    transcript = load_transcript(video_folder, video_id)
    has_transcript = transcript is not None
    
    try:
        transcript_indicator = "[T]" if has_transcript else "[--]"
        print(f"  [{idx}] {transcript_indicator} {title[:45]}...", end=' ')
        
        tags = extract_tags(model, title, normalized_desc, transcript)
        
        # Create derived metadata
        derived_data = {
            "video_id": video_id,
            "title": title,
            "tags": tags
        }
        
        # Save to video folder
        save_derived_metadata(video_folder, video_id, derived_data)
        
        # Create lock file
        create_lock_file(video_folder)
        
        print(f"✓ {tags}")
        return 'success'
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        add_failure(metadata, idx, video_id, f"extraction error: {str(e)}")
        return 'failed'


def process_batch(
    model: str,
    results: List[Dict[str, Any]],
    start_idx: int,
    batch_size: int,
    dataset_path: Path,
    metadata: Dict[str, Any],
    force_rewrite: bool = False
) -> tuple[int, int, int, int]:
    """
    Process a batch of results for metadata extraction.
    Returns (next_idx, success_count, skipped_count, failed_count)
    """
    end_idx = min(start_idx + batch_size, len(results))
    success_count = 0
    skipped_count = 0
    failed_count = 0
    
    for i in range(start_idx, end_idx):
        result = results[i]
        status = process_video(model, result, i, dataset_path, metadata, force_rewrite)
        
        if status == 'success':
            success_count += 1
        elif status == 'skipped':
            skipped_count += 1
        else:
            failed_count += 1
    
    return end_idx, success_count, skipped_count, failed_count


def main():
    parser = argparse.ArgumentParser(
        description='Extract derived metadata (tags) from healthcare videos using LLM'
    )
    parser.add_argument(
        '--folder',
        type=str,
        default='saved-data',
        help='Path to folder containing input file and dataset (default: saved-data)'
    )

    parser.add_argument(
        '--file',
        type=str,
        default='filtered-results.json',
        help='Filename of input JSON file (default: filtered-results.json)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default="qwen2.5:3b-instruct",
        help='Model name to use for extraction (default: qwen2.5:3b-instruct)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Batch size for processing (default: 5)'
    )
    parser.add_argument(
        '--force-rewrite',
        action='store_true',
        help='Ignore lock files and reprocess all videos'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    folder_path = Path(args.folder)
    file_name = args.file
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path
    
    results_path = folder_path / file_name
    dataset_path = folder_path / 'dataset'
    metadata_path = folder_path / 'extraction-metadata.json'
    
    # Validate input file exists
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        return 1
    
    # Create dataset folder if it doesn't exist
    if not dataset_path.exists():
        dataset_path.mkdir(parents=True, exist_ok=True)
        print(f"Created dataset folder: {dataset_path}")
    
    # Load results
    print(f"Loading results from {results_path}...")
    results = load_results(str(results_path))[:12]
    print(f"Found {len(results)} videos to process")
    print(f"Dataset path: {dataset_path}")
    
    # Print valid tags
    print(f"\nValid tags ({len(VALID_TAGS)}): {', '.join(sorted(VALID_TAGS))}")
    
    # Load run metadata (for tracking failures across runs)
    metadata = load_run_metadata(str(metadata_path), args.folder, args.file, args.model)
    
    # Process batches
    current_idx = 0
    total_items = len(results)
    batch_size = args.batch_size
    model = args.model
    
    total_success = 0
    total_skipped = 0
    total_failed = 0
    
    try:
        while current_idx < len(results):
            # Print batch header
            end_idx = min(current_idx + batch_size, len(results))
            print(f"\n--- Batch {current_idx}-{end_idx - 1} ---")
            
            # Process batch
            next_idx, batch_success, batch_skipped, batch_failed = process_batch(
                model,
                results,
                current_idx,
                batch_size,
                dataset_path,
                metadata,
                args.force_rewrite
            )
            
            total_success += batch_success
            total_skipped += batch_skipped
            total_failed += batch_failed
            
            # Print progress
            pct = (next_idx / total_items) * 100
            print(f"\n>>> {next_idx}/{total_items} ({pct:.1f}%) | new: {total_success}, skipped: {total_skipped}, failed: {total_failed}")
            
            # Update and save run metadata
            metadata['processed_count'] = total_success
            metadata['skipped_count'] = total_skipped
            save_run_metadata(str(metadata_path), metadata)
            
            current_idx = next_idx
    
    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress is saved via lock files. Resume with same command.")
        return 130
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        return 1
    
    # Final summary
    print(f"\n✓ Processing complete!")
    print(f"  Total videos in input: {len(results)}")
    print(f"  Newly processed: {total_success}")
    print(f"  Already processed (skipped): {total_skipped}")
    print(f"  Failed: {total_failed}")
    
    if metadata['failures']:
        print(f"\n  See extract-metadata.json for details on {len(metadata['failures'])} failures")
    
    print(f"\nDerived metadata saved to: dataset/<VIDEO_ID>/<VIDEO_ID>_derived-metadata.json")
    print(f"Run metadata saved to: {metadata_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
