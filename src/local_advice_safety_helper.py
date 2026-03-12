#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper module for local fine-tuned Advice-Safety Classification models.

Used by ``infer_downstream.py`` when ``--model`` is a local embedding model
for the ``advice-safety`` task.

Approach: frozen sentence-transformer embeds (patient_profile, recommendation)
pairs, then a trained MLP classifies each pair as SAFE / HARMFUL.

Loads the model once, then exposes ``predict(input_dict)`` which returns::

    {
      "patient_profile": "...",
      "recommendations": [
        {"content": "...", "label": "SAFE"},
        {"content": "...", "label": "HARMFUL"},
      ]
    }

Supported models are registered in ``EMBEDDING_CONFIGS``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import torch
import torch.nn as nn


# ── Path anchors ─────────────────────────────────────────────────────────────

_SRC_DIR = Path(__file__).resolve().parent
_ADVICE_SAFETY_FINETUNING_DIR = (
    _SRC_DIR / "downstream-artifacts" / "advice-safety" / "advice-safety-finetuning"
)


# ══════════════════════════════════════════════════════════════════════════════
#  Embedding model registry
# ══════════════════════════════════════════════════════════════════════════════

EMBEDDING_CONFIGS: Dict[str, Dict[str, Any]] = {
    "multilingual-minilm": {
        "model_dirs": [
            _ADVICE_SAFETY_FINETUNING_DIR / "multilingual-minilm-output" / "best_model",
        ],
    },
    "multilingual-e5-small": {
        "model_dirs": [
            _ADVICE_SAFETY_FINETUNING_DIR / "multilingual-e5-small-output" / "best_model",
        ],
    },
}


# ── Model-dir discovery ──────────────────────────────────────────────────────

def _find_model_dir(model_name: str) -> Path:
    cfg = EMBEDDING_CONFIGS.get(model_name)
    if cfg is None:
        raise ValueError(
            f"Unknown advice-safety model '{model_name}'.  "
            f"Available: {', '.join(EMBEDDING_CONFIGS)}"
        )
    for d in cfg["model_dirs"]:
        if d.exists():
            return d
    checked = "\n  ".join(str(d) for d in cfg["model_dirs"])
    raise FileNotFoundError(
        f"No trained advice-safety model found for '{model_name}'.\n"
        f"  Checked:\n  {checked}\n"
        f"  Train first with: python train_advice_safety_embed.py --model {model_name}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Pair classifier head (must match training architecture)
# ══════════════════════════════════════════════════════════════════════════════

class PairClassifierHead(nn.Module):
    """MLP classifier that takes concatenated (profile, rec) embeddings."""

    def __init__(
        self,
        embedding_dim: int,
        hidden_dim: int,
        num_classes: int,
        dropout: float = 0.3,
    ):
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

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ══════════════════════════════════════════════════════════════════════════════
#  Public class
# ══════════════════════════════════════════════════════════════════════════════

class LocalAdviceSafetyModel:
    """Wrapper for local embedding-based advice-safety classifier.

    Parameters
    ----------
    model_name : str
        Key in ``EMBEDDING_CONFIGS`` (e.g. ``"multilingual-minilm"``).
    model_dir : str | Path | None
        Explicit path; auto-discovered if ``None``.
    """

    def __init__(self, model_name: str, model_dir: str | Path | None = None):
        if model_name not in EMBEDDING_CONFIGS:
            raise ValueError(
                f"Unknown advice-safety model '{model_name}'.  "
                f"Available: {', '.join(EMBEDDING_CONFIGS)}"
            )

        self.model_name = model_name

        if model_dir is not None:
            self.model_dir = Path(model_dir)
        else:
            self.model_dir = _find_model_dir(model_name)

        print(f"  Loading advice-safety model '{model_name}' from: {self.model_dir}")
        self._load()

    def _load(self) -> None:
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

        # Sentence-transformer (frozen)
        self.embedder = SentenceTransformer(
            mcfg["embedding_model"], device=str(self.device),
        )

        # Classifier head
        self.classifier = PairClassifierHead(
            embedding_dim=mcfg["embedding_dim"],
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
        """Run advice-safety classification on all recommendations.

        Parameters
        ----------
        input_dict : dict
            Must contain ``"patient_profile"`` and ``"recommendations"``
            (list of ``{"content": ...}``).

        Returns
        -------
        dict
            Same structure with ``"label"`` added to each recommendation.
        """
        profile = input_dict["patient_profile"]
        recs = input_dict.get("recommendations", [])

        if not recs:
            return {
                "patient_profile": profile,
                "recommendations": [],
            }

        # Embed profile once
        profile_emb = self.embedder.encode(
            [profile], convert_to_numpy=True, show_progress_bar=False,
        )  # shape (1, dim)

        # Embed all recommendations
        rec_texts = [r["content"] for r in recs]
        rec_embs = self.embedder.encode(
            rec_texts, convert_to_numpy=True, show_progress_bar=False,
        )  # shape (N, dim)

        # Repeat profile embedding for each recommendation
        import numpy as np
        profile_repeated = np.repeat(profile_emb, len(recs), axis=0)

        # Concatenate and classify
        pair_features = np.concatenate([profile_repeated, rec_embs], axis=-1)
        x = torch.tensor(pair_features, dtype=torch.float32).to(self.device)

        with torch.no_grad():
            logits = self.classifier(x)
        pred_ids = logits.argmax(dim=-1).cpu().tolist()

        # Build output
        output_recs: List[Dict[str, str]] = []
        for rec, pred_id in zip(recs, pred_ids):
            output_recs.append({
                "content": rec["content"],
                "label": self.id2label[pred_id],
            })

        return {
            "patient_profile": profile,
            "recommendations": output_recs,
        }

