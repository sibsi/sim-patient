"""Validate and count the judge's behavior annotations."""
import yaml
from persona_profile import TRAITS, render_profile
from evaluation.schemas import BEHAVIOR_SUBTYPES, quote_ok, normalise, require, split_joined_excerpt


def saved_assignment(metadata):
    """The Big Five levels saved with the run, or None with a reason."""
    snapshot = metadata.get("inputs", {}).get("persona_profile")
    if snapshot is None:
        return None, "No saved Big Five profile; see generation metadata for the experimental condition."
    try:
        profile = yaml.safe_load(snapshot["content"])
        render_profile(profile)
        return dict(profile["traits"]), None
    except (KeyError, TypeError, ValueError, AttributeError, yaml.YAMLError):
        return None, "Saved Big Five profile is invalid; experimental assignment is unavailable."


def text(value):
    require(isinstance(value, str) and bool(value.strip()), "Missing text")


def validate_annotations(row, target, corrections, normalizations=None, supplied_statements=None):
    """Return the accepted annotations and whether the whole turn passed validation."""
    number = target["turn"]
    annotations = []
    # rejects copied fact-only evidence; paraphrases still need judge review
    statements = supplied_statements if supplied_statements is not None else [
        item["statement"] for item in target.get("expected_items", [])]
    supplied = [normalise(statement) for statement in statements]
    complete = True
    for field in ("behaviors", "other_observations"):
        rows = row.get(field)
        try:
            require(isinstance(rows, list), "Missing or invalid annotation list")
            require(len(rows) <= (sum(map(len, BEHAVIOR_SUBTYPES.values())) if field == "behaviors" else 3), "Too many annotations")
            seen = set()
            accepted = []
            for index, entry in enumerate(rows):
                expected = {"category", "subtype", "reason", "evidence"} if field == "behaviors" else {"label", "reason", "evidence"}
                require(isinstance(entry, dict) and set(entry) == expected, "Missing or unexpected annotation fields")
                text(entry["reason"])
                quotes = entry["evidence"]
                if isinstance(quotes, list) and not all(quote_ok({number: target}, number, q) for q in quotes):
                    # splits ellipsis-joined excerpts into verified reply spans
                    split = []
                    for quote in quotes:
                        parts = None if quote_ok({number: target}, number, quote) else \
                            split_joined_excerpt({number: target}, number, quote)
                        split.extend(parts or [quote])
                    if split != quotes and len(split) <= 3:
                        if normalizations is not None:
                            normalizations.append(f"Turn {number}: split ellipsis-joined {field} excerpt")
                        entry, quotes = {**entry, "evidence": split}, split
                require(isinstance(quotes, list) and 1 <= len(quotes) <= 3, "Invalid excerpt list")
                for quote in quotes:
                    text(quote)
                    require(quote_ok({number: target}, number, quote), "Evidence not found in referenced patient reply")
                require(not all(any(normalise(quote) in fact for fact in supplied) for quote in quotes),
                        "Behavior evidence contains only unchanged supplied factual text")
                if field == "behaviors":
                    category = entry["category"]
                    require(isinstance(category, str) and category in BEHAVIOR_SUBTYPES, "Unknown behavior category")
                    subtype = entry["subtype"]
                    require(subtype in BEHAVIOR_SUBTYPES[category], "Invalid subtype for behavior category")
                    require((category, subtype) not in seen, "Duplicate category/subtype in one turn")
                    seen.add((category, subtype))
                    identifier = f"t{number:02d}_{category}" + (f"_{subtype}" if subtype else "")
                else:
                    text(entry["label"])
                    category = "other_observations"
                    identifier = f"t{number:02d}_other_{index + 1}"
                accepted.append({**entry, "id": identifier, "turn": number, "category": category})
            annotations.extend(accepted)
        except (ValueError, KeyError, TypeError) as exc:
            complete = False
            corrections.append({"turn": number, "field": field, "reason": str(exc), "rejected": rows})
    return annotations, complete


def behavior_summary(turns, turn_count=16):
    """Count turns showing each category and subtype; other_observations are not counted."""
    assessed = [t for t in turns if t.get("annotations_complete")]
    annotations = [a for t in assessed for a in t["annotations"]]

    def counts(rows):
        numbers = sorted({a["turn"] for a in rows})
        return {"count": len(numbers) if assessed else None, "turns": numbers,
                "assessed_turns": len(assessed), "unassessed_turns": turn_count - len(assessed),
                "total_turns": turn_count}

    behaviors = {}
    for category, subtypes in BEHAVIOR_SUBTYPES.items():
        rows = [a for a in annotations if a["category"] == category]
        behaviors[category] = {**counts(rows), "subtypes": {
            subtype: counts([a for a in rows if a["subtype"] == subtype])
            for subtype in subtypes if subtype is not None}}
    return {"behaviors": behaviors}
