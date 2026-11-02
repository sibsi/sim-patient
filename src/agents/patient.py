"""Patient agent: a JSON plan, then the spoken reply (or the reply alone without planning),
and a minimal repair when the checker flags the reply."""
from agents.common import ask_json, call_seed, chat_history, format_transcript
from evaluation.schemas import TEXT, array, enum, obj

ACTIONS = ["disclose", "hint", "withhold", "deny"]
SCALE = {"type": "integer", "enum": [1, 2, 3, 4, 5]}


def render_memory(ledger, last_state):
    lines = []
    # omits withholds from displayed memory to avoid reinforcing them
    shown = {fact_id: entry for fact_id, entry in ledger.items() if entry[1] != "withhold"}
    if shown:
        lines.append("Your latest decision for each fact so far (what you planned):")
        lines += [f"- {fact_id}: {action} (turn {turn})" for fact_id, (turn, action) in shown.items()]
    if last_state:
        # carries state values without repeating the previous reason
        lines.append(f"How you felt last turn: trust {last_state['trust']}/5, anxiety {last_state['anxiety']}/5")
    return "\n".join(lines)


def render_plan(plan):
    lines = [f"- {d['id']}: {d['action']} ({d['why']})" for d in plan["decisions"]]
    lines += [f"- {v['id']}: bring up yourself ({v['why']})" for v in plan["volunteer"]]
    lines += [f"Trust {plan['state']['trust']}/5, anxiety {plan['state']['anxiety']}/5: {plan['state']['why']}",
              f"How the doctor comes across: {plan['doctor_tone']}",
              f"Reaction you expect from the doctor: {plan['anticipated_reaction']}"]
    return "\n".join(lines)


def validate_plan(plan):
    ids = [d["id"] for d in plan["decisions"]]
    if len(set(ids)) != len(ids):
        raise ValueError("each fact id may appear only once in decisions")
    volunteered = [v["id"] for v in plan["volunteer"]]
    if len(set(volunteered)) != len(volunteered) or set(volunteered) & set(ids):
        raise ValueError("volunteer ids must be unique and not appear in decisions")


class PatientAgent:
    def __init__(self, backend, case_facts, prompt, *, persona_text, run_seed, temperature=0.7, planning=True):
        self.backend, self.prompt, self.planning = backend, prompt, planning
        self.run_seed, self.temperature = run_seed, temperature
        self.identity = case_facts["identity"]
        facts = case_facts["facts"]
        self.negative_ids = {f["id"] for f in facts if f["is_negative"]}

        # skips empty fact groups
        sections = []
        for group, heading in prompt["fact_sections"].items():
            lines = [f"- {f['id']}: {f['statement']}" for f in facts if f["group"] == group]
            if lines:
                sections.append(f"### {heading}\n" + "\n".join(lines))
        self.fact_text = "\n\n".join(sections)
        self.persona = f"### Your Personality & Disposition\n{persona_text}" if persona_text else ""

        fact_id = enum(*[f["id"] for f in facts])
        self.plan_schema = obj({
            "decisions": array(obj({"id": fact_id, "action": enum(*ACTIONS), "why": TEXT})),
            "volunteer": array(obj({"id": fact_id, "why": TEXT})),
            "state": obj({"trust": SCALE, "anxiety": SCALE, "why": TEXT}),
            "doctor_tone": TEXT,
            "anticipated_reaction": TEXT})

    def system(self, ledger, last_state):
        memory = render_memory(ledger, last_state)
        section = self.prompt["memory_section"].format(memory=memory) if memory else ""
        return self.prompt["system_prompt"].format(
            **self.identity, b5_personality=self.persona, facts=self.fact_text, memory_section=section).rstrip()

    def plan(self, turns, utterance, turn, ledger, last_state):
        user = self.prompt["plan_prompt"].format(transcript=format_transcript(turns), utterance=utterance)
        plan = ask_json(self.backend, [{"role": "system", "content": self.system(ledger, last_state)},
                                       {"role": "user", "content": user}],
                        self.plan_schema, run_seed=self.run_seed, turn=turn, stage="patient_plan",
                        temperature=self.temperature, validate=validate_plan)
        # treats denial of an explicit negative as disclosure; keeps the original label
        for d in plan["decisions"]:
            if d["action"] == "deny" and d["id"] in self.negative_ids:
                d["action"], d["relabelled_from"] = "disclose", "deny"
        return plan

    def speak(self, turns, utterance, turn, ledger, last_state, plan):
        system = self.system(ledger, last_state) + "\n\n"
        if plan is not None:
            system += self.prompt["plan_section"].format(plan=render_plan(plan)) + "\n"
        system += self.prompt["speak_prompt"]
        messages = ([{"role": "system", "content": system}] + chat_history(turns, "patient")
                    + [{"role": "user", "content": utterance}])
        reply = self.backend.generate(messages, seed=call_seed(self.run_seed, turn, "patient_speak", 1),
                                      temperature=self.temperature, turn_number=turn,
                                      stage="patient_speak", attempt=1).strip()
        if not reply:
            raise ValueError("Patient returned an empty reply")
        return reply

    def repair(self, reply, issues, turn, round_number, ledger, last_state):
        listed = "\n".join(f'- "{issue["quote"]}": {issue["note"]}' for issue in issues)
        user = self.prompt["repair_prompt"].format(reply=reply, issues=listed)
        repaired = self.backend.generate(
            [{"role": "system", "content": self.system(ledger, last_state)}, {"role": "user", "content": user}],
            seed=call_seed(self.run_seed, turn, "patient_repair", round_number), temperature=0,
            turn_number=turn, stage="patient_repair", attempt=round_number).strip()
        if not repaired:
            raise ValueError("Patient returned an empty repair")
        return repaired
