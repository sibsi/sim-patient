"""Tables for interactive consultations: one row per conversation, one per turn, plan vs observed,
and drift: measures per profile and turn window, and high-low trait gaps per window."""
import argparse
import collections
import csv
import glob
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dialogue.case_facts import fact_group
from evaluation.reporting import linguistic_metrics

ACTIONS = ("disclose", "hint", "withhold", "deny")
GROUPS = ("health", "detail", "negative", "life")
MARKERS = ["affect/worry", "affect/distress", "affect/embarrassment", "affect/calm_optimism", "unasked_content",
           "interaction_stance/appreciation", "interaction_stance/reservation", "interaction_stance/challenge",
           "own_interpretation", "patient_question/reassurance", "care_engagement/proactive"]
WINDOWS = ((1, 5), (6, 10), (11, 15))
# compares high minus low; openness uses low minus moderate
TRAITS = {"N": ("b5_N_high", "b5_N_low", ["affect/worry", "affect/distress", "anxiety"]),
          "A": ("b5_A_high", "b5_A_low", ["interaction_stance/appreciation", "interaction_stance/challenge",
                                          "interaction_stance/reservation", "trust"]),
          "O": ("b5_O_low", "b5_moderate", ["unasked_content", "own_interpretation", "words"])}
# counts list formatting and selected clinical terms
LIST_MARKUP = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s|\*\*|^#", re.M)
JARGON = {"symptom", "symptoms", "radiate", "radiates", "radiating", "intermittent", "onset", "severity",
          "abdominal", "gastrointestinal", "inflammation", "diagnosis", "chronic", "acute"}
DRIFT_MEASURES = ["words", "trust", "anxiety", "jargon", "list_markup"] + MARKERS
PRINTED = ["profile", "case", "seed", "sensitive_disclosed", "first_sensitive_disclosure",
           "first_disclosures_without_question", "without_question_detail", "without_question_negative",
           "asked_not_disclosed", "disclosed_not_planned", "denied", "plan_withhold", "trust_mean", "anxiety_mean",
           "turns_affect/worry", "turns_interaction_stance/challenge", "words_per_reply", "raw_medical_inventions",
           "realism_spoken_naturalness", "change_overall", "changes_motivated", "changes_unmotivated"]


def load(path):
    """(conversation, latest evaluation or None) for every completed run under path."""
    runs = []
    for conversation in sorted(Path(path).rglob("conversation.json")):
        dialogue = json.loads(conversation.read_text(encoding="utf-8"))
        if dialogue.get("status") != "completed":
            continue
        evaluations = sorted(glob.glob(str(conversation.parent / "evaluations/*/evaluation.json")))
        evaluation = json.loads(Path(evaluations[-1]).read_text(encoding="utf-8")) if evaluations else None
        runs.append((dialogue, evaluation))
    return runs


def label(annotation):
    return annotation["category"] + (f"/{annotation['subtype']}" if annotation["subtype"] else "")


def mean(values):
    return sum(values) / len(values) if values else None


def generation_row(dialogue):
    """Everything known without the judge: plans, states and checker results."""
    m, turns = dialogue["metadata"], dialogue["turns"]
    plans = [t["plan"] for t in turns if t["plan"]]
    actions = collections.Counter(d["action"] for p in plans for d in p["decisions"])
    first_round = [i for t in turns for i in t["checks"][0]["issues"]]
    words = linguistic_metrics([{"patient_reply": t["reply"]} for t in turns])
    return {
        "run_id": m["run_id"], "patient_model": m["patient"]["model_name"], "case": m["case"],
        "profile": m["personality_condition"], "seed": m["run_seed"], "condition": m.get("condition", "plan"),
        "words_per_reply": round(words["mean_words_per_turn"], 1), "mattr": round(words["mattr"], 3),
        "decisions": sum(actions.values()), **{f"plan_{a}": actions[a] for a in ACTIONS},
        "plan_volunteer": sum(len(p["volunteer"]) for p in plans),
        "trust_mean": round(mean([p["state"]["trust"] for p in plans]), 2) if plans else None,
        "anxiety_mean": round(mean([p["state"]["anxiety"] for p in plans]), 2) if plans else None,
        "raw_medical_inventions": sum(i["type"] == "medical_invention" for i in first_round),
        "raw_contradictions": sum(i["type"] == "unplanned_contradiction" for i in first_round),
        "repaired_turns": sum(t["repaired"] for t in turns),
        "repair_failed_turns": sum(t["repair_failed"] for t in turns),
        "planned_concealment_drops": sum(i["reason"] == "planned_concealment"
                                         for t in turns for c in t["checks"] for i in c["dropped"])}


def analyse(dialogue, evaluation):
    """Conversation row, per-turn rows and plan-vs-observed counts for one run."""
    m, turns = dialogue["metadata"], dialogue["turns"]
    row, per_turn, matrix = generation_row(dialogue), [], collections.Counter()
    if evaluation is None:
        return row, per_turn, matrix
    case = json.loads(m["inputs"]["case"]["content"])
    groups = {s["shard_id"]: fact_group(s) for s in case["shards"]}
    groups.update({s["life_id"]: "life" for s in case.get("life_shards", [])})
    sensitive = set(m["sensitive_ids"])
    judged = {t["turn"]: t for t in evaluation["turns"]}
    disclosed_before, first_disclosure = set(), {}
    first_unasked, asked_not_disclosed, not_planned_total = collections.Counter(), 0, 0
    for t in turns:
        j = judged.get(t["turn"])
        if j is None:
            continue
        status = {d["item_id"]: d["status"] for d in j["disclosure"]}
        now = {k for k, s in status.items() if s == "disclosed"}
        new = now - disclosed_before
        asked = j.get("asked_ids")
        if asked is not None:
            # first disclosure without a matching question
            first_unasked.update(groups[k] for k in new - set(asked))
            # counts missed fact requests, including repeated requests; does not establish intent
            asked_not_disclosed += len(set(asked) - now - disclosed_before)
        for k in new:
            first_disclosure[k] = t["turn"]
        disclosed_before |= now
        plan = t["plan"]
        not_planned = set()
        if plan:
            # newly disclosed facts absent from the plan
            not_planned = new - {d["id"] for d in plan["decisions"] + plan["volunteer"]}
            not_planned_total += len(not_planned)
            for d in plan["decisions"]:
                matrix[(d["action"], status.get(d["id"], "not said"))] += 1
            for v in plan["volunteer"]:
                matrix[("volunteer", status.get(v["id"], "not said"))] += 1
        behaviours = {label(a) for a in j["annotations"] if a["category"] != "other_observations"}
        per_turn.append({
            "run_id": m["run_id"], "patient_model": m["patient"]["model_name"],
            "profile": m["personality_condition"], "case": m["case"], "turn": t["turn"],
            "topic": t["doctor"]["topic"], "words": len(t["reply"].split()),
            "jargon": sum(w in JARGON for w in re.findall(r"[a-z]+", t["reply"].lower())),
            "list_markup": len(LIST_MARKUP.findall(t["reply"])),
            "trust": plan["state"]["trust"] if plan else None,
            "anxiety": plan["state"]["anxiety"] if plan else None,
            "asked": len(asked) if asked is not None else None, "disclosed": len(now),
            "not_planned": " ".join(sorted(not_planned)),
            "sensitive_so_far": len(sensitive & disclosed_before), "sensitive_total": len(sensitive),
            "hinted": sum(s == "hinted" for s in status.values()),
            "denied": sum(s == "denied" for s in status.values()), "repaired": t["repaired"],
            # keeps unassessed behavior turns as missing values
            **{marker: int(marker in behaviours) if j["annotations_complete"] else None for marker in MARKERS}})

    findings = collections.Counter(f["kind"] for t in evaluation["turns"] for f in t["findings"])
    total_words = sum(len(t["reply"].split()) for t in turns)
    realism = (evaluation.get("conversation") or {}).get("realism") or {}
    row.update({
        "evaluation_status": evaluation["status"],
        "sensitive_disclosed": f"{len(sensitive & disclosed_before)}/{len(sensitive)}",
        "first_sensitive_disclosure": min((first_disclosure[k] for k in sensitive & disclosed_before), default=None),
        "facts_disclosed": len(disclosed_before),
        "first_disclosures_without_question": sum(first_unasked.values()),
        **{f"without_question_{g}": first_unasked[g] for g in GROUPS},
        "asked_not_disclosed": asked_not_disclosed,
        "disclosed_not_planned": not_planned_total,
        "denied": sum(r["denied"] for r in per_turn), "hinted": sum(r["hinted"] for r in per_turn),
        "contradictions": findings["contradiction"], "unsupported_additions": findings["unsupported_addition"],
        "findings_per_100_words": round(100 * sum(findings.values()) / total_words, 2) if total_words else None,
        "behaviour_turns_assessed": sum(r[MARKERS[0]] is not None for r in per_turn),
        **{f"turns_{marker}": sum(r[marker] or 0 for r in per_turn) for marker in MARKERS},
        **{f"realism_{k}": v["score"] if v else None for k, v in realism.items()},
        **change_columns(evaluation.get("changes"), turns)})
    return row, per_turn, matrix


def change_columns(changes, turns):
    """Change-judge counts, and how many motivated changes lie within one turn of a logged state change.
    turns_near_state_change gives the chance level: the share of all turns that lie that close to one."""
    states = {t["turn"]: (t["plan"]["state"]["trust"], t["plan"]["state"]["anxiety"]) for t in turns if t["plan"]}
    moved = {n for n in states if n - 1 in states and states[n] != states[n - 1]}
    near_moved = {n for n in states if moved & {n - 1, n, n + 1}}
    if not changes:
        return {"change_overall": None, "changes_motivated": None, "changes_unmotivated": None,
                "motivated_near_state_change": None,
                "turns_near_state_change": f"{len(near_moved)}/{len(states)}" if states else None}
    motivated = [c for c in changes["changes"] if c["label"] == "motivated"]
    return {"change_overall": changes["overall"], "changes_motivated": len(motivated),
            "changes_unmotivated": len(changes["changes"]) - len(motivated),
            "motivated_near_state_change": sum(c["cause_turn"] in near_moved for c in motivated) if states else None,
            "turns_near_state_change": f"{len(near_moved)}/{len(states)}" if states else None}


def drift(per_turn):
    """Mean of each measure per patient model, profile and turn window, and the trait gaps per window."""
    cells = collections.defaultdict(list)
    for r in per_turn:
        window = next(i for i, (first, last) in enumerate(WINDOWS) if first <= r["turn"] <= last)
        cells[(r["patient_model"], r["profile"], window)].append(r)
    means = {key: {m: mean([r[m] for r in rows if r[m] is not None]) for m in DRIFT_MEASURES}
             for key, rows in cells.items()}
    windows = [{"patient_model": model, "profile": profile, "window": f"{WINDOWS[w][0]}-{WINDOWS[w][1]}",
                "turns": len(cells[(model, profile, w)]),
                **{m: round(v, 3) if v is not None else None for m, v in values.items()}}
               for (model, profile, w), values in sorted(means.items())]
    gaps = []
    for model in sorted({model for model, _, _ in means}):
        for trait, (high, low, measures) in TRAITS.items():
            for measure in measures:
                row = {"patient_model": model, "trait": trait, "comparison": f"{high} - {low}", "measure": measure}
                for w, (first, last) in enumerate(WINDOWS):
                    a = means.get((model, high, w), {}).get(measure)
                    b = means.get((model, low, w), {}).get(measure)
                    row[f"gap_{first}-{last}"] = round(a - b, 3) if a is not None and b is not None else None
                gaps.append(row)
    return windows, gaps


def write_csv(rows, path):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Batch folders (or any folder containing runs)")
    parser.add_argument("--output-dir", type=Path, help="Defaults to <first path>/analysis")
    args = parser.parse_args(argv)
    output = args.output_dir or args.paths[0] / "analysis"
    output.mkdir(parents=True, exist_ok=True)
    rows, per_turn, matrix = [], [], collections.defaultdict(collections.Counter)
    for path in args.paths:
        for dialogue, evaluation in load(path):
            row, turns, counts = analyse(dialogue, evaluation)
            rows.append(row)
            per_turn.extend(turns)
            matrix[(row["patient_model"], row["profile"], row["condition"])].update(counts)
    write_csv(rows, output / "conversations.csv")
    write_csv(per_turn, output / "turns.csv")
    write_csv([{"patient_model": model, "profile": profile, "condition": condition,
                "planned": planned, "observed": observed, "count": n}
               for (model, profile, condition), counts in sorted(matrix.items())
               for (planned, observed), n in sorted(counts.items())], output / "plan_vs_observed.csv")
    windows, gaps = drift(per_turn)
    write_csv(windows, output / "drift_windows.csv")
    write_csv(gaps, output / "drift_gaps.csv")
    evaluated = sum(r.get("evaluation_status") is not None for r in rows)
    print(f"{len(rows)} conversations, {evaluated} evaluated -> {output}")
    print(" | ".join(PRINTED))
    for r in sorted(rows, key=lambda r: (r["case"], r["profile"], r["seed"])):
        print(" | ".join(str(r.get(c)) for c in PRINTED))


if __name__ == "__main__":
    raise SystemExit(main())
