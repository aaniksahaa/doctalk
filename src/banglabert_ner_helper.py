#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper module for fine-tuned BanglaBERT Medical NER inference.

Used by infer_downstream.py when --model banglabert is specified
for the medical-ner task.

Loads the model once, then exposes predict(text) -> dict that returns
output in the same format as LLM-based NER inference:
    {"text": "...", "entities": [{"text": "...", "label": "..."}, ...]}
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    pipeline as hf_pipeline,
)
from normalizer import normalize as bangla_normalize


# Default model path (relative to this file, i.e. src/)
_DEFAULT_MODEL_DIR = (
    Path(__file__).resolve().parent
    / "downstream-artifacts"
    / "medical-ner"
    / "banglabert-finetuning"
    / "banglabert-medical-ner-output"
    / "best_model"
)


def _merge_subword_entities(raw_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge adjacent subword predictions with the same label."""
    if not raw_entities:
        return []

    merged: List[Dict[str, Any]] = []
    cur = dict(raw_entities[0])

    for ent in raw_entities[1:]:
        if (
            ent["entity_group"] == cur["entity_group"]
            and ent["start"] <= cur["end"] + 1
        ):
            cur["end"] = max(cur["end"], ent["end"])
            cur["word"] = cur["word"] + " " + ent["word"]
            cur["score"] = (cur["score"] + ent["score"]) / 2
        else:
            merged.append(cur)
            cur = dict(ent)

    merged.append(cur)
    return merged


class BanglaBERTNER:
    """Wrapper around a fine-tuned BanglaBERT token-classification model."""

    def __init__(self, model_dir: str | Path | None = None):
        model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        if not model_dir.exists():
            raise FileNotFoundError(
                f"BanglaBERT NER model not found at: {model_dir}\n"
                "Train first with: python train_ner_banglabert.py"
            )

        self.model_dir = model_dir
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self.model = AutoModelForTokenClassification.from_pretrained(str(model_dir))

        device = 0 if torch.cuda.is_available() else -1
        self.ner_pipeline = hf_pipeline(
            "token-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",
            device=device,
        )

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Run NER on *text* and return output in LLM-compatible format:
            {"text": <input_text>, "entities": [{"text": ..., "label": ...}, ...]}
        """
        norm_text = bangla_normalize(text)
        raw = self.ner_pipeline(norm_text)
        raw = _merge_subword_entities(raw)

        entities: List[Dict[str, str]] = []
        for ent in raw:
            entities.append({
                "text": norm_text[ent["start"]:ent["end"]],
                "label": ent["entity_group"],
            })

        return {
            "text": norm_text,
            "entities": entities,
        }

