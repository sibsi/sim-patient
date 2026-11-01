"""Judge output schemas and the validation checks shared by every evaluation stage."""
import re
import unicodedata


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def enum(*values):
    return {"type": "string", "enum": list(values)}


def array(items, minimum=None, maximum=None):
    schema = {"type": "array", "items": items}
    if minimum is not None:
        schema["minItems"] = minimum
    if maximum is not None:
        schema["maxItems"] = maximum
    return schema


TEXT = {"type": "string"}
INT = {"type": "integer"}

SEVERITIES = ("minor_context", "could_change_interpretation", "could_change_care")
REALISM_DIMENSIONS = ("spoken_naturalness", "conversational_fit")
BEHAVIOR_SUBTYPES = {
    "affect": ("worry", "distress", "embarrassment", "calm_optimism"),
    "patient_question": ("reassurance", "explanation", "practical"),
    "interaction_stance": ("appreciation", "reservation", "challenge"),
    "own_interpretation": (None,),
    "unasked_content": (None,),
    "reporting_style": ("organizing_clarifying", "difficulty_recounting"),
    "care_engagement": ("proactive", "avoidant"),
}
BEHAVIORS = tuple(BEHAVIOR_SUBTYPES)

FINDING_SCHEMA = obj({
    "kind": enum("contradiction", "unsupported_addition"),
    "medical": {"type": "boolean"},
    "claim": TEXT,
    "severity": enum(*SEVERITIES),
    "explanation": TEXT,
    "contradicted_turn": {"type": ["integer", "null"]},
    "contradicted_item_id": {"type": ["string", "null"]},
})
LOCAL_SCHEMA = array(obj({"dimension": enum(*REALISM_DIMENSIONS), "quote": TEXT, "explanation": TEXT}))
BEHAVIOR_SCHEMA = array(obj({
    "category": enum(*BEHAVIORS),
    "subtype": {"type": ["string", "null"],
                "enum": list(dict.fromkeys(t for types in BEHAVIOR_SUBTYPES.values() for t in types))},
    "reason": TEXT, "evidence": array(TEXT, 1, 3),
}), maximum=sum(len(types) for types in BEHAVIOR_SUBTYPES.values()))
OTHER_SCHEMA = array(obj({"label": TEXT, "reason": TEXT,
                          "evidence": array(TEXT, 1, 3)}), maximum=3)
TURN_SCHEMA = obj({"turns": array(obj({
    "turn": INT,
    "disclosure": array(obj({"item_id": TEXT, "evidence": TEXT})),
    "findings": array(FINDING_SCHEMA),
    "behaviors": BEHAVIOR_SCHEMA,
    "other_observations": OTHER_SCHEMA,
    "local_realism": LOCAL_SCHEMA,
}))})
CONVERSATION_SCHEMA = obj({
    "realism": obj({key: obj({"score": {"type": "integer", "minimum": 1, "maximum": 5},
                              "turn": INT, "quote": TEXT, "context_turns": array(INT), "explanation": TEXT})
                    for key in REALISM_DIMENSIONS}),
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalise(text):
    text = unicodedata.normalize("NFKC", text).translate(str.maketrans(
        {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
         "\u2014": "-", "\u2013": "-"}))
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_ok(turns, number, quote):
    """Quotes must appear in that turn's reply, ignoring case, whitespace and typographic quotes."""
    return (type(number) is int and number in turns and isinstance(quote, str)
            and bool(quote.strip()) and normalise(quote) in normalise(turns[number]["patient_reply"]))


def ordered_parts_ok(turns, number, quote, min_words=3):
    """An excerpt joined with ellipses matches when each part appears, in order, in that turn's reply."""
    if not (type(number) is int and number in turns and isinstance(quote, str)):
        return False
    text = normalise(quote)  # NFKC turns the single ellipsis character into "..."
    parts = [part.strip() for part in text.split("...") if part.strip()]
    if "..." not in text or not parts or any(len(part.split()) < min_words for part in parts):
        return False
    reply, position = normalise(turns[number]["patient_reply"]), 0
    for part in parts:
        found = reply.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True


def split_joined_excerpt(turns, number, quote):
    """Return the parts of an ellipsis-joined excerpt as separate excerpts, or None if they do not match."""
    if not ordered_parts_ok(turns, number, quote):
        return None
    parts = [part.strip(" .…") for part in re.split(r"\.\.\.|…", quote)]
    parts = [part for part in parts if part]
    return parts if all(quote_ok(turns, number, part) for part in parts) else None
