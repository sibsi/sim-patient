import json
import ollama
from llm_backend import LLMBackendPicker

llm = LLMBackendPicker(backend="ollama", model_name="mistral-nemo:latest")

with open('datasets/medicationqa_paraphrased.json', 'r', encoding='utf-8') as f:
    scenarios = json.load(f)

results = []

test_scenarios = scenarios[:10]  # for testing, limit to first 10 scenarios

for entry in test_scenarios:
    scenario_text = entry['response']
    prompt = f"""Deconstruct the following first-person patient scenario into a chronological sequence of conversational pieces for a doctor-patient roleplay.

Given the patient scenario below, break it into a list of SHARDS. Each shard is one atomic piece of information (one fact, symptom, worry, or question) that the patient would reveal AT A TIME during a conversation with a doctor, rather than saying everything at once.

Rules for strict extraction:
- Each shard must be a short, natural, first-person sentence (or two), in the patient's voice.
- Each shard should contain exactly ONE new piece of information - don't combine two facts into one shard.
- Do not split a single fact into multiple shards.
- Order the shards the way a real patient would naturally reveal them: starting with why they're there, then supporting details, then the actual question/worry.
- Do not add any new facts, causal links between facts that aren't in the original scenario.
- Do not drop any facts, every shard must trace back to a piece of information from the original scenario.

Patient scenario:
{scenario_text}

Respond with ONLY valid JSON in this exact format, nothing else:
{{
  "shards": ["shard 1 text", "shard 2 text", "..."],
  "opener_index": 0
}}"""

    try:
        response = llm.chat(
            messages=[
                {"role": "system", "content": "You are a computational medical data analyst, who performs lossless information extraction, converting flat patient scenarios into structured, atomic multi-turn shards."},
                {"role": "user", "content": prompt}
            ],
            force_json=True # ollama's json mode forces model
        )
        raw_output = response.strip()

        # try to parse as JSON
        try:
            parsed = json.loads(raw_output)
            shards = parsed.get("shards", [])
            opener_index = parsed.get("opener_index", 0)
            parse_error = None
        except json.JSONDecodeError as e:
            shards = []
            opener_index = None
            parse_error = str(e)

    except Exception as e:
        print(f"Error on {entry['id']}: {e}")
        raw_output = "ERROR"
        shards = []
        opener_index = None
        parse_error = str(e)

    shards_data = {
        "shards": shards,
        "opener_index": opener_index,
        "parse_error": parse_error,
    }

    results.append({**entry, **shards_data})

output_file = 'datasets/medicationqa_sharded.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=4, ensure_ascii=False)