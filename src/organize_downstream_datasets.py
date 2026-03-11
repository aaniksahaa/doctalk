#!/usr/bin/env python3
"""
Organize downstream datasets into a structured, exportable format.

Collects downstream inference outputs (medical-ner, advice-safety, advice-generation, triage)
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
    advice-generation/
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

  advice-generation:
    input.json:        {"patient_profile": "..."}
    ground_truth.json: {"patient_profile": "...", "recommendations": [{"content": "...", "label": "..."}]}
    NOTE: Built from the same advice-safety source data. Input contains only
    patient_profile (no recommendations). Ground truth retains full
    recommendations with labels for evaluation.

Usage:
  python organize_downstream_datasets.py
  python organize_downstream_datasets.py --train-pct 70 --val-pct 15
  python organize_downstream_datasets.py --model gemini-2.5-flash --seed 42
  python organize_downstream_datasets.py --tasks "medical-ner;triage"
  python organize_downstream_datasets.py --tasks advice-generation
  python organize_downstream_datasets.py --force-rewrite
"""

import argparse
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


from constants import C


# ── Constants ────────────────────────────────────────────────────────────────

CONVERSATION_SUBPATH = "transcribed/yt-auto/parsed/gemini-3-flash-preview"
DOWNSTREAM_DIR = "downstream"
DOWNSTREAM_DATASETS_DIR = "downstream-datasets"

VALID_TASKS = ["medical-ner", "advice-safety", "advice-generation", "triage"]
ALL_TASKS_STR = ";".join(VALID_TASKS)


def parse_tasks(tasks_str: str) -> List[str]:
    """Parse semicolon-separated task string and validate each task."""
    tasks = [t.strip() for t in tasks_str.split(";") if t.strip()]
    for t in tasks:
        if t not in VALID_TASKS:
            print(
                f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} unknown task '{t}'. "
                f"Valid tasks: {', '.join(VALID_TASKS)}{C.RESET}"
            )
            sys.exit(1)
    return tasks


TASK_CONFIG = {
    "medical-ner": {
        "subdir": "medical-ner",
        "output_file": "ner_output.json",
    },
    "advice-safety": {
        "subdir": "advice-safety",
        "output_file": "advice_safety_output.json",
    },
    "advice-generation": {
        # Reuses the same source data as advice-safety.
        # Only the input/ground_truth processing differs.
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
) -> Tuple[Dict[str, Any], Dict[str, Any]] | None:
    """
    Process a single advice-safety element into (input, ground_truth).

    input.json:        patient_profile + recommendations without labels
    ground_truth.json: patient_profile + full recommendations with labels

    The conversation field is excluded from both.
    Returns None if the recommendations array is empty (element is skipped).
    """
    recs = element.get("recommendations", [])
    if not recs:
        return None
    input_recs = [
        {"content": r["content"]}
        for r in recs
    ]
    input_data = {
        "patient_profile": element["patient_profile"],
        "recommendations": input_recs,
    }
    ground_truth = {
        "patient_profile": element["patient_profile"],
        "recommendations": recs,
    }
    return input_data, ground_truth


def process_advice_generation_element(
    element: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]] | None:
    """
    Process a single advice-generation element into (input, ground_truth).

    Built from the same advice-safety source data, but the input contains
    only patient_profile (no recommendations). The LLM is expected to
    generate recommendations from scratch.

    input.json:        {"patient_profile": "..."}
    ground_truth.json: {"patient_profile": "...", "recommendations": [{"content": "...", "label": "..."}]}

    Returns None if the recommendations array is empty (element is skipped).
    """
    recs = element.get("recommendations", [])
    if not recs:
        return None
    input_data = {
        "patient_profile": element["patient_profile"],
    }
    ground_truth = {
        "patient_profile": element["patient_profile"],
        "recommendations": recs,
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
    "advice-generation": process_advice_generation_element,
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
                result = processor(item)
                if result is None:
                    # Processor decided to skip this element
                    # (e.g. empty recommendations)
                    continue
                input_data, ground_truth = result
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
    force_rewrite: bool = False,
) -> None:
    """Write a single element to a numbered directory.

    If the element directory already exists and force_rewrite is False,
    the write is skipped to preserve existing data (e.g. inference results).
    """
    elem_dir = target_dir / str(idx)
    if elem_dir.exists() and not force_rewrite:
        return
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
    force_rewrite: bool = False,
) -> None:
    """Write all elements to the all/ directory with sequential numbering.

    If force_rewrite is True, removes the existing all/ directory first.
    Otherwise, only writes elements whose directories don't yet exist.
    """
    all_dir = output_base / task_name / "all"
    if all_dir.exists() and force_rewrite:
        shutil.rmtree(all_dir)
    all_dir.mkdir(parents=True, exist_ok=True)

    for idx, element in enumerate(elements, start=1):
        write_element(all_dir, idx, element, force_rewrite=force_rewrite)


def write_splits(
    output_base: Path,
    task_name: str,
    elements: List[Dict[str, Any]],
    train_pct: float,
    val_pct: float,
    seed: int,
    force_rewrite: bool = False,
) -> Dict[str, int]:
    """
    Randomly shuffle elements and write train/val/test splits.

    Each split directory contains copies of the numbered element folders
    from all/, preserving the original numbering for traceability.

    If force_rewrite is True, removes the existing split/ directory first.
    Otherwise, only copies elements whose split directories don't yet exist.
    """
    split_dir = output_base / task_name / "split"
    if split_dir.exists() and force_rewrite:
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
            if dst.exists() and not force_rewrite:
                continue
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
        default=80,
        help="Train split percentage (default: 80)",
    )
    parser.add_argument(
        "--val-pct",
        type=float,
        default=10,
        help="Validation split percentage (default: 10)",
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
        default=ALL_TASKS_STR,
        help=(
            "Semicolon-separated list of downstream tasks to organize. "
            f"Valid tasks: {', '.join(VALID_TASKS)}. "
            f"(default: all — {ALL_TASKS_STR})"
        ),
    )
    parser.add_argument(
        "--force-rewrite",
        action="store_true",
        help=(
            "Overwrite existing element directories. Without this flag, "
            "existing directories are preserved to avoid clobbering "
            "inference results."
        ),
    )

    args = parser.parse_args()

    # ── validate percentages ──
    test_pct = 100 - args.train_pct - args.val_pct
    if test_pct < 0:
        print(
            f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} train-pct ({args.train_pct}) + "
            f"val-pct ({args.val_pct}) exceeds 100{C.RESET}"
        )
        return

    # ── resolve paths ──
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path(__file__).parent / folder_path

    dataset_path = folder_path / "dataset"
    output_base = folder_path / DOWNSTREAM_DATASETS_DIR

    if not dataset_path.exists():
        print(f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} dataset path not found: {dataset_path}{C.RESET}")
        return

    # ── parse tasks ──
    tasks = parse_tasks(args.tasks)

    print(f"{C.BOLD}{C.CYAN}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Downstream Dataset Organizer{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 60}{C.RESET}")
    print(f"  {C.BOLD}Dataset path{C.RESET}  : {C.DIM}{dataset_path}{C.RESET}")
    print(f"  {C.BOLD}Output path{C.RESET}   : {C.DIM}{output_base}{C.RESET}")
    print(f"  {C.BOLD}Model{C.RESET}         : {C.CYAN}{args.model}{C.RESET}")
    print(f"  {C.BOLD}Train/Val/Test{C.RESET}: {C.YELLOW}{args.train_pct}%{C.RESET} / {C.YELLOW}{args.val_pct}%{C.RESET} / {C.YELLOW}{test_pct}%{C.RESET}")
    print(f"  {C.BOLD}Seed{C.RESET}          : {args.seed}")
    print(f"  {C.BOLD}Tasks{C.RESET}         : {C.MAGENTA}{', '.join(tasks)}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 60}{C.RESET}")
    print()

    for task_name in tasks:
        print(f"{C.BOLD}{C.BLUE}{'─' * 60}{C.RESET}")
        print(f"  {C.BOLD}Task:{C.RESET} {C.MAGENTA}{task_name}{C.RESET}")
        print(f"{C.BOLD}{C.BLUE}{'─' * 60}{C.RESET}")

        # ── collect elements ──
        elements = collect_task_elements(dataset_path, task_name, args.model)
        print(f"  {C.BOLD}Collected{C.RESET}      : {C.CYAN}{len(elements)}{C.RESET} elements")

        if not elements:
            print(f"  {C.YELLOW}{C.BOLD}⚠ No elements found, skipping{C.RESET}")
            print()
            continue

        # ── count source videos ──
        source_videos = len(set(e["origin_video_id"] for e in elements))
        print(f"  {C.BOLD}Source videos{C.RESET}  : {C.CYAN}{source_videos}{C.RESET}")

        # ── write all/ ──
        write_all(output_base, task_name, elements, force_rewrite=args.force_rewrite)
        all_dir = output_base / task_name / "all"
        print(f"  {C.GREEN}✓{C.RESET} {C.BOLD}Written all/{C.RESET} → {C.DIM}{all_dir.relative_to(folder_path)}{C.RESET}")

        # ── write splits ──
        split_counts = write_splits(
            output_base, task_name, elements,
            args.train_pct, args.val_pct, args.seed,
            force_rewrite=args.force_rewrite,
        )
        print(
            f"  {C.GREEN}✓{C.RESET} {C.BOLD}Split{C.RESET}        : "
            f"train={C.GREEN}{split_counts['train']}{C.RESET}, "
            f"val={C.YELLOW}{split_counts['val']}{C.RESET}, "
            f"test={C.BLUE}{split_counts['test']}{C.RESET}"
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
            f"  {C.GREEN}✓{C.RESET} {C.BOLD}Summary{C.RESET}      → "
            f"{C.DIM}{summary_path.relative_to(folder_path)}{C.RESET}"
        )
        print()

    print(f"{C.GREEN}{C.BOLD}✓ Organization complete!{C.RESET}")


if __name__ == "__main__":
    main()
