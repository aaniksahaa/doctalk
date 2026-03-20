#!/usr/bin/env python3
"""
Compare line similarity between output.json and ground_truth.json
for each inference result in the folder structure.
"""

import argparse
import json
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer, util


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_similarities(output_recommendations, ground_truth_recommendations, model):
    results = []

    gt_contents = [item["content"] for item in ground_truth_recommendations]
    gt_labels = [item.get("label", "") for item in ground_truth_recommendations]

    # Encode all ground truth sentences once
    gt_embeddings = model.encode(gt_contents, convert_to_tensor=True)

    for output_item in output_recommendations:
        output_content = output_item["content"]
        output_embedding = model.encode(output_content, convert_to_tensor=True)

        scores_list = []
        for i, gt_content in enumerate(gt_contents):
            score = util.cos_sim(output_embedding, gt_embeddings[i]).item()
            scores_list.append({
                "content": gt_content,
                "label": gt_labels[i],
                "score": round(score, 6)
            })

        results.append({
            "content": output_content,
            "scores": scores_list
        })

    return results


def process_folder(folder_path, model):
    folder_path = Path(folder_path)

    # Iterate over each ID folder (e.g., 1, 21, ...)
    for id_folder in sorted(folder_path.iterdir()):
        if not id_folder.is_dir():
            continue

        ground_truth_path = id_folder / "ground_truth.json"
        if not ground_truth_path.exists():
            print(f"  [SKIP] No ground_truth.json in {id_folder}")
            continue

        ground_truth = load_json(ground_truth_path)
        gt_recommendations = ground_truth.get("recommendations", [])

        inference_dir = id_folder / "inference"
        if not inference_dir.exists():
            print(f"  [SKIP] No inference dir in {id_folder}")
            continue

        # Iterate over method folders (e.g., few-shot, zero-shot)
        for method_folder in sorted(inference_dir.iterdir()):
            if not method_folder.is_dir():
                continue
            method_name = method_folder.name

            # Iterate over model folders (e.g., gpt-4o)
            for model_folder in sorted(method_folder.iterdir()):
                if not model_folder.is_dir():
                    continue
                model_name = model_folder.name

                output_path = model_folder / "output.json"
                if not output_path.exists():
                    print(f"  [SKIP] No output.json in {model_folder}")
                    continue

                output_data = load_json(output_path)
                output_recommendations = output_data.get("recommendations", [])

                print(f"  Processing: {id_folder.name}/{method_name}/{model_name} "
                      f"({len(output_recommendations)} outputs vs {len(gt_recommendations)} ground truths)")

                results = compute_similarities(output_recommendations, gt_recommendations, model)

                results_path = model_folder / "results.json"
                with open(results_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

                print(f"  Saved: {results_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare output.json recommendations with ground_truth.json using sentence similarity."
    )
    parser.add_argument("folder_path", help="Path to the root folder containing ID subfolders")
    args = parser.parse_args()

    print("Loading Bengali sentence similarity model...")
    model = SentenceTransformer("l3cube-pune/bengali-sentence-similarity-sbert")
    print("Model loaded.\n")

    print(f"Processing folder: {args.folder_path}\n")
    process_folder(args.folder_path, model)
    print("\nDone!")


if __name__ == "__main__":
    main()