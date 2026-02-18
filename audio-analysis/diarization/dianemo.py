import argparse
import csv
import json
import os
from pathlib import Path

from omegaconf import OmegaConf
from nemo.collections.asr.models import ClusteringDiarizer


def write_manifest(manifest_path: str, audio_path: str, num_speakers=None):
    # NeMo diarization expects a JSONL manifest (one JSON per line)
    entry = {
        "audio_filepath": os.path.abspath(audio_path),
        "offset": 0,
        "duration": None,
        "label": "infer",
        "text": "-",
        "num_speakers": num_speakers,   # can be None for auto speaker count
        "rttm_filepath": None,
        "uem_filepath": None,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def parse_rttm(rttm_path: str):
    # RTTM lines look like:
    # SPEAKER <file-id> 1 <start> <dur> <NA> <NA> <speaker> <NA> <NA>
    segments = []
    with open(rttm_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 9 or parts[0].upper() != "SPEAKER":
                continue
            start = float(parts[3])
            dur = float(parts[4])
            spk = parts[7]
            segments.append((start, start + dur, spk))
    segments.sort(key=lambda x: x[0])
    return segments


def seconds_to_hhmmss(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def normalize_speaker_id(label: str) -> str:
    if label.startswith("speaker_"):
        return label.split("_", 1)[1]
    return label


def write_segments_csv(csv_path: str, segments):
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start_time", "end_time", "speaker_id"])
        for start, end, speaker in segments:
            writer.writerow([
                seconds_to_hhmmss(start),
                seconds_to_hhmmss(end),
                normalize_speaker_id(speaker),
            ])


def build_config(manifest_path: str, out_dir: str, device: str | None,
                 vad_model: str, speaker_model: str, msdd_model: str | None):
    """
    This config is the same shape as NeMo's diar_infer_general.yaml, just embedded in Python.
    See the NeMo example YAML for field meanings. :contentReference[oaicite:1]{index=1}
    """
    cfg = {
        "name": "ClusterDiarizer",
        "num_workers": 0,
        "sample_rate": 16000,
        "batch_size": 4,
        "device": device,  # e.g. "cuda", "cuda:0", or "cpu", or None for auto
        "verbose": True,
        "diarizer": {
            "manifest_filepath": manifest_path,
            "out_dir": out_dir,
            "oracle_vad": False,
            "collar": 0.25,
            "ignore_overlap": True,

            "vad": {
                "model_path": vad_model,  # .nemo path OR pretrained model name
                "external_vad_manifest": None,
                "parameters": {
                    "window_length_in_sec": 0.63,
                    "shift_length_in_sec": 0.08,
                    "smoothing": False,
                    "overlap": 0.5,
                    "onset": 0.5,
                    "offset": 0.3,
                    "pad_onset": 0.2,
                    "pad_offset": 0.2,
                    "min_duration_on": 0.5,
                    "min_duration_off": 0.5,
                    "filter_speech_first": True,
                },
            },

            "speaker_embeddings": {
                "model_path": speaker_model,  # .nemo path OR pretrained model name
                "parameters": {
                    "window_length_in_sec": [1.9, 1.2, 0.5],
                    "shift_length_in_sec": [0.95, 0.6, 0.25],
                    "multiscale_weights": [1, 1, 1],
                    "save_embeddings": True,
                },
            },

            "clustering": {
                "parameters": {
                    "oracle_num_speakers": False,
                    "max_num_speakers": 8,
                    "enhanced_count_thres": 80,
                    "max_rp_threshold": 0.25,
                    "sparse_search_volume": 10,
                    "maj_vote_spk_count": False,
                    "chunk_cluster_count": 50,
                    "embeddings_per_chunk": 10000,
                }
            },

            # Optional neural refinement (MSDD). Set model_path to None to skip.
            "msdd_model": {
                "model_path": msdd_model,  # .nemo path OR pretrained model name OR None
                "parameters": {
                    "use_speaker_model_from_ckpt": True,
                    "infer_batch_size": 25,
                    "sigmoid_threshold": [0.7],
                    "seq_eval_mode": False,
                    "split_infer": True,
                    "diar_window_length": 50,
                    "overlap_infer_spk_limit": 5,
                },
            },

            # ASR is optional; leaving disabled here
            "asr": {"model_path": None, "parameters": {"asr_based_vad": False}},
        },
    }
    return OmegaConf.create(cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="Path to input audio (wav/flac/etc.)")
    ap.add_argument("--out_dir", default="diar_out", help="Output directory")
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Path to output CSV in format: start_time,end_time,speaker_id. "
            "Default: <out_dir>/<audio_basename>.csv"
        ),
    )
    ap.add_argument("--num_speakers", type=int, default=None, help="Optional oracle speaker count")
    ap.add_argument("--cpu", action="store_true", help="Force CPU inference (default: use CUDA if available)")
    args = ap.parse_args()

    audio_path = args.input
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # # ---- SET THESE (either local .nemo paths OR pretrained model names) ----
    # VAD_MODEL = "/path/to/vad_multilingual_marblenet.nemo"   # or e.g. "vad_multilingual_marblenet"
    # SPK_MODEL = "/path/to/titanet-l.nemo"                    # or e.g. "titanet_large"
    # MSDD_MODEL = "/path/to/diarizer_msdd_telephonic.nemo"    # or None to disable
    # # ----------------------------------------------------------------------

    VAD_MODEL = "vad_multilingual_marblenet"
    SPK_MODEL = "titanet_large"
    MSDD_MODEL = "diar_msdd_telephonic"   # or None to disable

    # Device selection: CUDA by default, CPU fallback or if --cpu flag
    import torch
    if args.cpu:
        device = "cpu"
        print("Using CPU for inference.")
    elif torch.cuda.is_available():
        device = "cuda"
        print("Using CUDA for inference.")
    else:
        device = "cpu"
        print("CUDA not available, falling back to CPU.")

    manifest_path = os.path.join(out_dir, "manifest.json")
    write_manifest(manifest_path, audio_path, num_speakers=args.num_speakers)

    cfg = build_config(
        manifest_path=manifest_path,
        out_dir=out_dir,
        device=device,
        vad_model=VAD_MODEL,
        speaker_model=SPK_MODEL,
        msdd_model=MSDD_MODEL,
    )

    diarizer = ClusteringDiarizer(cfg=cfg)
    diarizer.diarize()  # runs the pipeline :contentReference[oaicite:2]{index=2}

    # NeMo writes RTTMs here by default:
    # <out_dir>/pred_rttms/<audio-basename>.rttm
    rttm_dir = os.path.join(out_dir, "pred_rttms")
    base = Path(audio_path).stem
    rttm_path = os.path.join(rttm_dir, f"{base}.rttm")

    if not os.path.exists(rttm_path):
        raise FileNotFoundError(
            f"Expected RTTM not found at: {rttm_path}\n"
            f"Check {out_dir} for logs and outputs."
        )

    segments = parse_rttm(rttm_path)
    output_csv = args.output or os.path.join(out_dir, f"{base}.csv")
    write_segments_csv(output_csv, segments)

    print(f"\nRTTM: {rttm_path}")
    print("Speaker turns:")
    for (st, et, spk) in segments:
        print(f"{st:8.2f} - {et:8.2f}   {spk}")
    print(f"\nCSV: {os.path.abspath(output_csv)}")


if __name__ == "__main__":
    main()
