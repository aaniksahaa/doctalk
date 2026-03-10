#!/usr/bin/env python3
"""
Run downstream inference on organized dataset splits.

Reads samples from downstream-datasets/<task>/split/<split>/, batches them,
sends to an LLM for inference using task- and setting-specific prompts,
and saves results back into each sample directory.

Output structure (per sample):
  <sample_dir>/
    inference/
      <setting>/          (e.g., zero-shot, few-shot)
        <model>/          (e.g., gemini-3-flash-preview, openai-gpt-4o-mini)
          output.json
          inference_metadata.json

Usage:
  python infer_downstream.py --tasks medical-ner --split test --model gemini-3-flash-preview --setting zero-shot
  python infer_downstream.py --tasks "advice-safety;triage" --split test --model gemini-2.5-flash --setting few-shot --batch-size 3
  python infer_downstream.py --tasks "medical-ner;advice-generation" --split test --model gemini-2.5-flash --setting zero-shot --force-rewrite
  python infer_downstream.py --tasks triage --split test --model gemini-3-flash-preview --setting few-shot --first-n 10
  python infer_downstream.py --tasks medical-ner --split test --model openai/gpt-4o --provider openrouter -s gpt-4o --setting zero-shot
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from llm import Provider, LLMOptions, InferenceMetadata, get_response


from constants import C


# ── Constants ────────────────────────────────────────────────────────────────

DOWNSTREAM_DATASETS_DIR = "downstream-datasets"
PROMPTS_DIR = Path(__file__).parent / "prompts"
INFERENCE_SUBDIR = "inference"
OUTPUT_FILE = "output.json"
INFERENCE_METADATA_FILE = "inference_metadata.json"

VALID_TASKS = ["medical-ner", "advice-safety", "advice-generation", "triage"]
ALL_TASKS_STR = ";".join(VALID_TASKS)
VALID_SPLITS = ["train", "val", "test"]


def parse_tasks(tasks_str: str) -> List[str]:
    """Parse semicolon-separated task string and validate each task."""
    tasks = [t.strip() for t in tasks_str.split(";") if t.strip()]
    for t in tasks:
        if t not in VALID_TASKS:
            print(
                f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} unknown task '{t}'. "
                f"Valid tasks: {', '.join(VALID_TASKS)}{C.RESET}"
            )
            sys.exit(1)
    return tasks

# Map task name → inference prompt subdirectory
TASK_PROMPT_DIR = {
    "medical-ner": "medical-ner-inference",
    "advice-safety": "advice-safety-inference",
    "advice-generation": "advice-generation-inference",
    "triage": "triage-inference",
}


# ── Prompt loading ───────────────────────────────────────────────────────────

def load_prompts(task: str, setting: str) -> Tuple[str, str]:
    """
    Load system.md and header.md for the given task and setting.

    Returns:
        (system_prompt, header_prompt) tuple
    """
    prompt_dir = PROMPTS_DIR / TASK_PROMPT_DIR[task] / setting

    system_path = prompt_dir / "system.md"
    header_path = prompt_dir / "header.md"

    if not system_path.exists():
        raise FileNotFoundError(f"System prompt not found: {system_path}")
    if not header_path.exists():
        raise FileNotFoundError(f"Header prompt not found: {header_path}")

    with open(system_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    with open(header_path, "r", encoding="utf-8") as f:
        header_prompt = f.read()

    return system_prompt, header_prompt


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_model_name(model: str) -> str:
    """Normalize model name for use as a directory name.

    If the model name contains a slash (e.g. 'openai/gpt-4o'),
    only the part after the last slash is used (e.g. 'gpt-4o').
    """
    if "/" in model:
        return model.rsplit("/", 1)[-1]
    return model


# ── Sample discovery & I/O ───────────────────────────────────────────────────

def discover_samples(split_dir: Path) -> List[Tuple[int, Path]]:
    """
    Discover all sample directories in a split.

    Returns list of (sample_number, sample_path) sorted by sample number.
    """
    samples = []
    for d in split_dir.iterdir():
        if d.is_dir() and d.name.isdigit():
            samples.append((int(d.name), d))
    return sorted(samples, key=lambda x: x[0])


def load_sample_input(sample_dir: Path) -> Dict[str, Any]:
    """Load input.json from a sample directory."""
    input_path = sample_dir / "input.json"
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_sample_processed(
    sample_dir: Path, setting: str, model: str,
    standard_model_name: str | None = None,
) -> bool:
    """Check if inference output already exists for this sample."""
    model_dir = standard_model_name or normalize_model_name(model)
    output_path = (
        sample_dir / INFERENCE_SUBDIR / setting / model_dir / OUTPUT_FILE
    )
    return output_path.exists()


def save_output(
    sample_dir: Path,
    setting: str,
    model: str,
    output: Dict[str, Any],
    standard_model_name: str | None = None,
    inference_metadata: InferenceMetadata | None = None,
    batch_size: int | None = None,
) -> None:
    """Save inference output and inference metadata to the sample directory."""
    effective_name = standard_model_name or normalize_model_name(model)
    output_dir = sample_dir / INFERENCE_SUBDIR / setting / effective_name
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / OUTPUT_FILE
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    metadata: Dict[str, Any] = {
        "model": effective_name,
        "setting": setting,
    }
    # Merge detailed inference metadata when available
    if inference_metadata is not None:
        meta_dict = inference_metadata.to_dict()
        # Per-sample share: divide batch-level token counts & cost evenly
        n = batch_size if batch_size and batch_size > 0 else 1
        metadata["provider"] = meta_dict.get("provider", "")
        metadata["model_id"] = meta_dict.get("model", "")
        metadata["input_tokens"] = meta_dict.get("input_tokens", 0)
        metadata["output_tokens"] = meta_dict.get("output_tokens", 0)
        metadata["total_tokens"] = meta_dict.get("total_tokens", 0)
        metadata["input_tokens_per_sample"] = round(meta_dict.get("input_tokens", 0) / n, 1)
        metadata["output_tokens_per_sample"] = round(meta_dict.get("output_tokens", 0) / n, 1)
        metadata["total_tokens_per_sample"] = round(meta_dict.get("total_tokens", 0) / n, 1)
        metadata["inference_time_seconds"] = meta_dict.get("inference_time_seconds", 0.0)
        metadata["inference_time_per_sample_seconds"] = round(
            meta_dict.get("inference_time_seconds", 0.0) / n, 3
        )
        metadata["cost_usd"] = meta_dict.get("cost_usd", 0.0)
        metadata["cost_usd_per_sample"] = round(meta_dict.get("cost_usd", 0.0) / n, 6)
        metadata["batch_size"] = n
        metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

    metadata_path = output_dir / INFERENCE_METADATA_FILE
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


# ── Batching ─────────────────────────────────────────────────────────────────

def batch_items(
    items: List[Any], batch_size: int
) -> List[List[Any]]:
    """Split items into batches of at most batch_size."""
    return [
        items[i : i + batch_size]
        for i in range(0, len(items), batch_size)
    ]


# ── LLM inference ───────────────────────────────────────────────────────────

def run_inference_on_batch(
    model: str,
    system_prompt: str,
    header_prompt: str,
    batch_inputs: List[Dict[str, Any]],
    max_retries: int = 2,
    provider: str = None,
    options: LLMOptions = None,
) -> Tuple[List[Dict[str, Any]], InferenceMetadata]:
    """
    Send a batch of inputs to the LLM for inference.

    Constructs prompt by appending the JSON-encoded batch array after the
    header prompt. Uses system.md as the system prompt. Returns the parsed
    JSON array from the LLM response.

    Retries up to max_retries times on parse failures.

    Args:
        model: LLM model name
        system_prompt: System prompt text
        header_prompt: Header/task prompt text
        batch_inputs: List of input dicts (one per sample)
        max_retries: Max retries on parse failure
        provider: LLM provider (auto-detected if None)
        options: LLM inference options (sampling params etc.)

    Returns:
        Tuple of (results, metadata) where results is a list of output dicts
        (one per sample, same order as input) and metadata is the
        InferenceMetadata from the successful LLM call.
    """
    input_json = json.dumps(batch_inputs, ensure_ascii=False, indent=2)
    prompt = header_prompt + input_json

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = get_response(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                provider=provider,
                options=options,
            )

            raw = response.content.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                # Remove first line (```json or ```) and last line (```)
                start = 1
                end = len(lines)
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip() == "```":
                        end = i
                        break
                raw = "\n".join(lines[start:end])

            result = json.loads(raw)

            # Some models return a single object for batch of 1
            if isinstance(result, dict):
                result = [result]

            if not isinstance(result, list):
                raise ValueError(
                    f"Expected JSON array, got {type(result).__name__}"
                )

            if len(result) != len(batch_inputs):
                raise ValueError(
                    f"Expected {len(batch_inputs)} results, "
                    f"got {len(result)}"
                )

            return result, response.metadata

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(
                    f"    \033[93m⚠ Attempt {attempt}/{max_retries} failed: "
                    f"{e}, retrying...\033[0m"
                )

    raise Exception(
        f"Failed to get valid response after {max_retries} attempts: "
        f"{last_error}"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run downstream inference on organized dataset splits "
            "using LLM"
        ),
    )
    parser.add_argument(
        "--tasks",
        type=str,
        required=True,
        help=(
            "Semicolon-separated list of downstream tasks to infer on. "
            f"Valid tasks: {', '.join(VALID_TASKS)}. "
            "Example: 'medical-ner;advice-safety;triage'"
        ),
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=VALID_SPLITS,
        help="Data split to infer on (default: test)",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help=(
            "Model name for LLM inference "
            "(e.g., gemini-3-flash-preview, openai/gpt-4o-mini)"
        ),
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=[p.value for p in Provider],
        help=(
            "LLM provider (auto-detected from model name if not specified). "
            "e.g., google, openrouter, ollama"
        ),
    )
    parser.add_argument(
        "--setting",
        type=str,
        required=True,
        help="Inference setting (e.g., zero-shot, few-shot)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of samples per LLM batch (default: 5)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retries per batch on parse failure (default: 2)",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="saved-data",
        help=(
            "Path to folder containing downstream-datasets "
            "(default: saved-data)"
        ),
    )
    parser.add_argument(
        "-s",
        "--standard-model-name",
        type=str,
        default=None,
        help=(
            "Override the model name used for output directories and "
            "metadata. When set, this name is used instead of the "
            "auto-derived name from --model. Useful when the same "
            "logical model is accessed via different providers."
        ),
    )
    parser.add_argument(
        "--force-rewrite",
        action="store_true",
        help="Overwrite existing inference outputs",
    )
    parser.add_argument(
        "--first-n",
        type=int,
        default=-1,
        help="Only process the first N samples; -1 means all (default: -1)",
    )

    # ── Sampling / LLM option overrides ──
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (default: 0.1). Ignored for reasoning models.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help="Top-p (nucleus) sampling (default: 0.9)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Top-k sampling. Not supported by all providers (default: None)",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="Context window size (default: 32768, Ollama only)",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=None,
        help="Max tokens to generate (default: 16384)",
    )
    parser.add_argument(
        "--repeat-penalty",
        type=float,
        default=None,
        help="Repetition penalty (default: 1.1)",
    )

    args = parser.parse_args()

    # ── parse tasks ──
    tasks = parse_tasks(args.tasks)

    # ── build LLMOptions from CLI overrides ──
    llm_opts_kwargs = {}
    if args.temperature is not None:
        llm_opts_kwargs["temperature"] = args.temperature
    if args.top_p is not None:
        llm_opts_kwargs["top_p"] = args.top_p
    if args.top_k is not None:
        llm_opts_kwargs["top_k"] = args.top_k
    if args.num_ctx is not None:
        llm_opts_kwargs["num_ctx"] = args.num_ctx
    if args.num_predict is not None:
        llm_opts_kwargs["num_predict"] = args.num_predict
    if args.repeat_penalty is not None:
        llm_opts_kwargs["repeat_penalty"] = args.repeat_penalty

    llm_options = LLMOptions(**llm_opts_kwargs) if llm_opts_kwargs else None

    for task_idx, task_name in enumerate(tasks):
        if task_idx > 0:
            print()  # blank line between tasks
        run_task(task_name, args, llm_options=llm_options)


def run_task(task_name: str, args, llm_options: LLMOptions = None) -> None:
    """Run inference for a single task."""
    # ── validate setting directory exists ──
    setting_prompt_dir = (
        PROMPTS_DIR / TASK_PROMPT_DIR[task_name] / args.setting
    )
    if not setting_prompt_dir.exists():
        available = [
            d.name
            for d in (PROMPTS_DIR / TASK_PROMPT_DIR[task_name]).iterdir()
            if d.is_dir()
        ]
        print(
            f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} setting '{args.setting}' not found "
            f"for task '{task_name}'{C.RESET}"
        )
        print(f"  Available settings: {', '.join(sorted(available))}")
        return

    # ── resolve paths ──
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = Path(__file__).parent / folder_path

    split_dir = (
        folder_path
        / DOWNSTREAM_DATASETS_DIR
        / task_name
        / "split"
        / args.split
    )

    if not split_dir.exists():
        print(f"{C.RED}{C.BOLD}Error:{C.RESET}{C.RED} split directory not found: {split_dir}{C.RESET}")
        return

    # ── load prompts ──
    system_prompt, header_prompt = load_prompts(task_name, args.setting)

    # ── discover samples ──
    all_samples = discover_samples(split_dir)

    if not all_samples:
        print(f"{C.YELLOW}No samples found in {split_dir}{C.RESET}")
        return

    # ── resolve effective model name for dirs/metadata ──
    effective_model_name = (
        args.standard_model_name or normalize_model_name(args.model)
    )

    # ── filter already-processed samples (unless --force-rewrite) ──
    if args.force_rewrite:
        samples = all_samples
    else:
        samples = [
            (idx, path)
            for idx, path in all_samples
            if not is_sample_processed(
                path, args.setting, args.model,
                standard_model_name=args.standard_model_name,
            )
        ]

    already_done = len(all_samples) - len(samples)

    # ── apply --first-n limit ──
    total_pending = len(samples)
    if args.first_n > 0:
        samples = samples[: args.first_n]

    print(f"{C.BOLD}{C.CYAN}{'─' * 50}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Downstream Inference{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'─' * 50}{C.RESET}")
    print(f"  {C.BOLD}Task{C.RESET}         : {C.MAGENTA}{task_name}{C.RESET}")
    print(f"  {C.BOLD}Split{C.RESET}        : {args.split}")
    print(f"  {C.BOLD}Model{C.RESET}        : {C.CYAN}{args.model}{C.RESET}")
    print(f"  {C.BOLD}Model (dir){C.RESET}  : {C.CYAN}{effective_model_name}{C.RESET}")
    print(f"  {C.BOLD}Provider{C.RESET}     : {C.BLUE}{args.provider or 'auto-detect'}{C.RESET}")
    print(f"  {C.BOLD}Setting{C.RESET}      : {C.YELLOW}{args.setting}{C.RESET}")
    print(f"  {C.BOLD}Batch size{C.RESET}   : {args.batch_size}")
    print(f"  {C.BOLD}Max retries{C.RESET}  : {args.max_retries}")
    print(f"  {C.BOLD}Split dir{C.RESET}    : {C.DIM}{split_dir}{C.RESET}")
    print(f"  {C.BOLD}Total samples{C.RESET}: {len(all_samples)}")
    print(f"  {C.BOLD}Already done{C.RESET} : {C.GREEN}{already_done}{C.RESET}")
    print(
        f"  {C.BOLD}To process{C.RESET}   : {C.YELLOW}{len(samples)}{C.RESET}"
        f"{f' (limited from {total_pending})' if args.first_n > 0 else ''}"
    )
    print(f"{C.BOLD}{C.CYAN}{'─' * 50}{C.RESET}")
    print()

    if not samples:
        print(f"{C.GREEN}{C.BOLD}✓ All samples already processed!{C.RESET}")
        return

    # ── batch & process ──
    batches = batch_items(samples, args.batch_size)
    total_success = 0
    total_failed = 0

    try:
        for batch_idx, batch in enumerate(batches):
            sample_ids = [idx for idx, _ in batch]
            print(
                f"  {C.BOLD}{C.BLUE}Batch {batch_idx + 1}/{len(batches)}{C.RESET} "
                f"{C.DIM}(samples: {sample_ids}){C.RESET}"
            )

            # Load inputs for this batch
            batch_inputs: List[Dict[str, Any]] = []
            batch_paths: List[Tuple[int, Path]] = []
            for idx, sample_dir in batch:
                try:
                    inp = load_sample_input(sample_dir)
                    batch_inputs.append(inp)
                    batch_paths.append((idx, sample_dir))
                except Exception as e:
                    print(
                        f"    {C.YELLOW}⚠ Failed to load input for "
                        f"sample {idx}: {e}{C.RESET}"
                    )
                    total_failed += 1

            if not batch_inputs:
                continue

            # Run inference
            try:
                results, inference_meta = run_inference_on_batch(
                    model=args.model,
                    system_prompt=system_prompt,
                    header_prompt=header_prompt,
                    batch_inputs=batch_inputs,
                    max_retries=args.max_retries,
                    provider=args.provider,
                    options=llm_options,
                )

                # Save individual outputs
                for (idx, sample_dir), output in zip(batch_paths, results):
                    save_output(
                        sample_dir, args.setting, args.model, output,
                        standard_model_name=args.standard_model_name,
                        inference_metadata=inference_meta,
                        batch_size=len(batch_inputs),
                    )
                    total_success += 1

                print(f"    {C.GREEN}✓ Saved {len(results)} outputs{C.RESET}")

            except Exception as e:
                print(f"    {C.RED}✗ Batch failed: {e}{C.RESET}")
                total_failed += len(batch_inputs)

    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}{C.BOLD}⚠ Interrupted by user!{C.RESET}")
        print(f"  Completed so far: {C.GREEN}{total_success}{C.RESET}")
        print(f"  Failed so far   : {C.RED}{total_failed}{C.RESET}")
        sys.exit(1)

    # ── final summary ──
    print(f"\n{C.BOLD}{C.GREEN}✓ Inference complete!{C.RESET}")
    print(f"  {C.BOLD}Task{C.RESET}       : {C.MAGENTA}{task_name}{C.RESET}")
    print(f"  {C.BOLD}Split{C.RESET}      : {args.split}")
    print(f"  {C.BOLD}Model{C.RESET}      : {C.CYAN}{args.model}{C.RESET}")
    print(f"  {C.BOLD}Model (dir){C.RESET}: {C.CYAN}{effective_model_name}{C.RESET}")
    print(f"  {C.BOLD}Setting{C.RESET}    : {C.YELLOW}{args.setting}{C.RESET}")
    print(f"  {C.BOLD}Success{C.RESET}    : {C.GREEN}{total_success}{C.RESET}")
    print(f"  {C.BOLD}Failed{C.RESET}     : {C.RED}{total_failed}{C.RESET}")
    print(f"  {C.BOLD}Skipped{C.RESET}    : {C.DIM}{already_done}{C.RESET}")


if __name__ == "__main__":
    main()
