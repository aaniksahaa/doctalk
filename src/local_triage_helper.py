#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper module for local fine-tuned Triage Classification models.

Used by ``infer_downstream.py`` when ``--model`` is a local model
for the ``triage`` task.

Supports two model families:
  - **BERT-based** (banglabert, mmbert): fine-tuned ``AutoModelForSequenceClassification``
  - **Embedding-based** (multilingual-minilm, …): frozen sentence-transformer + MLP head

Loads the model once, then exposes ``predict(input_dict)`` which returns::

    {"patient_profile": "...", "type": "ROUTINE_OUTPATIENT_VISIT"}

Supported models are registered in ``BERT_CONFIGS`` and ``EMBEDDING_CONFIGS``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch
import torch.nn as nn


# ── Path anchors ─────────────────────────────────────────────────────────────

_SRC_DIR = Path(__file__).resolve().parent
_TRIAGE_FINETUNING_DIR = (
    _SRC_DIR / "downstream-artifacts" / "triage" / "triage-finetuning"
)


# ══════════════════════════════════════════════════════════════════════════════
#  BERT model registry  (sequence-classification fine-tuned encoders)
# ══════════════════════════════════════════════════════════════════════════════

BERT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "banglabert": {
        "normalize": "bangla",
        "model_dirs": [
            _TRIAGE_FINETUNING_DIR / "banglabert-output" / "best_model",
        ],
    },
    "mmbert": {
        "normalize": "strip",
        "model_dirs": [
            _TRIAGE_FINETUNING_DIR / "mmbert-output" / "best_model",
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  Embedding model registry  (frozen embedder + trained MLP)
# ══════════════════════════════════════════════════════════════════════════════

EMBEDDING_CONFIGS: Dict[str, Dict[str, Any]] = {
    "multilingual-minilm": {
        "model_dirs": [
            _TRIAGE_FINETUNING_DIR / "multilingual-minilm-output" / "best_model",
        ],
    },
    "multilingual-e5-small": {
        "model_dirs": [
            _TRIAGE_FINETUNING_DIR / "multilingual-e5-small-output" / "best_model",
        ],
    },
}

ALL_CONFIGS = {**BERT_CONFIGS, **EMBEDDING_CONFIGS}


# ── Normalisation ─────────────────────────────────────────────────────────────

def _get_normalize_fn(mode: str) -> Callable[[str], str]:
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

def _find_model_dir(model_name: str, configs: Dict[str, Dict]) -> Path:
    cfg = configs.get(model_name)
    if cfg is None:
        raise ValueError(
            f"Unknown triage model '{model_name}'.  "
            f"Available: {', '.join(ALL_CONFIGS)}"
        )
    for d in cfg["model_dirs"]:
        if d.exists():
            return d
    checked = "\n  ".join(str(d) for d in cfg["model_dirs"])
    raise FileNotFoundError(
        f"No trained triage model found for '{model_name}'.\n"
        f"  Checked:\n  {checked}\n"
        f"  Train first with the appropriate train_triage*.py script."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Classifier head (must match training architecture)
# ══════════════════════════════════════════════════════════════════════════════

class ClassifierHead(nn.Module):
    """Simple MLP matching train_triage_embed.py architecture."""

    def __init__(self, input_dim: int, hidden_dim: int, num_classes: int, dropout: float = 0.3):
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

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ══════════════════════════════════════════════════════════════════════════════
#  Public class
# ══════════════════════════════════════════════════════════════════════════════

class LocalTriageModel:
    """Wrapper for local triage classification models.

    Automatically detects whether the model is BERT-based or embedding-based
    from the model name.

    Parameters
    ----------
    model_name : str
        Key in ``ALL_CONFIGS`` (e.g. ``"banglabert"``, ``"multilingual-minilm"``).
    model_dir : str | Path | None
        Explicit path; auto-discovered if ``None``.
    """

    def __init__(self, model_name: str, model_dir: str | Path | None = None):
        if model_name not in ALL_CONFIGS:
            raise ValueError(
                f"Unknown triage model '{model_name}'.  "
                f"Available: {', '.join(ALL_CONFIGS)}"
            )

        self.model_name = model_name
        self.is_bert = model_name in BERT_CONFIGS

        if model_dir is not None:
            self.model_dir = Path(model_dir)
        elif self.is_bert:
            self.model_dir = _find_model_dir(model_name, BERT_CONFIGS)
        else:
            self.model_dir = _find_model_dir(model_name, EMBEDDING_CONFIGS)

        print(f"  Loading triage model '{model_name}' from: {self.model_dir}")

        if self.is_bert:
            self._load_bert()
        else:
            self._load_embedding()

    # ── BERT loader ───────────────────────────────────────────────────────

    def _load_bert(self) -> None:
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        cfg = BERT_CONFIGS[self.model_name]
        self.normalize_fn = _get_normalize_fn(cfg["normalize"])

        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_dir),
        )
        self.model.eval()

        label_info_path = self.model_dir / "label_info.json"
        if label_info_path.exists():
            with open(label_info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            self.id2label = {int(k): v for k, v in info["id2label"].items()}
        else:
            self.id2label = dict(self.model.config.id2label)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    # ── Embedding loader ─────────────────────────────────────────────────

    def _load_embedding(self) -> None:
        from sentence_transformers import SentenceTransformer

        config_path = self.model_dir / "model_config.json"
        if not config_path.exists():
            raise FileNotFoundError(
                f"model_config.json not found in {self.model_dir}"
            )
        with open(config_path, "r", encoding="utf-8") as f:
            mcfg = json.load(f)

        self.id2label = {int(k): v for k, v in mcfg["id2label"].items()}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load sentence-transformer
        self.embedder = SentenceTransformer(
            mcfg["embedding_model"], device=str(self.device),
        )

        # Load classifier head
        self.classifier = ClassifierHead(
            input_dim=mcfg["embedding_dim"],
            hidden_dim=mcfg["hidden_dim"],
            num_classes=mcfg["num_labels"],
            dropout=mcfg.get("dropout", 0.3),
        )
        state = torch.load(
            self.model_dir / "classifier.pt",
            map_location=self.device,
            weights_only=True,
        )
        self.classifier.load_state_dict(state)
        self.classifier.to(self.device)
        self.classifier.eval()

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Run triage classification.

        Parameters
        ----------
        input_dict : dict
            Must contain ``"patient_profile"`` key.

        Returns
        -------
        dict
            ``{"patient_profile": ..., "type": "ROUTINE_OUTPATIENT_VISIT"}``
        """
        profile = input_dict["patient_profile"]

        if self.is_bert:
            predicted_label = self._predict_bert(profile)
        else:
            predicted_label = self._predict_embedding(profile)

        return {
            "patient_profile": profile,
            "type": predicted_label,
        }

    def _predict_bert(self, text: str) -> str:
        norm_text = self.normalize_fn(text)
        enc = self.tokenizer(
            norm_text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**enc).logits
        pred_id = logits.argmax(dim=-1).item()
        return self.id2label[pred_id]

    def _predict_embedding(self, text: str) -> str:
        embedding = self.embedder.encode(
            [text], convert_to_numpy=True, show_progress_bar=False,
        )
        x = torch.tensor(embedding, dtype=torch.float32).to(self.device)

        with torch.no_grad():
            logits = self.classifier(x)
        pred_id = logits.argmax(dim=-1).item()
        return self.id2label[pred_id]

