import argparse
import csv
import warnings
from pathlib import Path

from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate


def parse_time_to_seconds(value: str) -> float:
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


def csv_to_annotation(csv_path: str, uri: str, epsilon: float) -> Annotation:
    annotation = Annotation(uri=uri)

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = {"start_time", "end_time", "speaker_id"}
        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise ValueError(
                f"CSV '{csv_path}' must have exactly header: start_time,end_time,speaker_id"
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute DER between reference and hypothesis diarization CSVs using pyannote."
    )
    parser.add_argument("--reference_csv", required=True, help="Path to reference/annotation CSV")
    parser.add_argument("--hypothesis_csv", required=True, help="Path to prediction CSV")
    parser.add_argument(
        "--collar",
        type=float,
        default=0.0,
        help="Collar (seconds) passed to pyannote DiarizationErrorRate (default: 0.0)",
    )
    parser.add_argument(
        "--skip_overlap",
        action="store_true",
        help="If set, overlap regions are ignored when computing DER",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=1e-3,
        help="Small duration added when a segment has end_time <= start_time (default: 1e-3)",
    )
    parser.add_argument(
        "--show_warnings",
        action="store_true",
        help="If set, show pyannote warnings (suppressed by default for clean pipeline output)",
    )

    args = parser.parse_args()

    reference_csv = Path(args.reference_csv)
    hypothesis_csv = Path(args.hypothesis_csv)

    if not reference_csv.exists():
        raise FileNotFoundError(f"Reference CSV not found: {reference_csv}")
    if not hypothesis_csv.exists():
        raise FileNotFoundError(f"Hypothesis CSV not found: {hypothesis_csv}")

    uri = reference_csv.stem
    reference = csv_to_annotation(str(reference_csv), uri=uri, epsilon=args.epsilon)
    hypothesis = csv_to_annotation(str(hypothesis_csv), uri=uri, epsilon=args.epsilon)

    if not args.show_warnings:
        warnings.filterwarnings(
            "ignore",
            message="'uem' was approximated by the union of 'reference' and 'hypothesis' extents.",
            category=UserWarning,
        )

    metric = DiarizationErrorRate(collar=args.collar, skip_overlap=args.skip_overlap)
    der = float(metric(reference, hypothesis))

    # Parse-friendly output for pipeline usage.
    print(f"DER={der:.6f}")


if __name__ == "__main__":
    main()
