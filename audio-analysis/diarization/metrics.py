#!/usr/bin/env python3
"""
Reusable diarization metrics module.

Computes detailed pyannote-based metrics from reference/hypothesis CSV files:
  - DER (Diarization Error Rate)
  - False Alarm %
  - Missed Detection %
  - Speaker Confusion %
  - Correct %
  - RTF (Real-Time Factor)
"""
import csv
import warnings
import wave
from pathlib import Path
from typing import Dict, Optional

from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate


def parse_time_to_seconds(value: str) -> float:
    """Parse HH:MM:SS string to seconds."""
    text = value.strip()
    parts = text.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid time format '{value}'. Expected HH:MM:SS")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])

    if minutes < 0 or minutes >= 60:
        raise ValueError(f"Invalid minutes in '{value}'")
    if seconds < 0 or seconds >= 60:
        raise ValueError(f"Invalid seconds in '{value}'")

    return hours * 3600.0 + minutes * 60.0 + seconds


def csv_to_annotation(csv_path: str, uri: str, epsilon: float = 1e-3) -> Annotation:
    """
    Load a diarization CSV (start_time, end_time, speaker_id) into a
    pyannote Annotation object.
    """
    annotation = Annotation(uri=uri)

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV '{csv_path}' has no header")

        expected = {"start_time", "end_time", "speaker_id"}
        if not expected.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"CSV '{csv_path}' must have columns: {expected}"
            )

        for i, row in enumerate(reader, start=2):
            start = parse_time_to_seconds(row["start_time"])
            end = parse_time_to_seconds(row["end_time"])
            speaker = str(row["speaker_id"]).strip()

            if not speaker:
                raise ValueError(f"Empty speaker_id in '{csv_path}' at line {i}")

            # Guard against zero-length segments (can happen after HH:MM:SS rounding).
            if end <= start:
                end = start + epsilon

            annotation[Segment(start, end)] = speaker

    return annotation


def get_audio_duration(audio_path: str) -> float:
    """
    Get audio duration in seconds using the wave stdlib module.
    Falls back to soundfile if wave can't handle the format.
    """
    audio_path = str(audio_path)
    try:
        with wave.open(audio_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        pass

    # Fallback: try soundfile
    try:
        import soundfile as sf
        info = sf.info(audio_path)
        return info.duration
    except Exception:
        pass

    return -1.0


def compute_detailed_metrics(
    reference_csv: str,
    hypothesis_csv: str,
    collar: float = 0.0,
    skip_overlap: bool = False,
    epsilon: float = 1e-3,
) -> Dict[str, float]:
    """
    Compute detailed diarization metrics between reference and hypothesis CSVs.

    Returns dict with keys:
      - der:               overall DER (0–∞, typically 0–1)
      - false_alarm:       false alarm rate (fraction of scored time)
      - missed_detection:  missed speech rate (fraction of scored time)
      - confusion:         speaker confusion rate (fraction of scored time)
      - correct:           correct rate = 1 - der (can be negative if DER > 1)
    """
    ref_path = Path(reference_csv)
    hyp_path = Path(hypothesis_csv)

    if not ref_path.exists():
        raise FileNotFoundError(f"Reference CSV not found: {ref_path}")
    if not hyp_path.exists():
        raise FileNotFoundError(f"Hypothesis CSV not found: {hyp_path}")

    uri = ref_path.stem

    reference = csv_to_annotation(str(ref_path), uri=uri, epsilon=epsilon)
    hypothesis = csv_to_annotation(str(hyp_path), uri=uri, epsilon=epsilon)

    # Suppress pyannote UEM approximation warning
    warnings.filterwarnings(
        "ignore",
        message="'uem' was approximated by the union of 'reference' and 'hypothesis' extents.",
        category=UserWarning,
    )

    metric = DiarizationErrorRate(collar=collar, skip_overlap=skip_overlap)

    # Call with detailed=True to get per-pair component durations.
    details = metric(reference, hypothesis, detailed=True)

    total = details.get("total", 0.0)
    der = float(details.get("diarization error rate", 0.0))

    if total > 0:
        fa = details.get("false alarm", 0.0) / total
        miss = details.get("missed detection", 0.0) / total
        conf = details.get("confusion", 0.0) / total
        correct = details.get("correct", 0.0) / total
    else:
        fa = 0.0
        miss = 0.0
        conf = 0.0
        correct = 0.0

    return {
        "der": der,
        "false_alarm": fa,
        "missed_detection": miss,
        "confusion": conf,
        "correct": correct,
    }


def compute_rtf(inference_time: float, audio_path: str) -> float:
    """
    Compute Real-Time Factor = inference_time / audio_duration.
    Returns -1.0 if audio duration cannot be determined.
    """
    duration = get_audio_duration(audio_path)
    if duration > 0:
        return inference_time / duration
    return -1.0


# ── Formatting helpers ────────────────────────────────────────────────

METRICS_FIELDNAMES = [
    "model",
    "der",
    "false_alarm",
    "missed_detection",
    "confusion",
    "correct",
    "rtf",
    "inference_time",
    "audio_duration",
    "filepath",
]


def write_metrics_csv(
    metrics_path: str,
    model: str,
    metrics: Dict[str, float],
    rtf: float,
    inference_time: float,
    audio_duration: float,
    filepath: str,
) -> None:
    """Write a single-row extended metrics CSV."""
    with open(metrics_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(METRICS_FIELDNAMES)
        writer.writerow([
            model,
            f"{metrics['der']:.6f}",
            f"{metrics['false_alarm']:.6f}",
            f"{metrics['missed_detection']:.6f}",
            f"{metrics['confusion']:.6f}",
            f"{metrics['correct']:.6f}",
            f"{rtf:.6f}" if rtf >= 0 else "N/A",
            f"{inference_time:.2f}",
            f"{audio_duration:.2f}" if audio_duration >= 0 else "N/A",
            filepath,
        ])
