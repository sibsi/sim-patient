"""Run a frozen 16-turn interview: fixed doctor questions, one patient reply per turn."""
from copy import deepcopy
from datetime import datetime, timezone


def run_dialogue(patient, exchanges, metadata=None, on_turn=None, verbose=True):
    dialogue = {"metadata": metadata or {}, "status": "running", "turns": []}
    history = []
    if on_turn:
        on_turn(dialogue)
    for exchange in exchanges:
        try:
            reply = patient.respond(exchange["question"], history, exchange["facts"],
                                    exchange["turn"])
        except Exception as exc:
            dialogue.update(status="failed", error={
                "turn": exchange["turn"], "doctor_question": exchange["question"],
                "provided_ids": list(exchange["fact_ids"]),
                "message": f"{type(exc).__name__}: {exc}"})
            if on_turn:
                on_turn(dialogue)
            raise
        turn = {
            "turn": exchange["turn"], "question_type": exchange["type"],
            "doctor_question": exchange["question"],
            "provided_ids": list(exchange["fact_ids"]),
            "provided_facts": deepcopy(exchange["facts"]),
            **{key: exchange[key] for key in ("tags",) if key in exchange},
            "patient_reply": reply,
        }
        dialogue["turns"].append(turn)
        history.extend([{"role": "user", "content": exchange["question"]},
                        {"role": "assistant", "content": reply}])
        if on_turn:
            on_turn(dialogue)
        if verbose:
            print(f"Doctor: {exchange['question']}\n\nPatient: {reply}\n", flush=True)
    dialogue["status"] = "completed"
    dialogue["metadata"]["finished_at"] = datetime.now(timezone.utc).isoformat()
    if on_turn:
        on_turn(dialogue)
    return dialogue
