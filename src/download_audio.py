#!/usr/bin/env python3
"""
Download the audio track of every video in the dataset via yt-dlp.

This is an additive layer on top of the existing pipeline: it never touches
metadata, transcriptions or parsed conversations. For each video it creates

    dataset/<video_id>/audio/
        <video_id>_audio.<ext>          # the audio itself (mp3 by default)
        <video_id>_audio-info.json      # format / size / duration (ffprobe) / timestamps
        .audio.lock                     # completion marker (same convention as .lock, .parse.lock)

A video counts as "already downloaded" when BOTH the lock file and the audio
file exist, so re-running the script is idempotent and only fetches what is
missing.  Interrupted downloads are resumed by yt-dlp from its .part file.
An audio file that exists without a lock (e.g. copied in by hand or produced by
generate_example_dataset.py) is probed with ffprobe and adopted if it is valid.

Failures are recorded in <folder>/audio-download-metadata.json; failed videos
have no lock file and are simply retried on the next run.

Usage examples:
    python download_audio.py                                  # everything in filtered-results.json
    python download_audio.py --only-transcribed               # only videos that have a transcript (.lock)
    python download_audio.py --first-n 5                      # first 5 entries of the input file
    python download_audio.py --video-ids wRnLnfox9S8,mcJs7Gjk5hY
    python download_audio.py --format m4a --audio-quality 0   # different container / quality
    python download_audio.py --status                         # report what is downloaded, no downloads
    python download_audio.py --dry-run                        # list pending downloads only
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Layout constants (importable by other scripts)
# ─────────────────────────────────────────────────────────────────────────────

AUDIO_DIR_NAME = "audio"
AUDIO_LOCK_NAME = ".audio.lock"
AUDIO_FILE_STEM_SUFFIX = "_audio"           # -> <video_id>_audio.<ext>
AUDIO_INFO_SUFFIX = "_audio-info.json"      # -> <video_id>_audio-info.json
RUN_METADATA_NAME = "audio-download-metadata.json"
TRANSCRIBED_LOCK_NAME = ".lock"             # created by fetch_metadata_and_process_transcriptions.py

SUPPORTED_FORMATS = ["mp3", "m4a", "opus", "wav", "flac", "best"]
DEFAULT_FORMAT = "mp3"
DEFAULT_AUDIO_QUALITY = "5"                 # yt-dlp default (VBR); 0 = best, 9 = worst

# Files in the audio dir that are never considered "the audio file"
_NON_AUDIO_SUFFIXES = {".json", ".part", ".ytdl", ".lock", ".tmp"}


# ─────────────────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_audio_dir(video_folder: Path) -> Path:
    return video_folder / AUDIO_DIR_NAME


def get_audio_lock(video_folder: Path) -> Path:
    return get_audio_dir(video_folder) / AUDIO_LOCK_NAME


def get_audio_info_path(video_folder: Path, video_id: str) -> Path:
    return get_audio_dir(video_folder) / f"{video_id}{AUDIO_INFO_SUFFIX}"


def find_audio_file(video_folder: Path, video_id: str) -> Optional[Path]:
    """
    Return the downloaded audio file for a video, or None.
    Matches <video_id>_audio.<ext> for any real audio extension and ignores
    partial downloads, lock files and the info JSON.
    """
    audio_dir = get_audio_dir(video_folder)
    if not audio_dir.is_dir():
        return None
    candidates = []
    for p in audio_dir.glob(f"{video_id}{AUDIO_FILE_STEM_SUFFIX}.*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _NON_AUDIO_SUFFIXES or p.name.endswith(".part"):
            continue
        if p.name.startswith("."):
            continue
        candidates.append(p)
    if not candidates:
        return None
    # Prefer the largest file if several exist (should not normally happen)
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def is_audio_downloaded(video_folder: Path, video_id: str) -> bool:
    """True when the lock file AND the audio file are both present."""
    return get_audio_lock(video_folder).exists() and find_audio_file(video_folder, video_id) is not None


def has_transcript(video_folder: Path) -> bool:
    """True when fetch_metadata_and_process_transcriptions.py finished this video."""
    return (video_folder / TRANSCRIBED_LOCK_NAME).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Generic helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def human_size(num_bytes: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def run_command(cmd: List[str], timeout: Optional[int] = None) -> Tuple[bool, str, str]:
    """Run a command; return (ok, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        return False, "", f"executable not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "", f"command timed out after {timeout}s"
    except Exception as e:  # pragma: no cover
        return False, "", str(e)


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


# ─────────────────────────────────────────────────────────────────────────────
# ffprobe
# ─────────────────────────────────────────────────────────────────────────────

def probe_audio(path: Path) -> Optional[Dict[str, Any]]:
    """
    Return basic stream/format info via ffprobe, or None if ffprobe is missing
    or the file cannot be decoded.
    """
    if not tool_available("ffprobe"):
        return None
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,bit_rate,format_name",
        "-of", "json",
        str(path),
    ]
    ok, out, _ = run_command(cmd, timeout=120)
    if not ok:
        return None
    try:
        data = json.loads(out)
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        duration = float(fmt["duration"]) if fmt.get("duration") else None
        if duration is None or duration <= 0:
            return None
        return {
            "codec": stream.get("codec_name"),
            "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
            "channels": stream.get("channels"),
            "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
            "container": fmt.get("format_name"),
            "duration_sec": round(duration, 3),
        }
    except Exception:
        return None


def expected_duration(video_folder: Path, video_id: str) -> Optional[float]:
    """Duration from the yt-dlp metadata saved by the fetch script, if present."""
    meta_path = video_folder / f"{video_id}_yt-dlp-metadata.json"
    if not meta_path.exists():
        return None
    try:
        d = load_json(meta_path).get("duration")
        return float(d) if d else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Run metadata (failures log)
# ─────────────────────────────────────────────────────────────────────────────

def load_run_metadata(path: Path, folder: str, file: str, fmt: str, quality: str) -> Dict[str, Any]:
    if path.exists():
        try:
            meta = load_json(path)
            meta.setdefault("failures", [])
            return meta
        except Exception:
            print(f"  ⚠ Could not read {path.name}; starting a fresh one")
    return {
        "folder": folder,
        "file": file,
        "format": fmt,
        "audio_quality": quality,
        "downloaded_count": 0,
        "skipped_count": 0,
        "adopted_count": 0,
        "failed_count": 0,
        "last_run": None,
        "failures": [],
    }


def record_failure(meta: Dict[str, Any], idx: int, video_id: str, reason: str) -> None:
    """Add/replace the failure entry for a video (one entry per video)."""
    meta["failures"] = [f for f in meta["failures"] if f.get("video_id") != video_id]
    meta["failures"].append({
        "index": idx,
        "video_id": video_id,
        "reason": reason[:1000],
        "time": now_iso(),
    })


def clear_failure(meta: Dict[str, Any], video_id: str) -> None:
    meta["failures"] = [f for f in meta["failures"] if f.get("video_id") != video_id]


# ─────────────────────────────────────────────────────────────────────────────
# Download logic
# ─────────────────────────────────────────────────────────────────────────────

def write_info_and_lock(video_folder: Path, video_id: str, audio_file: Path,
                        fmt_requested: str, quality: str, adopted: bool) -> Dict[str, Any]:
    probe = probe_audio(audio_file)
    info = {
        "video_id": video_id,
        "file": audio_file.name,
        "format_requested": fmt_requested,
        "audio_quality": quality,
        "extension": audio_file.suffix.lstrip(".").lower(),
        "size_bytes": audio_file.stat().st_size,
        "downloaded_at": now_iso(),
        "adopted_existing_file": adopted,
        "yt_dlp_version": _yt_dlp_version(),
    }
    if probe:
        info.update(probe)
    exp = expected_duration(video_folder, video_id)
    if exp:
        info["expected_duration_sec"] = exp
        if probe and probe.get("duration_sec"):
            info["duration_mismatch"] = abs(probe["duration_sec"] - exp) > max(5.0, 0.05 * exp)
    save_json(get_audio_info_path(video_folder, video_id), info)
    get_audio_lock(video_folder).touch()
    return info


_YT_DLP_VERSION_CACHE: Optional[str] = None
_JS_RUNTIME_ARGS_CACHE: Optional[List[str]] = None


def js_runtime_args() -> List[str]:
    """
    yt-dlp needs a JavaScript runtime to solve YouTube's signature challenges; without one
    media URLs frequently return HTTP 403. Only deno is enabled by default, so when deno is
    absent but node is installed (e.g. via nvm) we pass --js-runtimes node explicitly.
    """
    global _JS_RUNTIME_ARGS_CACHE
    if _JS_RUNTIME_ARGS_CACHE is None:
        args: List[str] = []
        if not tool_available("deno"):
            for rt in ("node", "bun", "quickjs"):
                path = shutil.which(rt)
                if path:
                    ok, out, _ = run_command(["yt-dlp", "--help"], timeout=30)
                    if ok and "--js-runtimes" in out:
                        args = ["--js-runtimes", f"{rt}:{path}"]
                    break
        _JS_RUNTIME_ARGS_CACHE = args
    return _JS_RUNTIME_ARGS_CACHE


def _yt_dlp_version() -> Optional[str]:
    global _YT_DLP_VERSION_CACHE
    if _YT_DLP_VERSION_CACHE is None:
        ok, out, _ = run_command(["yt-dlp", "--version"], timeout=30)
        _YT_DLP_VERSION_CACHE = out.strip() if ok else "unknown"
    return _YT_DLP_VERSION_CACHE


def clean_partial_files(audio_dir: Path, video_id: str) -> None:
    """Remove leftover .part/.ytdl files for a video."""
    if not audio_dir.is_dir():
        return
    for p in audio_dir.glob(f"{video_id}{AUDIO_FILE_STEM_SUFFIX}.*"):
        if p.name.endswith(".part") or p.suffix in {".ytdl", ".tmp"}:
            try:
                p.unlink()
            except OSError:
                pass


def remove_if_empty(folder: Path) -> None:
    """Remove a directory if it exists and contains nothing (including hidden files)."""
    try:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    except OSError:
        pass


def reset_audio_dir(video_folder: Path) -> None:
    """Delete the whole audio dir (used by --force-rewrite)."""
    audio_dir = get_audio_dir(video_folder)
    if audio_dir.exists():
        shutil.rmtree(audio_dir)


def build_yt_dlp_cmd(video_id: str, audio_dir: Path, fmt: str, quality: str,
                     cookies: Optional[str], cookies_from_browser: Optional[str],
                     extra_args: List[str]) -> List[str]:
    output_template = str(audio_dir / f"{video_id}{AUDIO_FILE_STEM_SUFFIX}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", fmt,
        "--audio-quality", quality,
        "--no-playlist",
        "--no-progress",
        "--no-warnings",
        "--retries", "3",
        "--fragment-retries", "3",
        "-o", output_template,
    ]
    cmd += js_runtime_args()
    if cookies:
        cmd += ["--cookies", cookies]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd += extra_args
    cmd += ["--", video_id]  # "--" protects IDs that start with a dash
    return cmd


def download_one(video_id: str, video_folder: Path, fmt: str, quality: str,
                 cookies: Optional[str], cookies_from_browser: Optional[str],
                 extra_args: List[str], timeout: int) -> Tuple[bool, str]:
    """Run yt-dlp for one video. Returns (ok, error_message)."""
    audio_dir = get_audio_dir(video_folder)
    audio_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_yt_dlp_cmd(video_id, audio_dir, fmt, quality, cookies, cookies_from_browser, extra_args)
    ok, _, err = run_command(cmd, timeout=timeout)
    if not ok:
        msg = err.strip().splitlines()
        last = (msg[-1] if msg else "yt-dlp failed with no stderr")[:500]
        if "403" in last:
            last += ("  [hint: HTTP 403 from YouTube usually means yt-dlp is outdated or lacks a JS runtime; "
                     "run: python3 -m pip install -U yt-dlp]")
        return False, last
    if find_audio_file(video_folder, video_id) is None:
        return False, "yt-dlp reported success but no audio file was produced"
    return True, ""


def process_video(video_id: str, idx: int, dataset_path: Path, meta: Dict[str, Any], *,
                  fmt: str, quality: str, force_rewrite: bool, max_retries: int,
                  cookies: Optional[str], cookies_from_browser: Optional[str],
                  extra_args: List[str], timeout: int, dry_run: bool) -> str:
    """
    Returns one of: 'skipped', 'adopted', 'downloaded', 'failed', 'pending' (dry-run).
    """
    video_folder = dataset_path / video_id
    audio_dir = get_audio_dir(video_folder)
    lock = get_audio_lock(video_folder)

    # 1. Fast path: already complete
    if not force_rewrite and is_audio_downloaded(video_folder, video_id):
        print(f"  [{idx}] {video_id} - ✓ Audio already downloaded (lock file found)")
        return "skipped"

    if force_rewrite and audio_dir.exists():
        print(f"  [{idx}] {video_id} - ⚠ Force rewrite: removing existing audio folder")
        if not dry_run:
            reset_audio_dir(video_folder)

    # 2. Lock present but file missing → stale lock, redo
    if lock.exists() and not force_rewrite:
        print(f"  [{idx}] {video_id} - ⚠ Lock file without audio file; re-downloading")
        if not dry_run:
            lock.unlink()

    # 3. File present but no lock → verify and adopt (or discard if corrupt)
    existing = find_audio_file(video_folder, video_id) if not force_rewrite else None
    if existing is not None:
        probe = probe_audio(existing)
        if probe or not tool_available("ffprobe"):
            print(f"  [{idx}] {video_id} - ✓ Found existing audio without lock; adopting {existing.name}")
            if not dry_run:
                write_info_and_lock(video_folder, video_id, existing, fmt, quality, adopted=True)
                clear_failure(meta, video_id)
            return "adopted"
        print(f"  [{idx}] {video_id} - ⚠ Existing audio file is unreadable; deleting and re-downloading")
        if not dry_run:
            existing.unlink()

    if dry_run:
        print(f"  [{idx}] {video_id} - ○ Would download ({fmt})")
        return "pending"

    # 4. Download with retries
    video_folder.mkdir(parents=True, exist_ok=True)
    last_err = ""
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            wait = min(2 ** attempt, 60)
            print(f"      ⏳ Retry {attempt}/{max_retries} after {wait}s...")
            time.sleep(wait)
        print(f"  [{idx}] {video_id} - → Downloading audio ({fmt})...", end=" ", flush=True)
        t0 = time.time()
        ok, err = download_one(video_id, video_folder, fmt, quality, cookies, cookies_from_browser, extra_args, timeout)
        if ok:
            audio_file = find_audio_file(video_folder, video_id)
            info = write_info_and_lock(video_folder, video_id, audio_file, fmt, quality, adopted=False)
            clear_failure(meta, video_id)
            dur = info.get("duration_sec")
            dur_txt = f", {human_duration(dur)}" if dur else ""
            warn = "  ⚠ duration mismatch vs metadata" if info.get("duration_mismatch") else ""
            print(f"✓ {audio_file.name} ({human_size(info['size_bytes'])}{dur_txt}, {time.time() - t0:.0f}s){warn}")
            return "downloaded"
        last_err = err
        print(f"✗ {err}")

    clean_partial_files(audio_dir, video_id)
    remove_if_empty(audio_dir)
    remove_if_empty(video_folder)  # only removes a folder this run created and left empty
    record_failure(meta, idx, video_id, last_err or "unknown error")
    return "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Status report
# ─────────────────────────────────────────────────────────────────────────────

def report_status(dataset_path: Path, video_ids: Optional[List[str]]) -> int:
    """Scan the dataset folder and summarise audio coverage."""
    if not dataset_path.is_dir():
        print(f"Error: dataset folder not found: {dataset_path}")
        return 1

    if video_ids is None:
        folders = sorted(d for d in dataset_path.iterdir() if d.is_dir() and not d.name.startswith("."))
        scope = "all video folders in dataset"
    else:
        folders = [dataset_path / v for v in video_ids]
        scope = "videos in the selected input"

    total = len(folders)
    done = adopted_candidates = stale_lock = partial = 0
    total_bytes = 0
    total_dur = 0.0
    ext_counter: Dict[str, int] = {}
    done_transcribed = 0
    transcribed = 0
    for vf in folders:
        vid = vf.name
        if has_transcript(vf):
            transcribed += 1
        lock = get_audio_lock(vf).exists()
        af = find_audio_file(vf, vid)
        if lock and af is not None:
            done += 1
            total_bytes += af.stat().st_size
            ext_counter[af.suffix.lstrip(".").lower()] = ext_counter.get(af.suffix.lstrip(".").lower(), 0) + 1
            if has_transcript(vf):
                done_transcribed += 1
            info_path = get_audio_info_path(vf, vid)
            if info_path.exists():
                try:
                    total_dur += float(load_json(info_path).get("duration_sec") or 0)
                except Exception:
                    pass
        elif af is not None:
            adopted_candidates += 1
        elif lock:
            stale_lock += 1
        audio_dir = get_audio_dir(vf)
        if audio_dir.is_dir() and any(p.name.endswith(".part") for p in audio_dir.iterdir()):
            partial += 1

    print("=" * 60)
    print("AUDIO STATUS")
    print("=" * 60)
    print(f"Scope                          : {scope}")
    print(f"Video folders                  : {total}")
    print(f"  with transcript (.lock)      : {transcribed}")
    print(f"Audio downloaded (complete)    : {done}   ({done_transcribed} of them have a transcript)")
    print(f"Audio pending                  : {total - done}")
    if adopted_candidates:
        print(f"  file present, lock missing   : {adopted_candidates}  (will be adopted on next run)")
    if stale_lock:
        print(f"  lock present, file missing   : {stale_lock}  (will be re-downloaded on next run)")
    if partial:
        print(f"  partial downloads (.part)    : {partial}  (yt-dlp will resume them)")
    if ext_counter:
        print(f"Formats                        : " + ", ".join(f"{k}={v}" for k, v in sorted(ext_counter.items())))
    print(f"Total audio size               : {human_size(total_bytes)}")
    if total_dur:
        print(f"Total audio duration           : {human_duration(total_dur)}")
    print("=" * 60)
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download YouTube audio for dataset videos into dataset/<video_id>/audio/ (idempotent).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--folder", default="saved-data",
                   help="Folder containing the input JSON and the dataset/ directory (default: saved-data)")
    p.add_argument("--file", default="filtered-results.json",
                   help="JSON file with video entries (needs a 'videoId' key) (default: filtered-results.json)")
    p.add_argument("--format", default=DEFAULT_FORMAT, choices=SUPPORTED_FORMATS,
                   help=f"Audio container/codec passed to yt-dlp --audio-format (default: {DEFAULT_FORMAT}). "
                        "'best' keeps the source codec without re-encoding.")
    p.add_argument("--audio-quality", default=DEFAULT_AUDIO_QUALITY,
                   help="yt-dlp --audio-quality: 0 (best) to 9 (worst) for VBR, or a bitrate like 128K "
                        f"(default: {DEFAULT_AUDIO_QUALITY}, yt-dlp's default)")
    p.add_argument("--first-n", type=int, default=None,
                   help="Only consider the first N entries of the input file")
    p.add_argument("--video-ids", type=str, default=None,
                   help="Comma-separated video IDs to process instead of the input file "
                        "(folders are created if missing)")
    p.add_argument("--only-transcribed", action="store_true",
                   help="Only download audio for videos whose transcription step completed (dataset/<id>/.lock exists)")
    p.add_argument("--force-rewrite", action="store_true",
                   help="Delete existing audio folders and download again")
    p.add_argument("--delay", type=float, default=5.0,
                   help="Seconds to wait between actual downloads (default: 5)")
    p.add_argument("--max-retries", type=int, default=2,
                   help="Attempts per video before recording a failure (default: 2)")
    p.add_argument("--timeout", type=int, default=1800,
                   help="Per-attempt yt-dlp timeout in seconds (default: 1800)")
    p.add_argument("--cookies", type=str, default=None,
                   help="Path to a Netscape cookies file passed to yt-dlp (helps with sign-in walls)")
    p.add_argument("--cookies-from-browser", type=str, default=None,
                   help="Browser name passed to yt-dlp --cookies-from-browser (e.g. firefox, chrome)")
    p.add_argument("--yt-dlp-arg", action="append", default=[], metavar="ARG",
                   help="Extra raw argument forwarded to yt-dlp (repeatable), e.g. --yt-dlp-arg=--limit-rate --yt-dlp-arg=1M")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be downloaded without downloading anything")
    p.add_argument("--status", action="store_true",
                   help="Print audio coverage for the dataset and exit")
    return p.parse_args()


def select_video_ids(args: argparse.Namespace, folder_path: Path) -> Tuple[List[str], str]:
    """Resolve the list of video IDs to process and a description of the source."""
    if args.video_ids:
        ids = [v.strip() for v in args.video_ids.split(",") if v.strip()]
        return ids, f"--video-ids ({len(ids)} ids)"

    results_path = folder_path / args.file
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        sys.exit(1)
    entries = load_json(results_path)
    ids: List[str] = []
    seen = set()
    for e in entries:
        vid = e.get("videoId") if isinstance(e, dict) else None
        if vid and vid not in seen:
            seen.add(vid)
            ids.append(vid)
    if args.first_n is not None:
        ids = ids[: args.first_n]
    return ids, str(results_path)


def main() -> int:
    args = parse_args()

    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path.cwd() / folder_path
    dataset_path = folder_path / "dataset"
    run_meta_path = folder_path / RUN_METADATA_NAME

    if args.status:
        ids = None
        if args.video_ids or args.first_n is not None or args.only_transcribed:
            ids, _ = select_video_ids(args, folder_path)
            if args.only_transcribed:
                ids = [v for v in ids if has_transcript(dataset_path / v)]
        return report_status(dataset_path, ids)

    if not tool_available("yt-dlp"):
        print("Error: yt-dlp not found. Install with: python3 -m pip install -U yt-dlp")
        return 1
    if args.format != "best" and not tool_available("ffmpeg"):
        print("Error: ffmpeg is required to convert audio to", args.format)
        return 1
    if not tool_available("ffprobe"):
        print("⚠ ffprobe not found: existing files will be adopted without validation and no duration info is recorded")

    video_ids, source_desc = select_video_ids(args, folder_path)
    dataset_path.mkdir(parents=True, exist_ok=True)

    if args.only_transcribed:
        before = len(video_ids)
        video_ids = [v for v in video_ids if has_transcript(dataset_path / v)]
        print(f"--only-transcribed: {len(video_ids)} of {before} videos have a transcript")

    print(f"Input        : {source_desc}")
    print(f"Videos       : {len(video_ids)}")
    print(f"Dataset path : {dataset_path}")
    print(f"Output       : dataset/<video_id>/{AUDIO_DIR_NAME}/<video_id>{AUDIO_FILE_STEM_SUFFIX}.{args.format if args.format != 'best' else '<ext>'}")
    print(f"Format       : {args.format} (quality {args.audio_quality})")
    print(f"yt-dlp       : {_yt_dlp_version()}" + (f"  (JS runtime: {' '.join(js_runtime_args()[1:])})" if js_runtime_args() else "  (no JS runtime found: install deno or node if downloads return 403)"))
    if args.dry_run:
        print("Mode         : DRY RUN (nothing will be downloaded)")
    print()

    meta = load_run_metadata(run_meta_path, args.folder, args.file, args.format, args.audio_quality)
    meta.update({"format": args.format, "audio_quality": args.audio_quality, "last_run": now_iso()})

    counts = {"downloaded": 0, "skipped": 0, "adopted": 0, "failed": 0, "pending": 0}
    total = len(video_ids)
    t_start = time.time()

    try:
        for idx, video_id in enumerate(video_ids):
            status = process_video(
                video_id, idx, dataset_path, meta,
                fmt=args.format, quality=args.audio_quality,
                force_rewrite=args.force_rewrite, max_retries=args.max_retries,
                cookies=args.cookies, cookies_from_browser=args.cookies_from_browser,
                extra_args=args.yt_dlp_arg, timeout=args.timeout, dry_run=args.dry_run,
            )
            counts[status] += 1

            if not args.dry_run:
                meta["downloaded_count"] = counts["downloaded"]
                meta["skipped_count"] = counts["skipped"]
                meta["adopted_count"] = counts["adopted"]
                meta["failed_count"] = counts["failed"]
                save_json(run_meta_path, meta)

            if status in ("downloaded", "failed") and idx < total - 1 and args.delay > 0:
                time.sleep(args.delay)

            if (idx + 1) % 25 == 0 or idx == total - 1:
                pct = (idx + 1) / total * 100 if total else 100.0
                print(f"\n>>> {idx + 1}/{total} ({pct:.1f}%) | downloaded: {counts['downloaded']}, "
                      f"skipped: {counts['skipped']}, adopted: {counts['adopted']}, failed: {counts['failed']}"
                      + (f", pending: {counts['pending']}" if args.dry_run else "") + "\n")
    except KeyboardInterrupt:
        if not args.dry_run:
            save_json(run_meta_path, meta)
        print("\n\nInterrupted! Progress is tracked via lock files; re-run the same command to resume.")
        return 130

    elapsed = time.time() - t_start
    print("=" * 60)
    print("Audio download complete!" if not args.dry_run else "Dry run complete!")
    print(f"  Videos considered      : {total}")
    if args.dry_run:
        print(f"  Would download         : {counts['pending']}")
    else:
        print(f"  Newly downloaded       : {counts['downloaded']}")
    print(f"  Already present        : {counts['skipped']}")
    print(f"  Adopted existing files : {counts['adopted']}")
    print(f"  Failed                 : {counts['failed']}")
    print(f"  Elapsed                : {human_duration(elapsed)}")
    if not args.dry_run:
        print(f"  Run log                : {run_meta_path}")
        if meta["failures"]:
            print(f"\n  {len(meta['failures'])} failure(s) in the run log (a failed video has no lock file, "
                  f"so it is retried automatically whenever it is included in a run):")
            for f in meta["failures"][-10:]:
                print(f"    [{f['index']}] {f['video_id']}: {f['reason'][:120]}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
