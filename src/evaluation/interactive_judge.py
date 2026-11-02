"""Judge an interactive consultation, blinded to plans, state and persona:
annotation blocks of four turns against the full fact table, one realism call, and one question-only
call per turn that decides which facts the doctor asked for without seeing that turn's reply.
A last change call sees the persona (still no plans or state) and lists lasting behaviour changes."""
import hashlib
import json
from pathlib import Path

import yaml

from evaluation.judge import checked, explained, parse_judge_json, validate_realism
from evaluation.personality import validate_annotations
from evaluation.schemas import (BEHAVIOR_SCHEMA, CONVERSATION_SCHEMA, INT, LOCAL_SCHEMA, OTHER_SCHEMA,
                                REALISM_DIMENSIONS, SEVERITIES, TEXT, array, enum, obj, ordered_parts_ok,
                                quote_ok, require)

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
STATUSES = ("disclosed", "hinted", "denied")
BLOCK = 4
CHANGE_SCHEMA = obj({
    "changes": array(obj({
        "aspect": TEXT, "from_turn": INT, "to_turn": INT, "description": TEXT,
        "label": enum("motivated", "unmotivated"), "cause_turn": {"type": ["integer", "null"]},
        "evidence": array(obj({"turn": INT, "quote": TEXT}), 1, 3)})),
    "overall": enum("stable", "adapting", "drifting"), "explanation": TEXT})


def prepare_input(dialogue):
    if dialogue.get("status") != "completed":
        raise ValueError("Evaluate a completed conversation")
    metadata = dialogue["metadata"]
    if metadata.get("experiment") != "interactive":
        raise ValueError("Evaluation requires an interactive run")
    case = json.loads(metadata["inputs"]["case"]["content"])
    facts = ([{"id": s["shard_id"], "type": "medical", "statement": s["statement"]} for s in case["shards"]]
             + [{"id": s["life_id"], "type": "life", "statement": s["statement"]} for s in case.get("life_shards", [])])
    # passes spoken dialogue without plans, states, persona or diagnosis
    turns = [{"turn": t["turn"], "doctor_question": t["doctor"]["utterance"], "patient_reply": t["reply"]}
             for t in dialogue["turns"]]
    require([t["turn"] for t in turns] == list(range(1, len(turns) + 1)), "Turns must be sequential")
    return {"identity": {k: case[k] for k in ("name", "age", "sex")}, "facts": facts, "turns": turns}


def turn_schema(ids, numbers):
    fact = enum(*ids)
    return obj({"turns": array(obj({
        "turn": {"type": "integer", "enum": numbers},
        "disclosure": array(obj({"item_id": fact, "status": enum(*STATUSES), "evidence": TEXT})),
        "findings": array(obj({
            "kind": enum("contradiction", "unsupported_addition"), "medical": {"type": "boolean"},
            "claim": TEXT, "severity": enum(*SEVERITIES), "explanation": TEXT,
            "contradicted_item_id": {"type": ["string", "null"]}})),
        "behaviors": BEHAVIOR_SCHEMA,
        "other_observations": OTHER_SCHEMA,
        "local_realism": LOCAL_SCHEMA,
    }), len(numbers), len(numbers))})


def validate_block(result, targets, facts, corrections, normalizations):
    """Keep the valid parts of each target turn; record every rejected part in corrections."""
    ids = {f["id"] for f in facts}
    statements = [f["statement"] for f in facts]
    require(isinstance(result, dict) and isinstance(result.get("turns"), list), "Judge response must list turns")
    cleaned = []
    for target in targets:
        number = target["turn"]
        indexed = {number: target}
        matches = [r for r in result["turns"] if isinstance(r, dict) and r.get("turn") == number]
        row = matches[0] if len(matches) == 1 else {}
        if len(matches) != 1:
            corrections.append({"turn": number, "reason": "Missing or duplicate turn"})

        def evidence(quote):
            if not quote_ok(indexed, number, quote):
                require(ordered_parts_ok(indexed, number, quote), "Evidence not found in patient reply")
                normalizations.append(f"Turn {number}: accepted evidence joined with ellipses")

        def disclosure(d):
            require(d["item_id"] in ids and d["status"] in STATUSES, "Unknown item or status")
            evidence(d["evidence"])

        def finding(f):
            evidence(f["claim"])
            explained(f)
            if f["kind"] == "contradiction":
                require(f["contradicted_item_id"] in ids, "Contradiction needs a known fact id")
            else:
                require(f["contradicted_item_id"] is None, "Addition must not reference a fact")

        def local(observation):
            require(observation["dimension"] in REALISM_DIMENSIONS, "Unknown realism dimension")
            evidence(observation["quote"])
            explained(observation)

        output = {"turn": number}
        for field, check in (("disclosure", disclosure), ("findings", finding), ("local_realism", local)):
            rows = row.get(field, [])
            output[field] = [r for r in (checked(r, check, {"turn": number, "field": field}, corrections)
                                         for r in rows) if r is not None]
        seen = [d["item_id"] for d in output["disclosure"]]
        if len(seen) != len(set(seen)):
            corrections.append({"turn": number, "field": "disclosure", "reason": "Duplicate item"})
            output["disclosure"] = list({d["item_id"]: d for d in output["disclosure"]}.values())
        output["annotations"], output["annotations_complete"] = validate_annotations(
            row, target, corrections, normalizations, supplied_statements=statements)
        output["status"] = "needs_review" if any(c.get("turn") == number for c in corrections) else "completed"
        cleaned.append(output)
    result["turns"] = cleaned


def validate_changes(result, turns, corrections):
    """Keep each change with a valid turn range, cause and evidence; record the rejected ones."""
    indexed = {t["turn"]: t for t in turns}
    require(isinstance(result, dict) and isinstance(result.get("changes"), list), "Judge response must list changes")
    require(result.get("overall") in ("stable", "adapting", "drifting"), "Unknown overall label")

    def change(c):
        require(c["from_turn"] in indexed and c["to_turn"] in indexed and c["from_turn"] < c["to_turn"],
                "Invalid turn range")
        if c["label"] == "motivated":
            require(type(c["cause_turn"]) is int and 1 <= c["cause_turn"] <= c["to_turn"], "Invalid cause turn")
        else:
            require(c["cause_turn"] is None, "Unmotivated change must not name a cause")
        for e in c["evidence"]:
            require(quote_ok(indexed, e["turn"], e["quote"]) or ordered_parts_ok(indexed, e["turn"], e["quote"]),
                    "Evidence not found in patient reply")

    result["changes"] = [c for c in (checked(c, change, {"field": "changes"}, corrections)
                                     for c in result["changes"]) if c is not None]


def evaluate(dialogue, backend, *, seed=42, temperature=0, judge_config=None, on_update=None):
    data = prepare_input(dialogue)
    prompts = {name: (PROMPTS / filename).read_text(encoding="utf-8") for name, filename in
               (("annotation", "judge_interactive.yaml"), ("conversation", "judge_conversation_interactive.yaml"),
                ("asked", "judge_asked.yaml"), ("change", "judge_change.yaml"))}
    metadata = dialogue["metadata"]
    result = {"format": "interactive_v1", "status": "running", "prompt_snapshots": prompts,
              "evaluation_settings": {"seed": seed, "temperature": temperature, "judge": judge_config},
              "generation": {key: metadata.get(key) for key in
                             ("run_id", "batch_id", "case", "run_seed", "personality_condition", "condition")},
              "calls": [], "turns": [], "conversation": None, "changes": None}
    ids = [f["id"] for f in data["facts"]]

    def call(name, payload, schema, validator, key):
        call_seed = int.from_bytes(hashlib.sha256(f"{seed}:{key}".encode()).digest()[:4], "big") % (2**31)
        record = {"call": len(result["calls"]) + 1, "key": key, "seed": call_seed,
                  "normalizations": [], "corrections": []}
        parsed = None
        try:
            raw = backend.generate([
                {"role": "system", "content": yaml.safe_load(prompts[name])["system_prompt"]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                seed=call_seed, temperature=temperature, turn_number=record["call"], stage=f"judge_{name}",
                attempt=1, schema=schema)
            parsed = parse_judge_json(raw, record["normalizations"])
            validator(parsed, record["corrections"], record["normalizations"])
            record["status"] = "needs_review" if record["corrections"] else "completed"
        except Exception as exc:
            record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            parsed = None  # a call that fails validation counts as unassessed
        result["calls"].append(record)
        if on_update:
            on_update(result)
        return parsed

    turns = data["turns"]
    for start in range(0, len(turns), BLOCK):
        block = turns[start:start + BLOCK]
        payload = {"identity": data["identity"], "facts": data["facts"], "target_turns": block,
                   "earlier_history_context_only": turns[:start]}
        parsed = call("annotation", payload, turn_schema(ids, [t["turn"] for t in block]),
                      lambda value, corrections, notes: validate_block(value, block, data["facts"], corrections, notes),
                      f"annotation:{start + 1}")
        if parsed is not None:
            result["turns"].extend(parsed["turns"])

    # separate calls keep each target reply hidden from the asked-for judge
    asked_schema = obj({"asked_ids": array(enum(*ids))})
    asked = {}
    for index, target in enumerate(turns):
        payload = {"identity": data["identity"], "facts": data["facts"], "earlier_conversation": turns[:index],
                   "current_doctor_utterance": target["doctor_question"]}
        parsed = call("asked", payload, asked_schema, lambda value, corrections, notes: None, f"asked:{target['turn']}")
        # marks unassessed questions with None
        asked[target["turn"]] = sorted(set(parsed["asked_ids"])) if parsed is not None else None
    for row in result["turns"]:
        row["asked_ids"] = asked[row["turn"]]

    local = [{"turn": t["turn"], "observations": t["local_realism"]} for t in result["turns"]]
    result["conversation"] = call(
        "conversation", {"target_turns": turns, "local_observations": local}, CONVERSATION_SCHEMA,
        lambda value, corrections, notes: validate_realism(value, turns, corrections), "conversation")
    result["changes"] = call(
        "change", {"personality_description": metadata.get("persona_text") or "", "target_turns": turns},
        CHANGE_SCHEMA, lambda value, corrections, notes: validate_changes(value, turns, corrections), "change")
    result["status"] = "completed" if all(c["status"] == "completed" for c in result["calls"]) else "incomplete"
    if on_update:
        on_update(result)
    return result


def disclosure_timeline(result, facts):
    """Per fact: turns it was asked about, and turns it was disclosed, hinted or denied."""
    timeline = {f["id"]: {"asked": [], "disclosed": [], "hinted": [], "denied": []} for f in facts}
    for turn in result["turns"]:
        for fact_id in turn["asked_ids"] or []:
            timeline[fact_id]["asked"].append(turn["turn"])
        for d in turn["disclosure"]:
            timeline[d["item_id"]][d["status"]].append(turn["turn"])
    return {fact_id: row for fact_id, row in timeline.items() if any(row.values())}
