import os
import json
import csv
import sys

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_summary(dataset_path):
    summary_csv = os.path.join(dataset_path, "summary.csv")
    fieldnames = ["id", "method_name", "model_name", "expected", "predicted"]

    # Load already-processed (id, method, model) combos for restart capability
    processed = set()
    existing_rows = []
    if os.path.exists(summary_csv):
        with open(summary_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                processed.add((row["id"], row["method_name"], row["model_name"]))
        print(f"Resuming: {len(processed)} (id, method, model) combos already processed.")
    else:
        print("No existing summary.csv found. Starting fresh.")

    new_rows = []
    errors = []

    # Iterate over top-level folders (each is a case ID)
    entries = sorted(os.listdir(dataset_path))
    for entry in entries:
        entry_path = os.path.join(dataset_path, entry)
        if not os.path.isdir(entry_path):
            continue

        case_id = entry



        # Load ground truth
        gt_path = os.path.join(entry_path, "ground_truth.json")
        if not os.path.exists(gt_path):
            errors.append(f"Missing ground_truth.json for ID {case_id}")
            continue

        try:
            gt = load_json(gt_path)
            expected = gt.get("type", "")
        except Exception as e:
            errors.append(f"Error reading ground_truth.json for ID {case_id}: {e}")
            continue

        # Walk inference folder
        inference_path = os.path.join(entry_path, "inference")
        if not os.path.exists(inference_path):
            errors.append(f"Missing inference folder for ID {case_id}")
            continue

        # Each subdirectory is a method (few-shot, zero-shot, etc.)
        for method_name in sorted(os.listdir(inference_path)):
            method_path = os.path.join(inference_path, method_name)
            if not os.path.isdir(method_path):
                continue

            # Each subdirectory inside method is a model name
            for model_name in sorted(os.listdir(method_path)):
                model_path = os.path.join(method_path, model_name)
                if not os.path.isdir(model_path):
                    continue

                # Skip if this exact (id, method, model) combo already exists
                if (case_id, method_name, model_name) in processed:
                    print(f"  Skipping ID={case_id}, method={method_name}, model={model_name} (already exists)")
                    continue

                output_path = os.path.join(model_path, "output.json")
                if not os.path.exists(output_path):
                    errors.append(f"Missing output.json for ID {case_id}, method {method_name}, model {model_name}")
                    continue

                try:
                    output = load_json(output_path)
                    predicted = output.get("type", "")
                except Exception as e:
                    errors.append(f"Error reading output.json for ID {case_id}, method {method_name}, model {model_name}: {e}")
                    continue

                new_rows.append({
                    "id": case_id,
                    "method_name": method_name,
                    "model_name": model_name,
                    "expected": expected,
                    "predicted": predicted,
                })
                print(f"  ✓ ID={case_id}, method={method_name}, model={model_name}")

    # Write out all rows (existing + new)
    all_rows = existing_rows + new_rows
    with open(summary_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✅ Done. {len(new_rows)} new rows added. Total rows: {len(all_rows)}.")
    print(f"Saved to: {summary_csv}")

    if errors:
        print(f"\n⚠️  {len(errors)} errors encountered:")
        for e in errors:
            print(f"  - {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_summary.py <dataset_path>")
        sys.exit(1)
    generate_summary(sys.argv[1])