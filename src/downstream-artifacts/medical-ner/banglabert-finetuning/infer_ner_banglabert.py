#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference with a fine-tuned BanglaBERT Medical NER model.

Loads the best_model saved by train_ner_banglabert.py and runs NER
on user-provided Bengali medical text.

Usage:
    # Interactive (reads from stdin)
    python infer_ner_banglabert.py

    # Single sentence
    python infer_ner_banglabert.py --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"

    # Custom model directory
    python infer_ner_banglabert.py --model_dir ./banglabert-medical-ner-output/best_model

Requirements:
    pip install torch transformers
    pip install git+https://github.com/csebuetnlp/normalizer.git
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    pipeline,
)
from normalizer import normalize as bangla_normalize


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = str(SCRIPT_DIR / "banglabert-medical-ner-output" / "best_model")

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


def colorize(text: str, label: str) -> str:
    c = COLORS.get(label, "")
    return f"{BOLD}{c}[{text} | {label}]{RESET}"


def merge_subword_entities(raw_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge adjacent subword entity predictions with the same label
    (HF pipeline with aggregation_strategy="simple" usually handles this,
     but we do a safety pass to merge any leftovers).
    """
    if not raw_entities:
        return []

    merged: List[Dict[str, Any]] = []
    current = dict(raw_entities[0])

    for ent in raw_entities[1:]:
        # Same entity group or adjacent with same label → merge
        if ent["entity_group"] == current["entity_group"] and ent["start"] <= current["end"] + 1:
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
    merge: bool = True,
) -> List[Dict[str, Any]]:
    """Run NER on a single text and return entities."""
    norm_text = bangla_normalize(text)
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


def highlight_entities_in_text(text: str, entities: List[Dict[str, Any]]) -> str:
    """Return text with entities highlighted (ANSI colours)."""
    norm_text = bangla_normalize(text)
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


def print_results(text: str, entities: List[Dict[str, Any]]) -> None:
    print("\n" + "─" * 70)
    print("Input text:")
    print(f"  {bangla_normalize(text)}")
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
        print(f"  {highlight_entities_in_text(text, entities)}")

    print("─" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="BanglaBERT Medical NER Inference")
    parser.add_argument(
        "--model_dir",
        type=str,
        default=DEFAULT_MODEL_DIR,
        help="Path to the saved best_model directory.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single Bengali text to run NER on. If not given, enters interactive mode.",
    )
    parser.add_argument(
        "--json_input",
        type=str,
        default=None,
        help="Path to a JSON file (list of {\"text\": ...}) to run NER on.",
    )
    parser.add_argument(
        "--json_output",
        type=str,
        default=None,
        help="If given with --json_input, save results to this JSON file.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to use (e.g. 'cpu', 'cuda', 'cuda:0'). Auto-detected if not given.",
    )
    args = parser.parse_args()

    # ── Load model ─────────────────────────────────────────────────────────
    model_dir = args.model_dir
    print(f"Loading model from: {model_dir}")

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)

    # Load label info
    label_info_path = Path(model_dir) / "label_info.json"
    if label_info_path.exists():
        with open(label_info_path, "r", encoding="utf-8") as f:
            label_info = json.load(f)
        print(f"Entity labels: {label_info.get('entity_labels', [])}")

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
    print("Model loaded successfully!\n")

    # ── Mode: single text ─────────────────────────────────────────────────
    if args.text:
        entities = run_ner(args.text, ner)
        print_results(args.text, entities)
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
            entities = run_ner(text, ner)
            all_results.append({
                "text": bangla_normalize(text),
                "predicted_entities": entities,
            })
            print_results(text, entities)

        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to: {args.json_output}")
        return

    # ── Mode: interactive ─────────────────────────────────────────────────
    print("=" * 70)
    print(" Interactive Bengali Medical NER")
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

        entities = run_ner(text, ner)
        print_results(text, entities)


if __name__ == "__main__":
    main()

