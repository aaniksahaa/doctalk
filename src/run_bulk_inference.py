#!/usr/bin/env python3
"""
Bulk experiment runner for downstream inference.

Runs infer_downstream.py across a Cartesian product of
(tasks × settings × model/provider pairs).

Configure the MODELS and SETTINGS arrays below, then run:

  python run_bulk_inference.py --tasks medical-ner --split test --batch-size 5
  python run_bulk_inference.py --tasks "medical-ner;triage" --split test --batch-size 3 --force-rewrite
  python run_bulk_inference.py --tasks "advice-safety;advice-generation" --split test --first-n 10

All CLI arguments that infer_downstream.py accepts (except --model, --provider,
--setting, --standard-model-name, --tasks) are forwarded automatically.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


from constants import C

# ── Configuration ─────────────────────────────────────────────────────────────
# Each entry: { "provider": ..., "model": ..., "standard_model_name": ... }
# "standard_model_name" is optional — if omitted, infer_downstream derives it.

MODELS = [
    {
        "provider": "openai",
        "model": "gpt-4o",
    },
    # {
    #     "provider": "openai",
    #     "model": "gpt-5-mini-2025-08-07",
    #     "standard_model_name": "gpt-5-mini",
    # },
    # {
    #     "provider": "openai",
    #     "model": "gpt-4o-mini",
    # },
    # Example with standard_model_name override:
    # {
    #     "provider": "openrouter",
    #     "model": "openai/gpt-4o",
    #     "standard_model_name": "gpt-4o",
    # },
]

SETTINGS = [
    "zero-shot",
    "few-shot",
]

VALID_TASKS = ["medical-ner", "advice-safety", "advice-generation", "triage"]
ALL_TASKS_STR = ";".join(VALID_TASKS)


def parse_tasks(tasks_str: str) -> list[str]:
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


# ── Script path ───────────────────────────────────────────────────────────────
INFER_SCRIPT = Path(__file__).parent / "infer_downstream.py"


def build_command(
    task: str,
    model_entry: dict,
    setting: str,
    extra_args: list[str],
) -> list[str]:
    """Build the subprocess command for a single inference run."""
    cmd = [
        sys.executable,
        str(INFER_SCRIPT),
        "--tasks", task,
        "--model", model_entry["model"],
        "--provider", model_entry["provider"],
        "--setting", setting,
    ]
    if "standard_model_name" in model_entry:
        cmd += ["--standard-model-name", model_entry["standard_model_name"]]
    cmd += extra_args
    return cmd


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Bulk experiment runner — runs infer_downstream.py across "
            "a Cartesian product of tasks × settings × model/provider pairs."
        ),
    )
    # Mirror the non-model/provider/setting args from infer_downstream.py
    parser.add_argument(
        "--tasks",
        type=str,
        required=True,
        help=(
            "Semicolon-separated list of downstream tasks. "
            f"Valid tasks: {', '.join(VALID_TASKS)}. "
            "Example: 'medical-ner;advice-safety;triage'"
        ),
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Data split (default: test)",
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
        help="Path to folder containing downstream-datasets (default: saved-data)",
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

    # Build the extra args list forwarded to infer_downstream.py
    # (task is passed per-run, not here)
    extra_args = [
        "--split", args.split,
        "--batch-size", str(args.batch_size),
        "--max-retries", str(args.max_retries),
        "--folder", args.folder,
        "--first-n", str(args.first_n),
    ]
    if args.force_rewrite:
        extra_args.append("--force-rewrite")
    # Forward sampling params if specified
    if args.temperature is not None:
        extra_args += ["--temperature", str(args.temperature)]
    if args.top_p is not None:
        extra_args += ["--top-p", str(args.top_p)]
    if args.top_k is not None:
        extra_args += ["--top-k", str(args.top_k)]
    if args.num_ctx is not None:
        extra_args += ["--num-ctx", str(args.num_ctx)]
    if args.num_predict is not None:
        extra_args += ["--num-predict", str(args.num_predict)]
    if args.repeat_penalty is not None:
        extra_args += ["--repeat-penalty", str(args.repeat_penalty)]

    # Build experiment grid: tasks × settings × models
    experiments = []
    for task in tasks:
        for setting in SETTINGS:
            for model_entry in MODELS:
                experiments.append((task, setting, model_entry))

    total = len(experiments)
    if total == 0:
        print(f"{C.YELLOW}No experiments to run. Check MODELS and SETTINGS arrays.{C.RESET}")
        sys.exit(0)

    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Bulk Inference Runner{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")
    print(f"  {C.BOLD}Tasks{C.RESET}      : {C.MAGENTA}{', '.join(tasks)}{C.RESET}")
    print(f"  {C.BOLD}Split{C.RESET}      : {args.split}")
    print(f"  {C.BOLD}Settings{C.RESET}   : {C.YELLOW}{SETTINGS}{C.RESET}")
    print(f"  {C.BOLD}Models{C.RESET}     : {C.CYAN}{len(MODELS)}{C.RESET}")
    print(f"  {C.BOLD}Experiments{C.RESET}: {C.BOLD}{total}{C.RESET} (tasks × settings × models)")
    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")
    print()

    completed = 0
    failed = 0
    results = []  # (task, setting, model, provider, status, elapsed)

    for i, (task, setting, model_entry) in enumerate(experiments, start=1):
        model_label = model_entry.get(
            "standard_model_name",
            model_entry["model"],
        )
        provider = model_entry["provider"]

        print(f"{C.BOLD}{C.BLUE}{'-' * 60}{C.RESET}")
        print(
            f"  {C.BOLD}[{i}/{total}]{C.RESET} "
            f"task={C.MAGENTA}{task}{C.RESET}  "
            f"setting={C.YELLOW}{setting}{C.RESET}  "
            f"model={C.CYAN}{model_label}{C.RESET}  "
            f"provider={C.BLUE}{provider}{C.RESET}"
        )
        print(f"{C.BOLD}{C.BLUE}{'-' * 60}{C.RESET}")

        cmd = build_command(task, model_entry, setting, extra_args)

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                check=True,
            )
            elapsed = time.time() - start_time
            completed += 1
            results.append((task, setting, model_label, provider, "OK", elapsed))
            print(
                f"  {C.GREEN}{C.BOLD}✓ [{i}/{total}]{C.RESET} "
                f"{C.GREEN}Completed in {elapsed:.1f}s{C.RESET}\n"
            )
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            failed += 1
            results.append(
                (task, setting, model_label, provider, f"FAIL (exit {e.returncode})", elapsed)
            )
            print(
                f"  {C.RED}{C.BOLD}✗ [{i}/{total}]{C.RESET} "
                f"{C.RED}Failed (exit code {e.returncode}) "
                f"after {elapsed:.1f}s{C.RESET}\n"
            )
        except KeyboardInterrupt:
            print(f"\n\n{C.YELLOW}{C.BOLD}⚠ Interrupted by user after {completed} experiments!{C.RESET}")
            break

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Summary{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")
    print(f"  {C.BOLD}Total{C.RESET}      : {total}")
    print(f"  {C.BOLD}Completed{C.RESET}  : {C.GREEN}{completed}{C.RESET}")
    print(f"  {C.BOLD}Failed{C.RESET}     : {C.RED}{failed}{C.RESET}")
    print(f"  {C.BOLD}Remaining{C.RESET}  : {C.YELLOW}{total - completed - failed}{C.RESET}")
    print()
    for task, setting, model, provider, status, elapsed in results:
        if status == "OK":
            status_str = f"{C.GREEN}{C.BOLD}{status}{C.RESET}"
        else:
            status_str = f"{C.RED}{C.BOLD}{status}{C.RESET}"
        print(
            f"  {status_str:<30s}  {C.MAGENTA}{task:<20s}{C.RESET}  "
            f"{C.YELLOW}{setting:<12s}{C.RESET}  "
            f"{C.CYAN}{model:<28s}{C.RESET}  {C.BLUE}{provider:<14s}{C.RESET}  "
            f"{C.DIM}{elapsed:.1f}s{C.RESET}"
        )
    print(f"{C.BOLD}{C.CYAN}{'=' * 60}{C.RESET}")


if __name__ == "__main__":
    main()
