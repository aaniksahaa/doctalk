#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convert ground_truth.json and inference output.json files to BIO format.

Folder structure:
.
├── 15
│   ├── ground_truth.json
│   ├── input.json
│   ├── metadata.json
│   └── inference
│       ├── few-shot
│       │   └── gpt-4o
│       │       ├── inference_metadata.json
│       │       └── output.json
│       └── zero-shot
│           └── gpt-4o
│               ├── inference_metadata.json
│               └── output.json
├── 16
│   ├── ground_truth.json
│   ...

This script converts ground_truth.json and each output.json to BIO format .txt files
in the same directory.
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from convert_to_bio_and_visualize import (
    convert_dataset_to_bio,
    export_conll_like,
)


def load_json_file(path: str) -> Any:
    """Load a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_conll_file(samples: List[Dict[str, Any]], output_path: str) -> None:
    """Save BIO-converted samples to a CoNLL-like .txt file."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, sample in enumerate(samples):
            if "error" in sample:
                f.write(f"# SAMPLE #{sample.get('sample_index', i)} — ERROR\n")
                f.write(f"# {sample['error']}\n\n")
                continue

            f.write(f"# sample_index = {sample.get('sample_index', i)}\n")
            f.write(f"# text = {sample['text']}\n")
            f.write(export_conll_like(sample))
            f.write("\n\n")


def convert_json_to_bio(
    input_json_path: str,
    output_txt_path: str,
    mode: str = "whitespace",
    hf_model_name: Optional[str] = None,
) -> None:
    """
    Convert a single JSON file to BIO format and save as .txt file.
    """
    try:
        data = load_json_file(input_json_path)

        # Handle both single object and list of objects
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError(f"Expected JSON to be a dict or list, got {type(data)}")

        # Convert to BIO
        converted, total_skipped, total_warnings, total_errors = convert_dataset_to_bio(
            dataset=data,
            mode=mode,
            hf_model_name=hf_model_name,
        )

        # Save to .txt file
        save_conll_file(converted, output_txt_path)
        print(f"  ✓ {input_json_path.split('/')[-1]} → {Path(output_txt_path).name}")

    except Exception as e:
        print(f"  ✗ Error converting {input_json_path}: {e}")


def process_folder(
    folder_path: str,
    mode: str = "whitespace",
    hf_model_name: Optional[str] = None,
) -> None:
    """
    Process a folder and convert ground_truth.json and inference output.json files to BIO format.
    """
    folder_path = Path(folder_path)

    if not folder_path.is_dir():
        print(f"Error: {folder_path} is not a directory")
        return

    # Find all numbered subfolders
    subfolders = sorted(
        [d for d in folder_path.iterdir() if d.is_dir() and d.name.isdigit()],
        key=lambda x: int(x.name),
    )

    if not subfolders:
        print(f"No numbered subfolders found in {folder_path}")
        return

    print(f"Processing {len(subfolders)} folders...\n")

    for subfolder in subfolders:
        print(f"📁 Folder {subfolder.name}/")

        # Convert ground_truth.json
        ground_truth_path = subfolder / "ground_truth.json"
        if ground_truth_path.exists():
            output_path = subfolder / "ground_truth.txt"
            convert_json_to_bio(
                str(ground_truth_path), str(output_path), mode, hf_model_name
            )
        else:
            print(f"  ⚠ ground_truth.json not found")

        # Convert inference output files
        inference_dir = subfolder / "inference"
        if inference_dir.exists():
            for strategy_dir in inference_dir.iterdir():
                if not strategy_dir.is_dir():
                    continue

                for model_dir in strategy_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    output_json_path = model_dir / "output.json"
                    if output_json_path.exists():
                        # Create output.txt in the same directory
                        output_txt_path = model_dir / "output.txt"
                        rel_path = output_json_path.relative_to(subfolder)
                        print(f"  Processing {strategy_dir.name}/{model_dir.name}/")
                        convert_json_to_bio(
                            str(output_json_path),
                            str(output_txt_path),
                            mode,
                            hf_model_name,
                        )
        else:
            print(f"  ⚠ inference/ directory not found")

        print()


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python convert-to-bio.py <folder_path> [mode] [hf_model_name]")
        print()
        print("Arguments:")
        print("  folder_path:     Path to folder with numbered subfolders")
        print()
        print("Optional arguments:")
        print("  mode:            Tokenization mode (default: whitespace)")
        print("                   Options: whitespace, wordpunct, char, hf")
        print("  hf_model_name:   Model name for HF tokenization")
        print("                   (required if mode=hf)")
        print()
        print("Examples:")
        print("  python convert-to-bio.py ./data/")
        print("  python convert-to-bio.py ./data/ wordpunct")
        print("  python convert-to-bio.py ./data/ hf xlm-roberta-base")
        sys.exit(1)

    folder_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "whitespace"
    hf_model_name = sys.argv[3] if len(sys.argv) > 3 else None

    if mode == "hf" and not hf_model_name:
        print("Error: hf_model_name is required when mode=hf")
        sys.exit(1)

    process_folder(folder_path, mode=mode, hf_model_name=hf_model_name)
    print("✓ All conversions completed!")


if __name__ == "__main__":
    main()
