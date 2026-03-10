#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference with a fine-tuned Medical NER model.

Supports multiple base models (select with --model):
  banglabert   csebuetnlp/banglabert
  mmbert       jhu-clsp/mmBERT-base

Usage:
    # Interactive mode
    python infer_ner.py --model banglabert
    python infer_ner.py --model mmbert

    # Single sentence
    python infer_ner.py --model banglabert --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"
    python infer_ner.py --model mmbert    --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"

    # Custom model directory
    python infer_ner.py --model banglabert --model-dir ./custom-path/best_model

    # JSON file in, JSON file out
    python infer_ner.py --model mmbert --json-input input.json --json-output preds.json

Requirements:
    pip install torch transformers
    pip install git+https://github.com/csebuetnlp/normalizer.git   # only for banglabert
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    pipeline,
)


SCRIPT_DIR = Path(__file__).resolve().parent

# ═══════════════════════════════════════════════════════════════════════════════
#  Model registry  (mirrors train_ner.py)
# ═══════════════════════════════════════════════════════════════════════════════

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "banglabert": {
        "normalize": "bangla",
        "default_model_dir": SCRIPT_DIR / "banglabert-output" / "best_model",
        "legacy_model_dirs": [
            # From the old banglabert-finetuning folder
            SCRIPT_DIR.parent / "banglabert-finetuning"
            / "banglabert-medical-ner-output" / "best_model",
        ],
    },
    "mmbert": {
        "normalize": "strip",
        "default_model_dir": SCRIPT_DIR / "mmbert-output" / "best_model",
        "legacy_model_dirs": [],
    },
}

# ANSI colours for pretty terminal output
COLORS = {
    "ANATOMY_BODY_PART":     "\033[36m",   # cyan
    "DISEASE_CONDITION":     "\033[35m",   # magenta
    "DRUG_MEDICATION":       "\033[32m",   # green
    "SYMPTOM_SIGN":          "\033[31m",   # red
    "TEST_INVESTIGATION":    "\033[34m",   # blue
    "TREATMENT_PROCEDURE":   "\033[33m",   # yellow
}
RESET = "\033[0m"
BOLD = "\033[1m"


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_normalize_fn(mode: str) -> Callable[[str], str]:
    """Return a text normalisation function based on *mode*."""
    if mode == "bangla":
        try:
            from normalizer import normalize as _bn
        except ImportError:
            print(
                "[ERROR] 'normalizer' package not found.  Install with:\n"
                "  pip install git+https://github.com/csebuetnlp/normalizer.git"
            )
            sys.exit(1)
        return _bn
    elif mode == "strip":
        return lambda t: t.strip()
    return lambda t: t


def find_model_dir(model_name: str, explicit_dir: str | None) -> Path:
    """Resolve the best_model directory, checking known paths."""
    if explicit_dir:
        p = Path(explicit_dir)
        if not p.exists():
            print(f"[ERROR] Explicit model dir not found: {p}")
            sys.exit(1)
        return p

    profile = MODEL_REGISTRY[model_name]

    # Check primary location
    primary = profile["default_model_dir"]
    if primary.exists():
        return primary

    # Check legacy locations
    for legacy in profile.get("legacy_model_dirs", []):
        if legacy.exists():
            print(f"  [INFO] Using legacy model dir: {legacy}")
            return legacy

    print(f"[ERROR] No trained model found for '{model_name}'.")
    print(f"  Expected at: {primary}")
    for lp in profile.get("legacy_model_dirs", []):
        print(f"  Also checked: {lp}")
    print(f"\n  Train first with: python train_ner.py --model {model_name}")
    sys.exit(1)


def colorize(text: str, label: str) -> str:
    c = COLORS.get(label, "")
    return f"{BOLD}{c}[{text} | {label}]{RESET}"


def merge_subword_entities(
    raw_entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge adjacent subword entity predictions with the same label.
    (HF pipeline with aggregation_strategy="simple" usually handles this,
     but we do a safety pass to merge any leftovers.)
    """
    if not raw_entities:
        return []

    merged: List[Dict[str, Any]] = []
    current = dict(raw_entities[0])

    for ent in raw_entities[1:]:
        if (
            ent["entity_group"] == current["entity_group"]
            and ent["start"] <= current["end"] + 1
        ):
            current["end"] = max(current["end"], ent["end"])
            current["word"] = current["word"] + " " + ent["word"]
            current["score"] = (current["score"] + ent["score"]) / 2
        else:
            merged.append(current)
            current = dict(ent)

    merged.append(current)
    return merged


def run_ner(
    text: str,
    ner_pipeline,
    normalize_fn: Callable[[str], str],
    merge: bool = True,
) -> List[Dict[str, Any]]:
    """Run NER on a single text and return entities."""
    norm_text = normalize_fn(text)
    raw = ner_pipeline(norm_text)

    if merge:
        raw = merge_subword_entities(raw)

    entities: List[Dict[str, Any]] = []
    for ent in raw:
        entities.append({
            "text": norm_text[ent["start"]:ent["end"]],
            "label": ent["entity_group"],
            "start": ent["start"],
            "end": ent["end"],
            "score": round(float(ent["score"]), 4),
        })

    return entities


def highlight_entities_in_text(
    text: str,
    entities: List[Dict[str, Any]],
    normalize_fn: Callable[[str], str],
) -> str:
    """Return text with entities highlighted (ANSI colours)."""
    norm_text = normalize_fn(text)
    sorted_ents = sorted(entities, key=lambda e: e["start"])

    parts: List[str] = []
    cursor = 0
    for ent in sorted_ents:
        s, e = ent["start"], ent["end"]
        if cursor < s:
            parts.append(norm_text[cursor:s])
        parts.append(colorize(norm_text[s:e], ent["label"]))
        cursor = e
    if cursor < len(norm_text):
        parts.append(norm_text[cursor:])

    return "".join(parts)


def print_results(
    text: str,
    entities: List[Dict[str, Any]],
    normalize_fn: Callable[[str], str],
) -> None:
    print("\n" + "─" * 70)
    print("Input text:")
    print(f"  {normalize_fn(text)}")
    print("─" * 70)

    if not entities:
        print("  (no entities found)")
    else:
        print(f"Found {len(entities)} entities:\n")
        for i, ent in enumerate(entities, 1):
            label_col = COLORS.get(ent["label"], "") + BOLD
            print(
                f"  {i:>2}. {label_col}{ent['label']:<25s}{RESET}  "
                f"\"{ent['text']}\"  (score: {ent['score']:.4f})"
            )

        print("\nHighlighted:")
        print(f"  {highlight_entities_in_text(text, entities, normalize_fn)}")

    print("─" * 70)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Medical NER Inference (BanglaBERT / mmBERT / ...)",
    )
    parser.add_argument(
        "--model", required=True,
        choices=list(MODEL_REGISTRY.keys()),
        help="Which fine-tuned model to use for inference",
    )
    parser.add_argument(
        "--model-dir", type=str, default=None,
        help="Explicit path to the saved best_model directory",
    )
    parser.add_argument(
        "--text", type=str, default=None,
        help="Single Bengali text to run NER on  (otherwise: interactive mode)",
    )
    parser.add_argument(
        "--json-input", type=str, default=None,
        help='Path to a JSON file (list of {"text": ...}) for batch inference',
    )
    parser.add_argument(
        "--json-output", type=str, default=None,
        help="Save results to this JSON file  (used with --json-input)",
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Device  (e.g. 'cpu', 'cuda', 'cuda:0').  Auto-detected if omitted",
    )
    args = parser.parse_args()

    # ── Resolve model config ──────────────────────────────────────────────
    profile = MODEL_REGISTRY[args.model]
    normalize_fn = get_normalize_fn(profile["normalize"])
    model_dir = find_model_dir(args.model, args.model_dir)

    print(f"Model      : {args.model}")
    print(f"Model dir  : {model_dir}")
    print(f"Normalize  : {profile['normalize']}")

    # ── Load model ────────────────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForTokenClassification.from_pretrained(str(model_dir))

    label_info_path = model_dir / "label_info.json"
    if label_info_path.exists():
        with open(label_info_path, "r", encoding="utf-8") as f:
            label_info = json.load(f)
        print(f"Labels     : {label_info.get('entity_labels', [])}")

    device = args.device
    if device is None:
        device = 0 if torch.cuda.is_available() else -1
    else:
        device = int(device) if device.isdigit() else device

    ner = pipeline(
        "token-classification",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",
        device=device,
    )
    print("Model loaded!\n")

    # ── Mode: single text ─────────────────────────────────────────────────
    if args.text:
        entities = run_ner(args.text, ner, normalize_fn)
        print_results(args.text, entities, normalize_fn)
        return

    # ── Mode: JSON file ───────────────────────────────────────────────────
    if args.json_input:
        with open(args.json_input, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        all_results = []
        for item in data:
            text = item.get("text", "")
            entities = run_ner(text, ner, normalize_fn)
            all_results.append({
                "text": normalize_fn(text),
                "predicted_entities": entities,
            })
            print_results(text, entities, normalize_fn)

        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to: {args.json_output}")
        return

    # ── Mode: interactive ─────────────────────────────────────────────────
    print("=" * 70)
    print(f" Interactive Medical NER  ({args.model})")
    print(" Type Bengali medical text and press Enter.")
    print(" Type 'quit' or Ctrl+C to exit.")
    print("=" * 70)

    while True:
        try:
            text = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not text or text.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        entities = run_ner(text, ner, normalize_fn)
        print_results(text, entities, normalize_fn)


if __name__ == "__main__":
    main()

