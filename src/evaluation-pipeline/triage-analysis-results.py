import json
import os
from pathlib import Path


def generate_results(dataset_root: str = "."):
    dataset_root = Path(dataset_root)
    results_generated = []

    for case_dir in sorted(dataset_root.iterdir()):
        if not case_dir.is_dir():
            continue

        case_id = case_dir.name

        ground_truth_path = case_dir / "ground_truth.json"
        if not ground_truth_path.exists():
            print(f"[SKIP] No ground_truth.json in case {case_id}")
            continue

        with open(ground_truth_path, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)

        patient_profile = ground_truth.get("patient_profile", "")
        expected_type = ground_truth.get("type", "")

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

                predicted_type = output.get("type", "")

                result_entry = {
                    "id": case_id,
                    "patient_profile": patient_profile,
                    "expected_type": expected_type,
                    "predicted_type": predicted_type,
                }

                results_path = model_dir / "results.json"
                if results_path.exists():
                    with open(results_path, "r", encoding="utf-8") as f:
                        results = json.load(f)
                    results = [r for r in results if r.get("id") != case_id]
                else:
                    results = []

                results.append(result_entry)
                results.sort(key=lambda r: r["id"])

                with open(results_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

                results_generated.append(str(results_path))
                print(f"[OK] case={case_id} method={method_name} model={model_name} -> {results_path}")

    print(f"\nDone. {len(results_generated)} results.json file(s) updated.")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_results(root)