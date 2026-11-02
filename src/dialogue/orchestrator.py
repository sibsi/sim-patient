"""Run one interactive consultation: doctor turn, patient plan (if planning), patient reply, check and repair."""
import json
from pathlib import Path

from agents.checker import REPAIRABLE
from llm_backend import utc_now

MAX_REPAIRS = 2


def update_ledger(ledger, plan, turn):
    """Latest planned action per fact."""
    for d in plan["decisions"]:
        ledger[d["id"]] = (turn, d["action"])
    for v in plan["volunteer"]:
        ledger[v["id"]] = (turn, "volunteer")


def drop_reason(issue, reply, concealed, planning):
    if issue["quote"] not in reply:
        return "quote_not_found"
    if issue["type"] == "unplanned_contradiction":
        # preserves contradictions covered by a withhold or deny plan
        if issue["fact_id"] in concealed:
            return "planned_concealment"
        # leaves contradictions unchanged when no plan identifies intent
        if not planning:
            return "no_plan"
    return None


def check_and_repair(checker, patient, turns, utterance, raw, turn, ledger, last_state, plan):
    """Check, repair, check, repair, check: the final reply is always checked."""
    current = dict(ledger)
    if plan is not None:
        update_ledger(current, plan, turn)
    concealed = {fact_id for fact_id, (_, action) in current.items() if action in ("withhold", "deny")}
    reply, checks = raw, []
    for round_number in range(1, MAX_REPAIRS + 2):
        kept, dropped = [], []
        for issue in checker.check(turns, utterance, reply, turn, round_number):
            reason = drop_reason(issue, reply, concealed, patient.planning)
            if reason:
                dropped.append({**issue, "reason": reason})
            else:
                kept.append(issue)
        checks.append({"round": round_number, "reply": reply, "issues": kept, "dropped": dropped})
        repairable = [issue for issue in kept if issue["type"] in REPAIRABLE]
        if not repairable or round_number > MAX_REPAIRS:
            break
        reply = patient.repair(reply, repairable, turn, round_number, ledger, last_state)
    return {"raw_reply": raw, "checks": checks, "reply": reply,
            "repaired": reply != raw, "repair_failed": bool(repairable)}


def write_outputs(dialogue, directory):
    directory = Path(directory)
    contents = {
        "conversation.json": json.dumps(dialogue, ensure_ascii=False, indent=2) + "\n",
        "transcript.txt": "\n\n".join(f"[{t['turn']}] Doctor ({t['doctor']['topic']}): {t['doctor']['utterance']}"
                                      f"\n\nPatient: {t['reply']}" for t in dialogue["turns"]) + "\n",
    }
    for name, content in contents.items():
        temporary = directory / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(directory / name)


def run_interactive_dialogue(doctor, patient, checker, metadata, directory, *, total_turns=15, verbose=False):
    dialogue = {"metadata": metadata, "status": "running", "turns": []}
    turns, ledger, last_state = dialogue["turns"], {}, None
    write_outputs(dialogue, directory)
    turn = 0
    try:
        for turn in range(1, total_turns + 1):
            doctor_turn = doctor.next(turns, turn)
            utterance = doctor_turn["utterance"]
            plan = patient.plan(turns, utterance, turn, ledger, last_state) if patient.planning else None
            raw = patient.speak(turns, utterance, turn, ledger, last_state, plan)
            checked = check_and_repair(checker, patient, turns, utterance, raw, turn, ledger, last_state, plan)
            reply = checked["reply"]
            turns.append({"turn": turn, "doctor": doctor_turn, "plan": plan, **checked})
            if plan is not None:
                update_ledger(ledger, plan, turn)
                last_state = plan["state"]
            write_outputs(dialogue, directory)
            if verbose:
                note = " (repaired)" if checked["repaired"] else ""
                print(f"[{turn}] Doctor ({doctor_turn['topic']}): {utterance}\nPatient{note}: {reply}\n", flush=True)
    except Exception as exc:
        dialogue.update(status="failed", error={"turn": turn, "message": f"{type(exc).__name__}: {exc}"})
        write_outputs(dialogue, directory)
        raise
    dialogue["status"] = "completed"
    dialogue["metadata"]["finished_at"] = utc_now()
    write_outputs(dialogue, directory)
    return dialogue
