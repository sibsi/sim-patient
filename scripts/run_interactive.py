"""Run interactive doctor-patient consultations in parallel against OpenAI-compatible (vLLM) servers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml
from runner import (create_batch_directory, environment_info, file_reference, resolve_cases,
                    resolve_persona_profiles, safe_name, write_batch)
from agents.checker import CheckerAgent
from agents.doctor import DoctorAgent
from agents.patient import PatientAgent
from dialogue.case_facts import build_case_facts
from dialogue.orchestrator import run_interactive_dialogue
from llm_backend import LLMBackend, utc_now
from persona_profile import render_profile


def load_jobs(args):
    profiles = []
    for path in resolve_persona_profiles(args.persona_profile):
        reference = file_reference(path)
        profile = yaml.safe_load(reference["content"])
        profiles.append({"reference": reference, "text": render_profile(profile), "name": profile["name"]})
    prompts = {role: file_reference(path) for role, path in (("doctor_prompt", args.doctor_prompt),
                                                             ("patient_prompt", args.patient_prompt),
                                                             ("checker_prompt", args.checker_prompt))}
    jobs = []
    for path in resolve_cases(args.case):
        frozen_path = ROOT / "data/patient_cases/frozen_exchanges" / f"{path.stem}_frozen.yaml"
        inputs = {"case": file_reference(path), "frozen_exchanges": file_reference(frozen_path), **prompts}
        facts = build_case_facts(json.loads(inputs["case"]["content"]),
                                 yaml.safe_load(inputs["frozen_exchanges"]["content"]), path.stem)
        for seed, profile, condition in itertools.product(args.seed, profiles, args.condition):
            job = {"case": path.stem, "facts": facts, "seed": seed, "profile": profile, "condition": condition,
                   "inputs": {**inputs, "persona_profile": profile["reference"]}}
            build_agents(args, job, None, None, None)  # validate prompts before any model call
            jobs.append(job)
    return jobs


def build_agents(args, job, doctor_backend, patient_backend, checker_backend):
    doctor = DoctorAgent(doctor_backend, job["facts"], yaml.safe_load(job["inputs"]["doctor_prompt"]["content"]),
                         run_seed=job["seed"], total_turns=args.turns, temperature=args.temperature)
    patient = PatientAgent(patient_backend, job["facts"], yaml.safe_load(job["inputs"]["patient_prompt"]["content"]),
                           persona_text=job["profile"]["text"], run_seed=job["seed"], temperature=args.temperature,
                           planning=job["condition"] == "plan")
    patient.system({}, None)
    checker = CheckerAgent(checker_backend, job["facts"], yaml.safe_load(job["inputs"]["checker_prompt"]["content"]),
                           run_seed=job["seed"])
    return doctor, patient, checker


def make_backend(args, model, base_url, max_tokens, log_path, enable_thinking=False):
    key = os.environ.get(args.api_key_env)
    return LLMBackend(model, base_url=base_url, backend="compatible", max_tokens=max_tokens,
                      top_p=args.top_p, log_path=log_path, structured_output=True, enable_thinking=enable_thinking,
                      **({"api_key": key} if key else {}))


def run_one(args, job, destination, batch_id, environment, sources, verbose):
    destination.mkdir()
    log = destination / "model_calls.jsonl"
    # omits thinking options rejected by the Mistral tokenizer
    doctor_backend = make_backend(args, args.doctor_model, args.doctor_url, 800, log, enable_thinking=None)
    patient_backend = make_backend(args, args.patient_model, args.patient_url, 1500, log)
    checker_backend = make_backend(args, args.checker_model, args.checker_url, 1500, log)
    doctor, patient, checker = build_agents(args, job, doctor_backend, patient_backend, checker_backend)
    metadata = {
        "run_id": destination.name, "batch_id": batch_id, "started_at": utc_now(),
        "experiment": "interactive", "case": job["case"], "run_seed": job["seed"],
        "seed_method": "SHA256(run_seed:turn:stage:attempt), first 4 bytes big-endian modulo 2**31",
        "personality_condition": job["profile"]["name"], "persona_text": job["profile"]["text"],
        "condition": job["condition"], "total_turns": args.turns,
        "doctor": {**doctor_backend.metadata(), "temperature": args.temperature},
        "patient": {**patient_backend.metadata(), "temperature": args.temperature},
        "checker": {**checker_backend.metadata(), "temperature": 0},
        "core_topics": job["facts"]["core_topics"], "sensitive_ids": job["facts"]["sensitive_ids"],
        "environment": environment, "inputs": job["inputs"], "source_files": sources,
    }
    print(f"Running {destination.name}", flush=True)
    try:
        dialogue = run_interactive_dialogue(doctor, patient, checker, metadata, destination,
                                            total_turns=args.turns, verbose=verbose)
        return {"status": "completed", "completed_turns": len(dialogue["turns"])}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        print(f"Run failed ({destination.name}): {message}", file=sys.stderr, flush=True)
        return {"status": "failed", "error": message}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patient-model", required=True)
    parser.add_argument("--patient-url", required=True)
    parser.add_argument("--doctor-model", default="mistralai/Mistral-Small-3.2-24B-Instruct-2506")
    parser.add_argument("--doctor-url", required=True)
    parser.add_argument("--checker-model", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--checker-url", required=True)
    parser.add_argument("--case", nargs="+", action="extend", help="Patient names, case names, or all")
    parser.add_argument("--persona-profile", nargs="+", action="extend", required=True)
    parser.add_argument("--seed", type=int, nargs="+", default=[1])
    parser.add_argument("--condition", nargs="+", choices=["plan", "no_plan"], default=["plan"],
                        help="no_plan: the patient replies without a plan call or private memory")
    parser.add_argument("--turns", type=int, default=15)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--api-key-env", default="VLLM_API_KEY")
    parser.add_argument("--doctor-prompt", type=Path, default=ROOT / "prompts/doctor_interactive.yaml")
    parser.add_argument("--patient-prompt", type=Path, default=ROOT / "prompts/patient_interactive.yaml")
    parser.add_argument("--checker-prompt", type=Path, default=ROOT / "prompts/checker.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)
    if args.turns < 3 or args.workers < 1:
        parser.error("--turns must be at least 3 and --workers at least 1")
    return parser, args


def main(argv=None):
    parser, args = parse_args(argv)
    try:
        jobs = load_jobs(args)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    for case, facts in {job["case"]: job["facts"] for job in jobs}.items():
        print(f"{case}: topics {facts['core_topics']} | sensitive {facts['sensitive_ids']}")

    environment = environment_info()
    paths = [Path(__file__)] + [ROOT / "src" / name for name in (
        "llm_backend.py", "agents/common.py", "agents/doctor.py", "agents/patient.py", "agents/checker.py",
        "dialogue/case_facts.py", "dialogue/orchestrator.py", "evaluation/schemas.py", "persona_profile.py")]
    sources = {path.relative_to(ROOT).as_posix(): file_reference(path) for path in paths}
    directory = create_batch_directory(args.output_dir)
    entries = [{"case": job["case"], "personality_condition": job["profile"]["name"], "seed": job["seed"],
                "condition": job["condition"],
                "directory": f"{index:02d}_{safe_name(job['case'])}__{safe_name(job['profile']['name'])}"
                             f"__seed{job['seed']}__{job['condition']}",
                "status": "pending"} for index, job in enumerate(jobs, 1)]
    batch = {"batch_id": directory.name, "started_at": utc_now(), "folder_timezone": "Europe/Berlin",
             "status": "running", "experiment": "interactive", "patient_model": args.patient_model,
             "doctor_model": args.doctor_model, "seeds": args.seed, "turns": args.turns, "runs": entries}
    write_batch(batch, directory)
    print(f"Batch: {directory}", flush=True)
    lock = threading.Lock()

    def work(index):
        entry = entries[index]
        with lock:
            entry.update(status="running", started_at=utc_now())
            write_batch(batch, directory)
        result = run_one(args, jobs[index], directory / entry["directory"], directory.name,
                         environment, sources, verbose=len(jobs) == 1)
        with lock:
            entry.update(result, finished_at=utc_now())
            write_batch(batch, directory)

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, range(len(jobs))))
    except KeyboardInterrupt:
        batch["interrupted"] = True
    finally:
        for entry in entries:
            if entry["status"] in ("running", "pending"):
                entry.update(status="interrupted" if entry["status"] == "running" else "skipped")
        batch["status"] = "completed" if all(e["status"] == "completed" for e in entries) else "failed"
        batch["finished_at"] = utc_now()
        write_batch(batch, directory)
    print(f"Batch {batch['status']}: {directory / 'batch.json'}")
    return 0 if batch["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
