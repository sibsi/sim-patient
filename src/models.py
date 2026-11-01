from dataclasses import dataclass
from typing import Any

@dataclass
class Shard:
    shard_id: str  # Medical IDs use M0, M1, ... and added negatives use X0, X1, ...; life shards use L-prefixed IDs.
    # taken directly from DDXPlus dataset
    evidence_code: str | None
    value_codes: list[str]
    is_antecedent: bool
    data_type: str | None
    original_question: str
    original_answer: str
    is_initial: bool  # exactly one shard is initial
    code_question: str | None

    # created for conversation
    statement: str  # neutral phrasing of original question and answer
    is_negative: bool  # statement says something is absent ("I haven't travelled ...")
    in_history: bool  # positive medical history: always known to the patient
    evidence_codes: list[str] | None = None  # source codes for added negative shards


@dataclass
class PatientRecord:
    patient_id: int
    # taken directly from DDXPlus dataset
    age: int
    sex: str
    diagnosis: str
    differential_diagnosis: list[list[Any]]
    source_evidences: list[str]  # full original DDXPlus EVIDENCES list

    # created for conversation
    name: str
    shards: list[Shard]  # paraphrased from evidence codes
