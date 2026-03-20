"""
NER Aggregation Script.

Aggregates results.json files across all sample IDs for each (method, model) combo.
Sums raw counts (COR, INC, PAR, MIS, SPU, ACT, POS) per entity per scheme,
then recomputes Precision, Recall, F1 from those sums using nervaluate formulas.
Finally computes macro F1 over all entities (one per scheme).

Usage:
    python aggregate_ner.py <root_folder>

Output:
    <root_folder>/aggregated_results.json
"""

import os
import sys
import json
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Formula helpers (from nervaluate paper)
# ---------------------------------------------------------------------------

def compute_exact_metrics(cor, inc, par, mis, spu, act, pos):
    """Strict / Exact match: precision = COR/ACT, recall = COR/POS."""
    precision = cor / act if act > 0 else 0.0
    recall    = cor / pos if pos > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return precision, recall, f1


def compute_partial_metrics(cor, inc, par, mis, spu, act, pos):
    """Partial / Type match: precision = (COR + 0.5*PAR)/ACT, recall = (COR + 0.5*PAR)/POS."""
    precision = (cor + 0.5 * par) / act if act > 0 else 0.0
    recall    = (cor + 0.5 * par) / pos if pos > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return precision, recall, f1


SCHEME_COMPUTE = {
    "strict":   compute_exact_metrics,
    "exact":    compute_exact_metrics,
    "ent_type": compute_partial_metrics,
    "partial":  compute_partial_metrics,
}

COUNT_KEYS = ["correct", "incorrect", "partial", "missed", "spurious", "actual", "possible"]
SCHEMES    = ["strict", "exact", "ent_type", "partial"]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(root_folder):
    root = Path(root_folder)

    # Structure: agg[method][model][entity][scheme] = {count_key: int}
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )))

    found = 0
    for sample_dir in sorted(root.iterdir()):
        if not sample_dir.is_dir():
            continue
        inference_dir = sample_dir / "inference"
        if not inference_dir.exists():
            continue

        for method_dir in sorted(inference_dir.iterdir()):
            if not method_dir.is_dir():
                continue
            method = method_dir.name

            for model_dir in sorted(method_dir.iterdir()):
                if not model_dir.is_dir():
                    continue
                model = model_dir.name

                results_file = model_dir / "results.json"
                if not results_file.exists():
                    print(f"  [MISSING] {sample_dir.name}/{method}/{model}/results.json")
                    continue

                with open(results_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                found += 1
                for entity, schemes in data.items():
                    for scheme, counts in schemes.items():
                        for k in COUNT_KEYS:
                            agg[method][model][entity][scheme][k] += counts.get(k, 0)

    print(f"Loaded {found} results.json files.\n")

    # ---------------------------------------------------------------------------
    # Build output
    # ---------------------------------------------------------------------------
    output = {}

    for method, models in agg.items():
        output[method] = {}

        for model, entities in models.items():
            output[method][model] = {
                "entities": {},
                "macro_f1": {}
            }

            # Per-entity, per-scheme metrics
            entity_f1s = defaultdict(dict)  # entity_f1s[scheme][entity] = f1

            for entity, schemes in entities.items():
                output[method][model]["entities"][entity] = {}

                for scheme in SCHEMES:
                    if scheme not in schemes:
                        continue
                    c = schemes[scheme]
                    cor = c["correct"]
                    inc = c["incorrect"]
                    par = c["partial"]
                    mis = c["missed"]
                    spu = c["spurious"]
                    act = c["actual"]
                    pos = c["possible"]

                    compute_fn = SCHEME_COMPUTE[scheme]
                    precision, recall, f1 = compute_fn(cor, inc, par, mis, spu, act, pos)

                    output[method][model]["entities"][entity][scheme] = {
                        "correct":   cor,
                        "incorrect": inc,
                        "partial":   par,
                        "missed":    mis,
                        "spurious":  spu,
                        "actual":    act,
                        "possible":  pos,
                        "precision": round(precision, 6),
                        "recall":    round(recall, 6),
                        "f1":        round(f1, 6),
                    }

                    entity_f1s[scheme][entity] = f1

            # Macro F1 per scheme: average F1 over all entities
            for scheme in SCHEMES:
                if scheme not in entity_f1s or not entity_f1s[scheme]:
                    output[method][model]["macro_f1"][scheme] = None
                    continue
                f1_values = list(entity_f1s[scheme].values())
                macro = sum(f1_values) / len(f1_values)
                output[method][model]["macro_f1"][scheme] = round(macro, 6)

            # Micro average per scheme: sum counts across ALL entities, then recompute P/R/F1
            output[method][model]["micro_avg"] = {}
            for scheme in SCHEMES:
                cor = sum(entities[e][scheme]["correct"]   for e in entities if scheme in entities[e])
                inc = sum(entities[e][scheme]["incorrect"] for e in entities if scheme in entities[e])
                par = sum(entities[e][scheme]["partial"]   for e in entities if scheme in entities[e])
                mis = sum(entities[e][scheme]["missed"]    for e in entities if scheme in entities[e])
                spu = sum(entities[e][scheme]["spurious"]  for e in entities if scheme in entities[e])
                act = sum(entities[e][scheme]["actual"]    for e in entities if scheme in entities[e])
                pos = sum(entities[e][scheme]["possible"]  for e in entities if scheme in entities[e])

                compute_fn = SCHEME_COMPUTE[scheme]
                precision, recall, f1 = compute_fn(cor, inc, par, mis, spu, act, pos)

                output[method][model]["micro_avg"][scheme] = {
                    "correct":   cor,
                    "incorrect": inc,
                    "partial":   par,
                    "missed":    mis,
                    "spurious":  spu,
                    "actual":    act,
                    "possible":  pos,
                    "precision": round(precision, 6),
                    "recall":    round(recall, 6),
                    "f1":        round(f1, 6),
                }

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python aggregate_ner.py <root_folder>")
        sys.exit(1)

    root_folder = sys.argv[1]
    result = aggregate(root_folder)

    out_path = Path(root_folder) / "aggregated_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved aggregated results to: {out_path}")

    # Print a quick summary table
    print("\n--- Summary ---")
    for method, models in result.items():
        for model, data in models.items():
            print(f"\n[{method}] [{model}]")
            print(f"  {'Entity':<30} {'strict-F1':>10} {'exact-F1':>10} {'ent_type-F1':>12} {'partial-F1':>11}")
            print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*12} {'-'*11}")
            for entity, schemes in data["entities"].items():
                row = [
                    schemes.get("strict",   {}).get("f1", "-"),
                    schemes.get("exact",    {}).get("f1", "-"),
                    schemes.get("ent_type", {}).get("f1", "-"),
                    schemes.get("partial",  {}).get("f1", "-"),
                ]
                print(f"  {entity:<30} {str(row[0]):>10} {str(row[1]):>10} {str(row[2]):>12} {str(row[3]):>11}")
            mf1 = data["macro_f1"]
            print(f"  {'MACRO F1':<30} "
                  f"{str(mf1.get('strict','-')):>10} "
                  f"{str(mf1.get('exact','-')):>10} "
                  f"{str(mf1.get('ent_type','-')):>12} "
                  f"{str(mf1.get('partial','-')):>11}")
            mi = data["micro_avg"]
            print(f"  {'MICRO AVG F1':<30} "
                  f"{str(mi.get('strict',{}).get('f1','-')):>10} "
                  f"{str(mi.get('exact',{}).get('f1','-')):>10} "
                  f"{str(mi.get('ent_type',{}).get('f1','-')):>12} "
                  f"{str(mi.get('partial',{}).get('f1','-')):>11}")