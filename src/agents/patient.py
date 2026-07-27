from agents.base_agent import BaseAgent

PATIENT_SYSTEM = """You are a patient talking to a doctor. Stay in character.

# Your persona
{persona}

# Your private facts (what you know about your situation)
{facts}

# How to behave
- Answer only what's asked. Reveal facts gradually, like a real patient.
- Don't dump everything at once — share what's relevant to the question.
- Speak naturally, first person. Never break character or mention being an AI."""


class PatientAgent(BaseAgent):
    def __init__(self, llm, persona: str, shards: list):
        facts = "\n".join(f"- {s}" for s in shards)
        system = PATIENT_SYSTEM.format(persona=persona, facts=facts)
        super().__init__(role="patient", system_prompt=system, llm=llm)