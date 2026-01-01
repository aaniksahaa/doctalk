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
from ollama import chat
from pydantic import BaseModel

class Response(BaseModel):
  res: bool

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


def is_healthcare_video(model: str, title: str, description: str) -> bool:
    """
    Query Ollama to determine if a video is healthcare-related.
    Returns True if healthcare-related, False otherwise.
    """
    prompt = f"""You are a healthcare content classifier. Analyze the following video metadata and determine if it is related to healthcare, medicine, health tips, or medical discussions.

Title: {title}
Description: {description}

Respond with a JSON object with a single field "healthcare" set to true or false."""

    try:
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that classifies healthcare content."},
                {"role": "user", "content": prompt}
            ],
            format=Response.model_json_schema()
        )
        
        # Parse JSON response
        res = Response.model_validate_json(response.message.content)
        return res.res
    
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response from Ollama: {str(e)}")
    except Exception as e:
        raise Exception(f"Error querying Ollama: {str(e)}")


def process_batch(
    model: str,
    results: List[Dict[str, Any]],
    start_idx: int,
    batch_size: int,
    filtered_results: List[Dict[str, Any]],
    failed_indexes: List[int]
) -> tuple[int, int]:
    """
    Process a batch of results.
    Returns (next_idx, failed_count)
    """
    end_idx = min(start_idx + batch_size, len(results))
    failed_count = 0
    
    print(f"\nProcessing batch: {start_idx} to {end_idx - 1}")
    
    for i in range(start_idx, end_idx):
        result = results[i]
        title = result.get('title', '')
        normalized_desc = result.get('normalizedDescription', '')
        
        try:
            print(f"  [{i}] Processing: {title[:50]}...", end=' ')
            
            is_healthcare = is_healthcare_video(model, title, normalized_desc)
            
            if is_healthcare:
                # Add to filtered results with original index
                filtered_entry = result.copy()
                filtered_entry['idx'] = i
                filtered_results.append(filtered_entry)
                print("✓ Healthcare")
            else:
                print("✗ Not healthcare")
                failed_indexes.append(i)
                failed_count += 1
                
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            failed_indexes.append(i)
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
    filtered_path = folder_path / 'filtered-results.json'
    
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
        start_idx = existing_state['start_idx']
        batch_size = existing_state['batch_size']
        model = existing_state['model_name']
        filtered_results = load_filtered_results(str(filtered_path))
        failed_indexes = existing_state.get('failed_indexes', [])
        
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
        failed_indexes = []
    
    # Process batches
    current_idx = start_idx
    total_failed = len(failed_indexes)
    
    try:
        while current_idx < len(results):
            # Process batch
            next_idx, batch_failed = process_batch(
                model,
                results,
                current_idx,
                batch_size,
                filtered_results,
                failed_indexes
            )
            total_failed += batch_failed
            
            # Save state
            state = {
                'model_name': model,
                'start_idx': next_idx,
                'batch_size': batch_size,
                'failed_indexes': failed_indexes,
                'total_processed': next_idx,
                'total_results': len(results)
            }
            save_state(str(state_path), state)
            
            # Save filtered results
            save_filtered_results(str(filtered_path), filtered_results)
            
            print(f"  Saved: {len(filtered_results)} healthcare videos, {len(failed_indexes)} non-healthcare")
            
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
        print(f"  Non-healthcare videos: {len(failed_indexes)}")
        
        if failed_indexes:
            print(f"\n  Failed indexes (non-healthcare): {failed_indexes}")
        
        # Remove state file on completion
        if state_path.exists():
            state_path.unlink()
        
        print(f"\nResults saved to: {filtered_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
