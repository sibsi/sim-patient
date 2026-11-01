"""Materialise script-defined negative facts from absent DDXPlus binary evidence."""


def add_script_shards(case, script, evidence_dict):
    if script["patient_id"] != case["patient_id"]:
        raise ValueError("Script and case patient IDs must match")
    existing = {s["shard_id"]: s for s in case["shards"]}
    source_codes = {code.split("_@_", 1)[0] for code in case["source_evidences"]}
    for item in script.get("added_shards", []):
        identifier = item["shard_id"]
        codes = item.get("evidence_codes") or ([item["evidence_code"]] if "evidence_code" in item else [])
        definitions = [evidence_dict[code] for code in codes]
        if any(d["data_type"] != "B" for d in definitions) or source_codes.intersection(codes):
            raise ValueError(f"{identifier}: negative additions require absent binary evidence")
        shard = {
            "shard_id": identifier,
            "evidence_code": codes[0] if len(codes) == 1 else None,
            "value_codes": [], "is_antecedent": all(d["is_antecedent"] for d in definitions),
            "data_type": "B",
            "original_question": " ".join(d["question_en"] for d in definitions) if definitions else None,
            "original_answer": "No", "is_initial": False,
            "code_question": definitions[0]["code_question"] if len(codes) == 1 else None,
            "statement": item["statement"], "is_negative": True, "in_history": False,
            "evidence_codes": list(codes) if codes else None,
        }
        if identifier in existing:
            if existing[identifier] != shard:
                raise ValueError(f"Conflicting added shard: {identifier}")
        else:
            case["shards"].append(shard)
            existing[identifier] = shard
