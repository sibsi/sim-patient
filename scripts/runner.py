"""Run complete frozen interviews sequentially across models and patient cases."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml
from patient_speaker import PatientSpeaker
from persona_profile import render_profile
from dialogue.frozen_exchange import prepare_exchanges
from dialogue.conversation_fixed import run_dialogue
from dialogue.transcript import write_outputs
from llm_backend import HFBackend, LLMBackend, utc_now


def environment_info():
    info = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(), "pyyaml": yaml.__version__}
    for key, command in (
        ("gpu", ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
    ):
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            info[key] = result.stdout.strip() if result.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            info[key] = "unavailable"
    return info


def snapshot(path):
    content = path.read_text(encoding="utf-8")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "content": content}


def file_reference(path):
    """Record a portable path and preserve the file version used by this run."""
    path = Path(path).resolve()
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        # stores external inputs without machine-specific folders
        relative = Path(path.name)
    return {"path": relative.as_posix(), "content": path.read_text(encoding="utf-8")}


def safe_name(value):
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip(".-")[:100] or "unnamed"


def create_batch_directory(parent, stamp=None):
    stamp = stamp or datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d_%H-%M-%S")
    parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        path = parent / (stamp if index == 1 else f"{stamp}_{index:02d}")
        try:
            path.mkdir()
            return path
        except FileExistsError:
            index += 1


def write_batch(batch, directory):
    path = directory / "batch.json.tmp"
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.replace(directory / "batch.json")


def resolve_case(value):
    candidate = Path(value)
    if not candidate.is_file():
        candidate = ROOT / "data/patient_cases" / (value if value.endswith(".json") else value + ".json")
    if not candidate.is_file():
        matches = [path for path in sorted((ROOT / "data/patient_cases").glob("*.json"))
                   if path.stem.rsplit("_", 1)[0].casefold() == value.casefold()]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous patient name '{value}'; use a full case name: "
                             + ", ".join(path.stem for path in matches))
        if not matches:
            raise ValueError(f"Patient case not found: {value}")
        candidate = matches[0]
    return candidate.resolve()


def resolve_cases(values):
    paths = []
    seen = set()
    for value in values or ["anna_103370"]:
        if value.casefold() == "all":
            selected = sorted((ROOT / "data/patient_cases").glob("*.json"))
            if not selected:
                raise ValueError("No patient cases found")
        else:
            selected = [resolve_case(value)]
        for path in selected:
            path = path.resolve()
            if path in seen:
                raise ValueError(f"Duplicate patient case: {path}")
            seen.add(path)
            paths.append(path)
    return paths


def resolve_persona_profile(value):
    path = Path(value)
    if not path.is_file() and path.name == str(path):
        filename = path.name if path.suffix else path.name + ".yaml"
        matches = sorted((ROOT / "persona/profiles").rglob(filename))
        if len(matches) > 1:
            raise ValueError(f"Ambiguous persona profile name; use a YAML path: {value}")
        path = matches[0] if matches else ROOT / "persona/profiles" / filename
    if not path.is_file():
        raise ValueError(f"Persona profile not found: {value}")
    return path.resolve()


def all_profiles():
    """The moderate baseline plus every single-trait profile; combinations are selected by name."""
    folder = ROOT / "persona/profiles"
    return sorted(folder.glob("*.yaml")) + sorted((folder / "one_trait_change").glob("*.yaml"))


def resolve_persona_profiles(values):
    if not values:
        return [None]
    paths = []
    seen = set()
    for value in values:
        if str(value).casefold() == "all":
            selected = all_profiles()
            if not selected:
                raise ValueError("No persona profiles found")
        else:
            selected = [resolve_persona_profile(value)]
        for path in selected:
            path = path.resolve()
            if path in seen:
                raise ValueError(f"Duplicate persona profile: {path}")
            seen.add(path)
            paths.append(path)
    return paths


def load_cases(args):
    profile_paths = resolve_persona_profiles(args.persona_profile)
    profiles = []
    for path in profile_paths:
        reference = file_reference(path) if path else None
        profile = yaml.safe_load(reference["content"]) if reference else None
        profiles.append((reference, render_profile(profile) if reference is not None else "",
                         profile["name"] if reference is not None else "unspecified"))
    cases = []
    for path in resolve_cases(args.case):
        frozen_path = ROOT / "data/patient_cases/frozen_exchanges" / f"{path.stem}_frozen.yaml"
        inputs = {label: file_reference(p) for label, p in (
            ("case", path), ("frozen_exchanges", frozen_path), ("speaker_prompt", args.patient_prompt))}
        case = json.loads(inputs["case"]["content"])
        script = yaml.safe_load(inputs["frozen_exchanges"]["content"])
        exchanges = prepare_exchanges(script, case)
        speaker_prompt = yaml.safe_load(inputs["speaker_prompt"]["content"])
        for reference, persona_text, condition in profiles:
            run_inputs = dict(inputs)
            if reference is not None:
                run_inputs["persona_profile"] = reference
            # checks prompts before starting model calls
            patient = PatientSpeaker(case, None, prompt=speaker_prompt, persona_text=persona_text)
            for exchange in exchanges:
                patient.build_messages(exchange["question"], [], exchange["facts"])
            cases.append({"name": path.stem, "case": case, "exchanges": exchanges,
                          "inputs": run_inputs, "speaker_prompt": speaker_prompt, "pair": script.get("pair"),
                          "persona_text": persona_text, "personality_condition": condition})
    return cases


def make_backend(args, model, destination=None):
    if args.backend == "hf":
        return HFBackend(model, max_tokens=args.max_new_tokens, top_p=args.top_p,
                         log_path=destination / "model_calls.jsonl" if destination else None)
    key = os.environ.get(args.api_key_env) or ("ollama" if args.backend == "ollama" else None)
    if not key:
        raise ValueError(f"Set the {args.api_key_env} environment variable for backend {args.backend}")
    effort = args.reasoning_effort
    return LLMBackend(
        model, base_url=args.base_url, api_key=key, backend=args.backend,
        max_tokens=args.max_new_tokens, top_p=args.top_p, structured_output=False,
        reasoning_effort=effort if effort is not None else ("none" if args.backend == "ollama" else None),
        log_path=destination / "model_calls.jsonl" if destination else None)


def redact(text, clients):
    for client in clients:
        if client.api_key and client.api_key != "ollama":
            text = text.replace(client.api_key, "[REDACTED]")
    return text


def run_one(args, model, prepared, destination, batch_id, environment, sources, speaker=None):
    destination.mkdir()
    speaker = speaker if speaker is not None else make_backend(args, model, destination)
    speaker.log_path = destination / "model_calls.jsonl"
    try:
        patient = PatientSpeaker(prepared["case"], speaker, run_seed=args.seed,
                                 temperature=args.temperature, prompt=prepared["speaker_prompt"],
                                 persona_text=prepared.get("persona_text", ""))
        metadata = {
            "run_id": destination.name, "batch_id": batch_id, "started_at": utc_now(),
            "patient_id": prepared["case"]["patient_id"], "run_seed": args.seed,
            "seed_method": "SHA256(run_seed:turn:stage:attempt), first 4 bytes big-endian modulo 2**31",
            "speaker": {**speaker.metadata(), "temperature": args.temperature},
            "environment": environment, "inputs": prepared["inputs"], "source_files": sources,
            "pair": prepared.get("pair"),
            "experiment": "frozen_facts", "personality_condition": prepared.get("personality_condition", "unspecified"),
            "persona_text": prepared.get("persona_text", ""), "turn_count": len(prepared["exchanges"]),
        }
        print(f"Running {destination.name}", flush=True)
        dialogue = run_dialogue(patient, prepared["exchanges"], metadata,
                               on_turn=lambda data: write_outputs(data, destination))
        return {"status": "completed", "completed_turns": len(dialogue["turns"])}
    except Exception as exc:
        for path in (destination / "conversation.json", destination / "model_calls.jsonl"):
            if path.exists():
                path.write_text(redact(path.read_text(encoding="utf-8"), [speaker]), encoding="utf-8")
        message = redact(f"{type(exc).__name__}: {exc}", [speaker])
        print(f"Run failed: {message}", file=sys.stderr)
        return {"status": "failed", "error": message}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", nargs="+", action="extend", help="One or more models; default qwen3.5:9b")
    parser.add_argument("--case", nargs="+", action="extend",
                        help="Patient names (e.g. anna), full case names, or JSON paths; "
                             "use all to run every case alphabetically in sequence; default anna")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "deepinfra", "compatible", "hf"])
    parser.add_argument("--base-url", help="Defaults to the selected provider's endpoint")
    parser.add_argument("--api-key-env", default="LLM_API_KEY")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-new-tokens", type=int, default=400)
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--patient-prompt", type=Path, default=ROOT / "prompts/patient_speaker_frozen.yaml")
    parser.add_argument("--persona-profile", type=Path, nargs="+", action="extend",
                        help="One or more profile names or YAML paths, run in the given order; "
                             "all runs the moderate baseline and every one_trait_change profile "
                             "in one batch (combinations only by name); omit for no induction")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs",
                        help="Parent directory for a new timestamped batch folder")
    args = parser.parse_args(argv)
    if args.backend == "hf":
        if not args.model:
            parser.error("--model is required for hf: use an HF model ID or local model directory")
        if args.base_url or args.reasoning_effort is not None:
            parser.error("hf uses local weights and enable_thinking=False, not --base-url/--reasoning-effort")
    args.model = args.model or ["qwen3.5:9b"]
    if len(set(args.model)) != len(args.model):
        parser.error("Duplicate model names")
    if args.base_url is None and args.backend != "hf":
        if args.backend == "compatible":
            parser.error("--base-url is required for a compatible backend")
        args.base_url = {"ollama": "http://localhost:11434/v1",
                         "deepinfra": "https://api.deepinfra.com/v1/openai"}[args.backend]
    if args.max_new_tokens < 1:
        parser.error("Token limits must be positive")
    if not 0 <= args.temperature <= 2:  
        parser.error("Temperatures must be between 0 and 2")
    if not 0 < args.top_p <= 1:
        parser.error("top_p must be greater than 0 and at most 1")
    return parser, args


def main(argv=None):
    parser, args = parse_args(argv)
    try:
        cases = load_cases(args)
        groups = []
        for model in args.model:
            speaker = make_backend(args, model)
            speaker.check_available()
            groups.append((model, [speaker]))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, yaml.YAMLError) as exc:
        parser.error(str(exc))

    environment = environment_info()
    paths = [Path(__file__), ROOT / "src/llm_backend.py", ROOT / "src/patient_speaker.py",
             ROOT / "src/dialogue/frozen_exchange.py", ROOT / "src/dialogue/conversation_fixed.py",
             ROOT / "src/dialogue/transcript.py", ROOT / "src/persona_profile.py"]
    sources = {path.relative_to(ROOT).as_posix(): file_reference(path) for path in paths}
    directory = create_batch_directory(args.output_dir)
    entries = [{"model": model, "case": case["name"],
                "personality_condition": case.get("personality_condition", "unspecified"),
                "directory": f"{index:02d}_{safe_name(model)}__{safe_name(case['name'])}"
                + (f"__{safe_name(case['personality_condition'])}" if case.get("persona_text") else ""), "status": "pending"}
               for index, (model, case) in enumerate(((m, c) for m in args.model for c in cases), 1)]
    conditions = list(dict.fromkeys(case.get("personality_condition", "unspecified") for case in cases))
    batch = {"batch_id": directory.name, "started_at": utc_now(), "folder_timezone": "Europe/Berlin",
             "status": "running", "experiment": "frozen_facts",
             "personality_condition": conditions[0] if len(conditions) == 1 else "multiple",
             "personality_conditions": conditions,
             "seed": args.seed, "runs": entries}
    write_batch(batch, directory)
    print(f"Batch: {directory}", flush=True)
    stop = False
    try:
        for group_index, (model, controls) in enumerate(groups):
            try:
                for client in controls:
                    client.prepare_local_model()
                for case_index, prepared in enumerate(cases):
                    entry = entries[group_index * len(cases) + case_index]
                    entry.update(status="running", started_at=utc_now())
                    write_batch(batch, directory)
                    try:
                        entry.update(run_one(args, model, prepared, directory / entry["directory"],
                                             directory.name, environment, sources, speaker=controls[0]))
                    except Exception as exc:
                        entry.update(status="failed", error=redact(f"{type(exc).__name__}: {exc}", controls))
                    entry["finished_at"] = utc_now()
                    write_batch(batch, directory)
            except Exception as exc:
                batch["lifecycle_error"] = redact(f"{type(exc).__name__}: {exc}", controls)
                stop = True
            finally:
                for client in controls:
                    try:
                        client.unload()
                    except Exception as exc:
                        batch["lifecycle_error"] = redact(f"{type(exc).__name__}: {exc}", controls)
                        stop = True
                write_batch(batch, directory)
            if stop:
                break
    except KeyboardInterrupt:
        batch["interrupted"] = True
        stop = True
    finally:
        for entry in entries:
            if entry["status"] in ("running", "pending"):
                entry.update(status="interrupted" if entry["status"] == "running" else "skipped",
                             reason="Batch stopped before completion")
        batch["status"] = "completed" if not stop and all(r["status"] == "completed" for r in entries) else "failed"
        batch["finished_at"] = utc_now()
        write_batch(batch, directory)
    print(f"Batch {batch['status']}: {directory / 'batch.json'}")
    if batch.get("lifecycle_error"):
        print(batch["lifecycle_error"], file=sys.stderr)
    return 0 if batch["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
