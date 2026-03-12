#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference with a fine-tuned Advice-Safety Classification model.

Supports embedding-based models:
  multilingual-minilm       sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  multilingual-e5-small     intfloat/multilingual-e5-small

Usage:
    # JSON file (primary mode — input has patient_profile + recommendations)
    python infer_advice_safety.py --model multilingual-minilm \\
        --json-input input.json --json-output preds.json

    # Interactive mode
    python infer_advice_safety.py --model multilingual-minilm

Requirements:
    pip install torch sentence-transformers
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
import torch.nn as nn


SCRIPT_DIR = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════════
#  Model registry
# ═══════════════════════════════════════════════════════════════════════════════

EMBEDDING_MODELS: Dict[str, Dict[str, Any]] = {
    "multilingual-minilm": {
        "default_model_dir": SCRIPT_DIR / "multilingual-minilm-output" / "best_model",
    },
    "multilingual-e5-small": {
        "default_model_dir": SCRIPT_DIR / "multilingual-e5-small-output" / "best_model",
    },
}

SAFETY_LABELS = sorted(["HARMFUL", "SAFE"])

# ANSI
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"


# ═══════════════════════════════════════════════════════════════════════════════
#  Pair classifier head (must match training architecture)
# ═══════════════════════════════════════════════════════════════════════════════

class PairClassifierHead(nn.Module):
    def __init__(self, embedding_dim, hidden_dim, num_classes, dropout=0.3):
        super().__init__()
        input_dim = embedding_dim * 2
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
#  Predictor
# ═══════════════════════════════════════════════════════════════════════════════

class AdviceSafetyPredictor:
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
        self.classifier = PairClassifierHead(
            embedding_dim=mcfg["embedding_dim"],
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

    def predict(
        self,
        patient_profile: str,
        recommendations: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Classify each recommendation as SAFE or HARMFUL."""
        if not recommendations:
            return []

        profile_emb = self.embedder.encode(
            [patient_profile], convert_to_numpy=True, show_progress_bar=False,
        )
        rec_texts = [r["content"] for r in recommendations]
        rec_embs = self.embedder.encode(
            rec_texts, convert_to_numpy=True, show_progress_bar=False,
        )

        profile_repeated = np.repeat(profile_emb, len(recommendations), axis=0)
        pair_features = np.concatenate([profile_repeated, rec_embs], axis=-1)
        x = torch.tensor(pair_features, dtype=torch.float32).to(self.device)

        with torch.no_grad():
            logits = self.classifier(x)
        pred_ids = logits.argmax(dim=-1).cpu().tolist()

        results = []
        for rec, pid in zip(recommendations, pred_ids):
            results.append({
                "content": rec["content"],
                "label": self.id2label[pid],
            })
        return results


# ═══════════════════════════════════════════════════════════════════════════════
#  Output formatting
# ═══════════════════════════════════════════════════════════════════════════════

def colorize_label(label: str) -> str:
    c = GREEN if label == "SAFE" else RED
    return f"{BOLD}{c}{label}{RESET}"


def print_result(profile: str, recs: List[Dict[str, str]]) -> None:
    print("\n" + "─" * 70)
    print("Patient profile:")
    print(f"  {profile[:200]}{'...' if len(profile) > 200 else ''}")
    print("─" * 70)
    if not recs:
        print("  (no recommendations)")
    else:
        print(f"  {len(recs)} recommendations:")
        for i, r in enumerate(recs, 1):
            print(
                f"    {i:>2}. {colorize_label(r['label']):>30s}  "
                f"\"{r['content'][:80]}{'...' if len(r['content']) > 80 else ''}\""
            )
    print("─" * 70)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def find_model_dir(model_name: str, explicit_dir: str | None) -> Path:
    if explicit_dir:
        p = Path(explicit_dir)
        if not p.exists():
            print(f"[ERROR] Explicit model dir not found: {p}")
            sys.exit(1)
        return p

    profile = EMBEDDING_MODELS[model_name]
    primary = profile["default_model_dir"]
    if primary.exists():
        return primary

    print(f"[ERROR] No trained model found for '{model_name}'.")
    print(f"  Expected at: {primary}")
    print(f"\n  Train first: python train_advice_safety_embed.py --model {model_name}")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advice-Safety Classification Inference",
    )
    parser.add_argument(
        "--model", required=True,
        choices=list(EMBEDDING_MODELS.keys()),
    )
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--json-input", type=str, default=None)
    parser.add_argument("--json-output", type=str, default=None)
    args = parser.parse_args()

    model_dir = find_model_dir(args.model, args.model_dir)
    print(f"Model     : {args.model}")
    print(f"Model dir : {model_dir}")

    predictor = AdviceSafetyPredictor(model_dir)
    print("Model loaded!\n")

    # ── JSON file ─────────────────────────────────────────────────────────
    if args.json_input:
        with open(args.json_input, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]

        all_results = []
        for item in data:
            profile = item["patient_profile"]
            recs_in = item.get("recommendations", [])
            recs_out = predictor.predict(profile, recs_in)
            result = {
                "patient_profile": profile,
                "recommendations": recs_out,
            }
            all_results.append(result)
            print_result(profile, recs_out)

        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to: {args.json_output}")
        return

    # ── Interactive ───────────────────────────────────────────────────────
    print("=" * 70)
    print(f" Interactive Advice-Safety Classification  ({args.model})")
    print(" Enter patient profile, then recommendations (one per line).")
    print(" Type 'done' after the last recommendation.")
    print(" Type 'quit' or Ctrl+C to exit.")
    print("=" * 70)

    while True:
        try:
            print("\nPatient profile:")
            profile = input("  >>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not profile or profile.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        print("Recommendations (one per line, type 'done' to finish):")
        recs = []
        while True:
            try:
                line = input("  rec> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                return
            if line.lower() in ("done", "d", ""):
                break
            recs.append({"content": line})

        if not recs:
            print("  (no recommendations entered)")
            continue

        results = predictor.predict(profile, recs)
        print_result(profile, results)


if __name__ == "__main__":
    main()

