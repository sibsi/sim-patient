"""Rebuild the Part 2 evaluations from the judge's raw responses and apply the Part 1 fixes.

1. Validation repairs, only for entries that fail validation (the Part 1 functions): near-miss quotes become
   the exact reply wording (or the entry is dropped), out-of-range realism context turns are removed,
   finding references are made consistent and duplicate labels are merged.
2. The Part 1 label corrections: stance aimed at third parties, "no idea" as a hypothesis,
   unasked_content that answers the question, proactive that agrees to or restates the plan or safety net.
3. Three manually reviewed behavior lists, with the original validation failures retained as provenance.
The asked and change calls are replayed unchanged.

Rerunning reproduces the same files: python scripts/apply_fixes_part2.py <batch folder> [<batch folder> ...]
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import apply_fixes_part1 as part1
from evaluate_interactive import write_evaluation
from evaluation.interactive_judge import evaluate
from evaluation.judge import parse_judge_json
from evaluation.personality import validate_annotations
from evaluation.schemas import BEHAVIOR_SUBTYPES, quote_ok, split_joined_excerpt

LOG = part1.LOG
PLAN_TURN = 14  # turns 14 and 15 are the plan and the safety net
# matches agreement to tests, waiting for results or returning if worse
AGREES = re.compile(r"\bready\b|go ahead|get (those|these|the|them)\b.*\b(done|drawn|started)|tests? done"
                    r"|have the blood|wait (for|to hear)|eye out|\bbe (right )?back\b|follow your instructions"
                    r"|whatever (tests|else|is needed|you think)|trust your judg|\bI agree\b|that's fine|I can do that"
                    r"|let's (just )?do it|willing to (do|proceed)|try (those|these) (dietary )?changes|arrange those tests"
                    r"|rest and (avoid|stay)|stay away from people|as prescribed|proceed\?|start the antibiotics", re.I)
# matches plain not-knowing; keeps tentative hypotheses about a cause
NO_IDEA = re.compile(r"no idea|not sure what|\bdon't know(\.|$)", re.I)
THIRD_PARTY = re.compile(r"which I (really )?appreciate|grateful (for|to have) (him|her)")
# reviewed exception: the son's new job is an anecdote beyond the question
KEEP_UNASKED = {("Qwen/Qwen3.5-27B susanne_131469 b5_moderate s1", 9)}

# reviewed against the saved rubric, reference facts and dialogue through that turn
# identifies runs by profile; labels use reply evidence, not assigned traits
MANUAL_BEHAVIORS = {
    ("google/gemma-4-31B-it", "marie_93048", "b5_O_low", 2, 9): {
        "reply": "I'm doing my best, but it's a lot. On a happier note, my son's second child was born last month, "
                 "so that's been a lovely distraction. But health-wise, I should mention that I've also had some vaginal discharge.",
        "behaviors": [
            {"category": "affect", "subtype": "distress", "evidence": ["I'm doing my best, but it's a lot."],
             "reason": "Expresses feeling overwhelmed while trying to cope, beyond reporting the supplied facts."},
            {"category": "affect", "subtype": "calm_optimism",
             "evidence": ["On a happier note", "so that's been a lovely distraction."],
             "reason": "Adds a positive outlook and comforting interpretation of the family event, not present in the supplied fact."},
        ],
        "rationale": "Retain added overwhelm and positive framing. The birth and vaginal discharge are supplied facts, "
                     "so mentioning them does not establish unasked_content; the doctor also invites life updates.",
    },
    ("Qwen/Qwen3.5-27B", "jonas_102835", "b5_A_low", 2, 1): {
        "reply": "Yes, I've had a fever. Actually, the fever isn't even the worst part; it's the breathing. "
                 "I'm really short of breath and it's hard to catch my air. Sabine has been taking my temperature "
                 "every evening, and along with the fever, I've been getting these bad chills and shivers.",
        "behaviors": [
            {"category": "reporting_style", "subtype": "organizing_clarifying",
             "evidence": ["Actually, the fever isn't even the worst part; it's the breathing."],
             "reason": "Redirects the account from the doctor's opening focus on fever to breathing as the main problem, "
                       "adding an explicit prioritization rather than only listing symptoms."},
        ],
        "rationale": "Symptom severity alone is not fear or negative anticipation, so do not retain worry. "
                     "Temperature monitoring and the symptoms are supplied facts, not unasked_content. "
                     "The explicit correction of the account's focus supports organizing_clarifying.",
    },
    ("Qwen/Qwen3.5-27B", "marie_93048", "b5_N_low", 1, 8): {
        "reply": "Well, at work, I'm a secretary at a law firm. At home, my husband Thomas has had to help me out "
                 "quite a bit because of the breathing trouble and the hand pain. I even had to skip my Italian evening "
                 "class on Wednesdays recently because I just couldn't manage the breathing. It's been a tough time, "
                 "though on a brighter note, my son's second child was born last month, so I do have that happy thing to think about.",
        "behaviors": [
            {"category": "affect", "subtype": "distress", "evidence": ["It's been a tough time"],
             "reason": "Adds an explicit appraisal of emotional hardship beyond describing symptom-related limitations."},
            {"category": "affect", "subtype": "calm_optimism",
             "evidence": ["on a brighter note", "so I do have that happy thing to think about."],
             "reason": "Expresses a positive counterpoint to the difficulties, beyond the supplied fact about the birth."},
        ],
        "rationale": "Retain emotional hardship and positive framing. The birth is supplied factual content and "
                     "the daily-life effects answer the question, so neither supports unasked_content.",
    },
}


def complete_reviewed_annotations(result, dialogue):
    """Apply the three reviewed lists without altering other evaluation fields or raw judge logs."""
    m = dialogue["metadata"]
    run = (m["patient"]["model_name"], m["case"], m["personality_condition"], m["run_seed"])
    changed = 0
    for row in result["turns"]:
        review = MANUAL_BEHAVIORS.get((*run, row["turn"]))
        if review is None:
            continue
        review_id = f"behavior-review-2026-11-02-turn-{row['turn']}"
        if any(r["id"] == review_id for r in result.get("manual_annotation_reviews", [])):
            continue
        target = next(t for t in dialogue["turns"] if t["turn"] == row["turn"])
        if target["reply"] != review["reply"]:
            raise ValueError(f"Reviewed reply changed: {run}, turn {row['turn']}")
        call = next(c for c in result["calls"]
                    if c["key"] == f"annotation:{1 + 4 * ((row['turn'] - 1) // 4)}")
        resolved = [c for c in call["corrections"]
                    if c.get("turn") == row["turn"] and c.get("field") == "behaviors"]
        if row["annotations_complete"] or not resolved:
            raise ValueError(f"Expected an unassessed behavior list: {run}, turn {row['turn']}")
        case = json.loads(m["inputs"]["case"]["content"])
        corrections = []
        annotations, complete = validate_annotations(
            {"behaviors": deepcopy(review["behaviors"]), "other_observations": []},
            {"turn": row["turn"], "patient_reply": target["reply"]}, corrections,
            supplied_statements=[f["statement"] for f in case["shards"] + case.get("life_shards", [])])
        if not complete or corrections:
            raise ValueError(f"Manual annotations failed validation: {corrections}")
        result.setdefault("manual_annotation_reviews", []).append({
            "id": review_id, "reviewer": "Codex (AI-assisted manual annotation)", "date": "2026-11-02",
            "turn": row["turn"], "call_key": call["key"], "rationale": review["rationale"],
            "original_turn": deepcopy(row), "original_call": deepcopy(call),
            "replacement_annotations": deepcopy(annotations),
        })
        row["annotations"] = annotations
        row["annotations_complete"] = True
        call["corrections"] = [c for c in call["corrections"] if c not in resolved]
        call["status"] = "needs_review" if call["corrections"] else "completed"
        row["status"] = "needs_review" if any(c.get("turn") == row["turn"] for c in call["corrections"]) else "completed"
        changed += 1
    if changed:
        result["status"] = "completed" if all(c["status"] == "completed" for c in result["calls"]) else "incomplete"
    return changed


def repair_annotations(parsed, targets, ids):
    """Part 1 step 1 for one annotation block, adapted to the Part 2 schema (no script turns)."""
    replies = {t["turn"]: t["patient_reply"] for t in targets}
    for row in parsed.get("turns", []):
        number = row.get("turn")
        if number not in replies:
            continue
        reply = replies[number]
        disclosures = []
        for d in row.get("disclosure", []):
            d["evidence"] = part1.fix_quote(None, number, d["evidence"], reply, True)
            if d["evidence"]:
                disclosures.append(d)
        row["disclosure"] = disclosures

        findings = []
        for f in row.get("findings", []):
            if not (claim := part1.fix_quote(None, number, f["claim"], reply, True)):
                continue
            f["claim"] = claim
            ref = f["contradicted_item_id"]
            if f["kind"] == "contradiction" and ref not in ids:
                named = sorted(set(re.findall(r"\b[MLX]\d+\b", f["explanation"])) & ids)
                if len(named) == 1:
                    f["contradicted_item_id"] = named[0]
                else:  # a conflict with an earlier reply, not a fact, is an addition
                    f.update(kind="unsupported_addition", contradicted_item_id=None)
                LOG["contradiction reference repaired"] += 1
            elif f["kind"] == "unsupported_addition" and ref is not None:
                if ref in ids:
                    f["kind"] = "contradiction"
                else:
                    f["contradicted_item_id"] = None
                LOG["unsupported_addition reference repaired"] += 1
            findings.append(f)
        row["findings"] = findings

        local = []
        for observation in row.get("local_realism", []):
            observation["quote"] = part1.fix_quote(None, number, observation["quote"], reply)
            if observation["quote"]:
                local.append(observation)
        row["local_realism"] = local

        kept, seen = [], {}
        single = {1: {"patient_reply": reply}}
        for entry in row.get("behaviors", []):
            quotes = [q for q in (part1.fix_quote(None, number, q, reply) for q in entry["evidence"]) if q]
            if not quotes:
                continue
            if sum(1 if quote_ok(single, 1, q) else len(split_joined_excerpt(single, 1, q) or [q]) for q in quotes) > 3:
                # uses a covering span when splitting would exceed three excerpts
                quotes = [q if quote_ok(single, 1, q) else part1.covering_span(q, reply) or q for q in quotes]
                LOG["ellipsis excerpt replaced by covering span"] += 1
            entry["evidence"] = list(dict.fromkeys(quotes))[:3]
            category = entry["category"]
            if entry["subtype"] not in BEHAVIOR_SUBTYPES.get(category, (entry["subtype"],)):
                LOG["label with invalid subtype dropped"] += 1
                continue
            if (category, entry["subtype"]) in seen:
                first = seen[category, entry["subtype"]]
                first["evidence"] = list(dict.fromkeys(first["evidence"] + entry["evidence"]))[:3]
                first["reason"] += " " + entry["reason"]
                LOG["duplicate label merged"] += 1
                continue
            seen[category, entry["subtype"]] = entry
            kept.append(entry)
        row["behaviors"] = kept


class Replay:
    """Return the logged judge responses, repaired, instead of calling the model."""
    def __init__(self, lines, ids):
        self.lines, self.ids = iter(lines), ids

    def generate(self, messages, *, stage, **kwargs):
        line = next(self.lines)
        if line["stage"] != stage:
            raise ValueError(f"Logged call {line['stage']} does not match {stage}")
        if line.get("error"):
            raise RuntimeError(line["error"])
        text = line["response"]["choices"][0]["message"]["content"]
        targets = json.loads(messages[1]["content"])["target_turns"] if stage != "judge_asked" else None
        if stage == "judge_annotation":
            parsed = parse_judge_json(text, [])
            repair_annotations(parsed, targets, self.ids)
        elif stage == "judge_conversation":
            parsed = parse_judge_json(text, [])
            part1.repair_realism(parsed, {"turns": targets})
        else:
            return text
        return json.dumps(parsed, ensure_ascii=False)


def edit_labels(result, dialogue):
    m = dialogue["metadata"]
    key = f"{m['patient']['model_name']} {m['case']} {m['personality_condition']} s{m['run_seed']}"
    questions = {t["turn"]: t["doctor"]["utterance"] for t in dialogue["turns"]}
    for t in result["turns"]:
        number, kept = t["turn"], []
        for label in t["annotations"]:
            category, subtype, evidence = label["category"], label.get("subtype"), label["evidence"]
            if category == "interaction_stance" and any(THIRD_PARTY.search(x) for x in evidence):
                LOG["stance at third party removed"] += 1
                continue
            if category == "own_interpretation" and all(NO_IDEA.search(x) for x in evidence):
                LOG["'no idea' hypothesis removed"] += 1
                continue
            if category == "unasked_content" and (key, number) not in KEEP_UNASKED and any(
                    re.search(q, questions[number], re.I) and all(re.search(e, x, re.I) for x in evidence)
                    for q, e in part1.ASKED_TOPICS):
                LOG["unasked answer removed"] += 1
                continue
            if (category, subtype) == ("care_engagement", "proactive") and number >= PLAN_TURN:
                remaining = [x for x in evidence if not (part1.RESTATED.search(x) or AGREES.search(x))]
                if not remaining:
                    LOG["restated or agreeing proactive removed"] += 1
                    continue
                if remaining != evidence:
                    LOG["restated or agreeing proactive trimmed"] += 1
                    label["evidence"] = remaining
            kept.append(label)
        t["annotations"] = kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batches", nargs="+", type=Path)
    args = parser.parse_args(argv)
    statuses = {}
    for batch in args.batches:
        for path in sorted(batch.glob("*/evaluations/*/evaluation.json")):
            current = json.loads(path.read_text(encoding="utf-8"))
            dialogue = json.loads((path.parents[2] / "conversation.json").read_text(encoding="utf-8"))
            lines = [json.loads(l) for l in (path.parent / "evaluation_calls.jsonl").read_text(encoding="utf-8").splitlines()]
            case = json.loads(dialogue["metadata"]["inputs"]["case"]["content"])
            ids = {s["shard_id"] for s in case["shards"]} | {s["life_id"] for s in case.get("life_shards", [])}
            settings = current["evaluation_settings"]
            result = evaluate(dialogue, Replay(lines, ids), seed=settings["seed"],
                              temperature=settings["temperature"], judge_config=settings["judge"])
            result["prompt_snapshots"] = current["prompt_snapshots"]
            edit_labels(result, dialogue)
            complete_reviewed_annotations(result, dialogue)
            statuses[result["status"]] = statuses.get(result["status"], 0) + 1
            write_evaluation({"metadata": current["metadata"], **result}, path.parent)
    print(statuses)
    for name, count in sorted(LOG.items()):
        print(f"{count:4d}  {name}")


if __name__ == "__main__":
    raise SystemExit(main())
