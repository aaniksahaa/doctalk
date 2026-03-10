#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper module for local fine-tuned Medical NER models.

Used by ``infer_downstream.py`` when ``--model`` is a local model
(e.g. ``banglabert``, ``mmbert``) for the ``medical-ner`` task.

Loads the model once, then exposes ``predict(text)`` which returns
output in the same format as LLM-based NER inference::

    {"text": "...", "entities": [{"text": "...", "label": "..."}, ...]}

Supported models are registered in ``MODEL_CONFIGS``.  To add a new
encoder, just add an entry there and train with ``train_ner.py --model <name>``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    pipeline as hf_pipeline,
)


# ── Path anchors ─────────────────────────────────────────────────────────────

_SRC_DIR = Path(__file__).resolve().parent
_FINETUNING_DIR = (
    _SRC_DIR / "downstream-artifacts" / "medical-ner" / "ner-finetuning"
)
_LEGACY_BANGLABERT_DIR = (
    _SRC_DIR / "downstream-artifacts" / "medical-ner"
    / "banglabert-finetuning" / "banglabert-medical-ner-output" / "best_model"
)


# ── Model registry ───────────────────────────────────────────────────────────

MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "banglabert": {
        "normalize": "bangla",
        "model_dirs": [
            _FINETUNING_DIR / "banglabert-output" / "best_model",
            _LEGACY_BANGLABERT_DIR,
        ],
    },
    "mmbert": {
        "normalize": "strip",
        "model_dirs": [
            _FINETUNING_DIR / "mmbert-output" / "best_model",
        ],
    },
}


# ── Normalisation dispatch ───────────────────────────────────────────────────

def _get_normalize_fn(mode: str) -> Callable[[str], str]:
    """Return a normalisation function for the given *mode*."""
    if mode == "bangla":
        try:
            from normalizer import normalize as _bn
        except ImportError:
            print(
                "[ERROR] 'normalizer' package required for banglabert.  Install:\n"
                "  pip install git+https://github.com/csebuetnlp/normalizer.git"
            )
            sys.exit(1)
        return _bn
    elif mode == "strip":
        return lambda t: t.strip()
    return lambda t: t


# ── Model-dir discovery ──────────────────────────────────────────────────────

def _find_model_dir(model_name: str) -> Path:
    """Find the first existing model directory for *model_name*."""
    cfg = MODEL_CONFIGS.get(model_name)
    if cfg is None:
        raise ValueError(
            f"Unknown local model '{model_name}'.  "
            f"Available: {', '.join(MODEL_CONFIGS)}"
        )
    for d in cfg["model_dirs"]:
        if d.exists():
            return d
    checked = "\n  ".join(str(d) for d in cfg["model_dirs"])
    raise FileNotFoundError(
        f"No trained model found for '{model_name}'.\n"
        f"  Checked:\n  {checked}\n"
        f"  Train first with:  python train_ner.py --model {model_name}"
    )


# ── Subword merging ──────────────────────────────────────────────────────────

def _merge_subword_entities(
    raw_entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
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


# ═══════════════════════════════════════════════════════════════════════════════
#  Public class
# ═══════════════════════════════════════════════════════════════════════════════

class LocalNERModel:
    """Wrapper around a fine-tuned token-classification model.

    Parameters
    ----------
    model_name : str
        Key in ``MODEL_CONFIGS`` (e.g. ``"banglabert"``, ``"mmbert"``).
    model_dir : str | Path | None
        Explicit path to a ``best_model/`` directory.  If ``None``,
        the registry is searched automatically.
    """

    def __init__(
        self,
        model_name: str,
        model_dir: str | Path | None = None,
    ):
        cfg = MODEL_CONFIGS.get(model_name)
        if cfg is None:
            raise ValueError(
                f"Unknown local model '{model_name}'.  "
                f"Available: {', '.join(MODEL_CONFIGS)}"
            )

        self.model_name = model_name
        self.normalize_fn = _get_normalize_fn(cfg["normalize"])

        if model_dir is not None:
            self.model_dir = Path(model_dir)
            if not self.model_dir.exists():
                raise FileNotFoundError(
                    f"Model dir not found: {self.model_dir}"
                )
        else:
            self.model_dir = _find_model_dir(model_name)

        print(f"  Loading {model_name} from: {self.model_dir}")
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
        self.model = AutoModelForTokenClassification.from_pretrained(
            str(self.model_dir),
        )

        device = 0 if torch.cuda.is_available() else -1
        self.ner_pipeline = hf_pipeline(
            "token-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",
            device=device,
        )

    # ──────────────────────────────────────────────────────────────────────

    def predict(self, text: str) -> Dict[str, Any]:
        """Run NER and return output in LLM-compatible format.

        Returns
        -------
        dict
            ``{"text": <normalised_text>,
               "entities": [{"text": ..., "label": ...}, ...]}``
        """
        norm_text = self.normalize_fn(text)
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

