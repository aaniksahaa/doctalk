import csv
import json
import sys
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import precision_recall_fscore_support

VALID_LABELS = [
    "SAFE",
    "HARMFUL"
]


def load_summary(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_columns = {"model_name", "method_name", "expected", "predicted"}
        missing = required_columns - set(reader.fieldnames or [])

        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        for row in reader:
            rows.append(
                {
                    "model_name": row["model_name"].strip(),
                    "method_name": row["method_name"].strip(),
                    "expected": row["expected"].strip(),
                    "predicted": row["predicted"].strip(),
                }
            )
    return rows


def build_results(rows):
    grouped = defaultdict(list)

    for row in rows:
        key = (row["model_name"], row["method_name"])
        grouped[key].append(row)

    results = []

    for (model_name, method_name), group_rows in sorted(grouped.items()):
        expected = [r["expected"] for r in group_rows]
        predicted = [r["predicted"] for r in group_rows]

        precision, recall, f1, support = precision_recall_fscore_support(
            expected,
            predicted,
            labels=VALID_LABELS,
            average=None,
            zero_division=0,
        )

        micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
            expected,
            predicted,
            labels=VALID_LABELS,
            average="micro",
            zero_division=0,
        )

        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            expected,
            predicted,
            labels=VALID_LABELS,
            average="macro",
            zero_division=0,
        )

        class_wise = []
        for label, p, r, f, s in zip(VALID_LABELS, precision, recall, f1, support):
            class_wise.append(
                {
                    "label": label,
                    "precision": round(float(p), 4),
                    "recall": round(float(r), 4),
                    "f1": round(float(f), 4),
                    "support": int(s),
                }
            )

        results.append(
            {
                "model_name": model_name,
                "method_name": method_name,
                "num_samples": len(group_rows),
                "class_wise": class_wise,
                "micro_avg": {
                    "precision": round(float(micro_p), 4),
                    "recall": round(float(micro_r), 4),
                    "f1": round(float(micro_f1), 4),
                },
                "macro_avg": {
                    "precision": round(float(macro_p), 4),
                    "recall": round(float(macro_r), 4),
                    "f1": round(float(macro_f1), 4),
                },
            }
        )

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_results.py <path_to_summary.csv>")
        sys.exit(1)

    input_csv = Path(sys.argv[1]).resolve()
    script_dir = Path(__file__).resolve().parent
    output_json = script_dir / "harmful_evaluation_results.json"

    rows = load_summary(input_csv)
    results = build_results(rows)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_json}")