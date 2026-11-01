"""Rebuild the Part 1 evaluations from the judge's raw responses and apply the approved fixes.

1. Validation repairs, only for entries that fail validation: near-miss quotes become the exact reply
   wording (or the entry is dropped), out-of-range realism context turns are removed, finding references
   are made consistent, duplicate labels are merged and disclosures of unassigned facts are dropped.
2. Felix (Qwen3.5-27B, A_high, seed 2) turns 13-16 are hand-annotated: the judge call hit its token limit.
3. Approved label corrections: stance aimed at third parties, rhetorical fillers as questions,
   "no idea" as a hypothesis, unasked_content that answers the question, proactive that restates advice.

Rerunning reproduces the same files: python scripts/apply_fixes_part1.py
"""
from collections import Counter
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.judge import evaluate, parse_judge_json, prepare_input
from evaluation.reporting import write_reports
from evaluation.schemas import BEHAVIOR_SUBTYPES, normalise, ordered_parts_ok, quote_ok, split_joined_excerpt

# Run folders exceed the Windows path limit.
RESULTS = Path("\\\\?\\" + str(ROOT / "outputs/Part1_RESULTS")) if os.name == "nt" else ROOT / "outputs/Part1_RESULTS"

# The judge quoted the fact sheet or the doctor, or paraphrased: reply text carrying its decision,
# or None when the claim is not in that turn. Keyed by (run, turn, judge quote).
QUOTES = {
    ("Mistral-Small-3.2-24B jakob_19920__b5_N_high s1", 12, "I'm a tram driver"):
        "I've made a few small mistakes while driving. I'm worried about my safety and the safety of my passengers.",
    ("Qwen3.5-9B jakob_19920__b5_N_high s2", 12, "driving the tram"): "I can't concentrate on the tracks or the passengers",
    ("Mistral-Small-3.2-24B marie_93048__b5_E_low s2", 11, "I don't drink a lot of alcohol."): "Oh, not much, really.",
    ("Qwen3.5-27B marie_93048__b5_E_high s1", 11, "I don't drink a lot of alcohol."):
        "It's definitely nothing heavy; I don't drink every day or to excess.",
    ("Qwen3.5-27B marie_93048__b5_A_low s2", 11, "I don't drink a lot of alcohol."):
        "I don't drink every day, and I certainly don't drink to excess.",
    ("Mistral-Small-3.2-24B jonas_102835__b5_O_high s2", 1, "I see you've come in because you've had a fever"):
        "Nothing too high, mind you, but enough that Sabine, my wife, thought I should come in.",
    ("Qwen3.5-27B jakob_19920__b5_N_high s2", 1, "I see you've come in because you've had a fever"):
        "It's been pretty high, actually. I've been feeling really hot and shaky",
    ("Qwen3.5-27B jonas_102835__b5_E_high s1", 11, "I don't really have a problem with alcohol"):
        "I think I've got it under control. I don't drink to excess or anything like that.",
    ("Qwen3.5-27B jonas_102835__b5_N_high s1", 11,
     "I don't drink much alcohol. Maybe a glass of wine with dinner on weekends, but nothing excessive."):
        "I don't... I don't see a problem with it, honestly.",
    ("Qwen3.5-27B paul_102620__b5_N_high s2", 9, "I'm on those blood thinners for my kidneys"):
        "I'm currently on new oral anticoagulants to manage some of the complications from the kidney issues",
    ("Qwen3.5-9B susanne_131469__b5_O_high s2", 13, "my son leaving for college"): None,
    ("Qwen3.5-27B susanne_131469__b5_A_low s1", 7, "I've only had those for a couple of weeks"): None,
    ("Qwen3.5-27B marie_93048__b5_A_low s1", 14, "the swelling in my glands and the hand pain lasting for months"): None,
    ("Qwen3.5-27B sabine_60370__b5_A_low s2", 13, "It's affecting my sleep and my work"): None,
    ("Qwen3.5-27B sabine_60370__b5_A_low s2", 13, "waking up choking"): None,
}


def turn(number, disclosure=(), findings=(), behaviors=()):
    return {"turn": number, "disclosure": [dict(item_id=i, evidence=e) for i, e in disclosure],
            "findings": list(findings), "other_observations": [], "local_realism": [],
            "behaviors": [dict(category=c, subtype=s, evidence=e, reason=r) for c, s, e, r in behaviors]}


FELIX = ("Qwen3.5-27B felix_85945__b5_A_high s2", "annotation:13", {"turns": [
    turn(13, disclosure=[("L4", "We're rehearsing every Thursday evening"), ("L5", "our first concert is next month")],
         behaviors=[("affect", "worry", ["I'm terrified I won't be able to make it or that I'll collapse on stage."],
                     "Adds fear about collapsing or failing at the upcoming concert."),
                    ("affect", "distress", ["I feel like I'm barely holding it together.", "I'm just... overwhelmed."],
                     "Expresses being overwhelmed and struggling to cope.")]),
    turn(14, findings=[{"kind": "unsupported_addition", "medical": False, "claim": "She freaked out and basically drove me here.",
                        "severity": "minor_context", "contradicted_turn": None, "contradicted_item_id": None,
                        "explanation": "Adds that the cousin drove him to the appointment; the script only says the cousin told him to get it checked."}],
         behaviors=[("affect", "worry", ["I'm scared it's something serious because of the IV drug use and the weight loss."],
                     "Expresses fear that the condition is serious."),
                    ("own_interpretation", None, ["I've been worrying it could be an infection or something related to my lungs, maybe even something from the needles.",
                                                  "But I also know the drinking and the steroids could be messing things up."],
                     "Offers his own hypotheses about the cause."),
                    ("care_engagement", "avoidant", ["I was trying to ignore it"],
                     "Describes having avoided addressing the symptom until his cousin intervened.")]),
    turn(15, behaviors=[("patient_question", "reassurance", ["are there specific risks with the tests or the X-ray I should be worried about?"],
                         "Asks whether the tests give reason to worry."),
                        ("patient_question", "practical", ["how long do you think I'll need to stay away from people before it's safe to go back?"],
                         "Asks about the logistics of isolation and returning to work.")]),
    turn(16, behaviors=[("interaction_stance", "appreciation", ["Thanks for listening."], "Thanks the doctor for listening."),
                        ("affect", "calm_optimism", ["I'm really glad I finally came in."], "Expresses relief about having come in."),
                        ("care_engagement", "proactive", ["I know I need to be honest to get better."],
                         "Explicitly treats honest disclosure as his responsibility.")]),
]})

# Hand-reviewed label edits: (action, run, turn, category, subtype, quote in the label).
EDITS = [("remove", run, n, "interaction_stance", sub, q) for run, n, sub, q in [  # stance aimed at third parties
    ("Mistral-Small-3.2-24B susanne_131469__b5_A_high s1", 12, "appreciation", "I'm grateful to have him there"),
    ("Mistral-Small-3.2-24B susanne_131469__b5_A_high s1", 13, "appreciation", "I'm grateful for that"),
    ("Mistral-Small-3.2-24B susanne_131469__b5_A_low s1", 13, "appreciation", "I appreciate that"),
    ("Mistral-Small-3.2-24B felix_85945__b5_C_low s1", 15, "reservation", "tell my boss"),
    ("Mistral-Small-3.2-24B jonas_102835__b5_N_high s1", 12, "appreciation", "which I appreciate"),
    ("Mistral-Small-3.2-24B anna_103370__b5_O_high s2", 12, "appreciation", "which I really appreciate"),
    ("Mistral-Small-3.2-24B marie_93048__b5_A_low s2", 12, "appreciation", "which I appreciate"),
    ("Mistral-Small-3.2-24B felix_85945__b5_C_low s2", 12, "appreciation", "I'm glad I listened to him"),
    ("Mistral-Small-3.2-24B jonas_102835__b5_A_high s2", 12, "appreciation", "which I appreciate"),
    ("Mistral-Small-3.2-24B jonas_102835__b5_C_high s2", 12, "appreciation", "Sabine's been great"),
    ("Qwen3.5-9B marie_93048__b5_A_low s1", 16, "appreciation", "I appreciate everything he's doing"),
    ("Qwen3.5-9B felix_85945__b5_E_high s1", 4, "appreciation", "My cousin was right"),
    ("Qwen3.5-9B marie_93048__b5_A_high s2", 13, "appreciation", "Thomas has been incredibly supportive"),
    ("Qwen3.5-9B jonas_102835__b5_N_low s2", 12, "appreciation", "which I appreciate"),
    ("Qwen3.5-9B jonas_102835__b5_O_high s2", 12, "appreciation", "I'm grateful for her"),
    ("Qwen3.5-27B anna_103370__b5_O_low s1", 12, "appreciation", "which I appreciate"),
    ("Qwen3.5-27B marie_93048__b5_moderate s1", 12, "appreciation", "which I appreciate"),
    ("Qwen3.5-27B jonas_102835__b5_E_high s1", 14, "appreciation", "actually grateful for"),
    ("Qwen3.5-27B anna_103370__b5_moderate s2", 12, "appreciation", "which I really appreciate"),
    ("Qwen3.5-27B marie_93048__b5_O_low s2", 12, "appreciation", "which I appreciate"),
    ("Qwen3.5-27B jonas_102835__b5_N_low s2", 12, "appreciation", "which I appreciate")]] + [
    ("drop_quote", "Qwen3.5-9B jonas_102835__b5_O_high s1", 16, "interaction_stance", "appreciation", "I really appreciate Sabine's help"),
    ("drop_quote", "Qwen3.5-9B jonas_102835__b5_N_low s2", 16, "interaction_stance", "appreciation", "I'm really grateful for Sabine's help"),
    # Drinking minimized while waving off the wife: avoidance of care, not stance toward the doctor.
    ("avoidant", "Qwen3.5-27B jonas_102835__b5_E_high s1", 11, "interaction_stance", "challenge", "I think I've got it under control"),
    ("avoidant", "Qwen3.5-27B jonas_102835__b5_A_low s2", 11, "interaction_stance", "challenge", "she's just being dramatic"),
    ("avoidant", "Qwen3.5-27B jonas_102835__b5_C_low s2", 11, "interaction_stance", "challenge", "she's just being worried"),
    ("avoidant", "Qwen3.5-27B jonas_102835__b5_N_low s2", 11, "interaction_stance", "reservation", "I don't think I'd say it's a problem"),
    ("remove", "Mistral-Small-3.2-24B susanne_131469__b5_N_high s2", 13, "patient_question", "reassurance", "I just want to feel better, you know?"),
    ("drop_quote", "Mistral-Small-3.2-24B marie_93048__b5_C_low s1", 15, "patient_question", "practical", "I just want to know what to expect, you know?"),
    ("remove", "gemma-4-31B marie_93048__b5_C_low s1", 14, "own_interpretation", None, "I honestly have no idea"),
    ("remove", "gemma-4-31B marie_93048__b5_E_high s2", 14, "own_interpretation", None, "I honestly have no idea"),
]
AVOIDANT = "Minimizes the drinking and waves off the wife's concern; avoids addressing it as a care issue."

# unasked_content whose every excerpt is on the asked topic: doctor-question pattern -> excerpt pattern.
# Travel answers are excluded because they add anecdotes or reasons.
ASKED_TOPICS = [(r"breathing", r"\bbreath|\bair\b|winded|wheez|chest (feels )?tight|lungs"),
                (r"shivering or chills", r"shiver|chill|cold|shak"),
                (r"smoking or drinking", r"smok|drink|alcohol|wine|beer|vap|cigar"),
                (r"bowels", r"bowel|toilet|stool|poo|diarr|constipat"),
                (r"day-to-day life", r"\bwork|\bjob|\bshift|\bat home|housework|chores"),
                (r"any pain anywhere", r"pain|ache|hurt|sore"),
                (r"long-term health conditions", r"condition|diagnos|medicat|treat|prescri|tablet"),
                (r"swollen", r"gland|swollen|throat")]
KEEP_UNASKED = {("Mistral-Small-3.2-24B susanne_131469__b5_E_high s2", 4)}  # painkillers; treatment was not asked

# Proactive excerpts in turns 15-16 that restate the doctor's plan or safety-net advice.
RESTATED = re.compile(r"come (straight |right )?back|be back in|do the tests|whenever you are|keep my distance|smaller meals"
                      r"|eating too late|stay (off|home)|take (some )?time off|keep (a close |an )?eye on|rest as much|take it easy"
                      r"|follow your advice|the changes you suggested|just like you said|I'll do it|keep our interactions minimal", re.I)

LOG = Counter()


def run_key(path):
    run = path.parents[2].name
    model, rest = run.split("__", 1)
    model = re.sub(r"-(Instruct-\d+|it)$", "", model.split("_", 1)[1].split("-", 1)[1])
    seed = re.search(r"seed(\d)", str(path)).group(1)
    return f"{model} {rest} s{seed}"


def best_match(quote, reply, threshold=0.85):
    """The reply span closest to a misquoted excerpt, or None when nothing is close."""
    words, target = reply.split(), normalise(quote)
    size, best = len(quote.split()), (0, None)
    for length in range(max(1, size - 3), size + 4):
        for start in range(len(words) - length + 1):
            span = " ".join(words[start:start + length]).strip(" ,;:")
            score = SequenceMatcher(None, normalise(span), target).ratio()
            if score > best[0]:
                best = (score, span)
    return best[1] if best[0] >= threshold else None


def covering_span(quote, reply):
    """The reply text from the first to the last part of a quote that skips text, when all parts appear in order."""
    parts = [p.strip(" .,") for p in re.split(r"\.\.\.|…|(?<=[.?!])\s+", quote) if p.strip(" .,")]
    lower, start, position = normalise(reply), None, 0
    for part in parts:
        found = lower.find(normalise(part), position)
        if found < 0:
            return None
        start = found if start is None else start
        position = found + len(normalise(part))
    span = lower[start:position] if len(parts) > 1 else ""
    return best_match(span, reply, 0.95) if span and len(span.split()) <= 60 else None


def fix_quote(key, number, quote, reply, ellipses=False):
    if (key, number, quote) in QUOTES:
        LOG["hand-picked quote"] += 1
        return QUOTES[key, number, quote]
    turns = {1: {"patient_reply": reply}}
    if quote_ok(turns, 1, quote) or (ellipses and ordered_parts_ok(turns, 1, quote)) or split_joined_excerpt(turns, 1, quote):
        return quote
    bare = re.sub(r"\s*\[[^\]]*\]", "", quote)  # drop bracketed insertions
    fixed = bare if quote_ok(turns, 1, bare) else covering_span(bare, reply)
    if fixed is None and (fixed := best_match(bare, reply)):
        words = fixed.split()  # drop a stray word carried over from the neighbouring sentence
        if len(words) > 3 and re.search(r"[.?!]$", words[0]):
            words = words[1:]
        if len(words) > 3 and re.search(r"[.?!]$", words[-2]):
            words = words[:-1]
        fixed = " ".join(words)
    LOG["quote repaired" if fixed else "entry dropped: quote not in reply"] += 1
    return fixed


def repair_annotations(key, parsed, batch, data):
    assigned = {f["id"]: f["assigned_turns"] for f in data["script_facts"]}
    for row in parsed["turns"]:
        target = next((t for t in batch if t["turn"] == row.get("turn")), None)
        if target is None:
            continue
        number, reply = target["turn"], target["patient_reply"]
        items = {i["item_id"] for i in target["expected_items"]}
        disclosures = []
        for d in row["disclosure"]:
            if d["item_id"] not in items:
                LOG["disclosure of unassigned item dropped"] += 1
                continue
            d["evidence"] = fix_quote(key, number, d["evidence"], reply, True)
            if d["evidence"]:
                disclosures.append(d)
        row["disclosure"] = disclosures
        findings = []
        for f in row["findings"]:
            if not (claim := fix_quote(key, number, f["claim"], reply, True)):
                continue
            f["claim"] = claim
            ref = f["contradicted_item_id"]
            if f["kind"] == "contradiction" and ref not in assigned and not (f["contradicted_turn"] == 0 and ref in ("name", "age", "sex")):
                named = sorted(set(re.findall(r"\b[ML]\d+\b", f["explanation"])) & set(assigned))
                if len(named) == 1:
                    f.update(contradicted_item_id=named[0], contradicted_turn=assigned[named[0]][0])
                else:  # a conflict with an earlier reply, not a script fact, is an addition in this scheme
                    f.update(kind="unsupported_addition", contradicted_turn=None, contradicted_item_id=None)
                LOG["contradiction reference repaired"] += 1
            elif f["kind"] == "unsupported_addition" and (ref is not None or f["contradicted_turn"] is not None):
                if ref in assigned:
                    f.update(kind="contradiction", contradicted_turn=assigned[ref][0])
                else:
                    f.update(contradicted_turn=None, contradicted_item_id=None)
                LOG["unsupported_addition reference repaired"] += 1
            findings.append(f)
        row["findings"] = findings
        kept, seen = [], {}
        for entry in row["behaviors"]:
            quotes = [q for q in (fix_quote(key, number, q, reply) for q in entry["evidence"]) if q]
            if not quotes:
                continue
            turns = {1: {"patient_reply": reply}}
            if sum(1 if quote_ok(turns, 1, q) else len(split_joined_excerpt(turns, 1, q) or [q]) for q in quotes) > 3:
                # Splitting the ellipses would exceed three excerpts; quote the covering reply text instead.
                quotes = [q if quote_ok(turns, 1, q) else covering_span(q, reply) or q for q in quotes]
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


def repair_realism(parsed, data):
    replies = {t["turn"]: t["patient_reply"] for t in data["turns"]}
    for rating in parsed["realism"].values():
        context = [n for n in rating["context_turns"] if 1 <= n <= rating["turn"]]
        if context != rating["context_turns"]:
            LOG["realism context turn removed"] += 1
            rating["context_turns"] = context
        if not quote_ok({1: {"patient_reply": replies[rating["turn"]]}}, 1, rating["quote"]):
            rating["quote"] = fix_quote(None, None, rating["quote"], replies[rating["turn"]]) or rating["quote"]


class Replay:
    """Return the logged judge responses, repaired, instead of calling the model."""
    def __init__(self, key, lines, data):
        self.key, self.lines, self.data = key, iter(lines), data

    def generate(self, messages, *, stage, **kwargs):
        line = next(self.lines)
        targets = json.loads(messages[1]["content"])["target_turns"]
        call = "conversation" if stage == "judge_conversation" else f"annotation:{targets[0]['turn']}"
        if (self.key, call) == FELIX[:2]:
            return json.dumps(FELIX[2])
        if line.get("error"):
            raise RuntimeError(line["error"])
        parsed = parse_judge_json(line["response"]["text"], [])
        if call == "conversation":
            repair_realism(parsed, self.data)
        else:
            numbers = {t["turn"] for t in targets}
            repair_annotations(self.key, parsed, [t for t in self.data["turns"] if t["turn"] in numbers], self.data)
        return json.dumps(parsed, ensure_ascii=False)


def edit_labels(key, result):
    questions = {t["turn"]: t["doctor_question"] for t in result["report_context"]}
    for action, run, number, category, subtype, quote in EDITS:
        if run != key:
            continue
        labels = next(t for t in result["turns"] if t["turn"] == number)["annotations"]
        label = next(a for a in labels if (a["category"], a.get("subtype")) == (category, subtype) and any(quote in q for q in a["evidence"]))
        LOG[f"edit: {action}"] += 1
        if action == "drop_quote":
            label["evidence"] = [q for q in label["evidence"] if quote not in q]
            continue
        labels.remove(label)
        if action == "avoidant":
            labels.append({"category": "care_engagement", "subtype": "avoidant", "reason": AVOIDANT, "evidence": label["evidence"],
                           "id": f"t{number:02d}_care_engagement_avoidant", "turn": number})
    for t in result["turns"]:
        kept = []
        for label in t["annotations"]:
            if label["category"] == "unasked_content" and (key, t["turn"]) not in KEEP_UNASKED and any(
                    re.search(q, questions[t["turn"]], re.I) and all(re.search(e, x, re.I) for x in label["evidence"])
                    for q, e in ASKED_TOPICS):
                LOG["unasked answer removed"] += 1
                continue
            if (label["category"], label.get("subtype")) == ("care_engagement", "proactive") and t["turn"] >= 15:
                remaining = [x for x in label["evidence"] if not RESTATED.search(x)]
                if not remaining:
                    LOG["restated proactive removed"] += 1
                    continue
                if remaining != label["evidence"]:
                    LOG["restated proactive trimmed"] += 1
                    label["evidence"] = remaining
            kept.append(label)
        t["annotations"] = kept


if __name__ == "__main__":
    statuses = Counter()
    for path in sorted(RESULTS.rglob("evaluation.json")):
        key, current = run_key(path), json.loads(path.read_text(encoding="utf-8"))
        dialogue = json.loads((path.parents[2] / "conversation.json").read_text(encoding="utf-8"))
        lines = [json.loads(l) for l in (path.parent / "evaluation_calls.jsonl").read_text(encoding="utf-8").splitlines()]
        settings = current["evaluation_settings"]
        result = evaluate(dialogue, Replay(key, lines, prepare_input(dialogue)), seed=settings["seed"],
                          temperature=settings["temperature"], judge_config=settings["judge"])
        result["prompt_snapshots"] = current["prompt_snapshots"]
        edit_labels(key, result)
        statuses[result["status"]] += 1
        write_reports(result, path.parent, current["metadata"])
    print(dict(statuses))
    for name, count in sorted(LOG.items()):
        print(f"{count:4d}  {name}")
