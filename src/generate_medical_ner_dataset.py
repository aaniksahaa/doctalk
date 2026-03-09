#!/usr/bin/env python3
"""
Script to generate medical NER downstream dataset from conversation data using LLM.

Iterates over video folders in the dataset, finds conversation.json files,
extracts text samples from conversation turns, batches them, sends to LLM
for NER annotation using prompts from medical-ner-dataset-generator, and
saves results per video.

Output structure (sibling to conversation.json):
  downstream/
    medical-ner/
      <model-name>/
        batches/
          batch_0.json
          batch_1.json
          ...
        ner_output.json
        metadata.json
        .medical-ner.lock

Usage:
  python generate_medical_ner_dataset.py
  python generate_medical_ner_dataset.py --model gemini-2.5-flash --batch-size 5
  python generate_medical_ner_dataset.py --force-rewrite
"""

import json
import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from llm import get_response


# ── Prompt loading ───────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts" / "medical-ner-dataset-generator"


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the medical-ner-dataset-generator prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")


# ── Constants ────────────────────────────────────────────────────────────────

CONVERSATION_SUBPATH = "transcribed/yt-auto/parsed/gemini-3-flash-preview"
DOWNSTREAM_DIR = "downstream"
NER_SUBDIR = "medical-ner"
BATCHES_SUBDIR = "batches"
NER_OUTPUT_FILE = "ner_output.json"
METADATA_FILE = "metadata.json"
LOCK_FILE = ".medical-ner.lock"


# ── Conversation loading & sample extraction ─────────────────────────────────

def find_conversation_file(video_folder: Path, video_id: str) -> Optional[Path]:
    """Find the conversation.json file for a video."""
    conv_path = video_folder / CONVERSATION_SUBPATH / f"{video_id}_conversation.json"
    return conv_path if conv_path.exists() else None


def load_conversation(conv_path: Path) -> List[Dict[str, Any]]:
    """Load conversation JSON array."""
    with open(conv_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_text_samples(conversation: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Extract text samples from conversation elements.

    For each element (host_doctor_qa or patient_call), concatenates all turns'
    text into a single sample. Returns a list of {"text": "..."} dicts matching
    the LLM input format.
    """
    samples = []
    for element in conversation:
        turns = element.get("turns", [])
        if not turns:
            continue
        combined_text = " ".join(
            turn["text"] for turn in turns if turn.get("text")
        )
        if combined_text.strip():
            samples.append({"text": combined_text.strip()})
    return samples


# ── Batching ─────────────────────────────────────────────────────────────────

def batch_samples(
    samples: List[Dict[str, str]], batch_size: int
) -> List[List[Dict[str, str]]]:
    """Split samples into batches of at most batch_size."""
    return [
        samples[i : i + batch_size]
        for i in range(0, len(samples), batch_size)
    ]


# ── LLM interaction ─────────────────────────────────────────────────────────

def run_ner_on_batch(
    model: str,
    batch: List[Dict[str, str]],
    max_retries: int = 2,
) -> List[Dict[str, Any]]:
    """
    Send a batch of text samples to the LLM for medical NER annotation.

    Constructs the prompt by appending the JSON-encoded batch after HEADER_PROMPT.
    Returns the parsed NER annotation list from the LLM.
    Retries up to max_retries times on JSON parse failures.
    """
    input_json = json.dumps(batch, ensure_ascii=False, indent=2)
    prompt = HEADER_PROMPT + input_json

    # Estimate prompt size (system + user prompt characters)
    prompt_chars = len(SYSTEM_PROMPT) + len(prompt)
    est_tokens = prompt_chars // 4  # rough char-to-token estimate
    print(
        f"\n    \033[94m── Prompt size: ~{est_tokens:,} tokens "
        f"({prompt_chars:,} chars)\033[0m"
    )

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = get_response(
                prompt=prompt,
                model=model,
                system_prompt=SYSTEM_PROMPT,
            )

            # Print actual token usage from LLM response
            meta = response.metadata
            print(
                f"    \033[94m── Actual tokens  → "
                f"in: {meta.input_tokens:,}  "
                f"out: {meta.output_tokens:,}  "
                f"total: {meta.total_tokens:,}  "
                f"({meta.inference_time_seconds:.1f}s)\033[0m"
            )

            content = response.content.strip()

            # Strip markdown code fences if present
            if content.startswith("```json"):
                content = content[len("```json"):]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            if not isinstance(result, list):
                raise ValueError("LLM response is not a JSON array")

            if len(result) != len(batch):
                print(
                    f"\n    Warning: expected {len(batch)} results, got {len(result)}"
                )

            return result

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                print(
                    f"\n    \033[91mRetry {attempt}/{max_retries} – parse error: "
                    f"{str(e)}\033[0m"
                )
            continue
        except Exception as e:
            err_str = str(e)
            # Retry with exponential backoff on rate-limit (429) errors
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = min(2 ** attempt * 30, 120) 
                print(
                    f"\n    \033[91mRate limited (429). Waiting {wait}s before retry "
                    f"{attempt}/{max_retries}...\n    {err_str}\033[0m"
                )
                time.sleep(wait)
                last_error = e
                continue
            raise Exception(f"LLM inference error: {err_str}")

    raise Exception(
        f"Failed to parse LLM response after {max_retries} attempts: "
        f"{str(last_error)}"
    )


# ── Lock / skip helpers ──────────────────────────────────────────────────────

def is_video_processed(ner_dir: Path) -> bool:
    """Check if video has already been processed (lock file exists)."""
    return (ner_dir / LOCK_FILE).exists()


def create_lock_file(ner_dir: Path) -> None:
    """Create lock file to mark video as fully processed."""
    (ner_dir / LOCK_FILE).touch()


# ── Per-video processing ─────────────────────────────────────────────────────

def process_video(
    model: str,
    video_folder: Path,
    video_id: str,
    batch_size: int,
    max_retries: int,
    force_rewrite: bool = False,
    request_delay: float = 10.0,
) -> str:
    """
    Process a single video for NER dataset generation.

    Returns one of: 'success', 'skipped', 'no-conversation', 'failed'.
    """
    # ── locate conversation file ──
    conv_path = find_conversation_file(video_folder, video_id)
    if conv_path is None:
        return "no-conversation"

    # ── output directories ──
    parsed_dir = conv_path.parent
    ner_dir = parsed_dir / DOWNSTREAM_DIR / NER_SUBDIR / model
    batches_dir = ner_dir / BATCHES_SUBDIR

    # ── check lock ──
    if not force_rewrite and is_video_processed(ner_dir):
        return "skipped"

    # ── load conversation ──
    try:
        conversation = load_conversation(conv_path)
    except Exception as e:
        print(f"\n    \033[91mError loading conversation: {str(e)}\033[0m")
        return "failed"

    # ── extract samples ──
    samples = extract_text_samples(conversation)
    if not samples:
        return "no-conversation"

    # ── ensure output dirs ──
    batches_dir.mkdir(parents=True, exist_ok=True)

    # ── batch & process ──
    batches = batch_samples(samples, batch_size)
    all_results: List[Dict[str, Any]] = []

    for batch_idx, batch in enumerate(batches):
        batch_file = batches_dir / f"batch_{batch_idx}.json"

        # Reuse cached batch result if available (and not force-rewriting)
        if not force_rewrite and batch_file.exists():
            try:
                with open(batch_file, "r", encoding="utf-8") as f:
                    batch_result = json.load(f)
                all_results.extend(batch_result)
                print(f"\n    Batch {batch_idx}/{len(batches) - 1} – loaded from cache")
                continue
            except Exception:
                pass  # re-process if cache is corrupt

        try:
            print(
                f"\n    Batch {batch_idx}/{len(batches) - 1} "
                f"({len(batch)} sample{'s' if len(batch) != 1 else ''})...",
                end=" ",
            )
            batch_result = run_ner_on_batch(model, batch, max_retries)

            # Save batch checkpoint
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch_result, f, indent=2, ensure_ascii=False)

            all_results.extend(batch_result)
            print(f"✓ ({len(batch_result)} annotations)")

            # Throttle to avoid rate limits
            if request_delay > 0:
                print(f"    \033[90m── Sleeping {request_delay}s before next request...\033[0m")
                time.sleep(request_delay)

        except Exception as e:
            print(f"\033[91m✗ Error: {str(e)}\033[0m")
            return "failed"

    # ── combine & save final output ──
    output_file = ner_dir / NER_OUTPUT_FILE
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # ── save metadata ──
    meta = {
        "video_id": video_id,
        "model": model,
        "batch_size": batch_size,
        "total_samples": len(samples),
        "total_batches": len(batches),
        "total_annotations": len(all_results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_file = ner_dir / METADATA_FILE
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── mark done ──
    create_lock_file(ner_dir)

    return "success"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate medical NER downstream dataset from conversation data "
            "using LLM"
        )
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="saved-data",
        help="Path to folder containing the dataset (default: saved-data)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Model name for NER generation (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of text samples per LLM batch (default: 5)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retries per batch on parse failure (default: 2)",
    )
    parser.add_argument(
        "--force-rewrite",
        action="store_true",
        help="Ignore lock files and reprocess all videos",
    )
    parser.add_argument(
        "--first-n",
        type=int,
        default=-1,
        help="Only process the first N videos; -1 means all (default: -1)",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=60.0,
        help="Seconds to sleep after each successful LLM request (default: 60)",
    )

    args = parser.parse_args()

    # ── resolve paths ──
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path

    dataset_path = folder_path / "dataset"

    if not dataset_path.exists():
        print(f"Error: Dataset path {dataset_path} not found")
        return 1

    # ── discover video folders ──
    video_folders = sorted(
        d for d in dataset_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    # ── apply --first-n limit ──
    total_available = len(video_folders)
    if args.first_n > 0:
        video_folders = video_folders[: args.first_n]

    print(f"Dataset path : {dataset_path}")
    print(f"Model        : {args.model}")
    print(f"Batch size   : {args.batch_size}")
    print(f"Max retries  : {args.max_retries}")
    print(f"Video folders: {len(video_folders)}"
          f"{f' (limited from {total_available})' if args.first_n > 0 else ''}")
    print(f"First N      : {'all' if args.first_n < 0 else args.first_n}")
    print(f"Request delay: {args.request_delay}s")
    print()

    # ── counters ──
    total_success = 0
    total_skipped = 0
    total_no_conv = 0
    total_failed = 0

    try:
        for idx, video_folder in enumerate(video_folders):
            video_id = video_folder.name

            print(f"[{idx + 1}/{len(video_folders)}] {video_id}", end=" ")

            status = process_video(
                model=args.model,
                video_folder=video_folder,
                video_id=video_id,
                batch_size=args.batch_size,
                max_retries=args.max_retries,
                force_rewrite=args.force_rewrite,
                request_delay=args.request_delay,
            )

            if status == "success":
                total_success += 1
                print("✓")
            elif status == "skipped":
                total_skipped += 1
                print("– skipped (already processed)")
            elif status == "no-conversation":
                total_no_conv += 1
                print("– no conversation file")
            elif status == "failed":
                total_failed += 1
                # error details already printed in process_video

            # periodic progress summary
            if (idx + 1) % 50 == 0:
                pct = ((idx + 1) / len(video_folders)) * 100
                print(
                    f"\n>>> Progress: {idx + 1}/{len(video_folders)} ({pct:.1f}%) "
                    f"| success: {total_success}, skipped: {total_skipped}, "
                    f"no-conv: {total_no_conv}, failed: {total_failed}\n"
                )

    except KeyboardInterrupt:
        print(
            "\n\nInterrupted! Progress is saved via lock files and batch "
            "checkpoints. Resume with the same command."
        )
        return 130

    # ── final summary ──
    print(f"\n✓ Processing complete!")
    print(f"  Total video folders       : {len(video_folders)}")
    print(f"  Newly processed (success) : {total_success}")
    print(f"  Already processed (skip)  : {total_skipped}")
    print(f"  No conversation file      : {total_no_conv}")
    print(f"  Failed                    : {total_failed}")
    print(
        f"\nNER outputs saved to: "
        f"dataset/<VIDEO_ID>/{CONVERSATION_SUBPATH}/{DOWNSTREAM_DIR}/"
        f"{NER_SUBDIR}/<MODEL>/{NER_OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    exit(main())
