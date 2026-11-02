"""Evaluate saved interactive consultations in parallel against an OpenAI-compatible (vLLM) judge."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import find_runs, has_completed_evaluation
from evaluation.interactive_judge import disclosure_timeline, evaluate, prepare_input
from llm_backend import LLMBackend, utc_now
from runner import create_batch_directory, environment_info, safe_name, snapshot


def write_evaluation(document, directory):
    temporary = directory / "evaluation.json.tmp"
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(directory / "evaluation.json")


def summary(result, facts):
    """Short printable overview: disclosure timeline and realism scores."""
    lines = [f"{result['generation']['run_id']}: {result['status']}"]
    statements = {f["id"]: f["statement"] for f in facts}
    for fact_id, row in disclosure_timeline(result, facts).items():
        parts = [f"{key} {row[key]}" for key in ("asked", "disclosed", "hinted", "denied") if row[key]]
        lines.append(f"  {fact_id:4} {' | '.join(parts)}  ({statements[fact_id][:60]})")
    realism = (result.get("conversation") or {}).get("realism") or {}
    lines.append("  realism: " + ", ".join(f"{k} {v['score'] if v else None}" for k, v in realism.items()))
    changes = result.get("changes") or {}
    lines.append(f"  changes: {changes.get('overall')}")
    for c in changes.get("changes", []):
        lines.append(f"    {c['from_turn']}->{c['to_turn']} {c['label']} (cause {c['cause_turn']}): {c['aspect']}")
    return "\n".join(lines)


def evaluate_one(args, run, sources, environment):
    source = snapshot(run / "conversation.json")
    dialogue = json.loads(source["content"])
    data = prepare_input(dialogue)
    stamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d_%H-%M-%S")
    directory = create_batch_directory(run / "evaluations", stamp + "__" + safe_name(args.model))
    key = os.environ.get(args.api_key_env)
    backend = LLMBackend(args.model, base_url=args.base_url, backend="compatible", max_tokens=args.max_new_tokens,
                         top_p=1, log_path=directory / "evaluation_calls.jsonl", enable_thinking=False,
                         **({"api_key": key} if key else {}))
    metadata = {"started_at": utc_now(), "judge": backend.metadata(), "temperature": 0, "seed": args.seed,
                "seed_method": "SHA256(seed:stage-key), first 4 bytes modulo 2**31",
                "source_conversation": {k: source[k] for k in ("path", "sha256")},
                "source_files": sources, "environment": environment}
    config = {"model": args.model, "base_url": args.base_url, "max_new_tokens": args.max_new_tokens}
    result = evaluate(dialogue, backend, seed=args.seed, judge_config=config,
                      on_update=lambda data: write_evaluation({"metadata": metadata, **data}, directory))
    metadata["finished_at"] = utc_now()
    write_evaluation({"metadata": metadata, **result}, directory)
    print(summary(result, data["facts"]), flush=True)
    return result["status"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A run directory or a batch directory with batch.json")
    parser.add_argument("--model", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="VLLM_API_KEY")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--skip-evaluated", action="store_true",
                        help="Skip runs whose evaluation.json records a finished judge pass")
    args = parser.parse_args(argv)
    try:
        runs = find_runs(args.path)
        if args.skip_evaluated:
            runs = [run for run in runs if not has_completed_evaluation(run)]
        for run in runs:
            prepare_input(json.loads((run / "conversation.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    paths = [Path(__file__).resolve()] + [ROOT / "src" / name for name in (
        "evaluation/interactive_judge.py", "evaluation/judge.py", "evaluation/personality.py",
        "evaluation/schemas.py", "llm_backend.py")]
    sources = {str(p.relative_to(ROOT)): snapshot(p) for p in paths}
    environment = environment_info()

    def work(run):
        try:
            return evaluate_one(args, run, sources, environment)
        except Exception as exc:
            print(f"Evaluation failed ({run.name}): {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return "failed"

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        statuses = list(pool.map(work, runs))
    print(f"Evaluated {len(runs)} runs: " + ", ".join(f"{s} {statuses.count(s)}" for s in sorted(set(statuses))))
    return 0 if all(s == "completed" for s in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
