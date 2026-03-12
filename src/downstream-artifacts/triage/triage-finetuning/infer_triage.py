#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference with a fine-tuned Triage Classification model.

Supports both BERT-based and embedding-based models:
  BERT:      banglabert, mmbert   (AutoModelForSequenceClassification)
  Embedding: multilingual-minilm, multilingual-e5-small  (sentence-transformer + MLP)

Usage:
    # Interactive mode
    python infer_triage.py --model banglabert
    python infer_triage.py --model multilingual-minilm

    # Single text
    python infer_triage.py --model banglabert --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"

    # Custom model directory
    python infer_triage.py --model banglabert --model-dir ./custom-path/best_model

    # JSON file in, JSON file out
    python infer_triage.py --model mmbert --json-input input.json --json-output preds.json

Requirements:
    pip install torch transformers
    pip install sentence-transformers   # for embedding models
    pip install git+https://github.com/csebuetnlp/normalizer.git   # only for banglabert
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch
import torch.nn as nn


SCRIPT_DIR = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════════
#  Model registries (mirror train_triage.py / train_triage_embed.py)
# ═══════════════════════════════════════════════════════════════════════════════

BERT_MODELS: Dict[str, Dict[str, Any]] = {
    "banglabert": {
        "normalize": "bangla",
        "default_model_dir": SCRIPT_DIR / "banglabert-output" / "best_model",
    },
    "mmbert": {
        "normalize": "strip",
        "default_model_dir": SCRIPT_DIR / "mmbert-output" / "best_model",
    },
}

EMBEDDING_MODELS: Dict[str, Dict[str, Any]] = {
    "multilingual-minilm": {
        "default_model_dir": SCRIPT_DIR / "multilingual-minilm-output" / "best_model",
    },
    "multilingual-e5-small": {
        "default_model_dir": SCRIPT_DIR / "multilingual-e5-small-output" / "best_model",
    },
}

ALL_MODELS = {**BERT_MODELS, **EMBEDDING_MODELS}

# Triage labels
TRIAGE_LABELS = sorted([
    "REASSURANCE_SELF_CARE",
    "ROUTINE_OUTPATIENT_VISIT",
    "INVESTIGATION_OR_SPECIALIST_REFERRAL",
    "URGENT_EMERGENCY_CARE",
])

# ANSI colours
COLORS = {
    "REASSURANCE_SELF_CARE":                   "\033[32m",  # green
    "ROUTINE_OUTPATIENT_VISIT":                "\033[36m",  # cyan
    "INVESTIGATION_OR_SPECIALIST_REFERRAL":     "\033[33m",  # yellow
    "URGENT_EMERGENCY_CARE":                   "\033[31m",  # red
}
RESET = "\033[0m"
BOLD = "\033[1m"


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_normalize_fn(mode: str) -> Callable[[str], str]:
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
    if explicit_dir:
        p = Path(explicit_dir)
        if not p.exists():
            print(f"[ERROR] Explicit model dir not found: {p}")
            sys.exit(1)
        return p

    profile = ALL_MODELS[model_name]
    primary = profile["default_model_dir"]
    if primary.exists():
        return primary

    print(f"[ERROR] No trained model found for '{model_name}'.")
    print(f"  Expected at: {primary}")
    print(f"\n  Train first with the appropriate train_triage*.py script.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Classifier head (must match training architecture)
# ═══════════════════════════════════════════════════════════════════════════════

class ClassifierHead(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_classes, dropout=0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_classes),
        )

    def forward(self, x):
        return self.net(x)


# ═══════════════════════════════════════════════════════════════════════════════
#  Predictor classes
# ═══════════════════════════════════════════════════════════════════════════════

class BERTTriagePredictor:
    """BERT-based sequence classification predictor."""

    def __init__(self, model_dir: Path, normalize_mode: str):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.normalize_fn = get_normalize_fn(normalize_mode)
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        self.model.eval()

        label_info_path = model_dir / "label_info.json"
        if label_info_path.exists():
            with open(label_info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            self.id2label = {int(k): v for k, v in info["id2label"].items()}
        else:
            self.id2label = dict(self.model.config.id2label)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def predict(self, text: str) -> str:
        norm_text = self.normalize_fn(text)
        enc = self.tokenizer(
            norm_text, return_tensors="pt", truncation=True, max_length=512,
        ).to(self.device)
        with torch.no_grad():
            logits = self.model(**enc).logits
        return self.id2label[logits.argmax(dim=-1).item()]


class EmbeddingTriagePredictor:
    """Embedding + MLP classifier predictor."""

    def __init__(self, model_dir: Path):
        from sentence_transformers import SentenceTransformer

        config_path = model_dir / "model_config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            mcfg = json.load(f)

        self.id2label = {int(k): v for k, v in mcfg["id2label"].items()}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.embedder = SentenceTransformer(
            mcfg["embedding_model"], device=str(self.device),
        )
        self.classifier = ClassifierHead(
            input_dim=mcfg["embedding_dim"],
            hidden_dim=mcfg["hidden_dim"],
            num_classes=mcfg["num_labels"],
            dropout=mcfg.get("dropout", 0.3),
        )
        state = torch.load(
            model_dir / "classifier.pt", map_location=self.device, weights_only=True,
        )
        self.classifier.load_state_dict(state)
        self.classifier.to(self.device)
        self.classifier.eval()

    def predict(self, text: str) -> str:
        emb = self.embedder.encode(
            [text], convert_to_numpy=True, show_progress_bar=False,
        )
        x = torch.tensor(emb, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            logits = self.classifier(x)
        return self.id2label[logits.argmax(dim=-1).item()]


# ═══════════════════════════════════════════════════════════════════════════════
#  Output formatting
# ═══════════════════════════════════════════════════════════════════════════════

def colorize_label(label: str) -> str:
    c = COLORS.get(label, "")
    return f"{BOLD}{c}{label}{RESET}"


def print_result(text: str, predicted_type: str) -> None:
    print("\n" + "─" * 70)
    print("Patient profile:")
    print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")
    print("─" * 70)
    print(f"  Predicted triage: {colorize_label(predicted_type)}")
    print("─" * 70)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Triage Classification Inference",
    )
    parser.add_argument(
        "--model", required=True,
        choices=list(ALL_MODELS.keys()),
        help="Which fine-tuned model to use",
    )
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--text", type=str, default=None,
                        help="Single patient profile text to classify")
    parser.add_argument("--json-input", type=str, default=None)
    parser.add_argument("--json-output", type=str, default=None)
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args()

    model_dir = find_model_dir(args.model, args.model_dir)
    is_bert = args.model in BERT_MODELS

    print(f"Model      : {args.model}")
    print(f"Model type : {'BERT' if is_bert else 'Embedding+Classifier'}")
    print(f"Model dir  : {model_dir}")

    if is_bert:
        predictor = BERTTriagePredictor(
            model_dir, BERT_MODELS[args.model]["normalize"],
        )
    else:
        predictor = EmbeddingTriagePredictor(model_dir)

    print("Model loaded!\n")

    # ── Single text ───────────────────────────────────────────────────────
    if args.text:
        result = predictor.predict(args.text)
        print_result(args.text, result)
        return

    # ── JSON file ─────────────────────────────────────────────────────────
    if args.json_input:
        with open(args.json_input, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]

        all_results = []
        for item in data:
            text = item.get("patient_profile", item.get("text", ""))
            predicted = predictor.predict(text)
            all_results.append({
                "patient_profile": text,
                "type": predicted,
            })
            print_result(text, predicted)

        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to: {args.json_output}")
        return

    # ── Interactive ───────────────────────────────────────────────────────
    print("=" * 70)
    print(f" Interactive Triage Classification  ({args.model})")
    print(" Type a patient profile and press Enter.")
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

        result = predictor.predict(text)
        print_result(text, result)


if __name__ == "__main__":
    main()

