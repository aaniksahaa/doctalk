#!/usr/bin/env python3
"""
Script to generate triage classification downstream dataset from conversation
data using LLM.

Iterates over video folders in the dataset, finds conversation.json files,
collects only patient_call conversations, batches them, sends to LLM for
triage classification using prompts from triage-dataset-generator, and saves
results per video.

Output structure (sibling to conversation.json):
  downstream/
    triage/
      <model-name>/
        batches/
          batch_0.json
          batch_1.json
          ...
        triage_output.json
        metadata.json
        .triage.lock

Usage:
  python generate_triage_dataset.py
  python generate_triage_dataset.py --model gemini-2.5-flash --batch-size 3
  python generate_triage_dataset.py --force-rewrite
  python generate_triage_dataset.py --first-n 5
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

PROMPTS_DIR = Path(__file__).parent / "prompts" / "triage-dataset-generator"


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the triage-dataset-generator prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")


# ── Constants ────────────────────────────────────────────────────────────────

VALID_TYPES = {
    "REASSURANCE_SELF_CARE",
    "ROUTINE_OUTPATIENT_VISIT",
    "INVESTIGATION_OR_SPECIALIST_REFERRAL",
    "URGENT_EMERGENCY_CARE",
}

CONVERSATION_SUBPATH = "transcribed/yt-auto/parsed/gemini-3-flash-preview"
DOWNSTREAM_DIR = "downstream"
TRIAGE_SUBDIR = "triage"
BATCHES_SUBDIR = "batches"
TRIAGE_OUTPUT_FILE = "triage_output.json"
METADATA_FILE = "metadata.json"
LOCK_FILE = ".triage.lock"


# ── Conversation loading & sample extraction ─────────────────────────────────

def find_conversation_file(video_folder: Path, video_id: str) -> Optional[Path]:
    """Find the conversation.json file for a video."""
    conv_path = (
        video_folder
        / CONVERSATION_SUBPATH
        / f"{video_id}_conversation.json"
    )
    return conv_path if conv_path.exists() else None


def load_conversation(conv_path: Path) -> List[Dict[str, Any]]:
    """Load conversation JSON array."""
    with open(conv_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_patient_calls(
    conversation: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract only patient_call conversation elements from a conversation array.

    Returns a list of the raw conversation objects (with type, timestamp, turns)
    that have type == "patient_call".
    """
    return [
        elem
        for elem in conversation
        if elem.get("type") == "patient_call"
    ]


# ── Batching ─────────────────────────────────────────────────────────────────

def batch_items(
    items: List[Any], batch_size: int
) -> List[List[Any]]:
    """Split items into batches of at most batch_size."""
    return [
        items[i : i + batch_size]
        for i in range(0, len(items), batch_size)
    ]


# ── LLM interaction ─────────────────────────────────────────────────────────

def build_llm_input(
    patient_calls: List[Dict[str, Any]],
    id_offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Build the LLM input array from patient_call elements.

    Each element becomes {"id": <sequential>, "conversation": <the element>}.
    The id is batch-local and used only for matching LLM outputs.
    """
    return [
        {"id": id_offset + i, "conversation": call}
        for i, call in enumerate(patient_calls)
    ]


def run_triage_on_batch(
    model: str,
    batch_input: List[Dict[str, Any]],
    max_retries: int = 2,
) -> List[Dict[str, Any]]:
    """
    Send a batch of patient_call conversations to the LLM for triage
    classification.

    Args:
        model: LLM model name
        batch_input: list of {"id": ..., "conversation": {...}} dicts
        max_retries: max retries on parse failure

    Returns:
        list of {"id": ..., "type": "..."} dicts from the LLM
    """
    input_json = json.dumps(batch_input, ensure_ascii=False, indent=2)
    prompt = HEADER_PROMPT + input_json

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = get_response(
                prompt=prompt,
                model=model,
                system_prompt=SYSTEM_PROMPT,
            )

            content = response.content.strip()

            # Strip markdown code fences if present
            if content.startswith("```json"):
                content = content[len("```json") :]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            if not isinstance(result, list):
                raise ValueError("LLM response is not a JSON array")

            # Validate each element has id and type
            for item in result:
                if "id" not in item or "type" not in item:
                    raise ValueError(
                        f"Missing 'id' or 'type' in LLM output element: "
                        f"{json.dumps(item, ensure_ascii=False)[:80]}"
                    )
                if item["type"] not in VALID_TYPES:
                    raise ValueError(
                        f"Invalid type '{item['type']}' – expected one of "
                        f"{VALID_TYPES}"
                    )

            if len(result) != len(batch_input):
                print(
                    f"\n    Warning: expected {len(batch_input)} results, "
                    f"got {len(result)}"
                )

            return result

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                print(
                    f"\n    Retry {attempt}/{max_retries} – parse error: "
                    f"{str(e)[:80]}"
                )
            continue
        except Exception as e:
            raise Exception(f"LLM inference error: {str(e)}")

    raise Exception(
        f"Failed to parse LLM response after {max_retries} attempts: "
        f"{str(last_error)}"
    )


def merge_batch_results(
    batch_input: List[Dict[str, Any]],
    llm_output: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge LLM output (id, type) with original conversations to produce
    the final dataset format: {conversation, type}.

    The id field is dropped — it was only used for matching.
    """
    # Build id → type lookup from LLM output
    type_by_id = {item["id"]: item["type"] for item in llm_output}

    merged = []
    for inp in batch_input:
        triage_type = type_by_id.get(inp["id"])
        if triage_type is None:
            print(
                f"\n    Warning: no LLM output for id {inp['id']}, skipping"
            )
            continue
        merged.append({
            "conversation": inp["conversation"],
            "type": triage_type,
        })
    return merged


# ── Lock / skip helpers ──────────────────────────────────────────────────────

def is_video_processed(triage_dir: Path) -> bool:
    """Check if video has already been processed (lock file exists)."""
    return (triage_dir / LOCK_FILE).exists()


def create_lock_file(triage_dir: Path) -> None:
    """Create lock file to mark video as fully processed."""
    (triage_dir / LOCK_FILE).touch()


# ── Per-video processing ─────────────────────────────────────────────────────

def process_video(
    model: str,
    video_folder: Path,
    video_id: str,
    batch_size: int,
    max_retries: int,
    force_rewrite: bool = False,
) -> str:
    """
    Process a single video for triage classification dataset generation.

    Returns one of: 'success', 'skipped', 'no-conversation', 'no-patient-calls',
    'failed'.
    """
    # ── locate conversation file ──
    conv_path = find_conversation_file(video_folder, video_id)
    if conv_path is None:
        return "no-conversation"

    # ── output directories ──
    parsed_dir = conv_path.parent
    triage_dir = parsed_dir / DOWNSTREAM_DIR / TRIAGE_SUBDIR / model
    batches_dir = triage_dir / BATCHES_SUBDIR

    # ── check lock ──
    if not force_rewrite and is_video_processed(triage_dir):
        return "skipped"

    # ── load conversation ──
    try:
        conversation = load_conversation(conv_path)
    except Exception as e:
        print(f"\n    Error loading conversation: {str(e)[:80]}")
        return "failed"

    # ── extract patient_call only ──
    patient_calls = extract_patient_calls(conversation)
    if not patient_calls:
        return "no-patient-calls"

    # ── ensure output dirs ──
    batches_dir.mkdir(parents=True, exist_ok=True)

    # ── batch & process ──
    batches = batch_items(patient_calls, batch_size)
    all_results: List[Dict[str, Any]] = []
    global_id = 0  # running id across batches for this video

    for batch_idx, batch in enumerate(batches):
        batch_file = batches_dir / f"batch_{batch_idx}.json"

        # Reuse cached batch result if available (and not force-rewriting)
        if not force_rewrite and batch_file.exists():
            try:
                with open(batch_file, "r", encoding="utf-8") as f:
                    batch_result = json.load(f)
                all_results.extend(batch_result)
                global_id += len(batch)
                print(
                    f"\n    Batch {batch_idx}/{len(batches) - 1} "
                    f"– loaded from cache"
                )
                continue
            except Exception:
                pass  # re-process if cache is corrupt

        try:
            print(
                f"\n    Batch {batch_idx}/{len(batches) - 1} "
                f"({len(batch)} call{'s' if len(batch) != 1 else ''})...",
                end=" ",
            )

            # Build LLM input with sequential ids
            batch_input = build_llm_input(batch, id_offset=global_id)

            llm_output = run_triage_on_batch(model, batch_input, max_retries)

            # Merge to final format: {conversation, type}
            batch_result = merge_batch_results(batch_input, llm_output)

            # Save batch checkpoint
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch_result, f, indent=2, ensure_ascii=False)

            all_results.extend(batch_result)
            global_id += len(batch)
            print(f"✓ ({len(batch_result)} classified)")

        except Exception as e:
            print(f"✗ Error: {str(e)[:100]}")
            return "failed"

    # ── combine & save final output ──
    output_file = triage_dir / TRIAGE_OUTPUT_FILE
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # ── save metadata ──
    meta = {
        "video_id": video_id,
        "model": model,
        "batch_size": batch_size,
        "total_patient_calls": len(patient_calls),
        "total_batches": len(batches),
        "total_classified": len(all_results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_file = triage_dir / METADATA_FILE
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── mark done ──
    create_lock_file(triage_dir)

    return "success"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate triage classification downstream dataset from "
            "conversation data using LLM"
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
        help="Model name for triage classification (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Number of patient calls per LLM batch (default: 3)",
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
        d
        for d in dataset_path.iterdir()
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
    print(
        f"Video folders: {len(video_folders)}"
        f"{f' (limited from {total_available})' if args.first_n > 0 else ''}"
    )
    print(f"First N      : {'all' if args.first_n < 0 else args.first_n}")
    print()

    # ── counters ──
    total_success = 0
    total_skipped = 0
    total_no_conv = 0
    total_no_calls = 0
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
            elif status == "no-patient-calls":
                total_no_calls += 1
                print("– no patient calls")
            elif status == "failed":
                total_failed += 1
                # error details already printed in process_video

            # periodic progress summary
            if (idx + 1) % 50 == 0:
                pct = ((idx + 1) / len(video_folders)) * 100
                print(
                    f"\n>>> Progress: {idx + 1}/{len(video_folders)} "
                    f"({pct:.1f}%) | success: {total_success}, "
                    f"skipped: {total_skipped}, no-conv: {total_no_conv}, "
                    f"no-calls: {total_no_calls}, "
                    f"failed: {total_failed}\n"
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
    print(f"  No patient calls          : {total_no_calls}")
    print(f"  Failed                    : {total_failed}")
    print(
        f"\nTriage outputs saved to: "
        f"dataset/<VIDEO_ID>/{CONVERSATION_SUBPATH}/{DOWNSTREAM_DIR}/"
        f"{TRIAGE_SUBDIR}/<MODEL>/{TRIAGE_OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    exit(main())
