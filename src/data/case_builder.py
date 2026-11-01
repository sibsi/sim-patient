import json
import ast
from dataclasses import asdict
import pandas as pd
import yaml
from pathlib import Path
from ..models import Shard, PatientRecord
from .added_shards import add_script_shards

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "ddxplus"
SELECTED_CASES_PATH = PROJECT_ROOT / "data" / "selected_cases.csv"
LIFE_SHARDS_PATH = PROJECT_ROOT / "data" / "life_shards.yaml"
STATEMENT_OVERRIDES_PATH = PROJECT_ROOT / "data" / "case_statement_overrides.yaml"
CASES_DIR = PROJECT_ROOT / "data" / "patient_cases"

"""
Builds the 12 case JSONs: decodes each selected DDXPlus row into shards with first-person
statements, then applies statement overrides, life shards and the script's added shards.
"""

SEPARATOR = "_@_"

# ===HELPER METHODS===
def join_values(items: list[str]) -> str:
    # ['a'] -> 'a'; ['a','b'] -> 'a and b'; ['a','b','c'] -> 'a, b and c'
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"

def lookup_phrases(value_codes, table, key=None) -> list[str]:
    # looks up the paraphrase for each value code
    # table can be flat from value_phrasings or nested from body_locations
    phrases = []
    for v in value_codes:
        entry = table.get(v)
        # key is 'paraphrased' for body_locations, None for value_phrasings
        if key and isinstance(entry, dict):
            entry = entry.get(key)
        if entry:
            phrases.append(entry)
        else:
            raise ValueError(f"Missing {key or 'value'} phrasing for {v}")
    return phrases

PLURAL = {"foot": "feet"}

def merge_sides(regions: list[str]) -> list[str]:
    # "my right leg" + "my left leg" -> "both my legs"
    merged = []
    for r in regions:
        for side, other in (("my right ", "my left "), ("my left ", "my right ")):
            if r.startswith(side) and other + r[len(side):] in regions:
                part = r[len(side):]
                r = f"both my {PLURAL.get(part, part + 's')}"
        if r not in merged:
            merged.append(r)
    return merged

def location_text(value_codes, body_locations) -> str | None:
    """
    Plain-language body locations for first-person patient statements.
    1-2 locations: said exactly ("my left ankle").
    3+ locations: said as regions ("my chest and my upper belly").
    Collapse overlapping belly regions and combined upper/lower chest.
    """
    exact = lookup_phrases(value_codes, body_locations, key="paraphrased")
    if not exact:
        return None
    locations = (exact if len(exact) <= 2 else
                 merge_sides(lookup_phrases(value_codes, body_locations, key="region")))
    if "my belly" in locations and "my upper belly" in locations:
        locations = list(dict.fromkeys(
            "my belly" if item == "my upper belly" else item for item in locations))
    if "my lower chest" in locations and "my upper chest" in locations:
        locations = list(dict.fromkeys(
            "my chest" if item in {"my lower chest", "my upper chest"} else item
            for item in locations))
    return join_values(locations)

def build_statement(code, value_codes, data_type, phrasing, body_locations) -> tuple[str | None, bool]:
    # builds the first-person statement for one evidence -> (statement, is_negative)
    # usually all evidence should yield a statement, but if not, gets skipped (no shard)
    statement = phrasing.get("statement")

    # binary evidence -> one possible statement
    if data_type == "B":
        return statement, False

    # negative values = own negated statement and done
    negative_codes = phrasing.get("negative_values", [])
    positive_codes = [v for v in value_codes if v not in negative_codes]
    if not positive_codes:
        return phrasing.get("negative_statement"), True

    value_phrasings = phrasing.get("value_phrasings", {})
    format = phrasing.get("format")

    # some specific fix for scale value 0 negating the statement
    if phrasing.get("zero_statement") and positive_codes[0] == "0":
        return phrasing.get("zero_statement"), True

    if format == "numeric":
        value = positive_codes[0]
        return statement.format(value=value), False

    if format == "binned":
        value = int(positive_codes[0])
        for bin in phrasing["bins"]:
            if value <= bin["max"]:
                return bin["statement"], False
        return None, False

    if format == "valued":
        phrases = lookup_phrases(positive_codes[:1], value_phrasings)
        return (statement.format(value=phrases[0]) if phrases else None), False

    if format == "multi":
        if code == "E_55" and set(lookup_phrases(
                positive_codes, body_locations, key="region")) == {"my head"}:
            return "I have a headache.", False
        located = location_text(positive_codes, body_locations)
        if located is None:
            return None, False
        return statement.format(values=located), False

    if format == "multi-inline":  # exception for E_54 that doesn't use body locations
        phrases = lookup_phrases(positive_codes, value_phrasings)
        return (statement.format(values=join_values(phrases)) if phrases else None), False

    return None, False
    

def decode_evidence(evidences, evidence_dict, phrasings, body_locations, initial_evidence_code) -> list [Shard]:
    """
    Takes evidence codes and returns shards with original Q&A and first-person patient statements.

    3 types of different evidence and how it's decoded:
    1.) "data_type": "B" handled like 'E_91' -> 'Do you have a fever (either felt or measured with a thermometer)?' Always Yes -> 'I have had a fever.'
    2.) "C": 'E_59_@_3' supplies a single value.
    3.) "M": 'E_152_@_V_16' supplies a value; all values stay in one shard.
    Bare C/M entries are malformed, not an instruction to substitute a default.
    """

    # in case initial_evidence_code has value code attached, remove it
    initial_evidence_code = initial_evidence_code.split(SEPARATOR, 1)[0]

    # first, group multi-choice evidence, so answers are all together under one evidence code
    grouped = {}
    for e in evidences:
        if SEPARATOR in e:
            code, value_code = e.split(SEPARATOR, 1)
        else:
            code, value_code = e, None
        grouped.setdefault(code, []).append(value_code)

    # second, decode each group into one question with answer(s) and statement
    decoded_shards = []
    for code, value_codes in grouped.items():
        evidence_description = evidence_dict[code]
        data_type = evidence_description["data_type"]

        # DDXPlus artifact: follow-up details whose parent question is missing
        # (e.g. "the rash isn't swollen" without having a rash) -> no shard
        parent = evidence_description.get("code_question", code)
        if data_type != "B" and parent != code and parent not in grouped:
            continue

        value_meaning_list = evidence_description.get("value_meaning", {})
        if data_type == "B":
            if any(v is not None for v in value_codes):
                raise ValueError(f"Binary evidence {code} must not carry a value")
            value_codes = []
        else:
            if any(v is None for v in value_codes):
                raise ValueError(f"Missing value for {code}; C/M evidence requires _@_value")
            value_codes = list(dict.fromkeys(value_codes))
            allowed = {str(v) for v in evidence_description["possible-values"]}
            if not set(value_codes) <= allowed or (data_type == "C" and len(value_codes) != 1):
                raise ValueError(f"Invalid values for {code}: {value_codes}")

        statement, is_negative = build_statement(code, value_codes, data_type, phrasings[code], body_locations)
        meanings = [value_meaning_list.get(v, {}).get("en", v) for v in value_codes]
        unknown_value = bool(meanings) and all(v == "NA" for v in meanings)
        # NA does not describe a known medical fact. Keep it in the raw
        # source evidence, but do not create an unknown-valued patient shard.
        if unknown_value:
            continue
        if statement is None:
            raise ValueError(f"Evidence {code} could not be converted: {value_codes}")
        # N is an explicit negative answer; NA is not. Numeric zero is not
        # generically negative (e.g. E_59=0 describes gradual pain onset).
        is_negative = is_negative or (bool(meanings) and all(v == "N" for v in meanings))

        answer = "Yes" if data_type == "B" else ", ".join(meanings)

        decoded_shards.append(Shard(
            shard_id=f"M{len(decoded_shards)}",
            evidence_code=code,
            value_codes=value_codes,
            is_antecedent=evidence_description["is_antecedent"],
            data_type=data_type,
            original_question=evidence_description["question_en"],
            original_answer=answer,
            is_initial=(code == initial_evidence_code),
            code_question=evidence_description.get("code_question", code),
            statement=statement,
            is_negative=is_negative,
            # medical history the patient always knows (positive, and tagged "medical_history" in the phrasings)
            in_history=(evidence_description["is_antecedent"] and not is_negative
                        and phrasings[code].get("antecedent_kind") == "medical_history"),
        ))

    if not any(shard.is_initial for shard in decoded_shards):
        print(f" Initial shard needed for convo start, so this print should never happen. {initial_evidence_code} produced no shard.")

    return decoded_shards

# Fixed names for the 12 selected evaluation cases.
CASE_NAMES = {
    103370: "Anna",
    74168: "Christina",
    85945: "Felix",
    19920: "Jakob",
    102835: "Jonas",
    93048: "Marie",
    99935: "Olivia",
    102620: "Paul",
    133425: "Petra",
    60370: "Sabine",
    99594: "Stefan",
    131469: "Susanne",
}

def main():
    evidences_path = DATA_DIR / "raw" / "release_evidences.json"
    phrasings_path = DATA_DIR / "translations" / "evidence_phrasings.yaml"
    body_locations_path = DATA_DIR / "translations" / "body_locations.yaml"
    patients_csv_path = DATA_DIR / "raw" / "release_test_patients.csv"

    with open(evidences_path, "r", encoding="utf-8") as f:
        evidence_dict = json.load(f)

    with open(phrasings_path, "r", encoding="utf-8") as f:
        phrasings = yaml.safe_load(f)

    with open(body_locations_path, "r", encoding="utf-8") as f:
        body_locations = yaml.safe_load(f)

    with open(LIFE_SHARDS_PATH, "r", encoding="utf-8") as f:
        life_shards = yaml.safe_load(f)

    with open(STATEMENT_OVERRIDES_PATH, "r", encoding="utf-8") as f:
        statement_overrides = yaml.safe_load(f)

    # the 12 evaluation cases, chosen by scripts/cases_selection.py (rank 0 = drawn case, 1-3 = backups)
    selected = pd.read_csv(SELECTED_CASES_PATH)
    selected_ids = selected.loc[selected["rank"] == 0, "patient_id"].tolist()

    df = pd.read_csv(patients_csv_path)
    df = df[df.index.isin(selected_ids)]

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for i, row in df.iterrows():
        decoded_shards = decode_evidence(ast.literal_eval(row["EVIDENCES"]), evidence_dict, phrasings, body_locations, row["INITIAL_EVIDENCE"])
        for code, statement in statement_overrides.get(int(i), {}).items():
            matches = [shard for shard in decoded_shards if shard.evidence_code == code]
            if len(matches) != 1 or not isinstance(statement, str) or not statement.strip():
                raise ValueError(f"Invalid statement override for patient {i}, evidence {code}")
            matches[0].statement = statement

        name = CASE_NAMES[int(i)]
        case_path = CASES_DIR / f"{name.lower()}_{i}.json"

        record = PatientRecord(
            patient_id=int(i),
            age = int(row["AGE"]),
            sex = row["SEX"],
            diagnosis = row["PATHOLOGY"],
            differential_diagnosis = ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"]),
            name = name,
            shards = decoded_shards,
            source_evidences=ast.literal_eval(row["EVIDENCES"]),
        )

        case = asdict(record)
        case["life_shards"] = [{"life_id": f"L{n}", "field": field, "statement": statement}
                               for n, (field, statement) in enumerate(life_shards[int(i)].items())]
        script_path = CASES_DIR / "frozen_exchanges" / f"{case_path.stem}_frozen.yaml"
        if script_path.exists():
            add_script_shards(case, yaml.safe_load(script_path.read_text(encoding="utf-8")), evidence_dict)
        with open(case_path, "w", encoding="utf-8") as f:
            json.dump(case, f, ensure_ascii=False, indent=2)
        print(f"wrote {case_path.name} ({len(decoded_shards)} shards)")

if __name__ == "__main__":
    main()
