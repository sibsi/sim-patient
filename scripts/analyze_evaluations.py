"""Summarize selected evaluation.json files into analysis.json and analysis.md."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.personality import behavior_summary, saved_assignment
from evaluation.reporting import evaluation_overview, linguistic_metrics, cell, condition_label


def comparison_context(document):
    generation = document["generation"]
    inputs = generation["inputs"]
    return {"speaker": generation["speaker"], "run_seed": generation["run_seed"],
            "inputs": {name: inputs[name]["content"] for name in ("case", "frozen_exchanges", "speaker_prompt")},
            "evaluation_settings": document["evaluation_settings"], "prompts": document["prompt_snapshots"]}


def contradiction_timing(document):
    """Place each counted contradiction relative to when the speaker was given the contradicted fact.

    The judge's contradicted_turn may be any assigned turn, so timing is derived from the item ID:
    current (supplied this turn), earlier (supplied at any earlier turn), future (only supplied later).
    """
    assigned = {}
    for context in document["report_context"]:
        for item in context["expected_items"]:
            assigned.setdefault(item["item_id"], []).append(context["turn"])
    rows = []
    for turn in document["turns"]:
        if turn.get("factual_status") != "completed":
            continue  # Same rule as the overview: review turns are not counted.
        for finding in turn["findings"]:
            if finding["kind"] != "contradiction":
                continue
            item, number = finding["contradicted_item_id"], turn["turn"]
            turns = assigned.get(item, [])
            if item in ("name", "age", "sex"):
                timing = "identity"
            elif number in turns:
                timing = "current"
            elif any(t < number for t in turns):
                timing = "earlier"
            else:
                timing = "future"
            rows.append({"turn": number, "item_id": item, "assigned_turns": turns,
                         "fact_timing": timing, "claim": finding["claim"]})
    return rows


def aggregate(documents):
    """Group the dialogues and count behaviors; each conversation may appear only once."""
    seen = set()
    groups = {}
    dialogues = []
    buckets = {}
    for path, document in documents:
        if document.get("format_version") != 6:
            raise ValueError(f"{path}: expected evaluation format 6; legacy results have different semantics")
        source = document["metadata"]["source_conversation"]["path"]
        if source in seen:
            raise ValueError(f"Multiple evaluations of {source}; select one evaluation per dialogue")
        seen.add(source)
        context = comparison_context(document)
        context_key = json.dumps(context, sort_keys=True, ensure_ascii=False)
        if context_key not in groups:
            groups[context_key] = {"group": len(groups) + 1, "context": context}
        group = groups[context_key]["group"]
        summary = behavior_summary(document["turns"], len(document["report_context"]))
        overview = evaluation_overview(document, summary)
        dialogues.append({"evaluation": str(path), "source_conversation": source, "group": group,
                          "generation_condition": condition_label(document),
                          "assigned_traits": saved_assignment(document["generation"])[0],
                          "status": document["status"], "overview": overview,
                          "contradictions": contradiction_timing(document),
                          "linguistic_metrics": linguistic_metrics(document["report_context"])})
        key = (group, condition_label(document), json.dumps(saved_assignment(document["generation"])[0], sort_keys=True))
        buckets.setdefault(key, []).append(summary)
    comparisons = []
    for (group, generated, assigned), rows in sorted(buckets.items()):
        behaviors = {}
        def combine(counts):
            assessed = sum(c["assessed_turns"] for c in counts)
            count = sum(c["count"] or 0 for c in counts) if assessed else None
            return {"count": count, "assessed_turns": assessed,
                    "unassessed_turns": sum(c["unassessed_turns"] for c in counts),
                    "rate": count / assessed if assessed else None}
        for category in rows[0]["behaviors"]:
            counts = [r["behaviors"][category] for r in rows]
            behaviors[category] = {**combine(counts), "subtypes": {
                sub: combine([c["subtypes"][sub] for c in counts]) for sub in counts[0]["subtypes"]}}
        comparisons.append({"group": group, "generation_condition": generated,
            "assigned_traits": json.loads(assigned), "dialogues": len(rows), "behaviors": behaviors})
    return {"groups": list(groups.values()), "dialogues": dialogues, "behavior_comparisons": comparisons}


def render(summary):
    lines = ["# Evaluation comparisons", "",
             "Descriptive results only. Groups match saved case, script, speaker prompt, generation model/settings, "
             "run seed, judge settings and prompts. Missing baselines are not inferred. "
             "Each dialogue, including a baseline, is counted once. Behavioral rates are descriptive, "
             "not trait levels or personality-recognition scores.", ""]
    lines.extend(["", "## Response measures (one row per dialogue)", "",
                  "| Group | Condition | Evaluation | Direct disclosure | Background disclosure | Contradictions / additions | Naturalness / fit | MATTR | Mean words |",
                  "|---|---|---|---|---|---|---|---|---|"])
    def rate(row):
        return f"{row['disclosed']}/{row['assessed']}; {row['unassessed']} unassessed"
    for row in summary["dialogues"]:
        overview = row["overview"]
        facts = overview["factual_findings"]
        realism = overview["realism"]
        values = [row["group"], row["generation_condition"], row["evaluation"],
                  rate(overview["disclosure"]["directly_relevant"]), rate(overview["disclosure"]["related_background"]),
                  f"{facts['contradiction']} / {facts['unsupported_addition']} ({facts['assessed_turns']} assessed turns)",
                  f"{realism['spoken_naturalness']} / {realism['conversational_fit']}",
                  row["linguistic_metrics"]["mattr"], row["linguistic_metrics"]["mean_words_per_turn"]]
        lines.append("| " + " | ".join(cell(str(v)) for v in values) + " |")
    lines.extend(["", "## Contradictions by fact timing", "",
                  "| Group | Condition | Evaluation | Turn | Item | Supplied at | Fact timing | Claim |",
                  "|---|---|---|---|---|---|---|---|"])
    for row in summary["dialogues"]:
        for c in row["contradictions"]:
            values = [row["group"], row["generation_condition"], row["evaluation"], c["turn"], c["item_id"],
                      ", ".join(map(str, c["assigned_turns"])) or "identity", c["fact_timing"], c["claim"]]
            lines.append("| " + " | ".join(cell(str(v)) for v in values) + " |")
    lines.extend(["", "## Model-added behavior", "",
                  "| Group | Condition | Dialogues | Category / subtype | Positive / assessed turns | Unassessed |",
                  "|---|---|---|---|---|---|"])
    for row in summary["behavior_comparisons"]:
        for category, counts in row["behaviors"].items():
            for name, value in [(category, counts), *[(f"{category}/{sub}", c) for sub, c in counts["subtypes"].items()]]:
                values = [row["group"], row["generation_condition"], row["dialogues"], name,
                          f"{value['count']} / {value['assessed_turns']}", value["unassessed_turns"]]
                lines.append("| " + " | ".join(cell(str(v)) for v in values) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluations", nargs="+", type=Path, help="Explicit evaluation.json files, one per patient run")
    parser.add_argument("--output", type=Path, required=True, help="Directory for analysis.json and analysis.md")
    args = parser.parse_args(argv)
    try:
        documents = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in args.evaluations]
        summary = aggregate(documents)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "analysis.md").write_text(render(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
