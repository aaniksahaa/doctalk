#!/usr/bin/env python3
"""
Script to generate advice-safety downstream dataset from conversation data
using LLM.

Iterates over video folders in the dataset, finds conversation.json files,
collects ALL conversation elements (both patient_call and host_doctor_qa),
batches them, sends to LLM for recommendation-safety annotation using
prompts from advice-safety-dataset-generator, and saves results per video.

Output structure (sibling to conversation.json):
  downstream/
    advice-safety/
      <model-name>/
        batches/
          batch_0.json
          batch_1.json
          ...
        advice_safety_output.json
        metadata.json
        .advice-safety.lock

Usage:
  python generate_advice_safety_dataset.py
  python generate_advice_safety_dataset.py --model gemini-2.5-flash --batch-size 3
  python generate_advice_safety_dataset.py --force-rewrite
  python generate_advice_safety_dataset.py --first-n 5
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

PROMPTS_DIR = Path(__file__).parent / "prompts" / "advice-safety-dataset-generator"


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from the advice-safety-dataset-generator prompts directory."""
    filepath = PROMPTS_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_prompt_file("system.md")
HEADER_PROMPT = load_prompt_file("header.md")


# ── Constants ────────────────────────────────────────────────────────────────

VALID_LABELS = {"SAFE", "HARMFUL"}

CONVERSATION_SUBPATH = "transcribed/yt-auto/parsed/gemini-3-flash-preview"
DOWNSTREAM_DIR = "downstream"
SAFETY_SUBDIR = "advice-safety"
BATCHES_SUBDIR = "batches"
SAFETY_OUTPUT_FILE = "advice_safety_output.json"
METADATA_FILE = "metadata.json"
LOCK_FILE = ".advice-safety.lock"


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


def extract_all_conversations(
    conversation: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract all conversation elements (both patient_call and host_doctor_qa)
    that have non-empty turns.
    """
    return [
        elem
        for elem in conversation
        if elem.get("turns")
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
    conversations: List[Dict[str, Any]],
    id_offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Build the LLM input array from conversation elements.

    Each element becomes {"id": <sequential>, "conversation": <the element>}.
    The id is batch-local and used only for matching LLM outputs.
    """
    return [
        {"id": id_offset + i, "conversation": conv}
        for i, conv in enumerate(conversations)
    ]


def run_safety_on_batch(
    model: str,
    batch_input: List[Dict[str, Any]],
    max_retries: int = 2,
) -> List[Dict[str, Any]]:
    """
    Send a batch of conversations to the LLM for advice-safety annotation.

    Args:
        model: LLM model name
        batch_input: list of {"id": ..., "conversation": {...}} dicts
        max_retries: max retries on parse failure

    Returns:
        list of {"id": ..., "patient_profile": "...",
                 "recommendations": [{"content": "...", "label": "..."}]}
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

            # Validate each element
            for item in result:
                if "id" not in item:
                    raise ValueError(
                        f"Missing 'id' in LLM output element: "
                        f"{json.dumps(item, ensure_ascii=False)[:80]}"
                    )
                if "patient_profile" not in item:
                    raise ValueError(
                        f"Missing 'patient_profile' in LLM output for "
                        f"id {item.get('id')}"
                    )
                if "recommendations" not in item:
                    raise ValueError(
                        f"Missing 'recommendations' in LLM output for "
                        f"id {item.get('id')}"
                    )
                if not isinstance(item["recommendations"], list):
                    raise ValueError(
                        f"'recommendations' is not an array for "
                        f"id {item.get('id')}"
                    )
                for rec in item["recommendations"]:
                    if "content" not in rec or "label" not in rec:
                        raise ValueError(
                            f"Missing 'content' or 'label' in recommendation "
                            f"for id {item.get('id')}"
                        )
                    if rec["label"] not in VALID_LABELS:
                        raise ValueError(
                            f"Invalid label '{rec['label']}' – expected "
                            f"SAFE or HARMFUL"
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
                    f"\n    \033[91mRetry {attempt}/{max_retries} – parse error: "
                    f"{str(e)}\033[0m"
                )
            continue
        except Exception as e:
            err_str = str(e)
            # Retry with exponential backoff on rate-limit (429) errors
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = min(2 ** attempt * 40, 120)
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


def merge_batch_results(
    batch_input: List[Dict[str, Any]],
    llm_output: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge LLM output with original conversations to produce the final
    dataset format: {conversation, patient_profile, recommendations}.

    The id field is dropped — it was only used for matching.
    """
    # Build id → output lookup
    output_by_id = {item["id"]: item for item in llm_output}

    merged = []
    for inp in batch_input:
        out = output_by_id.get(inp["id"])
        if out is None:
            print(
                f"\n    Warning: no LLM output for id {inp['id']}, skipping"
            )
            continue
        merged.append({
            "conversation": inp["conversation"],
            "patient_profile": out["patient_profile"],
            "recommendations": out["recommendations"],
        })
    return merged


# ── Lock / skip helpers ──────────────────────────────────────────────────────

def is_video_processed(safety_dir: Path) -> bool:
    """Check if video has already been processed (lock file exists)."""
    return (safety_dir / LOCK_FILE).exists()


def create_lock_file(safety_dir: Path) -> None:
    """Create lock file to mark video as fully processed."""
    (safety_dir / LOCK_FILE).touch()


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
    Process a single video for advice-safety dataset generation.

    Returns one of: 'success', 'skipped', 'no-conversation', 'failed'.
    """
    # ── locate conversation file ──
    conv_path = find_conversation_file(video_folder, video_id)
    if conv_path is None:
        return "no-conversation"

    # ── output directories ──
    parsed_dir = conv_path.parent
    safety_dir = parsed_dir / DOWNSTREAM_DIR / SAFETY_SUBDIR / model
    batches_dir = safety_dir / BATCHES_SUBDIR

    # ── check lock ──
    if not force_rewrite and is_video_processed(safety_dir):
        return "skipped"

    # ── load conversation ──
    try:
        conversation = load_conversation(conv_path)
    except Exception as e:
        print(f"\n    \033[91mError loading conversation: {str(e)}\033[0m")
        return "failed"

    # ── extract all conversations (patient_call + host_doctor_qa) ──
    all_convs = extract_all_conversations(conversation)
    if not all_convs:
        return "no-conversation"

    # ── ensure output dirs ──
    batches_dir.mkdir(parents=True, exist_ok=True)

    # ── batch & process ──
    batches = batch_items(all_convs, batch_size)
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
                f"({len(batch)} conv{'s' if len(batch) != 1 else ''})...",
                end=" ",
            )

            # Build LLM input with sequential ids
            batch_input = build_llm_input(batch, id_offset=global_id)

            llm_output = run_safety_on_batch(model, batch_input, max_retries)

            # Merge to final format: {conversation, patient_profile, recommendations}
            batch_result = merge_batch_results(batch_input, llm_output)

            # Save batch checkpoint
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch_result, f, indent=2, ensure_ascii=False)

            all_results.extend(batch_result)
            global_id += len(batch)

            # Count total recommendations in this batch
            total_recs = sum(
                len(r.get("recommendations", [])) for r in batch_result
            )
            print(f"✓ ({len(batch_result)} profiles, {total_recs} recs)")

            # Throttle to avoid rate limits
            if request_delay > 0:
                print(f"    \033[90m── Sleeping {request_delay}s before next request...\033[0m")
                time.sleep(request_delay)

        except Exception as e:
            print(f"\033[91m✗ Error: {str(e)}\033[0m")
            return "failed"

    # ── combine & save final output ──
    output_file = safety_dir / SAFETY_OUTPUT_FILE
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # ── save metadata ──
    total_recs = sum(
        len(r.get("recommendations", [])) for r in all_results
    )
    meta = {
        "video_id": video_id,
        "model": model,
        "batch_size": batch_size,
        "total_conversations": len(all_convs),
        "total_batches": len(batches),
        "total_profiles": len(all_results),
        "total_recommendations": total_recs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_file = safety_dir / METADATA_FILE
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── mark done ──
    create_lock_file(safety_dir)

    return "success"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate advice-safety downstream dataset from conversation "
            "data using LLM"
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
        help=(
            "Model name for advice-safety annotation "
            "(default: gemini-2.5-flash)"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Number of conversations per LLM batch (default: 3)",
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
                    f"\n>>> Progress: {idx + 1}/{len(video_folders)} "
                    f"({pct:.1f}%) | success: {total_success}, "
                    f"skipped: {total_skipped}, "
                    f"no-conv: {total_no_conv}, "
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
    print(f"  Failed                    : {total_failed}")
    print(
        f"\nAdvice-safety outputs saved to: "
        f"dataset/<VIDEO_ID>/{CONVERSATION_SUBPATH}/{DOWNSTREAM_DIR}/"
        f"{SAFETY_SUBDIR}/<MODEL>/{SAFETY_OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    exit(main())
