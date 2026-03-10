"""
NER Evaluation Script using nervaluate.

Usage:
    python evaluate_ner.py <root_folder>

For each sample ID in the root folder, evaluates each model's output.txt
against ground_truth.txt and saves results.json in the model's folder.
"""

import os
import sys
import json
from pathlib import Path
from nervaluate import Evaluator

TAGS = ["SYMPTOM_SIGN", "DISEASE_CONDITION", "DRUG_MEDICATION", "TEST_INVESTIGATION", "TREATMENT_PROCEDURE", "ANATOMY_BODY_PART", "MEDICAL_SPECIALTY"]

def parse_ner_file(filepath):
    """Parse a NER txt file, skipping comment lines starting with #.
    Returns a list of (token, label) tuples."""
    tokens = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 2:
                token, label = parts
                tokens.append((token, label))
    return tokens


def get_labels(token_label_pairs):
    """Extract just the labels from token-label pairs."""
    return [label for _, label in token_label_pairs]


def get_entity_tags(labels):
    """Extract unique entity type names from BIO labels."""
    tags = set()
    for label in labels:
        if label != "O" and label.startswith(("B-", "I-")):
            tags.add(label[2:])
    return list(tags)


def evaluate(y_true_labels, y_pred_labels, tags):
    """Run nervaluate and return the entities portion of the results."""
    if not tags:
        return {}
    evaluator = Evaluator([y_true_labels], [y_pred_labels], tags)
    results = evaluator.evaluate()
    # Convert EvaluationResult namedtuples to dicts
    entities_raw = results.get("entities", {})
    entities_out = {}
    for entity, schemes in entities_raw.items():
        entities_out[entity] = {}
        for scheme_name, eval_result in schemes.items():
            entities_out[entity][scheme_name] = {
                "correct": eval_result.correct,
                "incorrect": eval_result.incorrect,
                "partial": eval_result.partial,
                "missed": eval_result.missed,
                "spurious": eval_result.spurious,
                "precision": eval_result.precision,
                "recall": eval_result.recall,
                "f1": eval_result.f1,
                "actual": eval_result.actual,
                "possible": eval_result.possible,
            }
    return entities_out


def process_folder(root_folder):
    root = Path(root_folder)
    if not root.exists():
        print(f"Error: folder '{root_folder}' does not exist.")
        sys.exit(1)

    processed = 0
    errors = 0

    for sample_dir in sorted(root.iterdir()):
        if not sample_dir.is_dir():
            continue

        ground_truth_file = sample_dir / "ground_truth.txt"
        if not ground_truth_file.exists():
            print(f"  [SKIP] No ground_truth.txt in {sample_dir.name}")
            continue

        gt_pairs = parse_ner_file(ground_truth_file)
        y_true = get_labels(gt_pairs)
        # tags = get_entity_tags(y_true)

        inference_dir = sample_dir / "inference"
        if not inference_dir.exists():
            print(f"  [SKIP] No inference/ folder in {sample_dir.name}")
            continue

        for method_dir in sorted(inference_dir.iterdir()):
            if not method_dir.is_dir():
                continue
            for model_dir in sorted(method_dir.iterdir()):
                if not model_dir.is_dir():
                    continue

                output_file = model_dir / "output.txt"
                if not output_file.exists():
                    print(f"  [SKIP] No output.txt in {model_dir}")
                    continue

                pred_pairs = parse_ner_file(output_file)
                y_pred = get_labels(pred_pairs)

                # Align lengths (pad with "O" if needed)
                if len(y_pred) < len(y_true):
                    y_pred += ["O"] * (len(y_true) - len(y_pred))
                elif len(y_pred) > len(y_true):
                    y_pred = y_pred[:len(y_true)]

                try:
                    entities_result = evaluate(y_true, y_pred, TAGS)
                    results_file = model_dir / "results.json"
                    with open(results_file, "w", encoding="utf-8") as f:
                        json.dump(entities_result, f, ensure_ascii=False, indent=2)
                    print(f"  [OK] {sample_dir.name}/{method_dir.name}/{model_dir.name} -> results.json")
                    processed += 1
                except Exception as e:
                    print(f"  [ERROR] {sample_dir.name}/{method_dir.name}/{model_dir.name}: {e}")
                    errors += 1

    print(f"\nDone. {processed} evaluated, {errors} errors.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python evaluate_ner.py <root_folder>")
        sys.exit(1)
    process_folder(sys.argv[1])