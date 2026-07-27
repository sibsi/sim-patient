import pandas as pd
import json 
import ollama
from llm_backend import LLMBackendPicker

llm = LLMBackendPicker(backend="ollama", model_name="mistral-nemo:latest")

df = pd.read_csv('datasets/medicationqa_cleaned.csv')

results = []

test_df = df.head(10)  # for testing, limit to first 10 rows

for index, row in test_df.iterrows():
    question = row['Question']
    focus_drug = row['Focus (Drug)']
    answer = row['Answer']

    # personality later with agent, here content density as focus
    prompt = f"""You are an expert clinical scenario architect designing realistic patient stories for medical education.
Given a flat, medication-related patient question and its reference answer, transform it into a SHORT patient profile: a first-person description of a patient who would plausibly ask this question.

Your goal is to enrich this single question with realistic clinical context so it can later be dismantled into separate, trackable facts.

The profile must adhere to these constraints:
- Persona: Talkative and highly detail-oriented. Tends to give specific, concrete facts about their situation.
- Perspective: Written strictly in the first person ("I", "my", "me").
- History: Include 1-2 concrete symptoms or reasons that led to the question.
- Intent: The narrative must logically culminate in the patient's desire to uncover the answer to the original question. Do NOT state the original question as a clean, polished one-liner; embed it naturally into how a person speaks.
- Restrictions: Do NOT mention any medical advice or answers found in the reference answer. Keep the response between 4-6 sentences.

Original question: {question}
Drug in focus: {focus_drug}
Reference answer (context only, do not repeat): {answer}

Output only the patient profile, nothing else."""
    
    try:
        raw_response = llm.chat(
            messages=[
                {"role": "system", "content": "You are an expert medical scenario writer."},
                {"role": "user", "content": prompt}
            ]
        )

        response = raw_response.strip().strip('"')

    except Exception as e:
        print(f"Error on row {index}: {e}")
        response = "ERROR"

    entry = {
        "id": f"{index}_medicationqa",
        "question": question,
        "focus_drug": focus_drug,
        "answer": answer,
        "response": response
    }

    results.append(entry)

output_file = 'datasets/medicationqa_paraphrased.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=4)