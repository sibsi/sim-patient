"""Doctor agent: one JSON call per turn; sees the transcript and topic checklist, never the facts."""
from agents.common import ask_json, format_transcript
from evaluation.schemas import TEXT, array, enum, obj


class DoctorAgent:
    def __init__(self, backend, case_facts, prompt, *, run_seed, total_turns=15, temperature=0.7):
        self.backend, self.prompt = backend, prompt
        self.run_seed, self.total_turns, self.temperature = run_seed, total_turns, temperature
        self.core_topics, self.topic_counts = case_facts["core_topics"], case_facts["topic_counts"]
        self.examples = {topic: " / ".join(f'"{q}"' for q in questions)
                         for topic, questions in case_facts["topic_examples"].items()}
        # shows plan and safety-net examples only on their required turns
        lines = [f"- {topic}: {self.examples[topic]}" for topic in self.core_topics]
        self.system = prompt["system_prompt"].format(
            **case_facts["identity"], chief_complaint=case_facts["chief_complaint"], topics="\n".join(lines))

    def required_topic(self, turn):
        return {1: "opening", self.total_turns - 1: "plan", self.total_turns: "safety_net"}.get(turn)

    def next(self, turns, turn):
        used = [t["doctor"]["topic"] for t in turns]
        # counts remaining topic slots; focused questions need two
        missing = [topic for topic in self.core_topics for _ in range(self.topic_counts[topic] - used.count(topic))]
        remaining = list(dict.fromkeys(missing))
        required = self.required_topic(turn)
        if required:
            allowed = [required]
            note = f"\nThis turn you must cover: {required}. Example: {self.examples[required]}"
        elif len(missing) >= self.total_turns - 1 - turn:
            # reserves the remaining turns for uncovered topics
            allowed = remaining
            note = "\nThis turn, pick one of the topics still to cover."
        else:
            allowed = remaining + ["follow_up"]
            note = ""
        notes = turns[-1]["doctor"]["follow_up_notes"] if turns else []
        user = self.prompt["turn_prompt"].format(
            transcript=format_transcript(turns), turn=turn, total=self.total_turns,
            remaining=", ".join(remaining) or "none", required=note,
            notes="\n".join(f"- {n}" for n in notes) or "(none)")
        schema = obj({"follow_up_notes": array(TEXT), "topic": enum(*allowed), "utterance": TEXT})

        def validate(data):
            if not data["utterance"].strip():
                raise ValueError("utterance must not be empty")

        data = ask_json(self.backend, [{"role": "system", "content": self.system},
                                       {"role": "user", "content": user}],
                        schema, run_seed=self.run_seed, turn=turn, stage="doctor",
                        temperature=self.temperature, validate=validate)
        return {**data, "required_topic": required}
