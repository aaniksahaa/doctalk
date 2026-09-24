#!/usr/bin/env python3
"""
Build the example dataset: a small replica of saved-data/ restricted to the
N highest-ranked videos.

Output layout (mirrors saved-data/ as if the corpus contained only the selected videos):

    example_dataset/
    ├── filtered-results.json               # the input entries of the selected videos only
    ├── example-selection.json              # ranking, per-video statistics and the score formula
    ├── dataset/
    │   └── <video_id>/                     # full copy of saved-data/dataset/<video_id>/
    │       ├── <video_id>_yt-dlp-metadata.json
    │       ├── <video_id>_derived-metadata.json
    │       ├── audio/<video_id>_audio.mp3  # downloaded here (see download_audio.py)
    │       └── transcribed/yt-auto/...     # srt, processed txt, parsed/<model>/..., downstream/...
    └── downstream-datasets/
        └── <task>/
            ├── summary.json                # recomputed for the subset
            ├── all/<idx>/                  # only elements whose origin_video_id is selected
            └── split/{train,val,test}/<idx>/   # same, original numbering preserved

Ranking. Every parsed video gets a score from its statistics:
  - downstream elements linked to it (from downstream-datasets/*/all/*/metadata.json:origin_video_id),
    with a bonus per task it contributes >= 2 elements to,
  - number of its elements in the test split (they carry inference results),
  - patient calls, host-doctor QA exchanges and duration.
The formula is written into example-selection.json so the choice is reproducible.

Nothing under saved-data/ is modified. Only the output folder is written.

Usage:
    python generate_example_dataset.py                    # top 10 into ../example_dataset
    python generate_example_dataset.py --n 5 --skip-audio
    python generate_example_dataset.py --force-rewrite --prune
    python generate_example_dataset.py --list             # print the ranking only
"""

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import download_audio as da

# ── Constants ────────────────────────────────────────────────────────────────

TASKS = ["medical-ner", "advice-safety", "advice-generation", "triage"]
SPLITS = ["train", "val", "test"]
ELEMENT_FILES = {"metadata.json", "input.json", "ground_truth.json"}
LEGACY_INPUT_NAME = "filtered-results.json"
SELECTION_NAME = "example-selection.json"

# Score weights (kept in one place; also written into the manifest)
SCORE_WEIGHTS = {
    "task_bonus_ge2_elements": 20.0,   # per task the video contributes >= 2 elements to
    "task_bonus_1_element": 5.0,       # per task the video contributes exactly 1 element to
    "per_downstream_element": 3.0,
    "per_test_split_element": 2.0,     # test elements usually carry inference results
    "per_patient_call": 2.0,
    "per_host_doctor_qa": 0.2,
    "per_10_minutes": 1.0,
}


def parsed_dir(video_folder: Path, parse_model: str) -> Path:
    model_dir = parse_model.replace("/", "-").replace(":", "-")
    return video_folder / "transcribed" / "yt-auto" / "parsed" / model_dir


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Downstream index ─────────────────────────────────────────────────────────

def index_downstream(downstream_root: Path) -> Dict[str, Dict[str, Dict[str, List[int]]]]:
    """
    Map origin_video_id -> task -> {"all": [idx...], "train": [...], "val": [...], "test": [...]}
    built from the metadata.json of every element folder.
    """
    index: Dict[str, Dict[str, Dict[str, List[int]]]] = defaultdict(
        lambda: defaultdict(lambda: {"all": [], "train": [], "val": [], "test": []})
    )
    if not downstream_root.is_dir():
        return index
    for task_dir in sorted(downstream_root.iterdir()):
        if not task_dir.is_dir():
            continue
        subdirs = {"all": task_dir / "all"}
        for s in SPLITS:
            subdirs[s] = task_dir / "split" / s
        for key, sub in subdirs.items():
            if not sub.is_dir():
                continue
            for elem in sub.iterdir():
                if not elem.is_dir() or not elem.name.isdigit():
                    continue
                meta_path = elem / "metadata.json"
                if not meta_path.exists():
                    continue
                try:
                    origin = load_json(meta_path).get("origin_video_id")
                except Exception:
                    continue
                if origin:
                    index[origin][task_dir.name][key].append(int(elem.name))
    return index


# ── Per-video statistics ─────────────────────────────────────────────────────

def video_stats(video_folder: Path, parse_model: str,
                ds_index: Dict[str, Dict[str, Dict[str, List[int]]]]) -> Optional[Dict[str, Any]]:
    """Collect everything we know about one video. Returns None if it has no parsed conversation."""
    vid = video_folder.name
    conv_path = parsed_dir(video_folder, parse_model) / f"{vid}_conversation.json"
    if not conv_path.exists():
        return None
    try:
        conversations = load_json(conv_path)
    except Exception:
        return None

    yt_meta: Dict[str, Any] = {}
    p = video_folder / f"{vid}_yt-dlp-metadata.json"
    if p.exists():
        try:
            yt_meta = load_json(p)
        except Exception:
            pass
    tags: List[str] = []
    p = video_folder / f"{vid}_derived-metadata.json"
    if p.exists():
        try:
            tags = load_json(p).get("tags", [])
        except Exception:
            pass

    types = Counter(e.get("type", "unknown") for e in conversations)
    turns = [t for e in conversations for t in e.get("turns", [])]
    speakers = Counter((t.get("speaker") or "unknown").lower() for t in turns)
    n_chars = sum(len(t.get("text", "")) for t in turns)

    ds = ds_index.get(vid, {})
    per_task = {t: len(ds.get(t, {}).get("all", [])) for t in TASKS}
    per_task_split = {t: {s: len(ds.get(t, {}).get(s, [])) for s in SPLITS} for t in TASKS}
    n_elems = sum(per_task.values())
    n_test = sum(per_task_split[t]["test"] for t in TASKS)
    tasks_ge2 = sum(1 for t in TASKS if per_task[t] >= 2)
    tasks_eq1 = sum(1 for t in TASKS if per_task[t] == 1)

    # per-video downstream generation outputs (inside the video folder itself)
    pv_root = parsed_dir(video_folder, parse_model) / "downstream"
    pv_outputs = []
    if pv_root.is_dir():
        for task_dir in sorted(pv_root.iterdir()):
            for model_dir in sorted(task_dir.iterdir()) if task_dir.is_dir() else []:
                if any(f.suffix == ".json" and f.name != "metadata.json" for f in model_dir.iterdir()):
                    pv_outputs.append(f"{task_dir.name}/{model_dir.name}")

    duration = float(yt_meta.get("duration") or 0)
    pc = types.get("patient_call", 0)
    qa = types.get("host_doctor_qa", 0)
    w = SCORE_WEIGHTS
    score = (
        w["task_bonus_ge2_elements"] * tasks_ge2
        + w["task_bonus_1_element"] * tasks_eq1
        + w["per_downstream_element"] * n_elems
        + w["per_test_split_element"] * n_test
        + w["per_patient_call"] * pc
        + w["per_host_doctor_qa"] * qa
        + w["per_10_minutes"] * duration / 600.0
    )

    return {
        "video_id": vid,
        "title": yt_meta.get("title"),
        "channel": yt_meta.get("channel") or yt_meta.get("uploader"),
        "upload_date": yt_meta.get("upload_date"),
        "duration_sec": duration,
        "tags": tags,
        "n_exchanges": len(conversations),
        "n_host_doctor_qa": qa,
        "n_patient_call": pc,
        "n_turns": len(turns),
        "n_chars": n_chars,
        "speaker_turns": dict(speakers),
        "downstream_elements_total": n_elems,
        "downstream_elements_per_task": per_task,
        "downstream_elements_per_task_split": per_task_split,
        "downstream_tasks_covered": sum(1 for t in TASKS if per_task[t]),
        "downstream_test_elements": n_test,
        "per_video_downstream_outputs": pv_outputs,
        "has_srt": (video_folder / "transcribed" / "yt-auto" / f"{vid}_transcription.srt").exists(),
        "score": round(score, 2),
    }


def rank_videos(dataset_path: Path, parse_model: str, ds_index) -> List[Dict[str, Any]]:
    rows = []
    for d in sorted(dataset_path.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            s = video_stats(d, parse_model, ds_index)
            if s:
                rows.append(s)
    rows.sort(key=lambda r: (-r["score"], -r["downstream_elements_total"], -r["n_patient_call"], r["video_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def print_ranking(rows: List[Dict[str, Any]], n: int) -> None:
    print(f"{'rank':<5}{'video_id':<13}{'score':>7}{'tasks':>6}{'elems':>6}{'test':>5}{'dur':>7}{'pcall':>6}{'qa':>4}{'turns':>6}  per task (ner/adv-safety/adv-gen/triage)")
    for r in rows[:n]:
        pt = r["downstream_elements_per_task"]
        print(f"{r['rank']:<5}{r['video_id']:<13}{r['score']:>7}{r['downstream_tasks_covered']:>6}"
              f"{r['downstream_elements_total']:>6}{r['downstream_test_elements']:>5}{int(r['duration_sec']):>7}"
              f"{r['n_patient_call']:>6}{r['n_host_doctor_qa']:>4}{r['n_turns']:>6}  "
              f"{pt['medical-ner']}/{pt['advice-safety']}/{pt['advice-generation']}/{pt['triage']}")


# ── Replica building ─────────────────────────────────────────────────────────

def looks_like_video_folder(p: Path) -> bool:
    return p.is_dir() and (p / f"{p.name}_yt-dlp-metadata.json").exists()


def copy_video_folder(src: Path, dst: Path, force: bool) -> str:
    """Copy a video folder; keep an existing audio/ sub-folder on rewrite. Returns action taken."""
    if dst.exists():
        if not force:
            return "kept"
        for child in dst.iterdir():
            if child.name == da.AUDIO_DIR_NAME:
                continue
            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
        action = "rewritten"
    else:
        action = "copied"
    # never copy an audio folder from the source: audio is managed per output folder
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(da.AUDIO_DIR_NAME))
    return action


def build_downstream_subset(src_root: Path, dst_root: Path, selected: List[str],
                            ds_index, force: bool) -> Dict[str, Any]:
    """Copy only the elements whose origin video is selected; recompute summary.json per task."""
    report: Dict[str, Any] = {}
    selected_set = set(selected)
    if not src_root.is_dir():
        return report
    for task_dir in sorted(src_root.iterdir()):
        if not task_dir.is_dir():
            continue
        task = task_dir.name
        dst_task = dst_root / task
        if force and dst_task.exists():
            shutil.rmtree(dst_task)

        counts = {"all": 0, "train": 0, "val": 0, "test": 0}
        copied = 0
        for key in ["all"] + SPLITS:
            src_sub = task_dir / "all" if key == "all" else task_dir / "split" / key
            dst_sub = dst_task / "all" if key == "all" else dst_task / "split" / key
            if not src_sub.is_dir():
                continue
            dst_sub.mkdir(parents=True, exist_ok=True)
            for vid in selected:
                for idx in sorted(ds_index.get(vid, {}).get(task, {}).get(key, [])):
                    s, d = src_sub / str(idx), dst_sub / str(idx)
                    counts[key] += 1
                    if d.exists():
                        continue
                    shutil.copytree(s, d)   # whole element, including inference/ results if present
                    copied += 1

        # split-level aggregate files (aggregated_results.json, summary.csv) describe the FULL
        # dataset, so they are intentionally not copied into the subset.
        omitted = sorted(
            f"split/{s}/{p.name}" for s in SPLITS
            for p in ((task_dir / "split" / s).iterdir() if (task_dir / "split" / s).is_dir() else [])
            if not p.is_dir()
        )

        full_summary = {}
        if (task_dir / "summary.json").exists():
            try:
                full_summary = load_json(task_dir / "summary.json")
            except Exception:
                pass
        n = counts["all"]
        summary = {
            "task": task,
            "generator_model": full_summary.get("generator_model"),
            "total_elements": n,
            "source_videos": sum(1 for v in selected if ds_index.get(v, {}).get(task, {}).get("all")),
            "train_count": counts["train"],
            "val_count": counts["val"],
            "test_count": counts["test"],
            "train_pct": round(100 * counts["train"] / n, 1) if n else 0,
            "val_pct": round(100 * counts["val"] / n, 1) if n else 0,
            "test_pct": round(100 * counts["test"] / n, 1) if n else 0,
            "seed": full_summary.get("seed"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "example_subset": {
                "note": "Subset of saved-data/downstream-datasets restricted to the selected example videos; "
                        "element numbering is preserved from the full dataset.",
                "full_total_elements": full_summary.get("total_elements"),
                "full_source_videos": full_summary.get("source_videos"),
                "full_split": {k: full_summary.get(f"{k}_count") for k in SPLITS},
                "selected_video_ids": [v for v in selected if ds_index.get(v, {}).get(task, {}).get("all")],
                "omitted_aggregate_files": omitted,
            },
        }
        if n:
            save_json(dst_task / "summary.json", summary)
        elif dst_task.exists() and not any(dst_task.rglob("*")):
            shutil.rmtree(dst_task)
        report[task] = {"elements": counts, "newly_copied": copied, "omitted_aggregate_files": omitted}
    return report


def prune_output(out_dir: Path, selected: List[str], downstream_report_tasks: List[str]) -> List[str]:
    """Remove legacy flat video folders and dataset/ folders no longer selected."""
    removed = []
    keep = set(selected)
    # legacy layout: example_dataset/<video_id>/...
    for p in list(out_dir.iterdir()):
        if looks_like_video_folder(p):
            shutil.rmtree(p)
            removed.append(str(p.relative_to(out_dir)))
    ds_dir = out_dir / "dataset"
    if ds_dir.is_dir():
        for p in list(ds_dir.iterdir()):
            if p.is_dir() and p.name not in keep:
                shutil.rmtree(p)
                removed.append(str(p.relative_to(out_dir)))
    dd_dir = out_dir / "downstream-datasets"
    if dd_dir.is_dir():
        for task_dir in list(dd_dir.iterdir()):
            if task_dir.is_dir() and task_dir.name not in downstream_report_tasks:
                shutil.rmtree(task_dir)
                removed.append(str(task_dir.relative_to(out_dir)))
    return removed


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Build the example dataset as a replica of saved-data/ "
                                                 "restricted to the top-N ranked videos.")
    parser.add_argument("--n", type=int, default=10, help="Number of videos to select (default: 10)")
    parser.add_argument("--folder", default="saved-data",
                        help="Source folder with dataset/ and downstream-datasets/ (default: saved-data)")
    parser.add_argument("--file", default=LEGACY_INPUT_NAME,
                        help=f"Input JSON in --folder to subset into the output (default: {LEGACY_INPUT_NAME})")
    parser.add_argument("--output", default=None,
                        help="Output folder (default: <repo root>/example_dataset, i.e. ../example_dataset)")
    parser.add_argument("--parse-model", default="gemini-3-flash-preview",
                        help="Parsing model whose conversation.json is used (default: gemini-3-flash-preview)")
    parser.add_argument("--video-ids", default=None,
                        help="Comma-separated video IDs to use instead of the ranking")
    parser.add_argument("--list", action="store_true", help="Print the ranking (top 3N) and exit")
    parser.add_argument("--force-rewrite", action="store_true",
                        help="Re-copy video folders and downstream elements (existing audio is kept)")
    parser.add_argument("--prune", action="store_true",
                        help="Remove legacy flat video folders and non-selected videos from the output")
    parser.add_argument("--skip-audio", action="store_true", help="Do not download audio")
    parser.add_argument("--audio-format", default=da.DEFAULT_FORMAT, choices=da.SUPPORTED_FORMATS)
    parser.add_argument("--audio-quality", default=da.DEFAULT_AUDIO_QUALITY)
    parser.add_argument("--audio-delay", type=float, default=2.0, help="Seconds between audio downloads")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = (Path.cwd() / folder_path).resolve()
    dataset_path = folder_path / "dataset"
    downstream_path = folder_path / "downstream-datasets"
    out_dir = Path(args.output).resolve() if args.output else (script_dir.parent / "example_dataset")

    if not dataset_path.is_dir():
        print(f"Error: dataset folder not found: {dataset_path}")
        return 1

    print(f"Source dataset      : {dataset_path}")
    print(f"Source downstream   : {downstream_path}")
    print(f"Output              : {out_dir}")
    print(f"Parse model         : {args.parse_model}")
    print()

    # ── rank ──
    print("Indexing downstream datasets and scanning parsed videos...")
    ds_index = index_downstream(downstream_path)
    rows = rank_videos(dataset_path, args.parse_model, ds_index)
    by_id = {r["video_id"]: r for r in rows}
    print(f"Parsed videos: {len(rows)} | videos with downstream elements: {sum(1 for r in rows if r['downstream_elements_total'])}\n")

    if args.list:
        print_ranking(rows, max(args.n * 3, 15))
        return 0

    if args.video_ids:
        selected = [v.strip() for v in args.video_ids.split(",") if v.strip()]
        missing = [v for v in selected if v not in by_id]
        if missing:
            print(f"Error: no parsed conversation for: {missing}")
            return 1
    else:
        selected = [r["video_id"] for r in rows[: args.n]]

    print(f"Selected {len(selected)} videos:")
    print_ranking([by_id[v] for v in selected], len(selected))
    print()

    # ── dataset/ ──
    out_dir.mkdir(parents=True, exist_ok=True)
    out_ds = out_dir / "dataset"
    out_ds.mkdir(exist_ok=True)
    print("Copying video folders...")
    for v in selected:
        action = copy_video_folder(dataset_path / v, out_ds / v, args.force_rewrite)
        print(f"  {v}: {action}")

    # ── downstream-datasets/ ──
    print("\nCopying downstream elements linked to the selected videos...")
    ds_report = build_downstream_subset(downstream_path, out_dir / "downstream-datasets", selected, ds_index, args.force_rewrite)
    for task, rep in ds_report.items():
        c = rep["elements"]
        print(f"  {task:<18} all={c['all']:<3} train={c['train']:<3} val={c['val']:<3} test={c['test']:<3} (newly copied: {rep['newly_copied']})")

    # ── input file subset ──
    src_input = folder_path / args.file
    if src_input.exists():
        try:
            entries = load_json(src_input)
            sel = set(selected)
            subset = [e for e in entries if isinstance(e, dict) and e.get("videoId") in sel]
            save_json(out_dir / args.file, subset)
            print(f"\nWrote {args.file} with {len(subset)} entries")
        except Exception as e:
            print(f"\n⚠ Could not subset {args.file}: {e}")

    # ── prune ──
    if args.prune:
        removed = prune_output(out_dir, selected, [t for t, r in ds_report.items() if r["elements"]["all"]])
        if removed:
            print("\nPruned from output:")
            for r in removed:
                print(f"  - {r}")

    # ── audio ──
    audio_results: Dict[str, str] = {}
    if args.skip_audio:
        print("\nSkipping audio (--skip-audio)")
    else:
        print(f"\nDownloading audio ({args.audio_format}) into {out_ds}/<video_id>/audio/ ...")
        audio_meta = da.load_run_metadata(out_dir / da.RUN_METADATA_NAME, str(out_dir), args.file,
                                          args.audio_format, args.audio_quality)
        audio_meta["last_run"] = da.now_iso()
        try:
            for i, v in enumerate(selected):
                status = da.process_video(
                    v, i, out_ds, audio_meta,
                    fmt=args.audio_format, quality=args.audio_quality, force_rewrite=False,
                    max_retries=2, cookies=None, cookies_from_browser=None, extra_args=[],
                    timeout=1800, dry_run=False,
                )
                audio_results[v] = status
                if status in ("downloaded", "failed") and i < len(selected) - 1 and args.audio_delay > 0:
                    import time
                    time.sleep(args.audio_delay)
        finally:
            audio_meta["failed_count"] = len(audio_meta["failures"])
            da.save_json(out_dir / da.RUN_METADATA_NAME, audio_meta)

    # ── manifest ──
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_folder": str(folder_path),
        "parse_model": args.parse_model,
        "n_selected": len(selected),
        "selection_mode": "explicit --video-ids" if args.video_ids else f"top {args.n} by score",
        "score_formula": {
            "description": "score = bonus(20 per task with >=2 linked elements, 5 per task with exactly 1) "
                           "+ 3*downstream_elements + 2*test_split_elements + 2*patient_calls "
                           "+ 0.2*host_doctor_qa + duration_minutes/10",
            "weights": SCORE_WEIGHTS,
        },
        "totals": {
            "duration_sec": sum(by_id[v]["duration_sec"] for v in selected),
            "n_exchanges": sum(by_id[v]["n_exchanges"] for v in selected),
            "n_patient_call": sum(by_id[v]["n_patient_call"] for v in selected),
            "n_host_doctor_qa": sum(by_id[v]["n_host_doctor_qa"] for v in selected),
            "n_turns": sum(by_id[v]["n_turns"] for v in selected),
            "downstream_elements_per_task": {t: sum(by_id[v]["downstream_elements_per_task"][t] for v in selected) for t in TASKS},
            "tags": dict(Counter(tag for v in selected for tag in by_id[v]["tags"])),
        },
        "downstream_subset": ds_report,
        "audio": audio_results,
        "videos": [by_id[v] for v in selected],
        "ranking_context": {
            "parsed_videos_total": len(rows),
            "videos_with_downstream_elements": sum(1 for r in rows if r["downstream_elements_total"]),
            "next_candidates": [
                {k: r[k] for k in ("rank", "video_id", "score", "downstream_elements_total", "n_patient_call", "duration_sec")}
                for r in rows if r["video_id"] not in set(selected)
            ][:10],
        },
    }
    save_json(out_dir / SELECTION_NAME, manifest)

    # ── summary ──
    tot = manifest["totals"]
    print("\n" + "=" * 60)
    print(f"Example dataset written to: {out_dir}")
    print(f"  Videos                : {len(selected)}")
    print(f"  Total duration        : {da.human_duration(tot['duration_sec'])}")
    print(f"  Exchanges             : {tot['n_exchanges']} (patient calls {tot['n_patient_call']}, host-doctor QA {tot['n_host_doctor_qa']})")
    print(f"  Downstream elements   : " + ", ".join(f"{t}={n}" for t, n in tot["downstream_elements_per_task"].items()))
    if audio_results:
        print(f"  Audio                 : " + ", ".join(f"{k}={v}" for k, v in Counter(audio_results.values()).items()))
    print(f"  Manifest              : {out_dir / SELECTION_NAME}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
