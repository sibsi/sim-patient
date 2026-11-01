"""Evaluate saved 16-turn frozen interviews without regenerating patient replies."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.judge import evaluate, prepare_input
from evaluation.reporting import write_reports
from llm_backend import HFBackend, LLMBackend, utc_now
from runner import create_batch_directory, environment_info, safe_name, snapshot


def find_runs(path):
    path = path.resolve()
    if (path / "conversation.json").is_file():
        return [path]
    manifest = path / "batch.json"
    if not manifest.is_file():
        raise ValueError("Provide a run directory or a batch directory with batch.json")
    runs = []
    for entry in json.loads(manifest.read_text(encoding="utf-8"))["runs"]:
        if entry["status"] == "completed":
            run = (path / entry["directory"]).resolve()
            if not run.is_relative_to(path):
                raise ValueError("Batch run path is outside its batch directory")
            runs.append(run)
    if not runs:
        raise ValueError("Batch has no completed runs")
    return runs


def has_completed_evaluation(run):
    """True once a judge pass finished, including 'incomplete' (needs_review) results.

    Deterministic judging would reproduce those, so only interrupted passes
    (no metadata.finished_at) are re-run.
    """
    for path in (run / "evaluations").glob("*/evaluation.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("metadata", {}).get("finished_at"):
                return True
        except (OSError, ValueError):
            pass
    return False


def select_runs(args):
    """Shard before skipping so every shard sees the same assignment."""
    runs = find_runs(args.path)
    index, count = args.shard
    runs = runs[index::count]
    if args.skip_evaluated:
        skipped = [run for run in runs if has_completed_evaluation(run)]
        runs = [run for run in runs if run not in skipped]
        print(f"Shard {index}/{count}: skipping {len(skipped)} evaluated, {len(runs)} to evaluate", flush=True)
    return runs


def parse_shard(value):
    try:
        index, count = map(int, value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError("--shard must look like i/n, e.g. 0/4")
    if count < 1 or not 0 <= index < count:
        raise argparse.ArgumentTypeError("--shard needs 0 <= i < n")
    return index, count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--reuse-evaluation", type=Path,
                        help="Reuse completed annotation/realism calls from this format-6 evaluation.json (single run)")
    parser.add_argument("--model", help="Judge model; DeepInfra defaults to deepseek-ai/DeepSeek-V4.1-Flash-1017")
    parser.add_argument("--backend", choices=("ollama", "deepinfra", "compatible", "hf"), default="ollama")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env", default="LLM_API_KEY")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--top-p", type=float, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--enable_thinking", "--enable-thinking", action="store_true",
                        help="Enable judge thinking; omitted effort uses the model/template default")
    parser.add_argument("--skip-evaluated", action="store_true",
                        help="Skip runs whose evaluation.json records a finished judge pass")
    parser.add_argument("--shard", type=parse_shard, default=(0, 1),
                        help="i/n: evaluate only every n-th completed run starting at i")
    args = parser.parse_args(argv)
    if args.model is None:
        if args.backend == "deepinfra":
            args.model = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
        else:
            parser.error("--model is required for ollama, compatible and hf backends")
    if not 0 <= args.temperature <= 2 or not 0 < args.top_p <= 1 or args.max_new_tokens < 1:
        parser.error("Invalid temperature, top-p, or token limit")
    endpoint = args.base_url or {"ollama": "http://localhost:11434/v1",
                                 "deepinfra": "https://api.deepinfra.com/v1/openai"}.get(args.backend)
    if args.backend == "hf" and args.base_url:
        parser.error("--base-url does not apply to hf")
    if args.backend == "hf" and args.reasoning_effort and not args.enable_thinking:
        parser.error("HF --reasoning-effort requires --enable_thinking")
    if args.enable_thinking and args.reasoning_effort == "none":
        parser.error("--enable_thinking conflicts with --reasoning-effort none")
    if not endpoint and args.backend != "hf":
        parser.error("--base-url is required for compatible backends")
    key = os.environ.get(args.api_key_env) or ("ollama" if args.backend == "ollama" else None)
    if not key and args.backend != "hf":
        parser.error(f"Set {args.api_key_env}")
    try:
        prepared = []
        for run in select_runs(args):
            source = snapshot(run / "conversation.json")
            dialogue = json.loads(source["content"])
            prepare_input(dialogue)
            prepared.append((run, source, dialogue))
        reuse = None
        if args.reuse_evaluation:
            if len(prepared) != 1:
                raise ValueError("--reuse-evaluation requires a single run")
            reuse = json.loads(args.reuse_evaluation.read_text(encoding="utf-8"))
        if args.backend == "hf":
            thinking = ({"enable_thinking": True, "reasoning_effort": args.reasoning_effort}
                        if args.enable_thinking else {})
            backend = HFBackend(args.model, max_tokens=args.max_new_tokens, top_p=args.top_p, **thinking)
        else:
            thinking = {"enable_thinking": True} if args.enable_thinking else {}
            backend = LLMBackend(args.model, base_url=endpoint, api_key=key, backend=args.backend,
                                 max_tokens=args.max_new_tokens, top_p=args.top_p,
                                 reasoning_effort=args.reasoning_effort or (None if args.enable_thinking else "none"),
                                 **thinking)
        backend.check_available()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.error(str(exc).replace(key, "[REDACTED]") if key and key != "ollama" else str(exc))
    if not prepared:
        print("Nothing to evaluate in this shard.", flush=True)
        return 0
    sources = {str(p.relative_to(ROOT)): snapshot(p) for p in
               [Path(__file__).resolve(), ROOT / "src/evaluation/judge.py",
                ROOT / "src/evaluation/personality.py", ROOT / "src/evaluation/schemas.py", ROOT / "src/persona_profile.py",
                ROOT / "src/evaluation/reporting.py", ROOT / "src/llm_backend.py", ROOT / "scripts/runner.py"]}
    environment = environment_info()
    failed = False
    try:
        backend.prepare_local_model()
        model_metadata = backend.metadata()
        for run, source, dialogue in prepared:
            stamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d_%H-%M-%S")
            directory = create_batch_directory(run / "evaluations", stamp + "__" + safe_name(args.model))
            backend.log_path = directory / "evaluation_calls.jsonl"
            metadata = {"started_at": utc_now(), "judge": model_metadata,
                        "temperature": args.temperature, "seed": args.seed,
                        "seed_method": "SHA256(seed:stage-key), first 4 bytes modulo 2**31",
                        "source_conversation": {k: source[k] for k in ("path", "sha256")},
                        "source_files": sources, "environment": environment}
            print(f"Evaluating {run.name} -> {directory.name}", flush=True)
            if args.reuse_evaluation:
                metadata["reused_evaluation"] = str(args.reuse_evaluation.resolve())
            config = {"model": args.model, "backend": args.backend, "base_url": endpoint,
                      "top_p": args.top_p, "max_new_tokens": args.max_new_tokens,
                      "reasoning_effort": args.reasoning_effort, "enable_thinking": args.enable_thinking,
                      "model_metadata": model_metadata}
            try:
                result = evaluate(dialogue, backend, seed=args.seed, temperature=args.temperature,
                                  reuse=reuse, judge_config=config,
                                  on_update=lambda data: write_reports(data, directory, metadata))
            except ValueError as exc:
                parser.error(str(exc))
            metadata["finished_at"] = utc_now()
            write_reports(result, directory, metadata)
            failed |= result["status"] != "completed"
            print(f"{result['status']}: {directory / 'evaluation.md'}", flush=True)
    finally:
        backend.unload()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())