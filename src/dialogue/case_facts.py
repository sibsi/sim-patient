"""Fact table, chief complaint, doctor topic checklist and sensitive ids for one case."""
from dialogue.frozen_exchange import prepare_exchanges

# orders consultation topics present in the case script
CORE_TOPICS = ["opening", "broad", "focused", "focused_pain", "history", "lifestyle",
               "sensitive", "impact", "coping", "ice"]
FINAL_TOPICS = ["plan", "safety_net"]
# turns needed to cover a topic; defaults to one
TOPIC_COUNTS = {"focused": 2}
# optional case-specific additions to sensitive fact IDs
EXTRA_SENSITIVE = {}
# symptom details: pain quality, intensity, radiation, precision and onset;
# rash colour, peeling, swelling, pain, size and itch; locations stay with the symptom
DETAIL_CODES = {"E_54", "E_56", "E_57", "E_58", "E_59", "E_130", "E_131", "E_132", "E_134", "E_135", "E_136"}


def fact_group(shard):
    """How the patient holds a medical fact: an experience, a detail of one, or something not the case."""
    if shard["is_negative"]:
        return "negative"
    return "detail" if shard.get("evidence_code") in DETAIL_CODES else "health"


def build_case_facts(case, script, case_name=None):
    exchanges = prepare_exchanges(script, case)
    negative = {shard["shard_id"] for shard in case["shards"] if shard["is_negative"]}
    facts = [{"id": shard["shard_id"], "type": "medical", "group": fact_group(shard), "statement": shard["statement"],
              "is_negative": shard["is_negative"]} for shard in case["shards"]]
    facts += [{"id": shard["life_id"], "type": "life", "group": "life", "statement": shard["statement"],
               "is_negative": False} for shard in case.get("life_shards", [])]
    topics = {}
    for exchange in exchanges:
        if exchange["type"] in CORE_TOPICS + FINAL_TOPICS:
            topics.setdefault(exchange["type"], []).append(exchange["question"])
    if any(topic not in topics for topic in FINAL_TOPICS):
        raise ValueError("Frozen script needs plan and safety_net exchanges")
    sensitive = {fact["id"] for exchange in exchanges if "sensitive" in exchange.get("tags", [])
                 for fact in exchange["facts"]
                 if fact["disclosure_category"] == "directly_relevant" and fact["id"] not in negative}
    sensitive |= set(EXTRA_SENSITIVE.get(case_name, []))
    return {
        "identity": {"name": case["name"], "age": case["age"],
                     "sex": {"F": "female", "M": "male"}.get(case["sex"], case["sex"])},
        "chief_complaint": next(s["statement"] for s in case["shards"] if s["is_initial"]),
        "facts": facts,
        "core_topics": [topic for topic in CORE_TOPICS if topic in topics],
        "topic_counts": {topic: min(TOPIC_COUNTS.get(topic, 1), len(topics[topic]))
                         for topic in CORE_TOPICS if topic in topics},
        "topic_examples": {topic: topics[topic] for topic in CORE_TOPICS + FINAL_TOPICS if topic in topics},
        "sensitive_ids": sorted(sensitive),
    }
