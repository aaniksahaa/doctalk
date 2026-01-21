#!/usr/bin/env python3
"""
Speaker Diarization Script using Pyannote

Usage:
  python a.py --input audio.wav --output diarization.csv
"""

import argparse
import os
from dotenv import load_dotenv
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook
import torch
import csv

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False


def main():
    parser = argparse.ArgumentParser(description="Speaker Diarization using Pyannote")
    parser.add_argument("--input", type=str, required=True,
                        help="Path to input WAV audio file")
    parser.add_argument("--output", type=str, required=True,
                        help="Path to output CSV file")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    HF_TOKEN = os.getenv("HF_TOKEN")
    if HF_TOKEN is None:
        raise ValueError("HF_TOKEN not found in .env file")

    # Check CUDA
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Install CUDA-enabled PyTorch.")

    print("Loading diarization pipeline on CUDA...")

    # Load pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN
    )

    # Move model to GPU
    pipeline.to(torch.device("cuda"))

    print(f"Running diarization on {args.input}...")

    # Apply pretrained pipeline (with optional progress hook)
    with ProgressHook() as hook:
        output = pipeline(args.input, hook=hook)

    rows = []
    # Print the result - use speaker_diarization attribute for pyannote-audio 4.x
    diarization = output.speaker_diarization
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        start = round(turn.start, 3)
        end = round(turn.end, 3)
        rows.append([start, end, speaker])
        print(f"start={start}s stop={end}s speaker_{speaker}")

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["start", "end", "speaker"])
        writer.writerows(rows)

    print(f"\nDiarization saved to {args.output}")


if __name__ == "__main__":
    main()