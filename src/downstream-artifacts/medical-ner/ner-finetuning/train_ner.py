#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fine-tune a pretrained encoder for Bengali Medical NER.

Supports multiple base models (select with --model):
  banglabert   csebuetnlp/banglabert   (~110M params, Bangla-specific normalizer)
  mmbert       jhu-clsp/mmBERT-base    (~307M params, multilingual ModernBERT)

All training hyper-parameters are tunable via command-line arguments.
Each model comes with sensible defaults suited for ~10K-sample datasets.
Override freely for smaller/larger data or different hardware.

Dataset location (auto-resolved relative to this script):
    ../../../saved-data/downstream-datasets/medical-ner/split/{train,val,test}/*/ground_truth.json

Output:
    <script_dir>/<model>-output/best_model/

Examples:
    # BanglaBERT with defaults (good for ~10K samples)
    python train_ner.py --model banglabert

    # mmBERT with custom params
    python train_ner.py --model mmbert --lr 2e-5 --train-batch 2 --grad-accum 4 --fp16

    # Tiny dataset (~38 samples) — more epochs, smaller batch
    python train_ner.py --model banglabert --epochs 30 --train-batch 4 --grad-accum 2 \\
        --warmup-steps 20 --early-stopping 7 --logging-steps 10

Requirements:
    pip install torch transformers datasets evaluate seqeval accelerate
    pip install git+https://github.com/csebuetnlp/normalizer.git   # only needed for banglabert
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import evaluate
from datasets import Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
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
        "normalize": "bangla",               # requires normalizer package
        "max_length": 512,                   # hard limit (ELECTRA, max_position_embeddings=512)
        "defaults": {
            "lr": 3e-5,
            "train_batch": 8,
            "eval_batch": 16,
            "grad_accum": 1,
            "epochs": 10,
            "warmup_steps": 100,
            "early_stopping": 5,
            "fp16": False,
            "weight_decay": 0.01,
            "logging_steps": 50,
        },
    },
    "mmbert": {
        "hf_name": "jhu-clsp/mmBERT-base",
        "normalize": "strip",                # no special normalizer needed
        "max_length": 1024,                  # ModernBERT supports up to 8192; 1024 is a safe default
        "defaults": {
            "lr": 2e-5,
            "train_batch": 4,
            "eval_batch": 8,
            "grad_accum": 4,
            "epochs": 10,
            "warmup_steps": 100,
            "early_stopping": 5,
            "fp16": True,
            "weight_decay": 0.01,
            "logging_steps": 50,
        },
    },
}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    SCRIPT_DIR / ".." / ".." / ".." / "saved-data"
    / "downstream-datasets" / "medical-ner" / "split"
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Entity / BIO labels  (fixed for Bengali medical NER)
# ═══════════════════════════════════════════════════════════════════════════════

ENTITY_LABELS = sorted([
    "ANATOMY_BODY_PART",
    "DISEASE_CONDITION",
    "DRUG_MEDICATION",
    "SYMPTOM_SIGN",
    "TEST_INVESTIGATION",
    "TREATMENT_PROCEDURE",
])


def build_bio_label_list(entity_labels: List[str]) -> List[str]:
    """O, then B-/I- for each entity label."""
    bio = ["O"]
    for lbl in entity_labels:
        bio.append(f"B-{lbl}")
        bio.append(f"I-{lbl}")
    return bio


LABEL_LIST = build_bio_label_list(ENTITY_LABELS)
LABEL2ID: Dict[str, int] = {lbl: i for i, lbl in enumerate(LABEL_LIST)}
ID2LABEL: Dict[int, str] = {i: lbl for lbl, i in LABEL2ID.items()}
NUM_LABELS = len(LABEL_LIST)


# ═══════════════════════════════════════════════════════════════════════════════
#  Normalisation dispatch
# ═══════════════════════════════════════════════════════════════════════════════

def get_normalize_fn(mode: str) -> Callable[[str], str]:
    """Return a text normalisation function.

    - ``"bangla"`` → csebuetnlp normalizer (must be installed)
    - ``"strip"``  → simple ``str.strip()``
    - anything else → identity
    """
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
    """Load every ground_truth.json from numbered subfolders in *split_dir*."""
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
            print(f"  [WARN] Missing ground_truth.json in {folder}")
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
#  Span resolution
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResolvedEntity:
    text: str
    label: str
    start: int   # inclusive char offset in normalised text
    end: int     # exclusive char offset


def _overlaps_any(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    for s, e in spans:
        if not (end <= s or start >= e):
            return True
    return False


def _find_non_overlapping(
    text: str,
    needle: str,
    search_from: int,
    used: List[Tuple[int, int]],
    fallback_global: bool = True,
) -> Optional[Tuple[int, int]]:
    """Find *needle* in *text* starting at *search_from*, skipping overlaps."""
    if not needle:
        return None

    pos = text.find(needle, search_from)
    while pos != -1:
        end = pos + len(needle)
        if not _overlaps_any(pos, end, used):
            return (pos, end)
        pos = text.find(needle, pos + 1)

    if not fallback_global:
        return None

    pos = text.find(needle, 0)
    while pos != -1:
        end = pos + len(needle)
        if not _overlaps_any(pos, end, used):
            return (pos, end)
        pos = text.find(needle, pos + 1)

    return None


def resolve_entities(
    norm_text: str,
    raw_entities: List[Dict[str, str]],
    normalize_fn: Callable[[str], str],
    sample_id: Any = "?",
) -> List[ResolvedEntity]:
    """Map entity mention texts → non-overlapping character spans."""
    resolved: List[ResolvedEntity] = []
    used: List[Tuple[int, int]] = []
    cursor = 0

    for ent in raw_entities:
        raw_ent_text = ent["text"].strip()
        label = ent["label"].strip()
        if not raw_ent_text:
            continue

        # Try normalised entity text first
        needle = normalize_fn(raw_ent_text)
        span = _find_non_overlapping(norm_text, needle, cursor, used)

        # Fallback: try original (un-normalised) entity text
        if span is None and needle != raw_ent_text:
            span = _find_non_overlapping(norm_text, raw_ent_text, cursor, used)

        if span is None:
            print(
                f"    [WARN] sample {sample_id}: could not resolve "
                f"'{raw_ent_text}' ({label}) — skipping"
            )
            continue

        start, end = span
        resolved.append(ResolvedEntity(
            text=norm_text[start:end], label=label, start=start, end=end,
        ))
        used.append((start, end))
        cursor = end

    return resolved


# ═══════════════════════════════════════════════════════════════════════════════
#  BIO projection onto subword tokens
# ═══════════════════════════════════════════════════════════════════════════════

def tokenize_and_build_labels(
    text: str,
    entities: List[Dict[str, str]],
    tokenizer,
    label2id: Dict[str, int],
    max_length: int,
    normalize_fn: Callable[[str], str],
    sample_id: Any = "?",
) -> Dict[str, List[int]]:
    """
    1. Normalise *text*.
    2. Resolve entity spans on the normalised text.
    3. Tokenise with HF fast tokenizer (offset_mapping).
    4. Project character-level spans → BIO token labels.

    Returns ``{"input_ids": [...], "attention_mask": [...], "labels": [...]}``.
    """
    norm_text = normalize_fn(text)
    resolved = resolve_entities(norm_text, entities, normalize_fn, sample_id=sample_id)
    resolved_sorted = sorted(resolved, key=lambda e: (e.start, e.end))

    enc = tokenizer(
        norm_text,
        truncation=True,
        max_length=max_length,
        return_offsets_mapping=True,
        padding=False,
    )
    offsets: List[Tuple[int, int]] = enc["offset_mapping"]

    # Step 1: assign an entity index (or None) to each token
    num_tokens = len(offsets)
    tok_ent_idx: List[Optional[int]] = [None] * num_tokens

    for t_idx, (t_s, t_e) in enumerate(offsets):
        if t_s == t_e:          # special token
            continue
        for e_idx, ent in enumerate(resolved_sorted):
            if ent.start >= t_e:
                break           # remaining entities are further right
            if not (t_e <= ent.start or t_s >= ent.end):
                tok_ent_idx[t_idx] = e_idx
                break           # first overlapping entity wins

    # Step 2: decide B- vs I- for each labelled token
    labels: List[int] = []
    for t_idx, (t_s, t_e) in enumerate(offsets):
        if t_s == t_e:
            labels.append(-100)              # ignored in loss (special tokens)
            continue

        e_idx = tok_ent_idx[t_idx]
        if e_idx is None:
            labels.append(label2id["O"])
            continue

        ent = resolved_sorted[e_idx]

        # Look at the immediately preceding real token
        is_continuation = False
        for prev in range(t_idx - 1, -1, -1):
            ps, pe = offsets[prev]
            if ps == pe:
                continue                     # skip special tokens
            if tok_ent_idx[prev] == e_idx:
                is_continuation = True
            break

        prefix = "I" if is_continuation else "B"
        tag = f"{prefix}-{ent.label}"
        labels.append(label2id.get(tag, label2id["O"]))

    return {
        "input_ids": enc["input_ids"],
        "attention_mask": enc["attention_mask"],
        "labels": labels,
    }


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
    """Pre-process all samples into a HF Dataset ready for the Trainer."""
    all_input_ids: List[List[int]] = []
    all_attention_mask: List[List[int]] = []
    all_labels: List[List[int]] = []

    print(f"\n  Tokenising {split_name} ({len(samples)} samples) ...")
    for sample in samples:
        sid = sample.get("_sample_id", "?")
        result = tokenize_and_build_labels(
            text=sample["text"],
            entities=sample.get("entities", []),
            tokenizer=tokenizer,
            label2id=label2id,
            max_length=max_length,
            normalize_fn=normalize_fn,
            sample_id=sid,
        )
        all_input_ids.append(result["input_ids"])
        all_attention_mask.append(result["attention_mask"])
        all_labels.append(result["labels"])

    ds = Dataset.from_dict({
        "input_ids": all_input_ids,
        "attention_mask": all_attention_mask,
        "labels": all_labels,
    })
    print(f"  → {split_name} dataset: {len(ds)} rows, "
          f"max seq len = {max(len(ids) for ids in all_input_ids)}")
    return ds


# ═══════════════════════════════════════════════════════════════════════════════
#  Debug: print a few aligned samples for visual sanity-check
# ═══════════════════════════════════════════════════════════════════════════════

def debug_print_sample(
    sample: Dict[str, Any],
    tokenizer,
    label2id: Dict[str, int],
    id2label: Dict[int, str],
    max_length: int,
    normalize_fn: Callable[[str], str],
    max_tokens_to_show: int = 60,
) -> None:
    """Pretty-print one sample's BIO alignment."""
    sid = sample.get("_sample_id", "?")
    text = sample["text"]
    norm_text = normalize_fn(text)

    result = tokenize_and_build_labels(
        text=text,
        entities=sample.get("entities", []),
        tokenizer=tokenizer,
        label2id=label2id,
        max_length=max_length,
        normalize_fn=normalize_fn,
        sample_id=sid,
    )

    tokens = tokenizer.convert_ids_to_tokens(result["input_ids"])

    print(f"\n{'─' * 70}")
    print(f"Sample #{sid}")
    print(f"Text (first 120 chars): {norm_text[:120]}...")
    print(f"Entities: {len(sample.get('entities', []))}  |  "
          f"Tokens: {len(tokens)}")
    print(f"{'─' * 70}")
    print(f"  {'Token':<30s}  {'Label'}")
    print(f"  {'─' * 30}  {'─' * 20}")

    shown = 0
    for tok, lbl_id in zip(tokens, result["labels"]):
        if shown >= max_tokens_to_show:
            print(f"  ... ({len(tokens) - shown} more tokens)")
            break
        lbl_str = id2label[lbl_id] if lbl_id != -100 else "<IGNORED>"
        marker = "" if lbl_str in ("O", "<IGNORED>") else "  ◄"
        print(f"  {tok:<30s}  {lbl_str}{marker}")
        shown += 1


# ═══════════════════════════════════════════════════════════════════════════════
#  Metrics (seqeval)
# ═══════════════════════════════════════════════════════════════════════════════

def make_compute_metrics(id2label: Dict[int, str]):
    """Return a ``compute_metrics`` function for the Trainer."""
    seqeval = evaluate.load("seqeval")

    def compute_metrics(eval_preds):
        logits, label_ids = eval_preds
        preds = np.argmax(logits, axis=-1)

        true_preds: List[List[str]] = []
        true_labels: List[List[str]] = []

        for pred_seq, label_seq in zip(preds, label_ids):
            seq_preds: List[str] = []
            seq_labels: List[str] = []
            for p, l in zip(pred_seq, label_seq):
                if l == -100:
                    continue
                seq_preds.append(id2label[int(p)])
                seq_labels.append(id2label[int(l)])
            true_preds.append(seq_preds)
            true_labels.append(seq_labels)

        results = seqeval.compute(
            predictions=true_preds,
            references=true_labels,
            zero_division=0,
        )

        # Overall metrics
        metrics = {
            "precision": results["overall_precision"],
            "recall": results["overall_recall"],
            "f1": results["overall_f1"],
            "accuracy": results["overall_accuracy"],
        }

        # Per-entity-type metrics
        for etype in ENTITY_LABELS:
            if etype in results:
                metrics[f"{etype}_f1"] = results[etype]["f1"]
                metrics[f"{etype}_precision"] = results[etype]["precision"]
                metrics[f"{etype}_recall"] = results[etype]["recall"]

        return metrics

    return compute_metrics


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fine-tune a pretrained encoder for Bengali Medical NER",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap_epilog(),
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
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed  (default: 42)")

    # ── Training hyperparameters (None = use model-profile default) ──────
    g = p.add_argument_group("Training hyperparameters (model-specific defaults)")
    g.add_argument("--lr",              type=float, default=None,
                   help="Learning rate")
    g.add_argument("--train-batch",     type=int,   default=None,
                   help="Per-device train batch size")
    g.add_argument("--eval-batch",      type=int,   default=None,
                   help="Per-device eval batch size")
    g.add_argument("--grad-accum",      type=int,   default=None,
                   help="Gradient accumulation steps")
    g.add_argument("--epochs",          type=int,   default=None,
                   help="Maximum training epochs")
    g.add_argument("--warmup-steps",    type=int,   default=None,
                   help="LR warmup steps")
    g.add_argument("--early-stopping",  type=int,   default=None,
                   help="Early-stopping patience (epochs)")
    g.add_argument("--weight-decay",    type=float, default=None,
                   help="Weight decay")
    g.add_argument("--logging-steps",   type=int,   default=None,
                   help="Log every N optimiser steps")
    g.add_argument("--max-length",      type=int,   default=None,
                   help="Max token sequence length")
    g.add_argument("--fp16", action="store_true",  default=None,
                   help="Enable FP16 mixed precision")
    g.add_argument("--no-fp16", dest="fp16", action="store_false",
                   help="Disable FP16 (override model default)")
    g.add_argument("--save-total-limit", type=int,  default=3,
                   help="Max checkpoints to keep  (default: 3)")

    return p


def textwrap_epilog() -> str:
    lines = [
        "Model profiles (defaults applied when a flag is omitted):",
        "",
    ]
    for name, prof in MODEL_REGISTRY.items():
        d = prof["defaults"]
        lines.append(f"  {name}  ({prof['hf_name']},  max_length={prof['max_length']})")
        lines.append(
            f"    --lr {d['lr']}  --train-batch {d['train_batch']}  "
            f"--eval-batch {d['eval_batch']}  --grad-accum {d['grad_accum']}"
        )
        lines.append(
            f"    --epochs {d['epochs']}  --warmup-steps {d['warmup_steps']}  "
            f"--early-stopping {d['early_stopping']}"
        )
        fp = "--fp16" if d["fp16"] else "(no --fp16)"
        lines.append(
            f"    --weight-decay {d['weight_decay']}  "
            f"--logging-steps {d['logging_steps']}  {fp}"
        )
        lines.append("")

    lines += [
        "Suggested overrides for tiny datasets (~38 samples):",
        "  --epochs 30  --train-batch 4  --grad-accum 2  --warmup-steps 20",
        "  --early-stopping 7  --logging-steps 10",
        "",
        "Suggested overrides for large datasets (~10K samples):",
        "  --epochs 5  --train-batch 16  --grad-accum 1  --warmup-steps 200",
        "  --early-stopping 3  --logging-steps 100",
    ]
    return "\n".join(lines)


def resolve_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Merge CLI args with model-profile defaults into a flat config dict."""
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

    # Data directory
    if args.data_dir:
        cfg["data_dir"] = Path(args.data_dir).resolve()
    else:
        cfg["data_dir"] = DEFAULT_DATA_DIR.resolve()

    # Output directory
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

    # Reproducibility
    set_seed(cfg["seed"])
    random.seed(cfg["seed"])
    np.random.seed(cfg["seed"])

    normalize_fn = get_normalize_fn(cfg["normalize_mode"])

    eff_batch = cfg["train_batch"] * cfg["grad_accum"]

    print("=" * 70)
    print(f" Medical NER Fine-tuning — {cfg['model_short']}")
    print("=" * 70)
    print(f"  Base model      : {cfg['hf_name']}")
    print(f"  Normalisation   : {cfg['normalize_mode']}")
    print(f"  Data dir        : {cfg['data_dir']}")
    print(f"  Output dir      : {cfg['output_dir']}")
    print(f"  Max length      : {cfg['max_length']}")
    print(f"  Labels ({NUM_LABELS})    : {LABEL_LIST}")
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
    print(f"  Is fast         : {tokenizer.is_fast}")

    if not tokenizer.is_fast:
        print("[WARN] Tokenizer is not fast — offset_mapping may not work.")

    # ── Debug: show a few aligned samples ─────────────────────────────────
    print("\n" + "=" * 70)
    print(" Sanity check: BIO alignment on first 2 train samples")
    print("=" * 70)
    for sample in train_samples[:2]:
        debug_print_sample(
            sample, tokenizer, LABEL2ID, ID2LABEL,
            cfg["max_length"], normalize_fn,
        )

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
    model = AutoModelForTokenClassification.from_pretrained(
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
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

    # ── Metrics ───────────────────────────────────────────────────────────
    compute_metrics = make_compute_metrics(ID2LABEL)

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
        metric_for_best_model="f1",
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
    print(f"  Epochs           : {cfg['epochs']} "
          f"(early-stop patience={cfg['early_stopping']})")
    print(f"  Batch / device   : {cfg['train_batch']}")
    print(f"  Grad accum       : {cfg['grad_accum']}")
    print(f"  Eff. batch size  : {eff_batch}")
    print(f"  Learning rate    : {cfg['lr']}")
    print(f"  Warmup steps     : {cfg['warmup_steps']}")
    print(f"  FP16             : {cfg['fp16']}")
    print()

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

    # Save label + config info
    label_info = {
        "label_list": LABEL_LIST,
        "entity_labels": ENTITY_LABELS,
        "label2id": LABEL2ID,
        "id2label": {str(k): v for k, v in ID2LABEL.items()},
        "base_model": cfg["hf_name"],
        "model_short": cfg["model_short"],
        "normalize_mode": cfg["normalize_mode"],
    }
    with open(os.path.join(best_dir, "label_info.json"), "w", encoding="utf-8") as f:
        json.dump(label_info, f, ensure_ascii=False, indent=2)

    # Save eval results + full config
    eval_results = {
        "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.items()},
        "validation": val_results,
        "test": test_results,
    }
    with open(os.path.join(output_dir, "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Best model saved to: {best_dir}")
    print(f"✓ Eval results saved to: "
          f"{os.path.join(output_dir, 'eval_results.json')}")
    print("\nDone!")


if __name__ == "__main__":
    main()

