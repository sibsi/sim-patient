import hashlib
import json
import ast
from dataclasses import asdict
import pandas as pd
import yaml
from models import Shard, PatientRecord

"""
Loader takes DDXPlus row, decodes the evidences into given Q&A pairs and paraphrased into my own neutral statements.
Puts data in PatientRecord (with list of Shards from evidences).

Examplary entry from DDXPlus:
{
    "AGE": 18,
    "DIFFERENTIAL_DIAGNOSIS": [["Bronchitis", 0.19171203430383882], ["Pneumonia", 0.17579340398940366]],
    "SEX": "M",
    "PATHOLOGY": "URTI",
    "EVIDENCES": ["E_48", "E_50", "E_53", "E_54_@_V_161", "E_54_@_V_183", "E_55_@_V_89", "E_55_@_V_108", "E_55_@_V_167", "E_56_@_4", "E_57_@_V_123", "E_58_@_3", "E_59_@_3", "E_77", "E_79", "E_91", "E_97", "E_201", "E_204_@_V_10"],
    "INITIAL_EVIDENCE": "E_91"
}

As PatientRecord:
{
    "patient_id": 4,
    "age": 18,
    "sex": "M",
    "diagnosis": "URTI",
    "differential_diagnosis": [["Bronchitis", 0.19171203430383882], ["Pneumonia", 0.17579340398940366]],
    "name": "Andreas",
    "shards": [...],
    "persona": null
}
"""

SEPERATOR = "_@_"

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
    # else: skipped
    return phrases

def build_statement(code, value_codes, data_type, phrasing, body_locations) -> str | None:
    # builds the neutral statement for one evidence
    # usually all evidence should yield a statement, but if not, gets skipped (no shard)
    statement = phrasing.get("statement")

    # binary evidence -> one possible statement
    if data_type == "B":
        return statement

    # negative values = own negated statement and done
    negative_codes = phrasing.get("negative_values", [])
    positive_codes = [v for v in value_codes if v not in negative_codes]
    if not positive_codes:
        return phrasing.get("negative_statement")

    value_phrasings = phrasing.get("value_phrasings", {})
    format = phrasing.get("format")

    # some specific fix for scale value 0 negating the statement
    if phrasing.get("zero_statement") and positive_codes[0] == "0":
        return phrasing.get("zero_statement")

    if format == "numeric":
        value = positive_codes[0]
        article = "an " if str(value).strip().startswith("8") else "a "
        return statement.format(value=value, article=article)

    if format == "binned":
        value = int(positive_codes[0])
        for bin in phrasing["bins"]:
            if value <= bin["max"]:
                return bin["statement"]
        return None

    if format == "valued":
        phrases = lookup_phrases(positive_codes[:1], value_phrasings)
        return statement.format(value=phrases[0]) if phrases else None

    if format == "multi":
        phrases = lookup_phrases(positive_codes, body_locations, key="paraphrased")
        return statement.format(values=join_values(phrases)) if phrases else None

    if format == "multi-inline":  # exception for E_54 that doesn't use body locations
        phrases = lookup_phrases(positive_codes, value_phrasings)
        return statement.format(values=join_values(phrases)) if phrases else None
    

def decode_evidence(evidences, evidence_dict, phrasings, body_locations, initial_evidence_code) -> list [Shard]:
    """
    Takes evidence codes and returns a list of shards with Q&A + paraphrasing of those.

    3 types of different evidence and how it's decoded:
    1.) "data_type": "B" handled like 'E_91' -> 'Do you have a fever (either felt or measured with a thermometer)?' Always Yes -> 'I have had a fever.'
    2.) "data_type": "C" handled like 'E_59_@_3' -> 'How fast did the pain appear?' integer after _@_ is the answer (here 3), if no _@_ then answer is "default_value" -> 'The pain came on very gradually.'
    3.) "data_type": "M" handled like 'E_152_@_V_16' -> 'Where is the swelling located?' "value_meaning" for decoding (here 'groin(R)'), if no _@_ then answer is "default_value" -> 'I have swelling in my right groin.'
    """

    # in case initial_evidence_code has value code attached, remove it
    initial_evidence_code = initial_evidence_code.split(SEPERATOR, 1)[0]

    # first, group multi-choice evidence, so answers are all together under one evidence code
    grouped = {}
    for e in evidences:
        if SEPERATOR in e:
            code, value_code = e.split(SEPERATOR, 1)
        else:
            code, value_code = e, None
        grouped.setdefault(code, []).append(value_code)

    # second, decode each group into one question with answer(s) and statement
    decoded_shards = []
    for code, value_codes in grouped.items():
        evidence_description = evidence_dict[code]
        data_type = evidence_description["data_type"]
        value_meaning_list = evidence_description.get("value_meaning", {})

        statement = build_statement(code, value_codes, data_type, phrasings[code], body_locations)
        if statement is None:
            # skip evidence, no statement
            continue

        # add answer, either Yes for binary evidence or from value codes
        if data_type == "B":
            answer = "Yes"
        else:
            answer = ", ".join(value_meaning_list.get(v, {}).get("en", v) for v in value_codes)
        
        decoded_shards.append(Shard(
            shard_id=len(decoded_shards),
            evidence_code=code,
            value_codes=value_codes,
            is_antecedent=evidence_description["is_antecedent"],
            original_question=evidence_description["question_en"],
            original_answer=answer,
            statement=statement,
            is_initial=(code == initial_evidence_code)
        ))

    if not any(shard.is_initial for shard in decoded_shards):
        print(f" Initial shard needed for convo start, so this print should never happen. {initial_evidence_code} produced no shard.")

    return decoded_shards

NAMES = {
    "M": ["Andreas", "Christian", "Daniel", "Felix", "Jakob", "Johannes",
          "Martin", "Matthias", "Michael", "Paul", "Peter", "Simon",
          "Stefan", "Thomas", "Tobias", "Wolfgang"],
    "F": ["Anna", "Christina", "Elisabeth", "Eva", "Johanna", "Julia",
          "Katharina", "Klara", "Laura", "Marie", "Martina", "Nina",
          "Petra", "Sabine", "Sophie", "Susanne"],
}

def assign_deterministic_name(patient_id: int, gender: str) -> str:
    # german names to have neutrality in convo (could make it a flag to not use names and see if it makes a difference)
    possible_names = NAMES[gender.upper()]
    digest = hashlib.sha256(str(patient_id).encode()).hexdigest()
    return possible_names[int(digest, 16) % len(possible_names)]




def main():
    with open('data/ddxplus/raw/release_evidences.json', 'r') as f:
        evidence_dict = json.load(f)

    with open('data/ddxplus/translations/evidence_phrasings.yaml', 'r') as f:
        phrasings = yaml.safe_load(f)

    with open('data/ddxplus/translations/body_locations.yaml', 'r') as f:
        body_locations = yaml.safe_load(f)

    df = pd.read_csv('data/ddxplus/raw/release_test_patients.csv')
    df = df[df["AGE"] >= 18] # skip minors: IPIP-50 not validated for children, also toddlers speaking not realistic

    """
    hand-picked 5 rows for testing
    id 4: most common pathology (URTI) with normal shards amount (14)
    id 66374 and 131882: normal shards amount
    id 2157: least shards (2)
    id 8355: most shards (35 aka 44)
    """
    # 
    DEMO_IDS = [4, 2157, 8355, 66374, 121826]


    df = df[df.index.isin(DEMO_IDS)]

    patient_records = []
    for i, row in df.iterrows():
        decoded_shards = decode_evidence(ast.literal_eval(row["EVIDENCES"]), evidence_dict, phrasings, body_locations, row["INITIAL_EVIDENCE"])

        patient_records.append(PatientRecord(
            patient_id=int(i),
            age = int(row["AGE"]),
            sex = row["SEX"],
            diagnosis = row["PATHOLOGY"],
            differential_diagnosis = ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"]),
            name = assign_deterministic_name(int(i), row["SEX"]),
            shards = decoded_shards,
            persona = None
        ))

    # decoded results saved as JSON
    with open('data/ddxplus/processed/decoded_test_patients.json', 'w', encoding='utf-8') as f:
        json.dump([asdict(record) for record in patient_records], f, ensure_ascii=False)
    
if __name__ == "__main__":
    main()