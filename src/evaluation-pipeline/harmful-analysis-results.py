import csv
import json
from pathlib import Path


def generate_results_csv(dataset_root: str = "."):
    dataset_root = Path(dataset_root)
    files_generated = []

    for case_dir in sorted(dataset_root.iterdir()):
        if not case_dir.is_dir():
            continue

        case_id = case_dir.name

        # Load ground truth
        ground_truth_path = case_dir / "ground_truth.json"
        if not ground_truth_path.exists():
            print(f"[SKIP] No ground_truth.json in case {case_id}")
            continue

        with open(ground_truth_path, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)

        gt_recommendations = ground_truth.get("recommendations", [])

        inference_dir = case_dir / "inference"
        if not inference_dir.exists():
            print(f"[SKIP] No inference folder in case {case_id}")
            continue

        for method_dir in sorted(inference_dir.iterdir()):
            if not method_dir.is_dir():
                continue
            method_name = method_dir.name

            for model_dir in sorted(method_dir.iterdir()):
                if not model_dir.is_dir():
                    continue
                model_name = model_dir.name

                output_path = model_dir / "output.json"
                if not output_path.exists():
                    print(f"[SKIP] No output.json for case {case_id} / {method_name} / {model_name}")
                    continue

                with open(output_path, "r", encoding="utf-8") as f:
                    output = json.load(f)

                pred_recommendations = output.get("recommendations", [])

                # Load existing rows for this model's CSV (accumulate across cases)
                csv_path = model_dir / "results.csv"
                existing_rows = []
                if csv_path.exists():
                    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                        reader = csv.DictReader(f)
                        existing_rows = [r for r in reader if r.get("case_id") != str(case_id)]

                # Build new rows for this case
                new_rows = []
                max_len = max(len(gt_recommendations), len(pred_recommendations))

                for i in range(max_len):
                    gt_rec = gt_recommendations[i] if i < len(gt_recommendations) else {}
                    pred_rec = pred_recommendations[i] if i < len(pred_recommendations) else {}

                    new_rows.append({
                        "case_id": case_id,
                        "index": i,
                        "content": gt_rec.get("content", ""),
                        "expected": gt_rec.get("label", ""),
                        "predicted": pred_rec.get("label", ""),
                    })

                all_rows = existing_rows + new_rows
                # Sort by case_id then index
                all_rows.sort(key=lambda r: (r["case_id"], int(r["index"])))

                fieldnames = ["case_id", "index", "content", "expected", "predicted"]
                with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_rows)

                files_generated.append(str(csv_path))
                print(f"[OK] case={case_id} method={method_name} model={model_name} -> {csv_path}")

    print(f"\nDone. {len(files_generated)} results.csv file(s) updated.")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_results_csv(root)