from dataclasses import dataclass
from typing import Any

@dataclass
class Shard:
    shard_id: int
    # copied from DDXPlus dataset
    evidence_code: str
    value_codes: list[str]
    is_antecedent: bool

    # created for conversation
    original_question: str # from release_evidences.json
    original_answer: str
    statement: str # neutral phrasing of original question and answer
    is_initial: bool = False # exactly one shard is initial
    
@dataclass
class PatientRecord:
    patient_id: int
    # copied from DDXPlus dataset
    age: int
    sex: str
    diagnosis: str
    differential_diagnosis: list[list[Any]]

    # created for conversation
    name: str
    shards: list[Shard] # paraphrased from evidence codes
    persona: dict | None = None # later TODO big five layers



    

    