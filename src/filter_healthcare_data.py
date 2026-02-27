#!/usr/bin/env python3
"""
Script to filter healthcare-related videos using Ollama LLM.
Processes results.json in batches with resume capability.
"""

import json
import argparse
import os
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel

from llm import get_response

from constants import PROGRAM_NAMES

class HealthcareResponse(BaseModel):
    """Structured response for healthcare classification."""
    healthcare: bool


# Load prompts from files
PROMPTS_DIR = Path(__file__).parent / "prompts" / "healthcare-classification"

def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the healthcare-classification prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")

def load_results(results_path: str) -> List[Dict[str, Any]]:
    """Load results.json file."""
    with open(results_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_state(state_path: str) -> Dict[str, Any]:
    """Load filter state if it exists."""
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_state(state_path: str, state: Dict[str, Any]) -> None:
    """Save filter state."""
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def load_metadata(metadata_path: str, folder: str, file: str, model: str) -> Dict[str, Any]:
    """Load or create filter metadata."""
    if os.path.exists(metadata_path):
        return json.load(open(metadata_path, 'r', encoding='utf-8'))
    
    return {
        'folder': folder,
        'file': file,
        'model': model,
        'failures': []
    }


def save_metadata(metadata_path: str, metadata: Dict[str, Any]) -> None:
    """Save filter metadata."""
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def load_filtered_results(filtered_path: str) -> List[Dict[str, Any]]:
    """Load filtered results if they exist."""
    if os.path.exists(filtered_path):
        with open(filtered_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_filtered_results(filtered_path: str, results: List[Dict[str, Any]]) -> None:
    """Save filtered results."""
    with open(filtered_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def load_rejected_results(rejected_path: str) -> List[Dict[str, Any]]:
    """Load rejected (non-healthcare) results if they exist."""
    if os.path.exists(rejected_path):
        with open(rejected_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_rejected_results(rejected_path: str, results: List[Dict[str, Any]]) -> None:
    """Save rejected (non-healthcare) results."""
    with open(rejected_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def add_failure(metadata: Dict[str, Any], index: int, video_id: str, reason: str) -> None:
    """Add a failure entry to metadata."""
    metadata['failures'].append({
        'index': index,
        'video_id': video_id,
        'reason': reason
    })

def is_healthcare_video(model: str, title: str, description: str, max_retries: int = 5) -> bool:
    """
    Query LLM to determine if a video is healthcare-related.
    Uses prompts loaded from markdown files.
    Retries up to max_retries times if JSON parsing fails.
    Returns True if healthcare-related, False otherwise.
    """

    # if any of the program names found in title, return true
    for pname in PROGRAM_NAMES:
        if pname.lower() in title.lower():
            # print("\n\nAUTO\n\n")
            return True

    # Build prompt from file-based templates
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
                format_schema=HealthcareResponse.model_json_schema(),
            )
            
            # Parse JSON response
            result = HealthcareResponse.model_validate_json(response.content)
            return result.healthcare
        
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


def process_batch(
    model: str,
    results: List[Dict[str, Any]],
    start_idx: int,
    batch_size: int,
    filtered_results: List[Dict[str, Any]],
    rejected_results: List[Dict[str, Any]],
    metadata: Dict[str, Any]
) -> tuple[int, int]:
    """
    Process a batch of results.
    Returns (next_idx, failed_count)
    """
    end_idx = min(start_idx + batch_size, len(results))
    failed_count = 0
    
    for i in range(start_idx, end_idx):
        result = results[i]
        title = result.get('title', '')
        normalized_desc = result.get('normalizedDescription', '')
        video_id = result.get('videoId', 'unknown')
        
        try:
            print(f"  [{i}] {title[:60]}...", end=' ')
            
            is_healthcare = is_healthcare_video(model, title, normalized_desc)
            
            if is_healthcare:
                # Add to filtered results with original index
                filtered_entry = result.copy()
                filtered_entry['idx'] = i
                filtered_results.append(filtered_entry)
                print("✓ Healthcare")
            else:
                # Add to rejected results with original index
                rejected_entry = result.copy()
                rejected_entry['idx'] = i
                rejected_results.append(rejected_entry)
                print("✗ Not healthcare")
                add_failure(metadata, i, video_id, "not healthcare-related")
                failed_count += 1
                
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            add_failure(metadata, i, video_id, f"classification error: {str(e)}")
            failed_count += 1
    
    return end_idx, failed_count


def main():
    parser = argparse.ArgumentParser(
        description='Filter healthcare videos from results.json using Ollama'
    )
    parser.add_argument(
        '--folder',
        type=str,
        default='saved-data',
        help='Path to folder containing results.json (default: saved-data)'
    )

    parser.add_argument(
        '--file',
        type=str,
        default='results.json',
        help='Filename of results JSON file (default: results.json)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default="ollama/qwen3:8b",
        help='Ollama model name to use for classification (default: ollama/qwen3:8b)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Batch size for processing (default: 5)'
    )
    parser.add_argument(
        '--force-restart',
        action='store_true',
        help='Ignore existing filter-state.json and start from beginning'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    folder_path = Path(args.folder)
    file_name = args.file
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path
    
    results_path = folder_path / file_name
    state_path = folder_path / 'filter-state.json'
    metadata_path = folder_path / 'filter-metadata.json'
    filtered_path = folder_path / 'filtered-results.json'
    rejected_path = folder_path / 'rejected-non-healthcare-results.json'
    
    # Validate results.json exists
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        return 1
    
    # Load results
    print(f"Loading results from {results_path}...")
    results = load_results(str(results_path))
    print(f"Found {len(results)} total videos")
    
    # Check for existing state
    existing_state = load_state(str(state_path))
    
    if existing_state and not args.force_restart:
        # Resume from existing state
        print(f"\nResuming from existing state...")
        start_idx = existing_state['last_processed_index'] + 1
        batch_size = existing_state['batch_size']
        model = existing_state['model']
        filtered_results = load_filtered_results(str(filtered_path))
        rejected_results = load_rejected_results(str(rejected_path))
        metadata = load_metadata(str(metadata_path), args.folder, args.file, args.model)
        
        if model != args.model:
            print(f"Warning: State has model '{model}' but using '{args.model}'")
            model = args.model
        
        print(f"Resuming from index {start_idx} with batch size {batch_size}")
    else:
        # Start fresh
        if existing_state:
            print("Force restarting (ignoring existing state)...")
        start_idx = 0
        batch_size = args.batch_size
        model = args.model
        filtered_results = []
        rejected_results = []
        metadata = load_metadata(str(metadata_path), args.folder, args.file, args.model)
    
    # Process batches
    current_idx = start_idx
    total_items = len(results)
    
    try:
        while current_idx < len(results):
            # Print batch header
            end_idx = min(current_idx + batch_size, len(results))
            print(f"\n--- Batch {current_idx}-{end_idx - 1} ---")
            
            # Process batch
            next_idx, batch_failed = process_batch(
                model,
                results,
                current_idx,
                batch_size,
                filtered_results,
                rejected_results,
                metadata
            )
            
            # Print progress
            pct = (next_idx / total_items) * 100
            print(f"\n>>> {next_idx}/{total_items} ({pct:.1f}%) processed | healthcare: {len(filtered_results)}, rejected: {len(rejected_results)}")
            
            # Save state after each batch
            state = {
                'folder': args.folder,
                'file': args.file,
                'model': model,
                'batch_size': batch_size,
                'last_processed_index': next_idx - 1
            }
            save_state(str(state_path), state)
            
            # Save metadata
            save_metadata(str(metadata_path), metadata)
            
            # Save filtered results
            save_filtered_results(str(filtered_path), filtered_results)
            
            # Save rejected results
            save_rejected_results(str(rejected_path), rejected_results)
            
            current_idx = next_idx
    
    except KeyboardInterrupt:
        print("\n\nInterrupted! State saved. Resume with same command.")
        return 130
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        return 1
    
    # Cleanup state file when complete
    if current_idx >= len(results):
        print(f"\n✓ Processing complete!")
        print(f"  Total videos processed: {len(results)}")
        print(f"  Healthcare videos found: {len(filtered_results)}")
        print(f"  Non-healthcare videos: {len(rejected_results)}")
        
        if metadata['failures']:
            print(f"\n  See filter-metadata.json for details on {len(metadata['failures'])} failures")
        
        # Remove state file on completion
        if state_path.exists():
            state_path.unlink()
            print(f"\n✓ Removed filter-state.json (processing complete)")
        
        print(f"\nResults saved to:")
        print(f"  Healthcare: {filtered_path}")
        print(f"  Non-healthcare: {rejected_path}")
        print(f"  Metadata: {metadata_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())