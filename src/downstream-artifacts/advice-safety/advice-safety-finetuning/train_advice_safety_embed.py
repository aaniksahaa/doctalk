#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Train a classifier on top of frozen multilingual embeddings for
Bengali Advice-Safety Classification.

Approach:
  1. For each (patient_profile, recommendation) pair in the dataset,
     encode both with a multilingual sentence-transformer.
  2. Concatenate the two embeddings to form the classifier input.
  3. Train a small MLP to predict SAFE / HARMFUL.
  4. The embedding model stays frozen; only the MLP is trained.

Note: each ground_truth.json contains one patient_profile with multiple
recommendations, so a single sample expands into multiple training pairs.

Supported embedding models (select with --model):
  multilingual-minilm       sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  (384-dim)
  multilingual-e5-small     intfloat/multilingual-e5-small                                (384-dim)

Dataset location (auto-resolved relative to this script):
    ../../../saved-data/downstream-datasets/advice-safety/split/{train,val,test}/*/ground_truth.json

Output:
    <script_dir>/<model>-output/best_model/
        classifier.pt       — MLP state_dict
        model_config.json   — label map + embedding model info

Examples:
    python train_advice_safety_embed.py --model multilingual-minilm
    python train_advice_safety_embed.py --model multilingual-e5-small --epochs 200 --lr 1e-3

Requirements:
    pip install torch sentence-transformers scikit-learn
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from torch.utils.data import DataLoader, TensorDataset


# ═══════════════════════════════════════════════════════════════════════════════
#  Embedding model registry
# ═══════════════════════════════════════════════════════════════════════════════

EMBEDDING_REGISTRY: Dict[str, Dict[str, Any]] = {
    "multilingual-minilm": {
        "hf_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "embedding_dim": 384,
        "defaults": {
            "lr": 5e-4,
            "epochs": 200,
            "batch_size": 8,
            "hidden_dim": 256,
            "dropout": 0.3,
            "early_stopping": 30,
            "weight_decay": 1e-4,
        },
    },
    "multilingual-e5-small": {
        "hf_name": "intfloat/multilingual-e5-small",
        "embedding_dim": 384,
        "defaults": {
            "lr": 5e-4,
            "epochs": 200,
            "batch_size": 8,
            "hidden_dim": 256,
            "dropout": 0.3,
            "early_stopping": 30,
            "weight_decay": 1e-4,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Advice-safety labels
# ═══════════════════════════════════════════════════════════════════════════════

SAFETY_LABELS = sorted(["HARMFUL", "SAFE"])   # alphabetical → HARMFUL=0, SAFE=1

LABEL2ID: Dict[str, int] = {lbl: i for i, lbl in enumerate(SAFETY_LABELS)}
ID2LABEL: Dict[int, str] = {i: lbl for lbl, i in LABEL2ID.items()}
NUM_LABELS = len(SAFETY_LABELS)


# ═══════════════════════════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    SCRIPT_DIR / ".." / ".." / ".." / "saved-data"
    / "downstream-datasets" / "advice-safety" / "split"
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Classifier head  (dual-embedding input)
# ═══════════════════════════════════════════════════════════════════════════════

class PairClassifierHead(nn.Module):
    """MLP classifier that takes concatenated (profile, recommendation) embeddings."""

    def __init__(
        self,
        embedding_dim: int,
        hidden_dim: int,
        num_classes: int,
        dropout: float = 0.3,
    ):
        super().__init__()
        input_dim = embedding_dim * 2   # concatenation of two embeddings
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


# ═══════════════════════════════════════════════════════════════════════════════
#  Data loading — flatten to (profile_text, rec_text, label) triples
# ═══════════════════════════════════════════════════════════════════════════════

def load_split_samples(split_dir: Path) -> List[Dict[str, Any]]:
    """Load raw ground_truth.json files."""
    samples: List[Dict[str, Any]] = []
    if not split_dir.exists():
        print(f"  [WARN] Split dir not found: {split_dir}")
        return samples

    folders = sorted(
        [f for f in split_dir.iterdir() if f.is_dir()],
        key=lambda x: int(x.name),
    )
    for folder in folders:
        gt_path = folder / "ground_truth.json"
        if not gt_path.exists():
            continue
        with open(gt_path, "r", encoding="utf-8") as fh:
            sample = json.load(fh)
        sample["_sample_id"] = int(folder.name)
        samples.append(sample)
    return samples


def flatten_to_pairs(
    samples: List[Dict[str, Any]],
    label2id: Dict[str, int],
) -> Tuple[List[str], List[str], torch.Tensor]:
    """
    Flatten samples into (profile_texts, rec_texts, labels).
    Each recommendation in a sample becomes a separate training pair.
    """
    profile_texts: List[str] = []
    rec_texts: List[str] = []
    labels: List[int] = []

    for sample in samples:
        profile = sample["patient_profile"]
        for rec in sample.get("recommendations", []):
            content = rec["content"]
            label = rec["label"]
            if label not in label2id:
                print(f"  [WARN] Unknown label '{label}' — skipping")
                continue
            profile_texts.append(profile)
            rec_texts.append(content)
            labels.append(label2id[label])

    return profile_texts, rec_texts, torch.tensor(labels, dtype=torch.long)


def load_all_splits(data_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    data_dir = data_dir.resolve()
    print(f"\nLoading data from: {data_dir}")
    splits: Dict[str, List[Dict[str, Any]]] = {}
    for name in ("train", "val", "test"):
        samples = load_split_samples(data_dir / name)
        splits[name] = samples
        print(f"  {name:>5s}: {len(samples)} samples (raw)")
    return splits


# ═══════════════════════════════════════════════════════════════════════════════
#  Embedding
# ═══════════════════════════════════════════════════════════════════════════════

def embed_texts(
    texts: List[str],
    model_name: str,
    device: torch.device,
) -> torch.Tensor:
    """Encode texts with a sentence-transformer (frozen, no grad)."""
    from sentence_transformers import SentenceTransformer

    print(f"  Loading embedding model: {model_name}")
    embedder = SentenceTransformer(model_name, device=str(device))
    print(f"  Encoding {len(texts)} texts ...")
    embeddings = embedder.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return torch.tensor(embeddings, dtype=torch.float32)


def build_pair_features(
    profile_embeds: torch.Tensor,
    rec_embeds: torch.Tensor,
) -> torch.Tensor:
    """Concatenate profile and recommendation embeddings."""
    return torch.cat([profile_embeds, rec_embeds], dim=-1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Training
# ═══════════════════════════════════════════════════════════════════════════════

def train_classifier(
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    X_val: torch.Tensor,
    y_val: torch.Tensor,
    cfg: Dict[str, Any],
    device: torch.device,
) -> nn.Module:
    """Train the pair classifier with early stopping."""

    model = PairClassifierHead(
        embedding_dim=cfg["embedding_dim"],
        hidden_dim=cfg["hidden_dim"],
        num_classes=NUM_LABELS,
        dropout=cfg["dropout"],
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg["lr"],
        weight_decay=cfg["weight_decay"],
    )
    criterion = nn.CrossEntropyLoss()

    train_ds = TensorDataset(X_train.to(device), y_train.to(device))
    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True)

    best_f1 = -1.0
    best_state = None
    patience_counter = 0

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        total_loss = 0.0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            logits = model(batch_X)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)

        model.eval()
        with torch.no_grad():
            val_logits = model(X_val.to(device))
            val_preds = val_logits.argmax(dim=-1).cpu().numpy()
            val_true = y_val.numpy()
            val_f1 = f1_score(val_true, val_preds, average="macro", zero_division=0)
            val_acc = accuracy_score(val_true, val_preds)

        if epoch % 10 == 0 or epoch == 1:
            print(
                f"  Epoch {epoch:>4d}/{cfg['epochs']}  "
                f"loss={avg_loss:.4f}  val_acc={val_acc:.4f}  val_f1={val_f1:.4f}"
            )

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= cfg["early_stopping"]:
                print(f"  Early stopping at epoch {epoch} (best val_f1={best_f1:.4f})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    print(f"  Best validation F1 (macro): {best_f1:.4f}")
    return model


def evaluate_model(
    model: nn.Module,
    X: torch.Tensor,
    y: torch.Tensor,
    device: torch.device,
    split_name: str,
) -> Dict[str, float]:
    model.eval()
    with torch.no_grad():
        logits = model(X.to(device))
        preds = logits.argmax(dim=-1).cpu().numpy()
    true = y.numpy()

    acc = accuracy_score(true, preds)
    f1_macro = f1_score(true, preds, average="macro", zero_division=0)
    f1_weighted = f1_score(true, preds, average="weighted", zero_division=0)

    print(f"\n── {split_name} ──")
    print(f"  Accuracy: {acc:.4f}   F1 (macro): {f1_macro:.4f}   F1 (weighted): {f1_weighted:.4f}")
    print(classification_report(
        true, preds,
        target_names=SAFETY_LABELS,
        zero_division=0,
    ))

    return {"accuracy": acc, "f1_macro": f1_macro, "f1_weighted": f1_weighted}


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Train embedding + classifier for Bengali Advice-Safety Classification",
    )
    p.add_argument(
        "--model", required=True,
        choices=list(EMBEDDING_REGISTRY.keys()),
        help="Which embedding model to use",
    )
    p.add_argument("--data-dir", type=str, default=None)
    p.add_argument("--output-dir", type=str, default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", type=str, default=None)

    g = p.add_argument_group("Training hyperparameters")
    g.add_argument("--lr",              type=float, default=None)
    g.add_argument("--epochs",          type=int,   default=None)
    g.add_argument("--batch-size",      type=int,   default=None)
    g.add_argument("--hidden-dim",      type=int,   default=None)
    g.add_argument("--dropout",         type=float, default=None)
    g.add_argument("--early-stopping",  type=int,   default=None)
    g.add_argument("--weight-decay",    type=float, default=None)

    return p


def resolve_config(args: argparse.Namespace) -> Dict[str, Any]:
    profile = EMBEDDING_REGISTRY[args.model]
    defaults = profile["defaults"]

    def pick(cli_val, key):
        return cli_val if cli_val is not None else defaults[key]

    cfg: Dict[str, Any] = {
        "model_short": args.model,
        "hf_name": profile["hf_name"],
        "embedding_dim": profile["embedding_dim"],
        "seed": args.seed,
        "lr": pick(args.lr, "lr"),
        "epochs": pick(args.epochs, "epochs"),
        "batch_size": pick(args.batch_size, "batch_size"),
        "hidden_dim": pick(args.hidden_dim, "hidden_dim"),
        "dropout": pick(args.dropout, "dropout"),
        "early_stopping": pick(args.early_stopping, "early_stopping"),
        "weight_decay": pick(args.weight_decay, "weight_decay"),
    }

    if args.data_dir:
        cfg["data_dir"] = Path(args.data_dir).resolve()
    else:
        cfg["data_dir"] = DEFAULT_DATA_DIR.resolve()

    if args.output_dir:
        cfg["output_dir"] = Path(args.output_dir).resolve()
    else:
        cfg["output_dir"] = (SCRIPT_DIR / f"{args.model}-output").resolve()

    return cfg


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = _build_parser().parse_args()
    cfg = resolve_config(args)

    torch.manual_seed(cfg["seed"])
    random.seed(cfg["seed"])
    np.random.seed(cfg["seed"])

    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("=" * 70)
    print(f" Advice-Safety Classification (Embedding) — {cfg['model_short']}")
    print("=" * 70)
    print(f"  Embedding model : {cfg['hf_name']}")
    print(f"  Embedding dim   : {cfg['embedding_dim']}")
    print(f"  Data dir        : {cfg['data_dir']}")
    print(f"  Output dir      : {cfg['output_dir']}")
    print(f"  Labels ({NUM_LABELS})     : {SAFETY_LABELS}")
    print(f"  Device          : {device}")
    print(f"  Seed            : {cfg['seed']}")
    print(f"  Learning rate   : {cfg['lr']}")
    print(f"  Epochs          : {cfg['epochs']}")
    print(f"  Batch size      : {cfg['batch_size']}")
    print(f"  Hidden dim      : {cfg['hidden_dim']}")
    print(f"  Dropout         : {cfg['dropout']}")
    print(f"  Early stopping  : {cfg['early_stopping']}")

    # ── Load data ─────────────────────────────────────────────────────────
    splits = load_all_splits(cfg["data_dir"])

    if not splits["train"]:
        print("\n[ERROR] No training samples found. Check --data-dir.")
        sys.exit(1)

    # ── Flatten to pairs ──────────────────────────────────────────────────
    train_profiles, train_recs, y_train = flatten_to_pairs(splits["train"], LABEL2ID)
    val_profiles, val_recs, y_val = flatten_to_pairs(splits["val"], LABEL2ID)
    test_profiles, test_recs, y_test = flatten_to_pairs(splits["test"], LABEL2ID)

    print(f"\n  Flattened training pairs  : {len(train_profiles)}")
    print(f"  Flattened validation pairs: {len(val_profiles)}")
    print(f"  Flattened test pairs      : {len(test_profiles)}")

    # Print label distribution
    from collections import Counter
    for name, labels in [("train", y_train), ("val", y_val), ("test", y_test)]:
        dist = Counter(labels.tolist())
        parts = [f"{ID2LABEL[k]}={v}" for k, v in sorted(dist.items())]
        print(f"    {name}: {', '.join(parts)}")

    # ── Embed all unique texts ────────────────────────────────────────────
    # Deduplicate texts for efficient embedding
    print("\n" + "=" * 70)
    print(" Embedding texts")
    print("=" * 70)

    all_profiles = train_profiles + val_profiles + test_profiles
    all_recs = train_recs + val_recs + test_recs

    # Build unique text → index mapping
    unique_texts = list(set(all_profiles + all_recs))
    print(f"  Unique texts to embed: {len(unique_texts)}")

    all_embeddings = embed_texts(unique_texts, cfg["hf_name"], device)
    text_to_idx = {t: i for i, t in enumerate(unique_texts)}

    def lookup_embeddings(texts: List[str]) -> torch.Tensor:
        indices = [text_to_idx[t] for t in texts]
        return all_embeddings[indices]

    # Build feature matrices
    X_train = build_pair_features(
        lookup_embeddings(train_profiles),
        lookup_embeddings(train_recs),
    )
    X_val = build_pair_features(
        lookup_embeddings(val_profiles),
        lookup_embeddings(val_recs),
    )
    X_test = build_pair_features(
        lookup_embeddings(test_profiles),
        lookup_embeddings(test_recs),
    )

    print(f"  Train features : {X_train.shape}")
    print(f"  Val features   : {X_val.shape}")
    print(f"  Test features  : {X_test.shape}")

    # ── Train ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Training classifier")
    print("=" * 70)
    classifier = train_classifier(X_train, y_train, X_val, y_val, cfg, device)

    # ── Evaluate ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Evaluation")
    print("=" * 70)
    val_results = evaluate_model(classifier, X_val, y_val, device, "Validation")
    test_results = evaluate_model(classifier, X_test, y_test, device, "Test")

    # ── Save ──────────────────────────────────────────────────────────────
    output_dir = cfg["output_dir"]
    best_dir = output_dir / "best_model"
    best_dir.mkdir(parents=True, exist_ok=True)

    torch.save(classifier.state_dict(), best_dir / "classifier.pt")

    model_config = {
        "task": "advice-safety",
        "model_type": "embedding_pair_classifier",
        "embedding_model": cfg["hf_name"],
        "embedding_model_short": cfg["model_short"],
        "embedding_dim": cfg["embedding_dim"],
        "hidden_dim": cfg["hidden_dim"],
        "dropout": cfg["dropout"],
        "num_labels": NUM_LABELS,
        "label_list": SAFETY_LABELS,
        "label2id": LABEL2ID,
        "id2label": {str(k): v for k, v in ID2LABEL.items()},
    }
    with open(best_dir / "model_config.json", "w", encoding="utf-8") as f:
        json.dump(model_config, f, ensure_ascii=False, indent=2)

    eval_results = {
        "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.items()},
        "validation": val_results,
        "test": test_results,
    }
    with open(output_dir / "eval_results.json", "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Classifier saved to: {best_dir}")
    print(f"✓ Eval results saved to: {output_dir / 'eval_results.json'}")
    print("\nDone!")


if __name__ == "__main__":
    main()

