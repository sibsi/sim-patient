"""Patient speaker: one model call per turn, given that turn's facts."""
import hashlib
from pathlib import Path

import yaml

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts/patient_speaker_frozen.yaml"


def speaker_seed(run_seed, turn_number):
    """Per-turn seed derived from the run seed."""
    key = f"{run_seed}:{turn_number}:speaker:1".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big") % (2**31)


class PatientSpeaker:
    def __init__(self, case, backend, *, run_seed=0, temperature=0.7, prompt=None, persona_text=""):
        self.identity = {key: case[key] for key in ("name", "age", "sex")}
        self.identity["sex"] = {"F": "female", "M": "male"}.get(case["sex"], case["sex"])
        self.backend = backend
        self.run_seed = run_seed
        self.temperature = temperature
        self.persona_text = persona_text
        if not isinstance(persona_text, str):
            raise ValueError("persona_text must be text")
        self.prompt = prompt if prompt is not None else yaml.safe_load(PROMPT_PATH.read_text(encoding="utf-8"))
        if persona_text and not any(token in self.prompt["system_prompt"]
                                    for token in ("{persona_text}", "{b5_personality}")):
            raise ValueError("Persona conditions require a {persona_text} or {b5_personality} placeholder")

    def build_messages(self, doctor_question, chat_history, supplied_facts):
        def fact_text(category):
            facts = [fact for fact in supplied_facts if fact["type"] == category]
            if not any(fact.get("disclosure_category") == "related_background" for fact in supplied_facts):
                return "\n".join("- " + fact["statement"] for fact in facts)
            groups = []
            for key, label in (("directly_relevant", "Directly relevant facts"),
                               ("related_background", "Related background")):
                statements = ["- " + fact["statement"] for fact in facts
                              if fact.get("disclosure_category", "directly_relevant") == key]
                if statements:
                    groups.append(label + ":\n" + "\n".join(statements))
            return "\n\n".join(groups)

        def section(heading, content):
            return f"### {heading}\n{content}" if content.strip() else ""

        medical, life = fact_text("medical"), fact_text("life")
        system = self.prompt["system_prompt"].format(
            **self.identity, persona_text=self.persona_text,
            b5_personality=section("Your Personality & Disposition", self.persona_text),
            medical_section=section("Your Lived Experience (Health)", medical),
            life_section=section("Your Lived Experience (Life)", life),
            medical_facts=medical or "(No facts supplied.)",
            life_facts=life or "(No facts supplied.)")
        return ([{"role": "system", "content": system}]
                + [dict(message) for message in chat_history]
                + [{"role": "user", "content": doctor_question}])

    def respond(self, doctor_question, chat_history, supplied_facts, turn_number):
        if type(turn_number) is not int or turn_number < 1:
            raise ValueError("Turn numbers start at 1")
        messages = self.build_messages(doctor_question, chat_history, supplied_facts)
        reply = self.backend.generate(
            messages, seed=speaker_seed(self.run_seed, turn_number), temperature=self.temperature,
            turn_number=turn_number, stage="speaker", attempt=1).strip()
        if not reply:
            raise ValueError("Patient speaker returned an empty reply")
        return reply
