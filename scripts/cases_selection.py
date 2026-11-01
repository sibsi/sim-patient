"""
Select the 12 evaluation cases from the DDXPlus test split.

Every rule is a plain filter, applied top to bottom. The script prints how many
cases remain after each step (the table for the thesis), then draws 2 cases per
pathology with a fixed seed: 1 female + 1 male where both exist.

Run from the project root:  python -m scripts.cases_selection
Out:  data/selected_cases.csv  (drawn cases + 3 backups per slot)
"""

import ast
import json
from collections import Counter
from functools import cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "ddxplus" / "raw"

SEED = 2026
PATHOLOGIES = ["HIV (initial infection)", "Anemia", "GERD", "Pneumonia", "Sarcoidosis", "Tuberculosis"]

# evidences that describe a trait expression (see persona_overlap in evidence_phrasings.yaml)
PERSONA_OVERLAP = {"E_16", "E_81", "E_80", "E_114", "E_111", "E_171", "E_147"}

# facts a patient might hesitate to share; lifestyle items (smoking, weight, diet) don't count
SENSITIVE = {
    "E_115", "E_189", "E_27", "E_2", "E_61", "E_62", "E_78", "E_15",   # stigma
    "E_179", "E_140", "E_188", "E_145", "E_163", "E_167",              # intimate / bodily
}

# body locations that only exist for one sex (DDXPlus sometimes mixes them up)
FEMALE_ONLY = {"V_36", "V_95", "V_96", "V_102", "V_139", "V_140", "V_141", "V_146", "V_147", "V_186", "V_190"}
MALE_ONLY = {"V_94", "V_155", "V_158", "V_168", "V_169"}

conditions = json.loads((RAW / "release_conditions.json").read_text(encoding="utf-8"))
evidences = json.loads((RAW / "release_evidences.json").read_text(encoding="utf-8"))


@cache
def pool_questions(initial_code, size=25):
    """The yes/no questions a doctor would ask after this chief complaint: the evidences most shared by
    every pathology that can present with it, so the pool does not depend on the case's diagnosis."""
    candidates = [c for c in conditions.values() if initial_code in c["symptoms"]]
    counts = Counter(code for c in candidates for code in list(c["symptoms"]) + list(c["antecedents"]))
    counts.pop(initial_code, None)  # already known from the opening
    yes_no = [code for code, _ in counts.most_common() if evidences[code]["data_type"] == "B"]
    return {evidences[code]["question_en"] for code in yes_no[:size]}


def codes(row):
    return {e.split("_@_")[0] for e in row.EVIDENCES}


def values(row):
    return {e.split("_@_")[1] for e in row.EVIDENCES if "_@_" in e}


def topics(row):
    # follow-up details (pain location, rash color, ...) share their parent's code_question.
    # details whose parent is missing (e.g. rash details without a rash) don't count as a topic.
    present = codes(row)
    return len({evidences[c]["code_question"] for c in present
                if not evidences[c]["is_antecedent"] and evidences[c]["code_question"] in present | {c}})


def top3(row):
    return [name for name, _ in row.DIFFERENTIAL_DIAGNOSIS[:3]]


def sensitive_in_pool(row):
    asked = pool_questions(row.INITIAL_EVIDENCE)
    return any(evidences[c]["question_en"] in asked for c in codes(row) & SENSITIVE)


cases = pd.read_csv(RAW / "release_test_patients.csv")
cases["EVIDENCES"] = cases.EVIDENCES.map(ast.literal_eval)
cases["DIFFERENTIAL_DIAGNOSIS"] = cases.DIFFERENTIAL_DIAGNOSIS.map(ast.literal_eval)

rules = [
    ("severity >= 3", lambda r: conditions[r.PATHOLOGY]["severity"] >= 3),
    ("not panic attack", lambda r: r.PATHOLOGY != "Panic attack"),
    ("age 18-85", lambda r: 18 <= r.AGE <= 85),
    ("body locations match sex", lambda r: not values(r) & (FEMALE_ONLY if r.SEX == "M" else MALE_ONLY)),
    ("no persona overlap", lambda r: not codes(r) & PERSONA_OVERLAP),
    ("true diagnosis in top 3", lambda r: r.PATHOLOGY in top3(r)),
    ("chief complaint is a symptom", lambda r: not evidences[r.INITIAL_EVIDENCE]["is_antecedent"]
                                               and r.INITIAL_EVIDENCE not in SENSITIVE),
    (">= 5 topics", lambda r: topics(r) >= 5),
    ("sensitive evidence present", lambda r: bool(codes(r) & SENSITIVE)),
    ("sensitive question in pool", sensitive_in_pool),
]

print(f"{'all test cases':32} {len(cases):7}")
for name, keep in rules:
    cases = cases[cases.apply(keep, axis=1)]
    print(f"{name:32} {len(cases):7}")

print("\neligible per pathology (F / M):")
for pathology, group in cases.groupby("PATHOLOGY"):
    print(f"  {pathology:28} {len(group):5}  ({(group.SEX == 'F').sum()} / {(group.SEX == 'M').sum()})")

# draw: per pathology one F and one M; if only one sex exists, two of that sex.
# rank 0 = drawn case, ranks 1-3 = backups for the manual review, in this order.
drawn = []
for pathology in PATHOLOGIES:
    group = cases[cases.PATHOLOGY == pathology]
    for slot, sex in enumerate(["F", "M"]):
        candidates = group[group.SEX == sex]
        if candidates.empty:                                   # e.g. Sarcoidosis: female only
            candidates = group[~group.index.isin([d.name for d in drawn])]
        for rank, (_, row) in enumerate(candidates.sample(n=4, random_state=SEED + slot).iterrows()):
            drawn.append(row.copy())
            drawn[-1]["slot"], drawn[-1]["rank"] = slot, rank

out = pd.DataFrame(drawn)
out.index.name = "patient_id"
out[["PATHOLOGY", "slot", "rank", "SEX", "AGE", "INITIAL_EVIDENCE", "EVIDENCES"]].to_csv(ROOT / "data" / "selected_cases.csv")

print("\ndrawn cases:")
print(out[out["rank"] == 0][["PATHOLOGY", "SEX", "AGE", "INITIAL_EVIDENCE"]].to_string())