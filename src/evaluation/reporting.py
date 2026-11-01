"""Readable assessment records and descriptive rates from validated results."""
import json
import re
from pathlib import Path

from evaluation.personality import TRAITS, behavior_summary, saved_assignment


def cell(value):
    return str(value).replace("|", r"\|").replace("\n", " ")


def summarize(result):
    return {"unassessed_turns": sorted({t["turn"] for t in result["report_context"]} - {t["turn"] for t in result["turns"]}),
            "review_turns": [t["turn"] for t in result["turns"] if t.get("status") == "needs_review"]}


def evaluation_overview(result, behavior):
    """Count supplied opportunities, keeping missing assessments out of denominators."""
    turns = {t["turn"]: t for t in result["turns"]}
    disclosure = {category: {"disclosed": 0, "assessed": 0, "unassessed": 0}
                  for category in ("directly_relevant", "related_background")}
    for context in result["report_context"]:
        rows = {row["item_id"]: row for row in turns.get(context["turn"], {}).get("disclosure", [])}
        for item in context["expected_items"]:
            counts = disclosure[item.get("disclosure_category", "directly_relevant")]
            value = rows.get(item["item_id"], {}).get("disclosed")
            if type(value) is bool:
                counts["assessed"] += 1
                counts["disclosed"] += int(value)
            else:
                counts["unassessed"] += 1
    for counts in disclosure.values():
        counts["percentage"] = (100 * counts["disclosed"] / counts["assessed"]
                                if counts["assessed"] else None)
    # A review turn may have rejected findings. Exclude it rather than imply it is error-free.
    assessed = [turns[t["turn"]] for t in result["report_context"]
                if turns.get(t["turn"], {}).get("factual_status") == "completed"]
    findings = {kind: sum(f["kind"] == kind for t in assessed for f in t["findings"])
                for kind in ("contradiction", "unsupported_addition")}
    findings["by_medical"] = {label: sum(f["medical"] == value for t in assessed for f in t["findings"])
                              for label, value in (("medical", True), ("nonmedical", False))}
    findings["by_severity"] = {level: sum(f["severity"] == level for t in assessed for f in t["findings"])
                               for level in ("minor_context", "could_change_interpretation", "could_change_care")}
    findings.update(assessed_turns=len(assessed),
                    unassessed_turns=len(result["report_context"]) - len(assessed),
                    turns_with_findings=sum(bool(t["findings"]) for t in assessed))
    findings["percentage"] = (100 * findings["turns_with_findings"] / len(assessed) if assessed else None)
    realism = (result.get("conversation") or {}).get("realism", {})
    return {"completeness": "complete" if result["status"] == "completed" else "partial",
            "disclosure": disclosure, "factual_findings": findings,
            "realism": {key: realism[key]["score"] if realism.get(key) else None
                        for key in ("spoken_naturalness", "conversational_fit")},
            "behaviors": behavior["behaviors"]}


def linguistic_metrics(turns):
    """Patient-only word counts and MATTR over replies in conversation order.

    Lowercase Unicode words/numbers; ignore punctuation and underscores, but
    retain internal apostrophes (normalizing curly apostrophes). No lemmatization.
    MATTR uses every overlapping 50-word window, including across turn boundaries.
    """
    tokens = [word for turn in turns for word in re.findall(
        r"[^\W_]+(?:'[^\W_]+)*", turn["patient_reply"].lower().replace("\u2019", "'"))]
    window = 50
    windows = len(tokens) - window + 1
    mattr = (sum(len(set(tokens[i:i + window])) / window for i in range(windows))
             / windows if windows > 0 else None)
    return {"mattr": mattr, "mattr_window": window,
            "mean_words_per_turn": len(tokens) / len(turns) if turns else None}


STAGES = {"judge_annotation": "annotation", "judge_conversation": "realism"}


def label(key):
    return key.replace("_", " ")


def quoted(text):
    return f'"{cell(text)}"'


def turn_list(numbers):
    return ", ".join(map(str, numbers))


def patient_name(result):
    try:
        return json.loads(result["generation"]["inputs"]["case"]["content"])["name"]
    except (KeyError, TypeError, ValueError):
        return "Patient"


def condition_label(result):
    """Short form of the saved assignment, e.g. "C high" or "O low · N high"."""
    assigned, _ = saved_assignment(result.get("generation") or {})
    if assigned:
        changed = [f"{name[0].upper()} {assigned[name]}" for name in TRAITS if assigned[name] != "moderate"]
        return " · ".join(changed) or "all moderate"
    condition = (result.get("generation") or {}).get("personality_condition")
    generation = result.get("generation") or {}
    if condition == "unspecified":
        return "unconditioned" if not generation.get("persona_text") and "persona_profile" not in generation.get("inputs", {}) else "unknown"
    return condition or "unknown"


def header_lines(result, metadata):
    generation = result.get("generation") or {}
    settings = result.get("evaluation_settings") or {}
    calls = result["calls"]
    lines = [f"# Evaluation · {cell(patient_name(result))} · {cell(condition_label(result))}", ""]
    if metadata.get("preview"):
        lines.extend(["> **Mock layout with synthetic data. These are not model results.**", ""])
    status = [result["status"], f"{sum(c['status'] == 'completed' for c in calls)}/{len(calls)} judge calls valid"]
    status.extend(f"{n} {label(state)}" for state in ("needs_review", "failed", "skipped")
                  if (n := sum(c["status"] == state for c in calls)))
    summary = summarize(result)
    if summary["review_turns"]:
        status.append(f"review turns: {turn_list(summary['review_turns'])}")
    if summary["unassessed_turns"]:
        status.append(f"unassessed turns: {turn_list(summary['unassessed_turns'])}")
    judge = metadata.get("judge", {}).get("model_name") or (settings.get("judge") or {}).get("model")
    if judge:
        judge = " · ".join([cell(judge)] + [f"{key} {settings[key]}" for key in ("temperature", "seed")
                                            if settings.get(key) is not None])
    rows = [("Run", f"`{generation['run_id']}`" if generation.get("run_id") else None),
            ("Speaker", (generation.get("speaker") or {}).get("model_name")),
            ("Judge", judge), ("Status", " · ".join(status))]
    lines.extend(["| | |", "|---|---|"])
    lines.extend(f"| **{name}** | {value} |" for name, value in rows if value)
    return lines + [""]


def summary_lines(result, overview, metrics):
    def rate(row, bold):
        if not row["assessed"]:
            return "Unassessed"
        value = f"{row['disclosed']}/{row['assessed']}"
        value = f"{f'**{value}**' if bold else value} ({row['percentage']:.0f}%)"
        return value + (f" · {row['unassessed']} unassessed" if row["unassessed"] else "")

    disclosure = overview["disclosure"]
    lines = ["## Summary", "", "| Measure | Result |", "|---|---|",
             f"| Disclosure: directly relevant | {rate(disclosure['directly_relevant'], True)} |",
             f"| Disclosure: related background | {rate(disclosure['related_background'], False)} |"]
    # Same rule as the overview: findings from review turns stay in the details only.
    assessed = [t for t in result["turns"] if t.get("factual_status") == "completed"]
    for kind, title in (("contradiction", "Contradictions"), ("unsupported_addition", "Unsupported additions")):
        if not assessed:
            lines.append(f"| {title} | Unassessed |")
            continue
        found = [f for t in assessed for f in t["findings"] if f["kind"] == kind]
        turns = sum(any(f["kind"] == kind for f in t["findings"]) for t in assessed)
        care = sum(f["severity"] == "could_change_care" for f in found)
        lines.append(f"| {title} | **{len(found)}** in {turns}/{len(assessed)} assessed turns"
                     + (f" · {care} could change care" if care else "") + " |")
    for key, score in overview["realism"].items():
        lines.append(f"| {label(key).capitalize()} | {f'**{score}**/5' if score is not None else 'Unassessed'} |")
    mattr = f"{metrics['mattr']:.3f}" if metrics["mattr"] is not None else "Unavailable (under 50 words)"
    words = f"{metrics['mean_words_per_turn']:.1f}" if metrics["mean_words_per_turn"] is not None else "Unavailable"
    lines.extend([f"| Lexical diversity (MATTR-50) | {mattr} |", f"| Mean words per reply | {words} |", "",
                  "<sub>Disclosure counts each supplied fact on each turn it was assigned. Background facts are "
                  "optional. Finding counts cover fully assessed turns only. No combined score is calculated.</sub>", ""])
    return lines


def behavior_lines(summary):
    lines = ["## Communication behaviors", "", "| Behavior / subtype | Turns | Where |", "|---|---|---|"]
    for category, counts in summary["behaviors"].items():
        for name, row in [(category, counts), *[(f"{category} / {sub}", value) for sub, value in counts["subtypes"].items()]]:
            count = f"{row['count']}/{row['assessed_turns']}" if row["count"] is not None else "Unassessed"
            lines.append(f"| {label(name)} | {count} | {turn_list(row['turns']) or '-'} |")
    lines += ["", "Counts are turns, not phrases. Categories/subtypes can overlap; category totals count each turn once. "
              "Incomplete annotation turns are excluded from denominators. Other observations are uncounted pilot notes.", ""]
    return lines


def realism_lines(conversation):
    lines = ["## Realism", ""]
    if conversation is None:
        return lines + ["Unassessed.", ""]
    for key, rating in conversation["realism"].items():
        title = label(key).capitalize()
        if rating is None:
            lines.extend([f"**{title}:** unassessed; see judge calls.", ""])
            continue
        context = list(dict.fromkeys(rating["context_turns"]))
        note = f" Context: {'turn' if len(context) == 1 else 'turns'} {turn_list(context)}." if context else ""
        lines.extend([f"**{title}: {rating['score']}/5**", "",
                      f"> {quoted(rating['quote'])} (turn {rating['turn']})", "",
                      cell(rating["explanation"]) + note, ""])
    return lines


def finding_lines(turn):
    review = turn.get("factual_status") != "completed"
    if not turn["findings"]:
        return ["**Findings:** " + ("none valid; the turn needs review." if review else "none."), ""]
    lines = ["**Findings**" + (" *(not counted in the summary: the turn needs review)*" if review else ""), ""]
    for f in turn["findings"]:
        tags = [f"**{label(f['kind']).capitalize()}**", "medical" if f["medical"] else "non-medical",
                f"*{label(f['severity'])}*"]
        if f["contradicted_turn"] is not None:
            where = "identity" if f["contradicted_turn"] == 0 else f"turn {f['contradicted_turn']}"
            tags.append(f"conflicts with **{cell(f['contradicted_item_id'])}** ({where})")
        lines.extend([f"- {' · '.join(tags)}", f"  > {quoted(f['claim'])}", "", f"  {cell(f['explanation'])}"])
    return lines + [""]


def annotation_lines(turn):
    annotations, complete = turn.get("annotations", []), turn.get("annotations_complete")
    if complete and not annotations:
        return ["**Behaviors:** none.", ""]
    lines = ["**Behaviors**" + ("" if complete else " *(incomplete; missing entries do not mean the behavior was absent)*"), ""]
    for a in annotations:
        lines.extend([f"- `{a['id']}` **{cell(a.get('label') or label(a['category'] + (' / ' + a['subtype'] if a.get('subtype') else '')))}** – {cell(a['reason'])}",
                      "  > " + " · ".join(quoted(q) for q in a["evidence"])])
    return lines + [""]


def local_lines(turn):
    if not turn.get("local_realism_complete"):
        return ["**Linguistic notes:** incomplete.", ""]
    if not turn["local_realism"]:
        return ["**Linguistic notes:** none.", ""]
    lines = ["**Linguistic notes**", ""]
    for o in turn["local_realism"]:
        lines.extend([f"- *{label(o['dimension'])}* – {cell(o['explanation'])}", f"  > {quoted(o['quote'])}"])
    return lines + [""]


def turn_lines(result, context):
    lines = ["## Turn by turn", "", "Legend: ✓ disclosed · ✗ not disclosed · ? unassessed · *(bg)* related background", ""]
    assessed = {t["turn"]: t for t in result["turns"]}
    for number, exchange in sorted(context.items()):
        turn = assessed.get(number)
        state = " · not assessed" if turn is None else (" · needs review" if turn.get("status") == "needs_review" else "")
        lines.extend(["---", "", f"### Turn {number}{state}", "",
                      f"**Doctor:** {cell(exchange['doctor_question'])}", "",
                      f"**Patient:** {cell(exchange['patient_reply'])}", ""])
        items = exchange.get("expected_items", [])
        rows = {d["item_id"]: d for d in (turn or {}).get("disclosure", [])}
        if items:
            lines.extend(["| | Item | Supplied statement | Evidence |", "|---|---|---|---|"])
            for item in items:
                row = rows.get(item["item_id"], {})
                mark = {True: "✓", False: "✗"}.get(row.get("disclosed"), "?")
                background = " *(bg)*" if item.get("disclosure_category") == "related_background" else ""
                evidence = quoted(row["evidence"]) if row.get("evidence") else "–"
                lines.append(f"| {mark} | {cell(item['item_id'])}{background} | {cell(item['statement'])} | {evidence} |")
            lines.append("")
        else:
            lines.extend(["**Supplied statements:** none.", ""])
        if turn is None:
            lines.extend(["No valid judge result for this turn.", ""])
            continue
        lines.extend(finding_lines(turn) + annotation_lines(turn) + local_lines(turn))
    return lines


def call_lines(calls):
    lines = ["## Judge calls", "", "| # | Stage | Turns | Status | Notes |", "|---|---|---|---|---|"]
    for call in calls:
        stage = STAGES.get(call.get("stage"), call.get("stage", "?"))
        turns = call.get("target_turns")
        status = ("✓" if call["status"] == "completed" else label(call["status"])) + (" (reused)" if call.get("reused") else "")
        notes = list(call.get("normalizations", []))
        if call.get("error"):
            notes.append(call["error"])
        for issue in call.get("corrections", []):
            where = " ".join(filter(None, (f"T{issue['turn']}" if "turn" in issue else None, issue.get("field"),
                                            f"`{issue['item_id']}`" if "item_id" in issue else None)))
            notes.append(f"{where}: {issue['reason']}" if where else issue["reason"])
        lines.append(f"| {call['call']} | {stage} | {f'{min(turns)}–{max(turns)}' if turns else '–'} | {status} | "
                     f"{cell('; '.join(notes)) or '–'} |")
    return lines + ["", "<sub>Rejected values are kept in `evaluation.json`; raw judge responses are in "
                        "`evaluation_calls.jsonl`.</sub>", ""]


def write_reports(result, directory, metadata):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Derived numbers are rendered here and recomputed by analyze_evaluations.py, so the JSON keeps only results.
    behavior = behavior_summary(result["turns"], len(result["report_context"]))
    overview = evaluation_overview(result, behavior)
    context = {t["turn"]: t for t in result["report_context"]}
    lines = header_lines(result, metadata)
    lines += summary_lines(result, overview, linguistic_metrics(result["report_context"]))
    lines += behavior_lines(behavior) + realism_lines(result["conversation"])
    lines += turn_lines(result, context) + call_lines(result["calls"])
    document = {"metadata": metadata, **result}
    for name, content in (("evaluation.json", json.dumps(document, ensure_ascii=False, indent=2)),
                          ("evaluation.md", "\n".join(lines))):
        temporary = directory / (name + ".tmp")
        temporary.write_text(content + "\n", encoding="utf-8")
        temporary.replace(directory / name)
