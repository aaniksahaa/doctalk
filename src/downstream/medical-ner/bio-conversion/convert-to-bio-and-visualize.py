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
import re
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
) -> List[Entity]:
    """
    Resolve entity texts to character spans in left-to-right order.
    """
    text = normalize_text(sample["text"])
    raw_entities = sample.get("entities", [])

    resolved: List[Entity] = []
    used_spans: List[Tuple[int, int]] = []
    cursor = 0

    for idx, ent in enumerate(raw_entities):
        ent_text = normalize_text(ent["text"])
        label = ent["label"]

        if strict_label_check and label not in ALLOWED_LABELS:
            raise ValueError(f"Invalid label at entity #{idx}: {label}")

        span = find_non_overlapping_span(
            text=text,
            needle=ent_text,
            search_from=cursor,
            used_spans=used_spans,
            fallback_global=fallback_global,
        )
        if span is None:
            raise ValueError(
                f"Could not resolve entity text '{ent_text}' in sample text.\n"
                f"Sample text: {text}"
            )

        start, end = span
        # Exact substring validation
        if text[start:end] != ent_text:
            raise ValueError(
                f"Resolved substring mismatch for entity '{ent_text}'. "
                f"Found '{text[start:end]}' at [{start}:{end}]"
            )

        resolved.append(Entity(text=ent_text, label=label, start=start, end=end))
        used_spans.append((start, end))
        cursor = end

    # Final left-to-right check
    for i in range(1, len(resolved)):
        if resolved[i].start < resolved[i - 1].start:
            raise ValueError("Resolved entities are not in non-decreasing left-to-right order.")

    return resolved


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
    """
    text = normalize_text(sample["text"])
    resolved_entities = resolve_entities_to_spans(sample)
    token_tuples = get_tokens(text, mode=mode, hf_model_name=hf_model_name)
    bio_tokens = spans_to_bio(text, resolved_entities, token_tuples)

    return {
        "text": text,
        "tokenization": mode if mode != "hf" else f"hf:{hf_model_name}",
        "resolved_entities": [asdict(e) for e in resolved_entities],
        "tokens": [asdict(t) for t in bio_tokens],
    }


def convert_dataset_to_bio(
    dataset: List[Dict[str, Any]],
    mode: str = "whitespace",
    hf_model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convert a whole dataset.
    """
    outputs = []
    for i, sample in enumerate(dataset):
        try:
            converted = convert_sample_to_bio(sample, mode=mode, hf_model_name=hf_model_name)
            converted["sample_index"] = i
            outputs.append(converted)
        except Exception as e:
            outputs.append({
                "sample_index": i,
                "text": sample.get("text", ""),
                "error": str(e),
            })
    return outputs


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
# I/O helpers
# -----------------------------

def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(obj: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# -----------------------------
# Demo / CLI
# -----------------------------

def main():
    """
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

    dataset = load_json_file(input_path)

    converted = convert_dataset_to_bio(
        dataset=dataset,
        mode=mode,
        hf_model_name=hf_model_name,
    )

    out_json = f"bio_{mode}.json"
    save_json_file(converted, out_json)
    print(f"Saved converted BIO JSON to: {out_json}")

    # Visualize first successful sample
    first_ok = next((x for x in converted if "error" not in x), None)
    if first_ok:
        visualize_bio_console(first_ok)
        print("\nHIGHLIGHTED TEXT:")
        print(visualize_entities_in_text(first_ok))
        print("\nCONLL-LIKE:")
        print(export_conll_like(first_ok))

    # Also export all successful samples to a single CoNLL-like file
    conll_path = f"bio_{mode}.conll.txt"
    with open(conll_path, "w", encoding="utf-8") as f:
        for sample in converted:
            if "error" in sample:
                continue
            f.write(f"# sample_index = {sample['sample_index']}\n")
            f.write(f"# text = {sample['text']}\n")
            f.write(export_conll_like(sample))
            f.write("\n\n")
    print(f"Saved CoNLL-like BIO to: {conll_path}")


if __name__ == "__main__":
    main()