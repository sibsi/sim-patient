"""Load a frozen doctor script and attach the case facts for each turn."""
from pathlib import Path

import yaml


def load_exchanges(path, case):
    return prepare_exchanges(yaml.safe_load(Path(path).read_text(encoding="utf-8")), case)


def prepare_exchanges(script, case):
    if not isinstance(script, dict) or script.get("patient_id") != case["patient_id"]:
        raise ValueError("Frozen exchange script and patient case IDs must match")
    exchanges = script.get("exchanges")
    if not isinstance(exchanges, list) or not exchanges:
        raise ValueError("Frozen script must contain a nonempty 'exchanges' list with explicit 'fact_ids'; old questions/expected_ids files need manual conversion")
    facts = {}
    for prefix, items, key, category in (
        ("M", case["shards"], "shard_id", "medical"),
        ("L", case.get("life_shards", []), "life_id", "life"),
    ):
        for item in items:
            identifier = item[key]
            if not isinstance(identifier, str) or not identifier.startswith(("M", "X") if prefix == "M" else "L") or not identifier[1:].isdigit():
                raise ValueError(f"Invalid case fact ID: {identifier!r}")
            if identifier in facts:
                raise ValueError(f"Duplicate case fact ID: {identifier}")
            statement = item["statement"]
            if not isinstance(statement, str) or not statement.strip():
                raise ValueError(f"Missing statement for {identifier}")
            facts[identifier] = {"id": identifier, "statement": statement, "type": category}
    prepared = []
    for number, exchange in enumerate(exchanges, 1):
        if not isinstance(exchange, dict) or type(exchange.get("turn")) is not int or exchange["turn"] != number:
            raise ValueError(f"Exchange {number}: turn numbers must be sequential starting at 1")
        question = exchange.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Turn {number}: question must be nonempty text")
        try:
            question = question.format(name=case["name"])
        except (KeyError, ValueError, IndexError) as exc:
            raise ValueError(f"Turn {number}: only the {{name}} question placeholder is supported") from exc
        kind = exchange.get("type")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"Turn {number}: type must be nonempty metadata text")
        ids = exchange.get("fact_ids")
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            raise ValueError(f"Turn {number}: fact_ids must be an explicit list of string IDs (or [])")
        background_ids = exchange.get("background_fact_ids", [])
        if not isinstance(background_ids, list) or any(not isinstance(i, str) for i in background_ids):
            raise ValueError(f"Turn {number}: background_fact_ids must be a list of string IDs")
        ids = ids + background_ids
        if len(set(ids)) != len(ids):
            raise ValueError(f"Turn {number}: duplicate fact IDs")
        unknown = [i for i in ids if i not in facts]
        if unknown:
            raise ValueError(f"Turn {number}: unknown fact IDs {unknown}")
        row = {"turn": number, "type": kind, "question": question,
               "fact_ids": list(ids), "facts": [
                   {**facts[i], "disclosure_category": (
                       "related_background" if i in background_ids else "directly_relevant")}
                   for i in ids]}
        if "tags" in exchange:
            tags = exchange["tags"]
            if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                raise ValueError(f"Turn {number}: tags must be a list of nonempty strings")
            row["tags"] = list(tags)
        prepared.append(row)
    return prepared
