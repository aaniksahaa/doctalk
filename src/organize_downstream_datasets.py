#!/usr/bin/env python3
"""
Organize downstream datasets into a structured, exportable format.

Collects downstream inference outputs (medical-ner, advice-safety, triage)
from per-video dataset folders and reorganizes them into a clean numbered
structure suitable for downstream model evaluation.

Output structure:
  downstream-datasets/
    medical-ner/
      all/
        1/  metadata.json, input.json, ground_truth.json
        2/  ...
      split/
        train/  1/ 5/ 12/ ...  (preserves original numbering from all/)
        val/    3/ 7/ ...
        test/   2/ 9/ ...
      summary.json
    advice-safety/
      all/ ...
      split/ ...
      summary.json
    triage/
      all/ ...
      split/ ...
      summary.json

Per-element files:
  metadata.json    – origin_video_id, generator_model
  input.json       – the input for downstream evaluation
  ground_truth.json – the expected output (ground truth)

Task-specific input/ground_truth schemas:

  medical-ner:
    input.json:        {"text": "..."}
    ground_truth.json: {"text": "...", "entities": [...]}

  advice-safety:
    input.json:        {"patient_profile": "...", "recommendations": [{"content": "..."}]}
    ground_truth.json: {"patient_profile": "...", "recommendations": [{"content": "...", "label": "..."}]}

  triage:
    input.json:        {"patient_profile": "..."}
    ground_truth.json: {"patient_profile": "...", "type": "..."}

Usage:
  python organize_downstream_datasets.py
  python organize_downstream_datasets.py --train-pct 70 --val-pct 15
  python organize_downstream_datasets.py --model gemini-2.5-flash --seed 42
  python organize_downstream_datasets.py --tasks medical-ner triage
"""

import argparse
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ── Constants ────────────────────────────────────────────────────────────────

CONVERSATION_SUBPATH = "transcribed/yt-auto/parsed/gemini-3-flash-preview"
DOWNSTREAM_DIR = "downstream"
DOWNSTREAM_DATASETS_DIR = "downstream-datasets"

TASK_CONFIG = {
    "medical-ner": {
        "subdir": "medical-ner",
        "output_file": "ner_output.json",
    },
    "advice-safety": {
        "subdir": "advice-safety",
        "output_file": "advice_safety_output.json",
    },
    "triage": {
        "subdir": "triage",
        "output_file": "triage_output.json",
    },
}


# ── Element processors ───────────────────────────────────────────────────────

def process_ner_element(
    element: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a single NER element into (input, ground_truth).

    input.json:        {"text": "..."}
    ground_truth.json: {"text": "...", "entities": [...]}
    """
    input_data = {
        "text": element["text"],
    }
    ground_truth = {
        "text": element["text"],
        "entities": element["entities"],
    }
    return input_data, ground_truth


def process_advice_safety_element(
    element: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a single advice-safety element into (input, ground_truth).

    input.json:        patient_profile + recommendations without labels
    ground_truth.json: patient_profile + full recommendations with labels

    The conversation field is excluded from both.
    """
    input_recs = [
        {"content": r["content"]}
        for r in element.get("recommendations", [])
    ]
    input_data = {
        "patient_profile": element["patient_profile"],
        "recommendations": input_recs,
    }
    ground_truth = {
        "patient_profile": element["patient_profile"],
        "recommendations": element.get("recommendations", []),
    }
    return input_data, ground_truth


def build_triage_patient_profile(conversation: Dict[str, Any]) -> str:
    """
    Build patient profile from conversation turns for triage evaluation.

    Includes all turns up to and including the last non-doctor turn.
    Trailing doctor turns are removed because leaking the doctor's final
    guidance would make the triage classification trivially easy.

    Example:
      turns = [patient, doctor, patient, doctor, doctor]
      → keep [patient, doctor, patient]
      → concatenate their text
    """
    turns = conversation.get("turns", [])
    if not turns:
        return ""

    # Find the last non-doctor turn
    last_non_doctor = -1
    for i in range(len(turns) - 1, -1, -1):
        if turns[i].get("speaker", "").lower() != "doctor":
            last_non_doctor = i
            break

    if last_non_doctor < 0:
        # All turns are doctor turns; use all as fallback
        relevant_turns = turns
    else:
        relevant_turns = turns[: last_non_doctor + 1]

    texts = [t["text"] for t in relevant_turns if t.get("text")]
    return " ".join(texts)


def process_triage_element(
    element: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a single triage element into (input, ground_truth).

    input.json:        {"patient_profile": "..."}
    ground_truth.json: {"patient_profile": "...", "type": "..."}

    The full conversation is replaced by a patient_profile that includes
    all turns up to (and including) the last non-doctor turn.
    """
    conversation = element.get("conversation", {})
    patient_profile = build_triage_patient_profile(conversation)

    input_data = {
        "patient_profile": patient_profile,
    }
    ground_truth = {
        "patient_profile": patient_profile,
        "type": element["type"],
    }
    return input_data, ground_truth


PROCESSORS = {
    "medical-ner": process_ner_element,
    "advice-safety": process_advice_safety_element,
    "triage": process_triage_element,
}


# ── Collection ───────────────────────────────────────────────────────────────

def collect_task_elements(
    dataset_path: Path,
    task_name: str,
    model: str,
) -> List[Dict[str, Any]]:
    """
    Collect all elements for a downstream task across all video folders.

    Iterates over every video directory, reads the task output JSON, and
    runs the task-specific processor on each element.

    Returns list of dicts:
      {origin_video_id, generator_model, input, ground_truth}
    """
    config = TASK_CONFIG[task_name]
    processor = PROCESSORS[task_name]
    elements: List[Dict[str, Any]] = []

    video_folders = sorted(
        d for d in dataset_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    for video_folder in video_folders:
        video_id = video_folder.name
        output_path = (
            video_folder
            / CONVERSATION_SUBPATH
            / DOWNSTREAM_DIR
            / config["subdir"]
            / model
            / config["output_file"]
        )

        if not output_path.exists():
            continue

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            try:
                input_data, ground_truth = processor(item)
                elements.append({
                    "origin_video_id": video_id,
                    "generator_model": model,
                    "input": input_data,
                    "ground_truth": ground_truth,
                })
            except Exception:
                continue

    return elements


# ── Writing helpers ──────────────────────────────────────────────────────────

def write_element(
    target_dir: Path,
    idx: int,
    element: Dict[str, Any],
) -> None:
    """Write a single element to a numbered directory."""
    elem_dir = target_dir / str(idx)
    elem_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "origin_video_id": element["origin_video_id"],
        "generator_model": element["generator_model"],
    }

    with open(elem_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    with open(elem_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(element["input"], f, ensure_ascii=False, indent=2)

    with open(elem_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(element["ground_truth"], f, ensure_ascii=False, indent=2)


def write_all(
    output_base: Path,
    task_name: str,
    elements: List[Dict[str, Any]],
) -> None:
    """Write all elements to the all/ directory with sequential numbering."""
    all_dir = output_base / task_name / "all"
    if all_dir.exists():
        shutil.rmtree(all_dir)
    all_dir.mkdir(parents=True, exist_ok=True)

    for idx, element in enumerate(elements, start=1):
        write_element(all_dir, idx, element)


def write_splits(
    output_base: Path,
    task_name: str,
    elements: List[Dict[str, Any]],
    train_pct: float,
    val_pct: float,
    seed: int,
) -> Dict[str, int]:
    """
    Randomly shuffle elements and write train/val/test splits.

    Each split directory contains copies of the numbered element folders
    from all/, preserving the original numbering for traceability.
    """
    split_dir = output_base / task_name / "split"
    if split_dir.exists():
        shutil.rmtree(split_dir)

    n = len(elements)
    # 1-based indices matching the all/ directory numbering
    indices = list(range(1, n + 1))
    rng = random.Random(seed)
    rng.shuffle(indices)

    n_train = int(n * train_pct / 100)
    n_val = int(n * val_pct / 100)
    # remainder goes to test
    train_indices = sorted(indices[:n_train])
    val_indices = sorted(indices[n_train : n_train + n_val])
    test_indices = sorted(indices[n_train + n_val :])

    all_dir = output_base / task_name / "all"

    splits = {
        "train": train_indices,
        "val": val_indices,
        "test": test_indices,
    }

    for split_name, split_indices in splits.items():
        split_subdir = split_dir / split_name
        split_subdir.mkdir(parents=True, exist_ok=True)
        for idx in split_indices:
            src = all_dir / str(idx)
            dst = split_subdir / str(idx)
            shutil.copytree(src, dst)

    return {k: len(v) for k, v in splits.items()}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Organize downstream datasets into a structured, exportable "
            "format for downstream model evaluation"
        ),
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
            "Model name whose downstream outputs to collect "
            "(default: gemini-2.5-flash)"
        ),
    )
    parser.add_argument(
        "--train-pct",
        type=float,
        default=70,
        help="Train split percentage (default: 70)",
    )
    parser.add_argument(
        "--val-pct",
        type=float,
        default=15,
        help="Validation split percentage (default: 15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for shuffling (default: 42)",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        nargs="+",
        default=["medical-ner", "advice-safety", "triage"],
        choices=["medical-ner", "advice-safety", "triage"],
        help=(
            "Downstream tasks to organize "
            "(default: all three)"
        ),
    )

    args = parser.parse_args()

    # ── validate percentages ──
    test_pct = 100 - args.train_pct - args.val_pct
    if test_pct < 0:
        print(
            f"Error: train-pct ({args.train_pct}) + "
            f"val-pct ({args.val_pct}) exceeds 100"
        )
        return

    # ── resolve paths ──
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path(__file__).parent / folder_path

    dataset_path = folder_path / "dataset"
    output_base = folder_path / DOWNSTREAM_DATASETS_DIR

    if not dataset_path.exists():
        print(f"Error: dataset path not found: {dataset_path}")
        return

    print(f"Dataset path  : {dataset_path}")
    print(f"Output path   : {output_base}")
    print(f"Model         : {args.model}")
    print(f"Train/Val/Test: {args.train_pct}% / {args.val_pct}% / {test_pct}%")
    print(f"Seed          : {args.seed}")
    print(f"Tasks         : {', '.join(args.tasks)}")
    print()

    for task_name in args.tasks:
        print(f"{'─' * 60}")
        print(f"  Task: {task_name}")
        print(f"{'─' * 60}")

        # ── collect elements ──
        elements = collect_task_elements(dataset_path, task_name, args.model)
        print(f"  Collected {len(elements)} elements")

        if not elements:
            print(f"  ⚠ No elements found, skipping")
            print()
            continue

        # ── count source videos ──
        source_videos = len(set(e["origin_video_id"] for e in elements))
        print(f"  Source videos: {source_videos}")

        # ── write all/ ──
        write_all(output_base, task_name, elements)
        all_dir = output_base / task_name / "all"
        print(f"  Written all/ → {all_dir.relative_to(folder_path)}")

        # ── write splits ──
        split_counts = write_splits(
            output_base, task_name, elements,
            args.train_pct, args.val_pct, args.seed,
        )
        print(
            f"  Split: train={split_counts['train']}, "
            f"val={split_counts['val']}, "
            f"test={split_counts['test']}"
        )

        # ── write task-level summary ──
        summary = {
            "task": task_name,
            "generator_model": args.model,
            "total_elements": len(elements),
            "source_videos": source_videos,
            "train_count": split_counts["train"],
            "val_count": split_counts["val"],
            "test_count": split_counts["test"],
            "train_pct": args.train_pct,
            "val_pct": args.val_pct,
            "test_pct": test_pct,
            "seed": args.seed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        summary_path = output_base / task_name / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(
            f"  Summary → "
            f"{summary_path.relative_to(folder_path)}"
        )
        print()

    print("✓ Organization complete!")


if __name__ == "__main__":
    main()
