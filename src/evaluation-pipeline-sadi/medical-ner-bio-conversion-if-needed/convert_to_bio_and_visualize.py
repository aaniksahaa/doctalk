#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convert span-text medical NER annotations to BIO format under multiple tokenizations.

Supported tokenization modes:
  1) whitespace  -> split on non-space runs
  2) wordpunct   -> split into words and punctuation via regex
  3) hf          -> Hugging Face fast tokenizer with offset mapping

Input format:
[
  {
    "text": "...",
    "entities": [
      {"text": "মাথাব্যথা", "label": "SYMPTOM_SIGN"},
      {"text": "সিটি স্ক্যান", "label": "TEST_INVESTIGATION"}
    ]
  },
  ...
]

Output:
- resolved character spans
- BIO-tagged tokens
- visualization utilities

Notes:
- This script assumes entities are already listed in left-to-right order in each sample.
- It resolves spans by searching sequentially from a moving cursor.
- If an entity is not found after the cursor, it can optionally fall back to global search.
- For transformer alignment, use a FAST tokenizer (AutoTokenizer(..., use_fast=True)).
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


# -----------------------------
# Data classes
# -----------------------------

@dataclass
class Entity:
    text: str
    label: str
    start: int
    end: int  # exclusive

@dataclass
class TokenBIO:
    token: str
    start: int
    end: int  # exclusive
    tag: str


# -----------------------------
# Configuration
# -----------------------------

ALLOWED_LABELS = {
    "SYMPTOM_SIGN",
    "DISEASE_CONDITION",
    "DRUG_MEDICATION",
    "TEST_INVESTIGATION",
    "TREATMENT_PROCEDURE",
    "ANATOMY_BODY_PART",
}

ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

LABEL_COLOR = {
    "SYMPTOM_SIGN": "red",
    "DISEASE_CONDITION": "magenta",
    "DRUG_MEDICATION": "green",
    "TEST_INVESTIGATION": "blue",
    "TREATMENT_PROCEDURE": "yellow",
    "ANATOMY_BODY_PART": "cyan",
}


# -----------------------------
# Text normalization
# -----------------------------

def normalize_text(text: str) -> str:
    """
    Minimal normalization only.
    Use NFC to keep Bengali text stable while reducing Unicode variation.
    """
    return unicodedata.normalize("NFC", text)


# -----------------------------
# Span resolution
# -----------------------------

def find_non_overlapping_span(
    text: str,
    needle: str,
    search_from: int,
    used_spans: List[Tuple[int, int]],
    fallback_global: bool = True,
) -> Optional[Tuple[int, int]]:
    """
    Find a non-overlapping occurrence of `needle` in `text`, preferably at/after search_from.
    Returns (start, end) or None.
    """
    if not needle:
        return None

    def overlaps(a_start: int, a_end: int, spans: List[Tuple[int, int]]) -> bool:
        for b_start, b_end in spans:
            if not (a_end <= b_start or a_start >= b_end):
                return True
        return False

    # Primary search: left-to-right from cursor
    pos = text.find(needle, search_from)
    while pos != -1:
        end = pos + len(needle)
        if not overlaps(pos, end, used_spans):
            return pos, end
        pos = text.find(needle, pos + 1)

    if not fallback_global:
        return None

    # Fallback: global search from the start, first non-overlapping match
    pos = text.find(needle, 0)
    while pos != -1:
        end = pos + len(needle)
        if not overlaps(pos, end, used_spans):
            return pos, end
        pos = text.find(needle, pos + 1)

    return None


def resolve_entities_to_spans(
    sample: Dict[str, Any],
    fallback_global: bool = True,
    strict_label_check: bool = True,
) -> Tuple[List[Entity], List[Dict[str, Any]]]:
    """
    Resolve entity texts to character spans in left-to-right order.
    Entities that cannot be resolved (e.g. due to overlap) are skipped
    with a warning rather than causing the entire sample to fail.

    Returns:
        (resolved_entities, skipped_entities)
    """
    text = normalize_text(sample["text"])
    raw_entities = sample.get("entities", [])

    resolved: List[Entity] = []
    skipped: List[Dict[str, Any]] = []
    used_spans: List[Tuple[int, int]] = []
    cursor = 0

    for idx, ent in enumerate(raw_entities):
        # Guard against malformed entity dicts
        if not isinstance(ent, dict):
            skipped.append({
                "index": idx, "text": str(ent), "label": "?",
                "reason": f"Entity is not a dict (got {type(ent).__name__})",
            })
            continue
        if "text" not in ent or "label" not in ent:
            missing = [k for k in ("text", "label") if k not in ent]
            skipped.append({
                "index": idx, "text": ent.get("text", "?"), "label": ent.get("label", "?"),
                "reason": f"Missing required key(s): {', '.join(missing)}",
            })
            continue

        ent_text = normalize_text(ent["text"])
        label = ent["label"]

        if strict_label_check and label not in ALLOWED_LABELS:
            skipped.append({
                "index": idx, "text": ent_text, "label": label,
                "reason": f"Invalid label: {label}",
            })
            continue

        span = find_non_overlapping_span(
            text=text,
            needle=ent_text,
            search_from=cursor,
            used_spans=used_spans,
            fallback_global=fallback_global,
        )
        if span is None:
            skipped.append({
                "index": idx, "text": ent_text, "label": label,
                "reason": "No non-overlapping span found in text",
            })
            # Do NOT advance cursor — let subsequent entities try from the same position
            continue

        start, end = span
        # Exact substring validation
        if text[start:end] != ent_text:
            skipped.append({
                "index": idx, "text": ent_text, "label": label,
                "reason": f"Substring mismatch: found '{text[start:end]}' at [{start}:{end}]",
            })
            continue

        resolved.append(Entity(text=ent_text, label=label, start=start, end=end))
        used_spans.append((start, end))
        cursor = end

    # Sort resolved entities by start position (safe since skipping may cause out-of-order)
    resolved.sort(key=lambda e: (e.start, e.end))

    return resolved, skipped


# -----------------------------
# Tokenization
# -----------------------------

def tokenize_whitespace(text: str) -> List[Tuple[str, int, int]]:
    """
    Non-space runs as tokens.
    Good for readable word-level BIO.
    """
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\S+", text, flags=re.UNICODE)]


def tokenize_wordpunct(text: str) -> List[Tuple[str, int, int]]:
    """
    Regex tokenization into word-like chunks and punctuation.
    Python 3's \\w is Unicode-aware, so Bengali letters are included.
    """
    pattern = r"\w+|[^\w\s]"
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(pattern, text, flags=re.UNICODE)]


def tokenize_char(text: str) -> List[Tuple[str, int, int]]:
    """
    Character-level tokenization.
    Useful for debugging alignment, not usually for training.
    """
    return [(ch, i, i + 1) for i, ch in enumerate(text)]


def tokenize_hf_fast(text: str, model_name: str) -> List[Tuple[str, int, int]]:
    """
    Hugging Face fast tokenizer tokenization with offset mapping.
    Requires a fast tokenizer.
    """
    try:
        from transformers import AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "transformers is required for hf tokenization. Install with:\n"
            "pip install transformers sentencepiece"
        ) from e

    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError(
            f"Tokenizer for '{model_name}' is not fast. "
            "Use a fast tokenizer so offset_mapping is available."
        )

    enc = tokenizer(
        text,
        return_offsets_mapping=True,
        add_special_tokens=False,
        truncation=False,
    )

    input_ids = enc["input_ids"]
    offsets = enc["offset_mapping"]
    tokens = tokenizer.convert_ids_to_tokens(input_ids)

    result: List[Tuple[str, int, int]] = []
    for tok, (start, end) in zip(tokens, offsets):
        # Skip zero-length offsets if any appear
        if end <= start:
            continue
        result.append((tok, start, end))
    return result


def get_tokens(text: str, mode: str, hf_model_name: Optional[str] = None) -> List[Tuple[str, int, int]]:
    mode = mode.lower()
    if mode == "whitespace":
        return tokenize_whitespace(text)
    if mode == "wordpunct":
        return tokenize_wordpunct(text)
    if mode == "char":
        return tokenize_char(text)
    if mode == "hf":
        if not hf_model_name:
            raise ValueError("hf_model_name is required when mode='hf'")
        return tokenize_hf_fast(text, hf_model_name)
    raise ValueError(f"Unknown tokenization mode: {mode}")


# -----------------------------
# BIO projection
# -----------------------------

def token_overlaps_entity(tok_start: int, tok_end: int, ent_start: int, ent_end: int) -> bool:
    """
    True if token char span overlaps entity char span.
    This is the safest rule for subword tokenizers with offset mappings.
    """
    return not (tok_end <= ent_start or tok_start >= ent_end)


def spans_to_bio(
    text: str,
    entities: List[Entity],
    token_tuples: List[Tuple[str, int, int]],
) -> List[TokenBIO]:
    """
    Project character spans onto tokenization as BIO tags.
    First overlapping token of an entity -> B-LABEL
    Remaining overlapping tokens -> I-LABEL
    """
    bio: List[TokenBIO] = []
    entity_idx = 0

    # Sort defensively
    entities = sorted(entities, key=lambda e: (e.start, e.end))

    for token, tok_start, tok_end in token_tuples:
        tag = "O"

        # Advance past entities that end before this token starts
        while entity_idx < len(entities) and entities[entity_idx].end <= tok_start:
            entity_idx += 1

        # Check current entity and maybe following ones
        matched_entity_index = None
        for j in range(entity_idx, len(entities)):
            ent = entities[j]
            if ent.start >= tok_end:
                break
            if token_overlaps_entity(tok_start, tok_end, ent.start, ent.end):
                matched_entity_index = j
                break

        if matched_entity_index is not None:
            ent = entities[matched_entity_index]

            # Determine whether this token is the first overlapping token for the entity
            is_first = True
            for prev_token, prev_start, prev_end in token_tuples:
                if prev_end <= tok_start and token_overlaps_entity(prev_start, prev_end, ent.start, ent.end):
                    is_first = False

            prefix = "B" if is_first else "I"
            tag = f"{prefix}-{ent.label}"

        bio.append(TokenBIO(token=token, start=tok_start, end=tok_end, tag=tag))

    return bio


# -----------------------------
# Sample conversion
# -----------------------------

def convert_sample_to_bio(
    sample: Dict[str, Any],
    mode: str = "whitespace",
    hf_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert one annotated sample to BIO.
    Never raises — returns a result dict, possibly with warnings.
    """
    warnings: List[str] = []

    # ── Validate sample structure ──
    if not isinstance(sample, dict):
        return {
            "text": "",
            "tokenization": mode if mode != "hf" else f"hf:{hf_model_name}",
            "resolved_entities": [],
            "tokens": [],
            "warnings": [f"Sample is not a dict (got {type(sample).__name__})"],
        }

    if "text" not in sample:
        return {
            "text": "",
            "tokenization": mode if mode != "hf" else f"hf:{hf_model_name}",
            "resolved_entities": [],
            "tokens": [],
            "warnings": ["Sample has no 'text' key — cannot process"],
        }

    text = normalize_text(sample["text"])

    if not text or not text.strip():
        warnings.append("Sample text is empty or whitespace-only")

    raw_entities = sample.get("entities", None)
    if raw_entities is None:
        warnings.append("No 'entities' key found — treating as zero entities")
        sample = {**sample, "entities": []}
    elif not isinstance(raw_entities, list):
        warnings.append(
            f"'entities' is not a list (got {type(raw_entities).__name__}) — treating as zero entities"
        )
        sample = {**sample, "entities": []}
    elif len(raw_entities) == 0:
        warnings.append("'entities' list is empty — all tokens will be tagged O")

    resolved_entities, skipped_entities = resolve_entities_to_spans(sample)
    token_tuples = get_tokens(text, mode=mode, hf_model_name=hf_model_name)
    bio_tokens = spans_to_bio(text, resolved_entities, token_tuples)

    result = {
        "text": text,
        "tokenization": mode if mode != "hf" else f"hf:{hf_model_name}",
        "resolved_entities": [asdict(e) for e in resolved_entities],
        "tokens": [asdict(t) for t in bio_tokens],
    }
    if skipped_entities:
        result["skipped_entities"] = skipped_entities
    if warnings:
        result["warnings"] = warnings
    return result


def convert_dataset_to_bio(
    dataset: List[Dict[str, Any]],
    mode: str = "whitespace",
    hf_model_name: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    """
    Convert a whole dataset.  Best-effort: never raises, always returns results.

    Returns:
        (outputs, total_skipped, total_warnings, total_errors)
    """
    outputs: List[Dict[str, Any]] = []
    total_skipped = 0
    total_warnings = 0
    total_errors = 0

    for i, sample in enumerate(dataset):
        try:
            converted = convert_sample_to_bio(sample, mode=mode, hf_model_name=hf_model_name)
            converted["sample_index"] = i

            has_issue = False

            # Report per-sample warnings
            if converted.get("warnings"):
                n_warn = len(converted["warnings"])
                total_warnings += n_warn
                has_issue = True
                print(colorize(f"  ⚠ Sample #{i}: {n_warn} warning(s):", "yellow", bold=True))
                for w in converted["warnings"]:
                    print(colorize(f"      → {w}", "yellow"))

            # Report skipped entities
            if converted.get("skipped_entities"):
                n_skip = len(converted["skipped_entities"])
                total_skipped += n_skip
                has_issue = True
                print(colorize(f"  ⚠ Sample #{i}: skipped {n_skip} entity(ies) due to overlap/issues:", "yellow", bold=True))
                for sk in converted["skipped_entities"]:
                    print(colorize(f"      entity #{sk['index']} \"{sk['text']}\" [{sk['label']}]: {sk['reason']}", "yellow"))

            if not has_issue:
                n_ents = len(converted.get("resolved_entities", []))
                n_toks = len(converted.get("tokens", []))
                print(colorize(f"  ✓ Sample #{i}: OK — {n_ents} entities, {n_toks} tokens", "green"))

            outputs.append(converted)

        except Exception as e:
            total_errors += 1
            print(colorize(f"  ✗ Sample #{i}: FAILED — {e}", "red", bold=True))
            # Include traceback detail for debugging
            tb = traceback.format_exc()
            print(colorize(f"      Traceback (last 3 lines):", "red"))
            for line in tb.strip().splitlines()[-3:]:
                print(colorize(f"      {line}", "red"))
            outputs.append({
                "sample_index": i,
                "text": sample.get("text", "") if isinstance(sample, dict) else "",
                "error": str(e),
            })

    return outputs, total_skipped, total_warnings, total_errors


# -----------------------------
# Visualization
# -----------------------------

def colorize(text: str, color_name: str, bold: bool = False) -> str:
    parts = []
    if bold:
        parts.append(ANSI["bold"])
    parts.append(ANSI.get(color_name, ""))
    parts.append(text)
    parts.append(ANSI["reset"])
    return "".join(parts)


def visualize_bio_console(converted_sample: Dict[str, Any]) -> None:
    """
    Pretty-print token/BIO rows in terminal.
    """
    print("=" * 80)
    print("TEXT:")
    print(converted_sample["text"])
    print("-" * 80)
    print(f"TOKENIZATION: {converted_sample['tokenization']}")
    print("-" * 80)

    for t in converted_sample["tokens"]:
        tag = t["tag"]
        if tag == "O":
            print(f"{t['token']:<25} {tag}")
        else:
            label = tag.split("-", 1)[1]
            color = LABEL_COLOR.get(label, "white")
            print(f"{colorize(t['token'], color, bold=True):<25} {colorize(tag, color)}")
    print("=" * 80)


def visualize_entities_in_text(converted_sample: Dict[str, Any]) -> str:
    """
    Return text with resolved entities highlighted by label color.
    """
    text = converted_sample["text"]
    entities = sorted(converted_sample["resolved_entities"], key=lambda x: x["start"])

    out = []
    cursor = 0
    for ent in entities:
        start, end = ent["start"], ent["end"]
        label = ent["label"]
        color = LABEL_COLOR.get(label, "white")

        if cursor < start:
            out.append(text[cursor:start])

        span_text = text[start:end]
        out.append(colorize(f"[{span_text}|{label}]", color, bold=True))
        cursor = end

    if cursor < len(text):
        out.append(text[cursor:])

    return "".join(out)


def export_conll_like(converted_sample: Dict[str, Any]) -> str:
    """
    Export BIO tokens in a CoNLL-like format: token<TAB>tag
    """
    lines = []
    for t in converted_sample["tokens"]:
        lines.append(f"{t['token']}\t{t['tag']}")
    return "\n".join(lines)


# -----------------------------
# I/O helpers (safe, never raise)
# -----------------------------

def safe_load_json_file(path: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load JSON from file.  Returns (data, None) on success or (None, error_msg) on failure.
    """
    if not os.path.exists(path):
        return None, f"File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return None, f"Cannot read file '{path}': {e}"

    if not content.strip():
        return None, f"File is empty: {path}"

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in '{path}': {e}"

    return data, None


def safe_save_json_file(obj: Any, path: str) -> Optional[str]:
    """
    Save JSON to file.  Returns None on success or error message string on failure.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return None
    except Exception as e:
        return f"Cannot write '{path}': {e}"


def safe_write_text_file(path: str, content: str) -> Optional[str]:
    """
    Write text to file.  Returns None on success or error message string on failure.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return None
    except Exception as e:
        return f"Cannot write '{path}': {e}"


# -----------------------------
# Demo / CLI
# -----------------------------

def format_bio_plain(converted_sample: Dict[str, Any]) -> str:
    """
    Format token/BIO rows as plain text (no ANSI colors).
    """
    lines = []
    lines.append("=" * 80)
    lines.append("TEXT:")
    lines.append(converted_sample["text"])
    lines.append("-" * 80)
    lines.append(f"TOKENIZATION: {converted_sample['tokenization']}")
    lines.append("-" * 80)

    for t in converted_sample["tokens"]:
        tag = t["tag"]
        lines.append(f"{t['token']:<25} {tag}")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_entities_in_text_plain(converted_sample: Dict[str, Any]) -> str:
    """
    Return text with resolved entities annotated (no ANSI colors).
    """
    text = converted_sample["text"]
    entities = sorted(converted_sample["resolved_entities"], key=lambda x: x["start"])

    out = []
    cursor = 0
    for ent in entities:
        start, end = ent["start"], ent["end"]
        label = ent["label"]

        if cursor < start:
            out.append(text[cursor:start])

        span_text = text[start:end]
        out.append(f"[{span_text}|{label}]")
        cursor = end

    if cursor < len(text):
        out.append(text[cursor:])

    return "".join(out)


def main():
    """
    Best-effort BIO conversion pipeline.
    This function NEVER crashes — every failure is caught, reported with
    colorful output, and the script keeps going to produce whatever it can.

    Edit these paths/settings as needed.
    """
    input_path = "input.json"

    # Choose one of:
    # mode = "whitespace"
    # mode = "wordpunct"
    # mode = "char"
    mode = "whitespace"

    # For HF mode, set mode="hf" and choose a fast tokenizer model.
    # Examples:
    # hf_model_name = "xlm-roberta-base"
    # hf_model_name = "google/muril-base-cased"
    hf_model_name = None

    # ════════════════════════════════════════════════════════════
    #  STAGE 1 — Load input file
    # ════════════════════════════════════════════════════════════
    print(colorize(f"\n{'═' * 60}", "cyan", bold=True))
    print(colorize(f"  STAGE 1: Loading input", "cyan", bold=True))
    print(colorize(f"{'═' * 60}", "cyan", bold=True))

    dataset, load_err = safe_load_json_file(input_path)
    if load_err is not None:
        print(colorize(f"\n  ✗ FATAL — {load_err}", "red", bold=True))
        print(colorize(f"    Cannot proceed without a valid input file.", "red"))
        print(colorize(f"    Please ensure '{input_path}' exists and contains a valid JSON array.\n", "red"))
        sys.exit(1)

    print(colorize(f"  ✓ Loaded '{input_path}' successfully", "green"))

    # ── Validate dataset structure ──
    if not isinstance(dataset, list):
        print(colorize(
            f"\n  ✗ FATAL — Expected a JSON array (list) at top level, got {type(dataset).__name__}.",
            "red", bold=True,
        ))
        print(colorize(f"    The file should contain a list of sample objects: [ {{\"text\": ..., \"entities\": [...]}}, ... ]", "red"))
        sys.exit(1)

    if len(dataset) == 0:
        print(colorize(f"\n  ⚠ WARNING — Input file contains an empty list (0 samples).", "yellow", bold=True))
        print(colorize(f"    Nothing to convert. Output files will be empty.", "yellow"))

    print(colorize(f"  ✓ Dataset has {len(dataset)} sample(s)", "green"))

    # ════════════════════════════════════════════════════════════
    #  STAGE 2 — Convert to BIO
    # ════════════════════════════════════════════════════════════
    print(colorize(f"\n{'═' * 60}", "cyan", bold=True))
    print(colorize(f"  STAGE 2: Converting {len(dataset)} sample(s)  ·  mode = {mode}", "cyan", bold=True))
    print(colorize(f"{'═' * 60}", "cyan", bold=True))

    converted, total_skipped, total_warnings, total_errors = convert_dataset_to_bio(
        dataset=dataset,
        mode=mode,
        hf_model_name=hf_model_name,
    )

    n_ok = sum(1 for s in converted if "error" not in s)

    if n_ok == 0 and len(dataset) > 0:
        print(colorize(f"\n  ✗ WARNING — ALL {len(dataset)} sample(s) failed! Output will contain only error entries.", "red", bold=True))
    elif total_errors > 0:
        print(colorize(f"\n  ⚠ {total_errors} sample(s) failed, {n_ok} succeeded — continuing with partial results.", "yellow", bold=True))

    # ════════════════════════════════════════════════════════════
    #  STAGE 3 — Save output files
    # ════════════════════════════════════════════════════════════
    print(colorize(f"\n{'═' * 60}", "cyan", bold=True))
    print(colorize(f"  STAGE 3: Saving output files", "cyan", bold=True))
    print(colorize(f"{'═' * 60}", "cyan", bold=True))

    files_saved = 0

    # ── 3a. BIO JSON ──
    out_json = f"bio_{mode}.json"
    err = safe_save_json_file(converted, out_json)
    if err:
        print(colorize(f"  ✗ Failed to save BIO JSON: {err}", "red", bold=True))
    else:
        files_saved += 1
        print(colorize(f"  ✓ Saved BIO JSON → {out_json}", "green"))

    # ── 3b. CoNLL-like file ──
    conll_path = f"bio_{mode}.conll.txt"
    try:
        conll_lines = []
        for sample in converted:
            if "error" in sample:
                continue
            conll_lines.append(f"# sample_index = {sample['sample_index']}")
            conll_lines.append(f"# text = {sample['text']}")
            conll_lines.append(export_conll_like(sample))
            conll_lines.append("")
        conll_content = "\n".join(conll_lines)
        err = safe_write_text_file(conll_path, conll_content)
        if err:
            print(colorize(f"  ✗ Failed to save CoNLL file: {err}", "red", bold=True))
        else:
            files_saved += 1
            if not conll_content.strip():
                print(colorize(f"  ⚠ Saved CoNLL file → {conll_path} (empty — no successful samples)", "yellow", bold=True))
            else:
                print(colorize(f"  ✓ Saved CoNLL file → {conll_path}", "green"))
    except Exception as e:
        print(colorize(f"  ✗ Failed to build CoNLL content: {e}", "red", bold=True))

    # ── 3c. Full visualization (plain text) ──
    output_txt_path = f"output_{mode}.txt"
    try:
        viz_parts = []
        for sample in converted:
            if "error" in sample:
                viz_parts.append(f"{'=' * 80}")
                viz_parts.append(f"SAMPLE #{sample['sample_index']} — ERROR")
                viz_parts.append(f"{sample['error']}")
                viz_parts.append(f"{'=' * 80}\n")
                continue

            # Warnings
            if sample.get("warnings"):
                viz_parts.append(f"⚠ WARNINGS FOR SAMPLE #{sample.get('sample_index', '?')}:")
                for w in sample["warnings"]:
                    viz_parts.append(f"  → {w}")
                viz_parts.append("")

            # Skipped entity warnings
            if sample.get("skipped_entities"):
                viz_parts.append(f"⚠ SKIPPED {len(sample['skipped_entities'])} ENTITY(IES):")
                for sk in sample["skipped_entities"]:
                    viz_parts.append(f"  entity #{sk['index']} \"{sk['text']}\" [{sk['label']}]: {sk['reason']}")
                viz_parts.append("")

            # BIO table
            viz_parts.append(format_bio_plain(sample))
            viz_parts.append("")

            # Highlighted text (plain)
            viz_parts.append("HIGHLIGHTED TEXT:")
            viz_parts.append(format_entities_in_text_plain(sample))
            viz_parts.append("")

            # CoNLL-like
            viz_parts.append("CONLL-LIKE:")
            viz_parts.append(export_conll_like(sample))
            viz_parts.append("")

        viz_content = "\n".join(viz_parts)
        err = safe_write_text_file(output_txt_path, viz_content)
        if err:
            print(colorize(f"  ✗ Failed to save visualization: {err}", "red", bold=True))
        else:
            files_saved += 1
            if not viz_content.strip():
                print(colorize(f"  ⚠ Saved visualization → {output_txt_path} (empty — nothing to visualize)", "yellow", bold=True))
            else:
                print(colorize(f"  ✓ Saved visualization → {output_txt_path}", "green"))
    except Exception as e:
        print(colorize(f"  ✗ Failed to build visualization content: {e}", "red", bold=True))

    # ════════════════════════════════════════════════════════════
    #  STAGE 4 — Preview first successful sample
    # ════════════════════════════════════════════════════════════
    first_ok = next((x for x in converted if "error" not in x), None)
    if first_ok:
        print(colorize(f"\n{'═' * 60}", "cyan", bold=True))
        print(colorize(f"  PREVIEW: Sample #{first_ok.get('sample_index', 0)}", "cyan", bold=True))
        print(colorize(f"{'═' * 60}", "cyan", bold=True))
        try:
            visualize_bio_console(first_ok)
            print("\nHIGHLIGHTED TEXT:")
            print(visualize_entities_in_text(first_ok))
            print("\nCONLL-LIKE:")
            print(export_conll_like(first_ok))
        except Exception as e:
            print(colorize(f"  ⚠ Preview rendering failed: {e}", "yellow", bold=True))
    else:
        if len(dataset) > 0:
            print(colorize(f"\n  ⚠ No successful samples to preview.", "yellow", bold=True))

    # ════════════════════════════════════════════════════════════
    #  SUMMARY
    # ════════════════════════════════════════════════════════════
    print(colorize(f"\n{'═' * 60}", "cyan", bold=True))
    print(colorize(f"  SUMMARY", "cyan", bold=True))
    print(colorize(f"{'═' * 60}", "cyan", bold=True))
    print(f"  Input file:     {input_path}")
    print(f"  Mode:           {mode}")
    print(f"  Total samples:  {len(converted)}")
    print(colorize(f"  ✓ Successful:   {n_ok}", "green", bold=True))

    if total_warnings > 0:
        print(colorize(f"  ⚠ Warnings:     {total_warnings} (structural issues in samples — processed best-effort)", "yellow", bold=True))
    else:
        print(f"  ⚠ Warnings:     0")

    if total_skipped > 0:
        print(colorize(f"  ⚠ Skipped ents: {total_skipped} (overlap / unresolvable — tagged remaining)", "yellow", bold=True))
    else:
        print(f"  ⚠ Skipped ents: 0")

    if total_errors > 0:
        print(colorize(f"  ✗ Errors:       {total_errors} (samples fully failed)", "red", bold=True))
    else:
        print(f"  ✗ Errors:       0")

    print(f"  Files saved:    {files_saved}/3")

    # Final verdict
    if total_errors == 0 and total_skipped == 0 and total_warnings == 0:
        print(colorize(f"\n  ★ Perfect run — all samples converted cleanly!", "green", bold=True))
    elif n_ok > 0:
        print(colorize(f"\n  ◐ Partial success — {n_ok}/{len(dataset)} samples converted (check warnings above).", "yellow", bold=True))
    elif len(dataset) > 0:
        print(colorize(f"\n  ✗ Complete failure — no samples could be converted. Check errors above.", "red", bold=True))

    print(colorize(f"{'═' * 60}\n", "cyan", bold=True))


if __name__ == "__main__":
    main()