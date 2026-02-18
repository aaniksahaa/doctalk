#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

# Load .env file from the same directory as this script
_script_dir = Path(__file__).parent.resolve()
_env_file = _script_dir / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        # If dotenv not installed, try manual parsing as fallback
        with open(_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# def load_pipeline(model_id: str, hf_token: str):
#     """
#     Tries both argument styles:
#     - use_auth_token=... (shown on the 3.1 model card)
#     - token=... (used by some newer pyannote/hf patterns)
#     """
#     from pyannote.audio import Pipeline

#     # First try the model-card way:
#     try:
#         return Pipeline.from_pretrained(model_id, use_auth_token=hf_token)
#     except TypeError:
#         # Fallback to newer signature
#         return Pipeline.from_pretrained(model_id, token=hf_token)

def load_pipeline(model_id: str, hf_token: str):
    from pyannote.audio import Pipeline
    return Pipeline.from_pretrained(model_id, use_auth_token=hf_token)


def seconds_to_hhmmss(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format (truncated, no milliseconds)."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def main():
    ap = argparse.ArgumentParser(
        description="Speaker diarization with pyannote/speaker-diarization-3.1 (CSV output)"
    )
    ap.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input audio (e.g., .wav)"
    )
    ap.add_argument(
        "-o", "--output",
        help="Path to output CSV (default: <input_stem>.csv in same folder)"
    )
    ap.add_argument(
        "--model",
        default="pyannote/speaker-diarization-3.1",
        help="Hugging Face pipeline id (default: pyannote/speaker-diarization-3.1)"
    )
    ap.add_argument(
        "--hf_token",
        default=os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_ACCESS_TOKEN"),
        help="Hugging Face token (or set HF_TOKEN env var)"
    )
    ap.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU inference (default: use CUDA if available, else CPU)"
    )
    ap.add_argument("--num_speakers", type=int, default=None, help="Force exact number of speakers")
    ap.add_argument("--min_speakers", type=int, default=None, help="Minimum number of speakers")
    ap.add_argument("--max_speakers", type=int, default=None, help="Maximum number of speakers")
    ap.add_argument(
        "--no_progress",
        action="store_true",
        help="Disable progress hook"
    )
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        eprint(f"ERROR: input file not found: {in_path}")
        sys.exit(2)

    out_path = Path(args.output) if args.output else in_path.with_suffix(".csv")

    if not args.hf_token:
        eprint(
            "ERROR: missing Hugging Face token.\n"
            "Set it via:\n"
            f"  - .env file in {_script_dir} (recommended)\n"
            "  - Environment variable HF_TOKEN\n"
            "  - Command line: --hf_token YOUR_TOKEN\n"
            "Also ensure you've accepted the model's user conditions on Hugging Face."
        )
        sys.exit(2)

    # Lazy imports so errors are clearer
    try:
        import torch
        from pyannote.audio.pipelines.utils.hook import ProgressHook
    except Exception as ex:
        eprint("ERROR: failed to import required libraries. Did you install pyannote.audio/torch?")
        eprint(f"Details: {ex}")
        sys.exit(2)

    # Load pipeline (requires gated access + token)
    try:
        pipeline = load_pipeline(args.model, args.hf_token)
    except Exception as ex:
        eprint("ERROR: could not load the diarization pipeline from Hugging Face.")
        eprint("Common causes:")
        eprint(" - You did not accept the user conditions for the model(s).")
        eprint(" - Your token is missing/invalid or lacks access.")
        eprint(" - No internet / blocked access to huggingface.co.")
        eprint(f"Details: {ex}")
        sys.exit(2)

    # Device selection: CUDA by default, CPU fallback or if --cpu flag
    if args.cpu:
        pipeline.to(torch.device("cpu"))
        eprint("Using CPU for inference.")
    elif torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
        eprint("Using CUDA for inference.")
    else:
        pipeline.to(torch.device("cpu"))
        eprint("CUDA not available, falling back to CPU.")

    # Run diarization
    call_kwargs = {}
    if args.num_speakers is not None:
        call_kwargs["num_speakers"] = args.num_speakers
    if args.min_speakers is not None:
        call_kwargs["min_speakers"] = args.min_speakers
    if args.max_speakers is not None:
        call_kwargs["max_speakers"] = args.max_speakers

    try:
        if args.no_progress:
            diarization = pipeline(str(in_path), **call_kwargs)
        else:
            with ProgressHook() as hook:
                diarization = pipeline(str(in_path), hook=hook, **call_kwargs)
    except Exception as ex:
        eprint("ERROR: diarization failed during inference.")
        eprint("Common causes:")
        eprint(" - Corrupt/unsupported audio file.")
        eprint(" - Missing audio backend dependencies (try .wav PCM 16-bit).")
        eprint(" - GPU OOM (try --device cpu).")
        eprint(f"Details: {ex}")
        sys.exit(2)

    # Build speaker ID mapping (SPEAKER_00 -> 1, SPEAKER_01 -> 2, etc.)
    speaker_labels = sorted(set(speaker for _, _, speaker in diarization.itertracks(yield_label=True)))
    speaker_to_id = {label: idx + 1 for idx, label in enumerate(speaker_labels)}

    # Write CSV
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("start_time,end_time,speaker_id\n")
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                start_str = seconds_to_hhmmss(turn.start)
                end_str = seconds_to_hhmmss(turn.end)
                speaker_id = speaker_to_id[speaker]
                f.write(f"{start_str},{end_str},{speaker_id}\n")
    except Exception as ex:
        eprint(f"ERROR: failed to write CSV to {out_path}")
        eprint(f"Details: {ex}")
        sys.exit(2)

    # Also print a readable summary
    print(f"CSV written to: {out_path}")
    print(f"Detected {len(speaker_labels)} speakers.")
    print("Segments:")
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        start_str = seconds_to_hhmmss(turn.start)
        end_str = seconds_to_hhmmss(turn.end)
        speaker_id = speaker_to_id[speaker]
        print(f"{start_str} {end_str}  {speaker_id}")

if __name__ == "__main__":
    main()
