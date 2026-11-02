"""Shared helpers for the interactive agents."""
import hashlib
import json


def call_seed(run_seed, turn, stage, attempt):
    key = f"{run_seed}:{turn}:{stage}:{attempt}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big") % (2**31)


def format_transcript(turns):
    lines = []
    for turn in turns:
        lines += [f"Doctor: {turn['doctor']['utterance']}", f"Patient: {turn['reply']}"]
    return "\n".join(lines) or "(nothing has been said yet)"


def chat_history(turns, own_role):
    """Earlier turns as chat messages, with own_role as the assistant."""
    messages = []
    for turn in turns:
        for role, text in (("doctor", turn["doctor"]["utterance"]), ("patient", turn["reply"])):
            messages.append({"role": "assistant" if role == own_role else "user", "content": text})
    return messages


def ask_json(backend, messages, schema, *, run_seed, turn, stage, temperature, validate=None):
    """One JSON call; on invalid output retry once with the error, then raise."""
    for attempt in (1, 2):
        text = backend.generate(messages, seed=call_seed(run_seed, turn, stage, attempt),
                                temperature=temperature, turn_number=turn, stage=stage,
                                attempt=attempt, schema=schema)
        try:
            data = json.loads(text)
            if validate:
                validate(data)
            return data
        except ValueError as exc:
            if attempt == 2:
                raise ValueError(f"{stage} turn {turn}: invalid output after retry: {exc}") from exc
            retry = f"That output was invalid: {exc}. Answer again with corrected JSON."
            messages = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": retry}]
