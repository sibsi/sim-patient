"""Judge a frozen interview: four annotation batches (turns 1-4, 5-8, 9-12, 13-16) and one realism call."""
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path

import yaml

from evaluation.personality import validate_annotations
from evaluation.schemas import (CONVERSATION_SCHEMA, FINDING_SCHEMA, REALISM_DIMENSIONS, SEVERITIES,
                                TURN_SCHEMA, ordered_parts_ok, quote_ok, require)

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def prepare_input(dialogue):
    if dialogue.get("status") != "completed":
        raise ValueError("Evaluate a completed conversation")
    metadata = dialogue["metadata"]
    if metadata.get("experiment") != "frozen_facts":
        raise ValueError("Evaluation requires a frozen-facts run")
    case = json.loads(metadata["inputs"]["case"]["content"])
    turns = dialogue["turns"]
    if len(turns) != 16 or [t["turn"] for t in turns] != list(range(1, 17)):
        raise ValueError("This evaluator requires 16 sequential completed turns")
    # selects judge input fields; excludes diagnosis and model metadata
    clean = []
    for turn in turns:
        clean.append({key: turn[key] for key in
                      ("turn", "doctor_question", "provided_ids", "provided_facts", "patient_reply")})
    for turn in clean:
        turn["expected_items"] = [{"item_id": f["id"], "statement": f["statement"],
                                   "disclosure_category": f.get("disclosure_category", "directly_relevant")}
                                  for f in turn["provided_facts"]]
    reference = {}
    for turn in clean:
        for fact in turn["provided_facts"]:
            identifier = fact["id"]
            if identifier in reference and reference[identifier]["statement"] != fact["statement"]:
                raise ValueError(f"Conflicting saved statements for {identifier}")
            if identifier not in reference:
                reference[identifier] = {"id": identifier, "statement": fact["statement"],
                                         "type": fact["type"], "assigned_turns": []}
            reference[identifier]["assigned_turns"].append(turn["turn"])
    return {"identity": {k: case[k] for k in ("name", "age", "sex")},
            "script_facts": list(reference.values()),
            "script_expectations": [{"turn": t["turn"], "doctor_question": t["doctor_question"],
                                     "expected_items": t["expected_items"]} for t in clean],
            "turns": clean}


def parse_judge_json(raw, normalizations):
    """Recover only an outer code fence and trailing commas; preserve quoted text."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
        normalizations.append("Removed surrounding JSON code fence")

    removed = 0

    def replace(match):
        nonlocal removed
        token = match.group()
        # preserves quoted strings while repairing JSON syntax
        if token == "," and text[:match.start()].rstrip()[-1:] not in ("", "[", "{", ":", ","):
            removed += 1
            return ""
        return token

    cleaned = re.sub(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])', replace, text)
    if removed:
        normalizations.append(f"Removed {removed} trailing comma(s)")
    return json.loads(cleaned)


def checked(value, check, location, corrections):
    try:
        check(value)
        return value
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        corrections.append({**location, "rejected": value, "reason": str(exc)})
        return None


def explained(row):
    require(isinstance(row["explanation"], str) and row["explanation"].strip(), "Missing explanation")


def validate_realism(result, turns, corrections=None):
    """Keep each valid conversation-level rating; a rejected dimension becomes None."""
    corrections = [] if corrections is None else corrections
    indexed = {t["turn"]: t for t in turns}
    if not isinstance(result, dict):
        raise ValueError("Judge response must be an object")
    ratings = result.get("realism", {})

    def rating(row):
        require(type(row["score"]) is int and 1 <= row["score"] <= 5, "Invalid score")
        require(quote_ok(indexed, row["turn"], row["quote"]), "Evidence not found in referenced patient reply")
        require(isinstance(row["context_turns"], list) and all(
            type(t) is int and t in indexed and t <= row["turn"] for t in row["context_turns"]),
            "Context must reference existing current or earlier turns")
        explained(row)
    validated = {key: checked(ratings.get(key) if isinstance(ratings, dict) else None,
                              rating, {"field": key}, corrections) for key in REALISM_DIMENSIONS}
    result.clear()
    result["realism"] = validated


def validate_result(result, targets, corrections=None, history=None, normalizations=None):
    """Keep the valid parts of a batch and record each rejected part in corrections."""
    corrections = [] if corrections is None else corrections
    notes = [] if normalizations is None else normalizations
    indexed = {t["turn"]: t for t in (history or targets)}
    assigned_turns = {}
    for t in indexed.values():
        for item in t["expected_items"]:
            assigned_turns.setdefault(item["item_id"], []).append(t["turn"])

    def excerpt(number, quote):
        require(quote_ok(indexed, number, quote), "Evidence not found in referenced patient reply")

    def collection(value, location):
        if isinstance(value, list):
            return value
        corrections.append({**location, "reason": "Missing or invalid list", "rejected": value})
        return []

    if not isinstance(result, dict):
        raise ValueError("Judge response must be an object")
    rows = collection(result.get("turns"), {"field": "turns"})
    expected_turns = {t["turn"] for t in targets}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("turn")) is not int or row["turn"] not in expected_turns:
            corrections.append({"field": "turns", "rejected": row, "reason": "Unexpected turn"})
    cleaned = []
    for target in targets:
        number = target["turn"]
        matches = [r for r in rows if isinstance(r, dict) and type(r.get("turn")) is int and r["turn"] == number]
        row = matches[0] if len(matches) == 1 else {}
        if len(matches) != 1:
            corrections.append({"turn": number, "reason": "Missing or duplicate turn"})
        output = {"turn": number, "disclosure": [], "findings": []}
        disclosures = collection(row.get("disclosure"), {"turn": number, "field": "disclosure"})
        expected_ids = {i["item_id"] for i in target["expected_items"]}
        for d in disclosures:
            if not isinstance(d, dict) or not isinstance(d.get("item_id"), str) or d["item_id"] not in expected_ids:
                corrections.append({"turn": number, "field": "disclosure", "rejected": d, "reason": "Unknown item"})
        disclosure_errors = any(c.get("turn") == number and c.get("field") == "disclosure" for c in corrections)
        for item in target["expected_items"]:
            identifier = item["item_id"]
            candidates = [d for d in disclosures if isinstance(d, dict) and d.get("item_id") == identifier]
            def disclosure(d):
                require(len(candidates) == 1, "Duplicate item")
                require(isinstance(d, dict) and set(d) == {"item_id", "evidence"}, "Invalid disclosure fields")
                # allows separate reply excerpts as evidence of disclosure
                if not quote_ok(indexed, number, d["evidence"]) and ordered_parts_ok(indexed, number, d["evidence"]):
                    notes.append(f"Turn {number}: accepted {identifier} evidence joined with ellipses")
                    return
                excerpt(number, d["evidence"])
            valid = checked(candidates[0], disclosure,
                            {"turn": number, "item_id": identifier, "field": "disclosure"}, corrections) if candidates else None
            if valid:
                entry = {"item_id": identifier, "disclosed": True, "evidence": valid["evidence"], "note": None}
            elif candidates or disclosure_errors or len(matches) != 1:
                entry = {"item_id": identifier, "status": "unassessed"}
            else:
                entry = {"item_id": identifier, "disclosed": False, "evidence": None,
                         "note": "No disclosure match identified in this reply."}
            entry["disclosure_category"] = item.get("disclosure_category", "directly_relevant")
            output["disclosure"].append(entry)
        def finding(f):
            require(isinstance(f, dict) and set(f) == set(FINDING_SCHEMA["properties"]),
                    "Unexpected or missing finding fields")
            if not ordered_parts_ok(indexed, number, f["claim"]):
                excerpt(number, f["claim"])
            require(f["kind"] in ("contradiction", "unsupported_addition"), "Unknown kind")
            require(type(f["medical"]) is bool, "Medical must be boolean")
            require(f["severity"] in SEVERITIES, "Invalid severity")
            explained(f)
            ref_turn, ref_id = f["contradicted_turn"], f["contradicted_item_id"]
            if f["kind"] == "contradiction":
                require(type(ref_turn) is int and isinstance(ref_id, str),
                        "Contradiction requires an integer turn and string item ID")
                identity_ref = ref_turn == 0 and ref_id in ("name", "age", "sex")
                scripted_ref = ref_turn in indexed and any(
                    i["item_id"] == ref_id for i in indexed[ref_turn]["expected_items"])
                require(identity_ref or scripted_ref, "Unknown contradicted item")
            else:
                require(ref_turn is None and ref_id is None,
                        "Unsupported addition must have null contradiction references")
        for f in collection(row.get("findings"), {"turn": number, "field": "findings"}):
            if (isinstance(f, dict) and f.get("kind") == "contradiction"
                    and f.get("contradicted_item_id") in assigned_turns
                    and f.get("contradicted_turn") not in assigned_turns[f["contradicted_item_id"]]):
                # recovers the fact reference from its item ID
                fixed = assigned_turns[f["contradicted_item_id"]][0]
                notes.append(f"Turn {number}: set {f['contradicted_item_id']} contradiction turn "
                             f"{f.get('contradicted_turn')} to {fixed}")
                f = {**f, "contradicted_turn": fixed}
            valid = checked(f, finding, {"turn": number, "field": "findings"}, corrections)
            if valid is not None:
                if not quote_ok(indexed, number, valid["claim"]):
                    notes.append(f"Turn {number}: accepted finding claim joined with ellipses")
                output["findings"].append(valid)
        output["factual_status"] = "needs_review" if any(c.get("turn") == number for c in corrections) else "completed"
        output["annotations"], output["annotations_complete"] = validate_annotations(
            row, target, corrections, normalizations,
            supplied_statements=[item["statement"] for t in indexed.values() if t["turn"] <= number
                                 for item in t["expected_items"]])
        output["local_realism"] = []
        def local(observation):
            require(isinstance(observation, dict) and set(observation) == {"dimension", "quote", "explanation"},
                    "Missing or unexpected local realism fields")
            require(observation["dimension"] in REALISM_DIMENSIONS, "Unknown realism dimension")
            excerpt(number, observation["quote"])
            explained(observation)
        for observation in collection(row.get("local_realism"), {"turn": number, "field": "local_realism"}):
            valid = checked(observation, local, {"turn": number, "field": "local_realism"}, corrections)
            if valid is not None:
                output["local_realism"].append(valid)
        output["local_realism_complete"] = not any(c.get("turn") == number and c.get("field") == "local_realism" for c in corrections)
        output["status"] = "needs_review" if any(c.get("turn") == number for c in corrections) else "completed"
        cleaned.append(output)
    result["turns"] = cleaned


def evaluate(dialogue, backend, *, seed=0, temperature=0,
             reuse=None, judge_config=None, on_update=None):
    data = prepare_input(dialogue)
    filenames = {"annotation": "annotation_judge.yaml", "conversation": "judge_conversation.yaml"}
    prompts = {name: (PROMPTS / filename).read_text(encoding="utf-8") for name, filename in filenames.items()}
    generation = {key: dialogue["metadata"].get(key) for key in
                  ("run_id", "batch_id", "patient_id", "run_seed", "speaker", "inputs", "personality_condition", "persona_text")}
    context = [{**{k: t[k] for k in ("turn", "doctor_question", "patient_reply", "expected_items")},
                **{k: original[k] for k in ("question_type", "tags") if k in original}}
               for t, original in zip(data["turns"], dialogue["turns"])]
    settings = {"seed": seed, "temperature": temperature, "judge": judge_config}
    result = {"format_version": 6, "status": "running", "prompt_snapshots": prompts,
              "evaluation_settings": settings, "generation": generation, "calls": [], "turns": [],
              "conversation": None,
              "pair": dialogue["metadata"].get("pair"), "report_context": context}
    if reuse is not None:
        require(judge_config is not None, "Reusing evaluations requires explicit judge configuration")
        require(reuse.get("format_version") == 6 and reuse.get("report_context") == context
                and reuse.get("generation") == generation and reuse.get("evaluation_settings") == settings
                and reuse.get("prompt_snapshots") == prompts,
                "Reuse requires the same conversation, prompts, format and judge settings")
        require(all(any(c.get("key") == f"annotation:{start}" and c.get("status") == "completed"
                        for c in reuse.get("calls", [])) for start in (1, 5, 9, 13)),
                "Reuse requires four completed annotation batches")
        # reuses completed calls and reruns failed or invalid ones
        result["turns"] = deepcopy(reuse["turns"])
        result["conversation"] = deepcopy(reuse["conversation"])

    def update():
        if on_update:
            on_update(result)

    def call(name, payload, schema, validator, key):
        stage = f"judge_{name}"
        old = next((c for c in (reuse or {}).get("calls", [])
                    if c.get("key") == key and c.get("status") == "completed"), None)
        if old:
            result["calls"].append({**deepcopy(old), "call": len(result["calls"]) + 1, "reused": True})
            return None, True
        call_seed = int.from_bytes(hashlib.sha256(f"{seed}:{key}".encode()).digest()[:4], "big") % (2**31)
        record = {"call": len(result["calls"]) + 1, "key": key, "stage": stage,
                  "target_turns": [t["turn"] for t in payload["target_turns"]], "seed": call_seed,
                  "normalizations": [], "corrections": []}
        parsed = None
        try:
            raw = backend.generate([
                {"role": "system", "content": yaml.safe_load(prompts[name])["system_prompt"]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                seed=call_seed, temperature=temperature, turn_number=record["call"], stage=stage,
                attempt=1, schema=schema)
            parsed = parse_judge_json(raw, record["normalizations"])
            validator(parsed, record["corrections"], record["normalizations"])
            record["status"] = "needs_review" if record["corrections"] else "completed"
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            api_key = getattr(backend, "api_key", None)
            record.update(status="failed", error=message.replace(api_key, "[REDACTED]") if api_key and api_key != "ollama" else message)
            parsed = None
        result["calls"].append(record)
        return parsed, False

    base = {key: data[key] for key in ("identity", "script_facts", "script_expectations")}
    transcript = [{k: t[k] for k in ("turn", "doctor_question", "patient_reply")} for t in data["turns"]]
    for start in range(0, 16, 4):
        batch = data["turns"][start:start + 4]
        payload = {**base, "target_turns": [{**transcript[t["turn"] - 1], "expected_items": t["expected_items"]} for t in batch],
                   "earlier_history_context_only": transcript[:start]}
        parsed, reused = call("annotation", payload, TURN_SCHEMA,
            lambda value, corrections, normalizations: validate_result(
                value, batch, corrections=corrections, history=data["turns"], normalizations=normalizations),
            f"annotation:{start + 1}")
        if not reused:
            numbers = {t["turn"] for t in batch}
            result["turns"] = [t for t in result["turns"] if t["turn"] not in numbers]
            if parsed is not None:
                result["turns"].extend(parsed["turns"])
            result["turns"].sort(key=lambda t: t["turn"])
        update()

    local = [{"turn": t["turn"], "observations": t["local_realism"],
              "complete": t["local_realism_complete"]} for t in result["turns"]]
    parsed, reused = call("conversation", {"target_turns": transcript, "local_observations": local}, CONVERSATION_SCHEMA,
        lambda value, corrections, normalizations: validate_realism(value, data["turns"], corrections), "conversation")
    if not reused:
        result["conversation"] = parsed
    update()

    result["status"] = "completed" if all(c["status"] == "completed" for c in result["calls"]) else "incomplete"
    update()
    return result
