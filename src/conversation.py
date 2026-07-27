import json

from llm_backend import LLMBackendPicker
from agents.doctor import DoctorAgent
from agents.patient import PatientAgent

MAX_TURNS = 6


def run_conversation(llm: LLMBackendPicker, persona: str, shards: list, max_turns: int = MAX_TURNS):
    doctor = DoctorAgent(llm=llm)
    patient = PatientAgent(llm=llm, persona=persona, shards=shards)

    # central knowledge, spoken script
    transcript = [{"role": "system_kickoff", "text": "The patient walked in. Greet them and ask what brings them in."}]

    # doctor starts convo as instructed in system prompt
    msg = doctor.generate_response(transcript)
    transcript.append({"role": "doctor", "text": msg})
    print(f"DOCTOR: {msg}\n")

    for i in range(max_turns):
        # patient replies
        patient_msg = patient.generate_response(transcript)
        transcript.append({"role": "patient", "text": patient_msg})
        print(f"PATIENT: {patient_msg}\n")

        # doctor replies, check if its last turn for assessment (DOESNT WORK)
        if i == max_turns - 1:
            transcript.append({"role": "system_kickoff", "text": "This is the last turn. Doctor, give your brief assessment."})
        doctor_msg = doctor.generate_response(transcript)
        transcript.append({"role": "doctor", "text": doctor_msg})
        print(f"DOCTOR: {doctor_msg}\n")

        # CHANGE
        if "[DONE]" in doctor_msg:
            transcript.append({"role": "doctor", "text": doctor_msg.replace("[DONE]", "").strip()})
            break

    return transcript


def main():
    # shared by both agents → model loads into VRAM once
    llm = LLMBackendPicker(backend="ollama", model_name="mistral-nemo:latest")

    scenarios = json.load(open("../datasets/medicationqa_sharded.json", encoding="utf-8"))
    # only first 3 for testing, remove this line for full run
    scenarios = scenarios[:3]

    results = []

    placeholder_persona = """Middle-aged patient. Polite but anxious, wants to understand their health. Tends to give specific, concrete facts about their situation. Speaks in first person, naturally and conversationally."""

    for i, item in enumerate(scenarios):
        print(f"\n{'='*60}")
        print(f"SCENARIO {i+1}/{len(scenarios)}")
        print(f"{'='*60}\n")

        transcript = run_conversation(
            llm=llm,
            persona=placeholder_persona,
            shards=item["shards"],
        )

        for turn in transcript:
            print(f"{turn['role'].upper()}: {turn['text']}\n")

        results.append({
            "id": item.get("id"),
            "focus_drug": item.get("focus_drug"),
            "original_question": item.get("question"),
            "persona": placeholder_persona,
            "transcript": transcript,
        })

    with open("conversations.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()