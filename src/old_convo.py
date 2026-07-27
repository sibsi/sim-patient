"""
conversation.py — minimal two-agent doctor/patient simulation.

Design (v1, deliberately simple):
- The PATIENT holds a list of shards (atomic facts) but the CODE controls
  revelation: one shard per patient turn, in order. The patient LLM only
  decides HOW to say the given shard, not WHICH fact to reveal.
- The DOCTOR is an LLM that asks questions. It does NOT know the shards;
  it has to draw them out.
- The ORCHESTRATOR loop alternates: doctor asks -> patient reveals next
  shard -> repeat until shards run out.

Later upgrades (not now): reveal the BEST-MATCHING shard instead of the
next one; add a persona to the patient; add an evaluator agent.
"""

import json
import ollama

MODEL = "mistral-nemo:latest"


# ---------------------------------------------------------------------------
# DOCTOR AGENT
# ---------------------------------------------------------------------------
def doctor_turn(conversation_history):
    """Ask the doctor LLM for its next question.

    conversation_history: a list of {"role", "content"} messages representing
    the dialogue SO FAR, written from the DOCTOR's point of view (i.e. the
    patient's utterances are 'user' messages, the doctor's are 'assistant').
    """
    system_prompt = (
        "You are a doctor conducting a medical consultation with a patient. "
        "Ask ONE clear, natural question at a time to understand their problem. "
        "Start broad, then probe for details based on what they tell you. "
        "Do not diagnose yet or give advice — your job right now is to gather "
        "information. Keep each turn short, like real speech."
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation_history

    response = ollama.chat(model=MODEL, messages=messages)
    return response.message.content.strip()


# ---------------------------------------------------------------------------
# PATIENT AGENT
# ---------------------------------------------------------------------------
def patient_turn(doctor_question, shard):
    """Ask the patient LLM to express ONE given shard, in response to the
    doctor's question.

    The patient does not choose the shard — we hand it exactly one fact and
    ask it to voice that fact naturally as an answer to the doctor.
    """
    system_prompt = (
        "You are a patient talking to a doctor. You will be given ONE piece "
        "of information about yourself and the doctor's most recent question. "
        "Respond in first person, naturally and conversationally, conveying "
        "ONLY that one piece of information. Do not volunteer other facts. "
        "Do not mention that you were 'given' information. Just talk like a "
        "real patient answering the doctor."
    )

    user_prompt = (
        f'The doctor just asked: "{doctor_question}"\n\n'
        f'The one piece of information to convey: "{shard}"\n\n'
        f"Reply as the patient, expressing only that information."
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.message.content.strip()


# ---------------------------------------------------------------------------
# ORCHESTRATOR — run one full conversation from one shard set
# ---------------------------------------------------------------------------
def run_conversation(shards, max_turns=None):
    """Alternate doctor/patient until all shards are revealed.

    Returns the full transcript as a list of {"speaker", "text"} dicts.
    """
    transcript = []

    # 'doctor_history' is the conversation as the DOCTOR sees it:
    # patient lines are 'user', doctor lines are 'assistant'.
    doctor_history = []

    n = len(shards) if max_turns is None else min(max_turns, len(shards))

    for i in range(n):
        # 1) Doctor asks a question based on the conversation so far
        question = doctor_turn(doctor_history)
        transcript.append({"speaker": "doctor", "text": question})
        # record the doctor's line in its own history (as 'assistant')
        doctor_history.append({"role": "assistant", "content": question})

        # 2) Patient answers by voicing the NEXT shard in order
        shard = shards[i]
        answer = patient_turn(question, shard)
        transcript.append({"speaker": "patient", "text": answer})
        # the patient's line becomes a 'user' message in the doctor's history
        doctor_history.append({"role": "user", "content": answer})

    return transcript


# ---------------------------------------------------------------------------
# MAIN — load sharded data, run a conversation for a few scenarios
# ---------------------------------------------------------------------------
def main():
    with open("datasets/medicationqa_sharded.json", "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    # just do the first 2 scenarios for a quick demo
    demo = scenarios[:2]

    all_conversations = []

    for entry in demo:
        shards = entry.get("shards", [])
        if not shards:
            print(f"Skipping {entry['id']} — no shards.")
            continue

        print("=" * 70)
        print(f"SCENARIO {entry['id']} — original question: {entry['question']}")
        print("=" * 70)

        transcript = run_conversation(shards)

        # print it nicely
        for turn in transcript:
            speaker = turn["speaker"].upper()
            print(f"\n{speaker}: {turn['text']}")

        print("\n")

        all_conversations.append({
            "id": entry["id"],
            "original_question": entry["question"],
            "transcript": transcript,
        })

    # save all conversations
    with open("datasets/conversations.json", "w", encoding="utf-8") as f:
        json.dump(all_conversations, f, indent=4, ensure_ascii=False)

    print("Saved to datasets/conversations.json")


if __name__ == "__main__":
    main()
