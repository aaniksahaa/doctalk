#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fine-tune csebuetnlp/banglabert for Bengali Medical NER.

Dataset location:
    saved-data/downstream-datasets/medical-ner/split/{train,val,test}/*/ground_truth.json

Each ground_truth.json:
    {"text": "...", "entities": [{"text": "...", "label": "..."}, ...]}

Entity labels (6 types):
    ANATOMY_BODY_PART, DISEASE_CONDITION, DRUG_MEDICATION,
    SYMPTOM_SIGN, TEST_INVESTIGATION, TREATMENT_PROCEDURE

BIO scheme: O, B-<LABEL>, I-<LABEL>  →  13 tags total.

Requirements:
    pip install torch transformers datasets evaluate seqeval accelerate
    pip install git+https://github.com/csebuetnlp/normalizer.git

Run:
    python train_ner_banglabert.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import evaluate
from datasets import Dataset, DatasetDict
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)
from normalizer import normalize as bangla_normalize


# ═══════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════════════

MODEL_NAME = "csebuetnlp/banglabert"

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "../../../saved-data/downstream-datasets/medical-ner/split"
OUTPUT_DIR = SCRIPT_DIR / "banglabert-medical-ner-output"

SEED = 42
MAX_LENGTH = 512  # BanglaBERT max position embeddings

# --- Training hyperparameters (tuned for a small dataset ≈26 train samples) ---
LEARNING_RATE = 3e-5
TRAIN_BATCH_SIZE = 4
EVAL_BATCH_SIZE = 8
GRADIENT_ACCUMULATION_STEPS = 2   # effective batch size = 4 * 2 = 8
NUM_EPOCHS = 30
WEIGHT_DECAY = 0.01
WARMUP_STEPS = 20
EARLY_STOPPING_PATIENCE = 7
FP16 = False  # set True if your GPU supports it (saves memory)
LOGGING_STEPS = 10

# --- Fixed entity label set (alphabetical) ---
ENTITY_LABELS = sorted([
    "ANATOMY_BODY_PART",
    "DISEASE_CONDITION",
    "DRUG_MEDICATION",
    "SYMPTOM_SIGN",
    "TEST_INVESTIGATION",
    "TREATMENT_PROCEDURE",
])


# ═══════════════════════════════════════════════════════════════════════════════
#  BIO label construction
# ═══════════════════════════════════════════════════════════════════════════════

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
#  Data loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_split_samples(split_dir: Path) -> List[Dict[str, Any]]:
    """
    Load every ground_truth.json from numbered subfolders in *split_dir*.
    Returns a list of dicts, each with 'text', 'entities', and '_sample_id'.
    """
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
#  Span resolution  (adapted from evaluation-pipeline BIO conversion script)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResolvedEntity:
    text: str
    label: str
    start: int   # inclusive char offset in normalized text
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
    """Find *needle* in *text* starting at *search_from*, skipping overlapping spans."""
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
    sample_id: Any = "?",
) -> List[ResolvedEntity]:
    """
    Map entity mention texts → non-overlapping character spans in *norm_text*.
    Uses sequential left-to-right cursor; handles duplicate mentions.
    """
    resolved: List[ResolvedEntity] = []
    used: List[Tuple[int, int]] = []
    cursor = 0

    for ent in raw_entities:
        raw_ent_text = ent["text"].strip()
        label = ent["label"].strip()
        if not raw_ent_text:
            continue

        # Try normalized entity text first
        needle = bangla_normalize(raw_ent_text)
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
    sample_id: Any = "?",
) -> Dict[str, List[int]]:
    """
    1. Normalise *text* with BanglaBERT normaliser.
    2. Resolve entity spans on the normalised text.
    3. Tokenise with HF fast tokenizer (offset_mapping).
    4. Project character-level spans → BIO token labels.

    Returns {"input_ids": [...], "attention_mask": [...], "labels": [...]}.
    """
    norm_text = bangla_normalize(text)
    resolved = resolve_entities(norm_text, entities, sample_id=sample_id)
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
    max_tokens_to_show: int = 60,
) -> None:
    """Pretty-print one sample's BIO alignment."""
    sid = sample.get("_sample_id", "?")
    text = sample["text"]
    norm_text = bangla_normalize(text)

    result = tokenize_and_build_labels(
        text=text,
        entities=sample.get("entities", []),
        tokenizer=tokenizer,
        label2id=label2id,
        max_length=max_length,
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
    """Return a compute_metrics function for the Trainer."""
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
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # Reproducibility
    set_seed(SEED)
    random.seed(SEED)
    np.random.seed(SEED)

    print("=" * 70)
    print(" BanglaBERT Medical NER Fine-tuning")
    print("=" * 70)
    print(f"Model          : {MODEL_NAME}")
    print(f"Data dir       : {DATA_DIR.resolve()}")
    print(f"Output dir     : {OUTPUT_DIR.resolve()}")
    print(f"Max length     : {MAX_LENGTH}")
    print(f"Labels ({NUM_LABELS}): {LABEL_LIST}")

    # ── Load data ──────────────────────────────────────────────────────────
    splits = load_all_splits(DATA_DIR)
    train_samples = splits["train"]
    val_samples = splits["val"]
    test_samples = splits["test"]

    if not train_samples:
        print("\n[ERROR] No training samples found. Check DATA_DIR.")
        sys.exit(1)

    # ── Tokenizer ──────────────────────────────────────────────────────────
    print(f"\nLoading tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"  Tokenizer class : {type(tokenizer).__name__}")
    print(f"  Vocab size      : {tokenizer.vocab_size}")
    print(f"  Is fast         : {tokenizer.is_fast}")

    if not tokenizer.is_fast:
        print("[WARN] Tokenizer is not fast — offset_mapping may not work correctly.")

    # ── Debug: show a few aligned samples ──────────────────────────────────
    print("\n" + "=" * 70)
    print(" Sanity check: BIO alignment on first 2 train samples")
    print("=" * 70)
    for sample in train_samples[:2]:
        debug_print_sample(sample, tokenizer, LABEL2ID, ID2LABEL, MAX_LENGTH)

    # ── Prepare datasets ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Preparing tokenized datasets")
    print("=" * 70)

    ds_train = prepare_dataset(train_samples, tokenizer, LABEL2ID, MAX_LENGTH, "train")
    ds_val = prepare_dataset(val_samples, tokenizer, LABEL2ID, MAX_LENGTH, "val")
    ds_test = prepare_dataset(test_samples, tokenizer, LABEL2ID, MAX_LENGTH, "test")

    # ── Model ──────────────────────────────────────────────────────────────
    print(f"\nLoading model: {MODEL_NAME}")
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME,
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
    output_dir = str(OUTPUT_DIR.resolve())
    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=LOGGING_STEPS,
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=EVAL_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        num_train_epochs=NUM_EPOCHS,
        weight_decay=WEIGHT_DECAY,
        warmup_steps=WARMUP_STEPS,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=3,
        report_to="none",
        fp16=FP16,
        seed=SEED,
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
        callbacks=[EarlyStoppingCallback(early_stopping_patience=EARLY_STOPPING_PATIENCE)],
    )

    # ── Train ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" Starting training")
    print("=" * 70)
    print(f"  Epochs           : {NUM_EPOCHS} (early-stop patience={EARLY_STOPPING_PATIENCE})")
    print(f"  Batch / device   : {TRAIN_BATCH_SIZE}")
    print(f"  Grad accum       : {GRADIENT_ACCUMULATION_STEPS}")
    print(f"  Eff. batch size  : {TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
    print(f"  Learning rate    : {LEARNING_RATE}")
    print(f"  FP16             : {FP16}")
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

    # Save label mappings
    label_info = {
        "label_list": LABEL_LIST,
        "entity_labels": ENTITY_LABELS,
        "label2id": LABEL2ID,
        "id2label": {str(k): v for k, v in ID2LABEL.items()},
    }
    with open(os.path.join(best_dir, "label_info.json"), "w", encoding="utf-8") as f:
        json.dump(label_info, f, ensure_ascii=False, indent=2)

    # Save eval results
    eval_results = {
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

