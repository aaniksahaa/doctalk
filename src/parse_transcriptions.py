#!/usr/bin/env python3
"""
Script to parse healthcare video transcriptions into structured JSON conversations.
Sends transcriptions to an LLM (Gemini or Ollama) which parses them into
host-doctor QA and patient-call conversation objects.

Output: dataset/<video_id>/transcribed/yt-auto/parsed/<model_name>/conversation.json
"""

import json
import re
import argparse
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from llm import get_response, LLMOptions


# Load prompts from files
PROMPTS_DIR = Path(__file__).parent / "prompts" / "parsing"


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the parsing prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")


def normalize_model_name(model: str) -> str:
    """Normalize model name for use as directory name (replace / and : with -)."""
    return model.replace("/", "-").replace(":", "-")


def load_results(results_path: str) -> List[Dict[str, Any]]:
    """Load results JSON file."""
    with open(results_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_run_metadata(metadata_path: str, folder: str, file: str, model: str) -> Dict[str, Any]:
    """Load or create parsing run metadata."""
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
    """Save parsing run metadata."""
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def add_failure(metadata: Dict[str, Any], index: int, video_id: str, reason: str) -> None:
    """Add a failure entry to metadata."""
    metadata['failures'].append({
        'index': index,
        'video_id': video_id,
        'reason': reason
    })


def load_transcript(video_folder: Path, video_id: str) -> Optional[str]:
    """
    Load the full transcript with timestamps from the video folder.
    Returns the full transcript text, or None if not found.
    """
    transcript_path = (
        video_folder / "transcribed" / "yt-auto"
        / f"{video_id}_transcription-processed-with-timestamp.txt"
    )

    if not transcript_path.exists():
        return None

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def extract_json_from_response(text: str) -> str:
    """
    Extract JSON content from LLM response.
    Handles responses wrapped in ```json ... ``` fences.
    """
    # Try to find JSON inside markdown code fences
    pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no fences found, return the raw text (might already be pure JSON)
    return text.strip()


def parse_transcript(
    model: str,
    transcript: str,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Send transcript to LLM for parsing into structured conversation JSON.
    Retries on JSON parse failures.
    Returns parsed list of conversation objects.
    """
    prompt = HEADER_PROMPT + transcript

    # Use larger context and output for parsing (transcripts can be long)
    options = LLMOptions(
        num_ctx=65536,
        num_predict=32768,
        temperature=0.1,
        top_p=0.9,
    )

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = get_response(
                prompt=prompt,
                model=model,
                system_prompt=SYSTEM_PROMPT,
                options=options,
            )

            # Extract JSON from response (strip markdown fences if present)
            json_text = extract_json_from_response(response.content)

            # Validate JSON
            parsed = json.loads(json_text)

            # Ensure it's a list
            if not isinstance(parsed, list):
                raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

            return parsed

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


def get_output_dir(video_folder: Path, model: str) -> Path:
    """Get the output directory for parsed results."""
    model_dir = normalize_model_name(model)
    return video_folder / "transcribed" / "yt-auto" / "parsed" / model_dir


def is_video_parsed(output_dir: Path) -> bool:
    """Check if video has already been parsed (lock file exists)."""
    lock_file = output_dir / ".parse.lock"
    return lock_file.exists()


def create_lock_file(output_dir: Path) -> None:
    """Create lock file to mark video as parsed."""
    lock_file = output_dir / ".parse.lock"
    lock_file.touch()


def save_conversation(output_dir: Path, data: List[Dict[str, Any]]) -> Path:
    """Save parsed conversation JSON to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "conversation.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_file


def process_video(
    model: str,
    result: Dict[str, Any],
    idx: int,
    dataset_path: Path,
    metadata: Dict[str, Any],
    force_rewrite: bool = False,
) -> str:
    """
    Process a single video for transcript parsing.
    Returns: 'success', 'skipped', or 'failed'
    """
    video_id = result.get('videoId', 'unknown')
    title = result.get('title', '')

    video_folder = dataset_path / video_id
    output_dir = get_output_dir(video_folder, model)

    # Check if already parsed
    if not force_rewrite and is_video_parsed(output_dir):
        print(f"  [{idx}] {video_id} - ✓ Already parsed (lock file found)")
        return 'skipped'

    # Load transcript
    transcript = load_transcript(video_folder, video_id)
    if transcript is None:
        print(f"  [{idx}] {video_id} - ✗ No transcript found")
        add_failure(metadata, idx, video_id, "no transcript found")
        return 'failed'

    try:
        transcript_len = len(transcript)
        print(f"  [{idx}] {title[:50]}... ({transcript_len} chars)", end=' ')

        # Parse transcript via LLM
        conversations = parse_transcript(model, transcript)

        # Save results
        output_file = save_conversation(output_dir, conversations)
        create_lock_file(output_dir)

        num_convos = len(conversations)
        print(f"✓ {num_convos} conversations → {output_file.relative_to(dataset_path)}")
        return 'success'

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        add_failure(metadata, idx, video_id, f"parsing error: {str(e)}")
        return 'failed'


def process_batch(
    model: str,
    results: List[Dict[str, Any]],
    start_idx: int,
    batch_size: int,
    dataset_path: Path,
    metadata: Dict[str, Any],
    force_rewrite: bool = False,
) -> tuple[int, int, int, int]:
    """
    Process a batch of results for transcript parsing.
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


def run_test_mode(model: str, video_id: str, dataset_path: Path) -> int:
    """
    Run parsing for a single video ID and dump to test-parse-output.json.
    Returns exit code.
    """
    print(f"\n{'='*60}")
    print(f"TEST MODE: Parsing single video {video_id}")
    print(f"{'='*60}\n")

    video_folder = dataset_path / video_id

    if not video_folder.exists():
        print(f"Error: Video folder not found: {video_folder}")
        return 1

    transcript = load_transcript(video_folder, video_id)
    if transcript is None:
        print(f"Error: No transcript found for {video_id}")
        return 1

    print(f"Transcript length: {len(transcript)} chars")
    print(f"Model: {model}")
    print(f"Sending to LLM...\n")

    try:
        conversations = parse_transcript(model, transcript)

        # Save to test output file in CWD
        test_output = Path("test-parse-output.json")
        with open(test_output, 'w', encoding='utf-8') as f:
            json.dump(conversations, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Parsed {len(conversations)} conversations")
        print(f"✓ Saved to: {test_output.resolve()}")

        # Print summary
        for i, conv in enumerate(conversations):
            conv_type = conv.get('type', '?')
            timestamp = conv.get('timestamp', '?')
            num_turns = len(conv.get('turns', []))
            print(f"  [{i}] {conv_type} @ {timestamp} ({num_turns} turns)")

        return 0

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Parse healthcare video transcriptions into structured JSON conversations using LLM'
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
        default='gemini-3-flash-preview',
        help='Model name to use for parsing (default: gemini-3-flash-preview)'
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
    parser.add_argument(
        '--test-video-id',
        type=str,
        default=None,
        help='Run parsing for a single video ID only (test mode). Output saved to test-parse-output.json'
    )

    args = parser.parse_args()

    # Resolve paths
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path

    dataset_path = folder_path / 'dataset'

    # Test mode: parse a single video
    if args.test_video_id:
        return run_test_mode(args.model, args.test_video_id, dataset_path)

    # Full mode: process all videos
    file_name = args.file
    results_path = folder_path / file_name
    metadata_path = folder_path / 'parsing-metadata.json'

    # Validate input file exists
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        return 1

    # Validate dataset folder exists
    if not dataset_path.exists():
        print(f"Error: Dataset folder not found: {dataset_path}")
        return 1

    # Load results
    print(f"Loading results from {results_path}...")
    results = load_results(str(results_path))
    print(f"Found {len(results)} videos to process")
    print(f"Model: {args.model}")
    print(f"Output: dataset/<video_id>/transcribed/yt-auto/parsed/{normalize_model_name(args.model)}/conversation.json")

    # Load run metadata
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
    print(f"\n✓ Parsing complete!")
    print(f"  Total videos in input: {len(results)}")
    print(f"  Newly parsed: {total_success}")
    print(f"  Already parsed (skipped): {total_skipped}")
    print(f"  Failed: {total_failed}")

    if metadata['failures']:
        print(f"\n  See parsing-metadata.json for details on {len(metadata['failures'])} failures")

    model_dir = normalize_model_name(args.model)
    print(f"\nParsed conversations saved to: dataset/<VIDEO_ID>/transcribed/yt-auto/parsed/{model_dir}/conversation.json")
    print(f"Run metadata saved to: {metadata_path}")

    return 0


if __name__ == '__main__':
    exit(main())
