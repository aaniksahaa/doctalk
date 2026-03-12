#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fine-tune a pretrained encoder for Bengali Triage Classification.

Supports multiple base models (select with --model):
  banglabert   csebuetnlp/banglabert   (~110M params, Bangla-specific normalizer)
  mmbert       jhu-clsp/mmBERT-base    (~307M params, multilingual ModernBERT)

This is a 4-class sequence classification task that classifies patient profiles
into triage disposition categories.

Dataset location (auto-resolved relative to this script):
    ../../../saved-data/downstream-datasets/triage/split/{train,val,test}/*/ground_truth.json

Output:
    <script_dir>/<model>-output/best_model/

Examples:
    # BanglaBERT with defaults
    python train_triage.py --model banglabert

    # mmBERT with custom params
    python train_triage.py --model mmbert --lr 2e-5 --train-batch 4 --fp16

    # Small dataset — more epochs, smaller batch
    python train_triage.py --model banglabert --epochs 50 --train-batch 4 \\
        --grad-accum 2 --warmup-steps 10 --early-stopping 10 --logging-steps 5

Requirements:
    pip install torch transformers datasets scikit-learn accelerate
    pip install git+https://github.com/csebuetnlp/normalizer.git   # only for banglabert
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import numpy as np
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Model registry
# ═══════════════════════════════════════════════════════════════════════════════

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "banglabert": {
        "hf_name": "csebuetnlp/banglabert",
        "normalize": "bangla",
        "max_length": 512,
        "defaults": {
            "lr": 3e-5,
            "train_batch": 4,
            "eval_batch": 8,
            "grad_accum": 2,
            "epochs": 50,
            "warmup_steps": 10,
            "early_stopping": 10,
            "fp16": False,
            "weight_decay": 0.01,
            "logging_steps": 5,
        },
    },
    "mmbert": {
        "hf_name": "jhu-clsp/mmBERT-base",
        "normalize": "strip",
        "max_length": 1024,
        "defaults": {
            "lr": 2e-5,
            "train_batch": 4,
            "eval_batch": 8,
            "grad_accum": 2,
            "epochs": 50,
            "warmup_steps": 10,
            "early_stopping": 10,
            "fp16": True,
            "weight_decay": 0.01,
            "logging_steps": 5,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Triage labels
# ═══════════════════════════════════════════════════════════════════════════════

TRIAGE_LABELS = sorted([
    "REASSURANCE_SELF_CARE",
    "ROUTINE_OUTPATIENT_VISIT",
    "INVESTIGATION_OR_SPECIALIST_REFERRAL",
    "URGENT_EMERGENCY_CARE",
])

LABEL2ID: Dict[str, int] = {lbl: i for i, lbl in enumerate(TRIAGE_LABELS)}
ID2LABEL: Dict[int, str] = {i: lbl for lbl, i in LABEL2ID.items()}
NUM_LABELS = len(TRIAGE_LABELS)


# ═══════════════════════════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    SCRIPT_DIR / ".." / ".." / ".." / "saved-data"
    / "downstream-datasets" / "triage" / "split"
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Normalisation dispatch
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


# ═══════════════════════════════════════════════════════════════════════════════
#  Data loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_split_samples(split_dir: Path) -> List[Dict[str, Any]]:
    """Load every ground_truth.json from numbered subfolders."""
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


def load_all_splits(data_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    data_dir = data_dir.resolve()
    print(f"\nLoading data from: {data_dir}")
    splits: Dict[str, List[Dict[str, Any]]] = {}
    for name in ("train", "val", "test"):
        samples = load_split_samples(data_dir / name)
        splits[name] = samples
        print(f"  {name:>5s}: {len(samples)} samples")
    return splits


# ═══════════════════════════════════════════════════════════════════════════════
#  Dataset preparation
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_dataset(
    samples: List[Dict[str, Any]],
    tokenizer,
    label2id: Dict[str, int],
    max_length: int,
    normalize_fn: Callable[[str], str],
    split_name: str = "",
) -> Dataset:
    """Tokenise all samples into a HF Dataset for the Trainer."""
    all_input_ids: List[List[int]] = []
    all_attention_mask: List[List[int]] = []
    all_labels: List[int] = []

    print(f"\n  Tokenising {split_name} ({len(samples)} samples) ...")
    for sample in samples:
        text = normalize_fn(sample["patient_profile"])
        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        all_input_ids.append(enc["input_ids"])
        all_attention_mask.append(enc["attention_mask"])
        all_labels.append(label2id[sample["type"]])

    ds = Dataset.from_dict({
        "input_ids": all_input_ids,
        "attention_mask": all_attention_mask,
        "labels": all_labels,
    })
    max_seq = max(len(ids) for ids in all_input_ids) if all_input_ids else 0
    print(f"  → {split_name} dataset: {len(ds)} rows, max seq len = {max_seq}")

    # Print label distribution
    from collections import Counter
    label_counts = Counter(all_labels)
    for lbl_id in sorted(label_counts):
        print(f"    {ID2LABEL[lbl_id]}: {label_counts[lbl_id]}")

    return ds


# ═══════════════════════════════════════════════════════════════════════════════
#  Metrics
# ═══════════════════════════════════════════════════════════════════════════════

def make_compute_metrics():
    """Return a compute_metrics function for the Trainer."""

    def compute_metrics(eval_preds):
        logits, labels = eval_preds
        preds = np.argmax(logits, axis=-1)

        acc = accuracy_score(labels, preds)
        f1_macro = f1_score(labels, preds, average="macro", zero_division=0)
        f1_weighted = f1_score(labels, preds, average="weighted", zero_division=0)
        precision_macro = precision_score(labels, preds, average="macro", zero_division=0)
        recall_macro = recall_score(labels, preds, average="macro", zero_division=0)

        metrics = {
            "accuracy": acc,
            "f1_macro": f1_macro,
            "f1_weighted": f1_weighted,
            "precision_macro": precision_macro,
            "recall_macro": recall_macro,
        }

        # Per-class metrics
        for lbl_name, lbl_id in LABEL2ID.items():
            mask = labels == lbl_id
            if mask.sum() == 0:
                continue
            cls_preds = (preds == lbl_id).astype(int)
            cls_true = (labels == lbl_id).astype(int)
            metrics[f"{lbl_name}_f1"] = f1_score(
                cls_true, cls_preds, zero_division=0,
            )

        return metrics

    return compute_metrics


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fine-tune a pretrained encoder for Bengali Triage Classification",
    )
    p.add_argument(
        "--model", required=True,
        choices=list(MODEL_REGISTRY.keys()),
        help="Which pretrained model to fine-tune",
    )
    p.add_argument(
        "--data-dir", type=str, default=None,
        help="Path to the split/ directory  (default: auto-resolved)",
    )
    p.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory  (default: <script_dir>/<model>-output)",
    )
    p.add_argument("--seed", type=int, default=42)

    g = p.add_argument_group("Training hyperparameters")
    g.add_argument("--lr",              type=float, default=None)
    g.add_argument("--train-batch",     type=int,   default=None)
    g.add_argument("--eval-batch",      type=int,   default=None)
    g.add_argument("--grad-accum",      type=int,   default=None)
    g.add_argument("--epochs",          type=int,   default=None)
    g.add_argument("--warmup-steps",    type=int,   default=None)
    g.add_argument("--early-stopping",  type=int,   default=None)
    g.add_argument("--weight-decay",    type=float, default=None)
    g.add_argument("--logging-steps",   type=int,   default=None)
    g.add_argument("--max-length",      type=int,   default=None)
    g.add_argument("--fp16",            action="store_true",  default=None)
    g.add_argument("--no-fp16", dest="fp16", action="store_false")
    g.add_argument("--save-total-limit", type=int,  default=3)

    return p


def resolve_config(args: argparse.Namespace) -> Dict[str, Any]:
    profile = MODEL_REGISTRY[args.model]
    defaults = profile["defaults"]

    def pick(cli_val, key):
        return cli_val if cli_val is not None else defaults[key]

    cfg: Dict[str, Any] = {
        "model_short": args.model,
        "hf_name": profile["hf_name"],
        "normalize_mode": profile["normalize"],
        "max_length": (
            args.max_length if args.max_length is not None
            else profile["max_length"]
        ),
        "seed": args.seed,
        "lr": pick(args.lr, "lr"),
        "train_batch": pick(args.train_batch, "train_batch"),
        "eval_batch": pick(args.eval_batch, "eval_batch"),
        "grad_accum": pick(args.grad_accum, "grad_accum"),
        "epochs": pick(args.epochs, "epochs"),
        "warmup_steps": pick(args.warmup_steps, "warmup_steps"),
        "early_stopping": pick(args.early_stopping, "early_stopping"),
        "fp16": pick(args.fp16, "fp16"),
        "weight_decay": pick(args.weight_decay, "weight_decay"),
        "logging_steps": pick(args.logging_steps, "logging_steps"),
        "save_total_limit": args.save_total_limit,
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

    set_seed(cfg["seed"])
    random.seed(cfg["seed"])
    np.random.seed(cfg["seed"])

    normalize_fn = get_normalize_fn(cfg["normalize_mode"])
    eff_batch = cfg["train_batch"] * cfg["grad_accum"]

    print("=" * 70)
    print(f" Triage Classification Fine-tuning — {cfg['model_short']}")
    print("=" * 70)
    print(f"  Base model      : {cfg['hf_name']}")
    print(f"  Normalisation   : {cfg['normalize_mode']}")
    print(f"  Data dir        : {cfg['data_dir']}")
    print(f"  Output dir      : {cfg['output_dir']}")
    print(f"  Max length      : {cfg['max_length']}")
    print(f"  Labels ({NUM_LABELS})     : {TRIAGE_LABELS}")
    print(f"  Seed            : {cfg['seed']}")
    print(f"  Learning rate   : {cfg['lr']}")
    print(f"  Train batch     : {cfg['train_batch']}")
    print(f"  Eval batch      : {cfg['eval_batch']}")
    print(f"  Grad accum      : {cfg['grad_accum']}")
    print(f"  Eff. batch      : {eff_batch}")
    print(f"  Epochs          : {cfg['epochs']}")
    print(f"  Warmup steps    : {cfg['warmup_steps']}")
    print(f"  Early stopping  : {cfg['early_stopping']}")
    print(f"  FP16            : {cfg['fp16']}")
    print(f"  Weight decay    : {cfg['weight_decay']}")

    # ── Load data ─────────────────────────────────────────────────────────
    splits = load_all_splits(cfg["data_dir"])
    train_samples = splits["train"]
    val_samples = splits["val"]
    test_samples = splits["test"]

    if not train_samples:
        print("\n[ERROR] No training samples found. Check --data-dir.")
        sys.exit(1)

    # ── Tokenizer ─────────────────────────────────────────────────────────
    hf_name = cfg["hf_name"]
    print(f"\nLoading tokenizer: {hf_name}")
    tokenizer = AutoTokenizer.from_pretrained(hf_name)
    print(f"  Tokenizer class : {type(tokenizer).__name__}")
    print(f"  Vocab size      : {tokenizer.vocab_size}")

    # ── Prepare datasets ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Preparing tokenized datasets")
    print("=" * 70)

    ds_train = prepare_dataset(
        train_samples, tokenizer, LABEL2ID,
        cfg["max_length"], normalize_fn, "train",
    )
    ds_val = prepare_dataset(
        val_samples, tokenizer, LABEL2ID,
        cfg["max_length"], normalize_fn, "val",
    )
    ds_test = prepare_dataset(
        test_samples, tokenizer, LABEL2ID,
        cfg["max_length"], normalize_fn, "test",
    )

    # ── Model ─────────────────────────────────────────────────────────────
    print(f"\nLoading model: {hf_name}")
    model = AutoModelForSequenceClassification.from_pretrained(
        hf_name,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total params     : {total_params:,}")
    print(f"  Trainable params : {trainable:,}")

    # ── Data collator ─────────────────────────────────────────────────────
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # ── Metrics ───────────────────────────────────────────────────────────
    compute_metrics = make_compute_metrics()

    # ── Training arguments ────────────────────────────────────────────────
    output_dir = str(cfg["output_dir"])
    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=cfg["logging_steps"],
        learning_rate=cfg["lr"],
        per_device_train_batch_size=cfg["train_batch"],
        per_device_eval_batch_size=cfg["eval_batch"],
        gradient_accumulation_steps=cfg["grad_accum"],
        num_train_epochs=cfg["epochs"],
        weight_decay=cfg["weight_decay"],
        warmup_steps=cfg["warmup_steps"],
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        save_total_limit=cfg["save_total_limit"],
        report_to="none",
        fp16=cfg["fp16"],
        seed=cfg["seed"],
        logging_first_step=True,
    )

    # ── Trainer ───────────────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=cfg["early_stopping"],
            ),
        ],
    )

    # ── Train ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Starting training")
    print("=" * 70)
    trainer.train()

    # ── Evaluate ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Evaluation")
    print("=" * 70)

    print("\n── Validation set ──")
    val_results = trainer.evaluate(ds_val)
    for k, v in sorted(val_results.items()):
        print(f"  {k}: {v}")

    print("\n── Test set ──")
    test_results = trainer.evaluate(ds_test)
    for k, v in sorted(test_results.items()):
        print(f"  {k}: {v}")

    # ── Save best model ──────────────────────────────────────────────────
    best_dir = os.path.join(output_dir, "best_model")
    trainer.save_model(best_dir)
    tokenizer.save_pretrained(best_dir)

    label_info = {
        "task": "triage",
        "label_list": TRIAGE_LABELS,
        "label2id": LABEL2ID,
        "id2label": {str(k): v for k, v in ID2LABEL.items()},
        "num_labels": NUM_LABELS,
        "base_model": cfg["hf_name"],
        "model_short": cfg["model_short"],
        "normalize_mode": cfg["normalize_mode"],
    }
    with open(os.path.join(best_dir, "label_info.json"), "w", encoding="utf-8") as f:
        json.dump(label_info, f, ensure_ascii=False, indent=2)

    eval_results = {
        "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.items()},
        "validation": val_results,
        "test": test_results,
    }
    with open(os.path.join(output_dir, "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Best model saved to: {best_dir}")
    print(f"✓ Eval results saved to: {os.path.join(output_dir, 'eval_results.json')}")
    print("\nDone!")


if __name__ == "__main__":
    main()

