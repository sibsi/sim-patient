# SimPatient

SimPatient simulates doctor–patient consultations with an LLM patient. Each patient is grounded in a
DDXPlus case, receives personal background facts, and is assigned a Big Five personality profile.
The project studies how personality changes what the patient says and discloses, in two settings:

| Study | Consultation | Experiment |
|---|---|---|
| Part 1: scripted | 16 fixed doctor questions, each with the facts that answer it | 8 cases, 11 profiles, 4 patient models, 2 seeds: 704 consultations |
| Part 2: interactive | 15 turns with a doctor agent. The patient holds its whole case and plans each reply, and a checker repairs invented medical content | 8 cases, 6 profiles, 2 patient models, 2 seeds: 192 consultations |

After generation, Qwen3.8-27B judges every consultation: which facts were disclosed, factual errors,
communication behavior the patient adds, and conversational realism. In Part 2, it also records
which facts the doctor asked for and identifies changes in the patient's behavior over the
consultation.

## How a consultation works

### Part 1

A scripted doctor asks the same sixteen questions in every run. For each question, the
patient receives only the facts that answer it plus related background, so replies of different
profiles can be compared turn by turn.

### Part 2

A doctor agent (Mistral-Small-3.2-24B) works through a fixed list of consultation topics
but words its own questions. Before each reply, the patient writes a structured plan: for every
relevant fact it chooses to disclose, hint, withhold, or deny, and it records its trust in the doctor
and its anxiety. The reply follows the plan. A checker then looks for invented medical content and
asks the patient for a minimal repair, at most twice. A short private memory carries the patient's
earlier decisions and state into the next turn.

### Evaluation

The judge sees the transcript and the patient's facts, but not the personality
profile or the plans. Only the change judge in Part 2 receives the profile, since it decides whether
a change in behavior moves away from the assigned personality.

## Setup

Python 3.10 or newer. Install `requirements.txt`. Add `numpy` and `matplotlib` for the analysis and
figures, `requirements-hf.txt` (with PyTorch/CUDA) for local Hugging Face inference, and `pandas` to
rebuild cases from raw DDXPlus data. Part 2 serves its models with vLLM, which is much faster when
many consultations run in parallel.

## Results

The analysis of both studies is in `outputs/Part1_ANALYSIS/` and `outputs/Part2_ANALYSIS/`. Start
with `tables.md`, followed by the CSVs and the `figures/` folder. Part 1's `dialogues.csv` has one row
per consultation, and Part 2's `conversations.csv` and `turns.csv` hold consultation- and turn-level
measures.

All transcripts, plans, and evaluations are archived in `outputs/Part1_RESULTS.zip` and
`outputs/Part2_RESULTS.zip`. The archived evaluations already include the corrections of invalid or
mislabeled judge output. `scripts/apply_fixes_part1.py` and `scripts/apply_fixes_part2.py` document
and replay them from the raw judge responses. From the extracted results, the tables and figures are
rebuilt with:

```text
python scripts/thesis_tables_part1.py
python scripts/thesis_figures_part1.py
python scripts/analyze_interactive.py outputs/Part2_RESULTS --output-dir outputs/Part2_ANALYSIS
python scripts/thesis_figures_part2.py
```

## Running new consultations

### Part 1

```text
python scripts/runner.py --backend hf --model Qwen/Qwen3.5-27B --case anna --persona-profile b5_moderate --seed 1
python scripts/evaluate.py <batch-directory> --backend hf --model Qwen/Qwen3.8-27B --seed 42
```

`--case` accepts patient names or `all`, and `--persona-profile all` selects the moderate reference and
the ten single-trait profiles.

### Part 2

Start OpenAI-compatible servers for the patient, the doctor, and the checker, then:

```text
python scripts/run_interactive.py --patient-model Qwen/Qwen3.5-27B --patient-url http://localhost:8000/v1 --doctor-url http://localhost:8001/v1 --checker-url http://localhost:8002/v1 --case anna --persona-profile b5_moderate --seed 1
python scripts/evaluate_interactive.py <batch-directory> --base-url http://localhost:8002/v1 --seed 42
python scripts/analyze_interactive.py <batch-directory> --output-dir outputs/my-interactive-analysis
```

The judge runs on the checker's server. The saved experiment uses Qwen3.5-27B
and gemma-4-31B-it with the profiles `b5_moderate`, `b5_N_high`, `b5_N_low`, `b5_A_high`, `b5_A_low`,
and `b5_O_low`.

### Slurm jobs

| Script in `scripts/` | Task |
|---|---|
| `run_frozen_four_models.sbatch` | Generate and evaluate Part 1 for four models and two seeds |
| `run_eval_shards.sbatch` | Evaluate a saved Part 1 batch in four shards |
| `run_interactive.sbatch` | Start patient, doctor, and checker servers and generate Part 2 consultations |
| `evaluate_interactive.sbatch` | Start a judge server and evaluate a saved Part 2 batch |

## Output files and reruns

| File | Contents |
|---|---|
| `batch.json` | Run directories, settings, and generation status |
| `<run>/conversation.json` | Turns, metadata, and copies of inputs and source files. Part 2 also records plans, state, and repairs |
| `<run>/model_calls.jsonl` | Generation requests and responses |
| `<run>/evaluations/<timestamp>/evaluation.json` | Validated annotations, settings, and evaluation status |
| `<run>/evaluations/<timestamp>/evaluation_calls.jsonl` | Raw judge requests and responses |

Run directories also contain readable transcripts, and each run stores a copy of its inputs and
source files.

Runners always create a new batch and do not resume interrupted generation. Evaluators accept a run
or batch directory, and each evaluation is written to its own timestamped directory.
`--skip-evaluated` skips runs that already have a finished judge pass. Check `status` in
`evaluation.json` to see whether a pass completed.

## Code layout

| Path | Purpose |
|---|---|
| `src/agents/` | Doctor agent, patient planning and replies, checker |
| `src/dialogue/orchestrator.py` | Part 2 turn loop: planning, memory, checking, and repair |
| `src/dialogue/conversation_fixed.py`, `frozen_exchange.py` | Part 1 consultation loop and per-turn facts |
| `src/dialogue/case_facts.py` | Case facts, topic checklist, and sensitive facts for Part 2 |
| `src/patient_speaker.py`, `src/persona_profile.py` | Part 1 patient prompting and Big Five rendering |
| `src/evaluation/` | Judge calls, annotation validation, measures, and reports |
| `src/llm_backend.py` | Model interface for HTTP servers and local Hugging Face inference |
| `prompts/`, `persona/profiles/` | Agent and judge instructions, personality profiles |
| `data/patient_cases/` | The eight cases and their doctor scripts |
| `scripts/` | Running, evaluating, correcting, analysing, and plotting |
| `tests/` | Offline checks of the evaluation |

Cases are built in `src/data/` from DDXPlus evidence, the statement translations in
`data/ddxplus/translations/`, reviewed statement overrides, and the life facts in
`data/life_shards.yaml`. Rebuilding them requires the DDXPlus files `release_conditions.json`,
`release_evidences.json`, and `release_test_patients.csv` in `data/ddxplus/raw/`.
`python -m scripts.cases_selection` selects cases, and `python -m src.data.case_builder` builds them.
