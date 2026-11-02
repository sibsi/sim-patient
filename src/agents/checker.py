"""Checker agent: finds medical inventions and contradictions in one patient reply."""
from agents.common import ask_json, format_transcript
from evaluation.schemas import TEXT, array, enum, obj

ISSUE_TYPES = ["medical_invention", "unplanned_contradiction", "non_medical_invention"]
REPAIRABLE = ("medical_invention", "unplanned_contradiction")


class CheckerAgent:
    def __init__(self, backend, case_facts, prompt, *, run_seed):
        self.backend, self.prompt, self.run_seed = backend, prompt, run_seed
        facts = case_facts["facts"]

        def fact_lines(kind):
            return "\n".join(f"- {f['id']}: {f['statement']}" for f in facts if f["type"] == kind)

        self.system = prompt["system_prompt"].format(
            **case_facts["identity"], medical_facts=fact_lines("medical"), life_facts=fact_lines("life"))
        self.schema = obj({"issues": array(obj({
            "type": enum(*ISSUE_TYPES),
            "fact_id": enum(*[f["id"] for f in facts], "none"),
            "quote": TEXT,
            "note": TEXT}))})

    def check(self, turns, utterance, reply, turn, round_number):
        user = self.prompt["user_prompt"].format(transcript=format_transcript(turns), utterance=utterance, reply=reply)
        return ask_json(self.backend, [{"role": "system", "content": self.system},
                                       {"role": "user", "content": user}],
                        self.schema, run_seed=self.run_seed, turn=turn, stage=f"checker_{round_number}",
                        temperature=0)["issues"]
