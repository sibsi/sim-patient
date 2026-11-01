# sim-patient

LLM-simulated GP patients with Big Five personality profiles, built from DDXPlus cases.

## Part 1: frozen interview study

A controlled comparison: every patient gets the same fixed 16-turn doctor script and the same supplied facts
per turn. Only the speaker model and the personality profile change, so any difference in the replies comes
from the profile.

- **Cases:** 8 DDXPlus patients (`data/patient_cases/`), drawn with `scripts/cases_selection.py`
  (result in `data/selected_cases.csv`). Each case has a frozen doctor script in
  `data/patient_cases/frozen_exchanges/`.
- **Profiles:** all-moderate baseline plus each trait high and low (`persona/profiles/`), 11 in total,
  inserted as plain trait levels into `prompts/patient_speaker_frozen.yaml`.
- **Speaker models:** Mistral-Small-3.2-24B, Qwen3.5-9B, Qwen3.5-27B, gemma-4-31B. Two seeds each:
  8 cases × 11 profiles × 2 seeds = 176 interviews per model, 704 in total.
- **Judge:** Qwen3.8-27B without thinking, temperature 0. Four annotation calls (turns 1–4, 5–8, 9–12, 13–16)
  cover fact disclosure, contradictions, unsupported additions and model-added behavior
  (`prompts/annotation_judge.yaml`). One call rates spoken naturalness and conversational fit
  (`prompts/judge_conversation.yaml`).

### Results

`outputs/Part1_RESULTS.zip` holds every interview with its evaluation; unzip it into `outputs/` first.
`outputs/Part1_ANALYSIS/` holds the thesis tables (`tables.md`) and one row per dialogue (`dialogues.csv`).

```bash
python scripts/apply_fixes_part1.py     # rebuild evaluations from raw judge output + approved fixes
python scripts/thesis_tables_part1.py   # write outputs/Part1_ANALYSIS
```

`apply_fixes_part1.py` repairs judge output that failed validation (misquoted excerpts, invalid references),
hand-annotates one batch whose judge call hit its token limit, and applies four rule-based label corrections.
Every change is listed in the script.

## Running

On the cluster (offline Hugging Face models), from `scripts/`:

```bash
sbatch --array=0-7 run_frozen_four_models.sbatch   # generate + evaluate: 4 models × 2 seeds
sbatch run_eval_shards.sbatch <batch>              # (re)evaluate a saved batch in shards
```

Locally or against an API:

```bash
python scripts/runner.py --backend hf --model <model> --case anna_103370 --persona-profile all --seed 1
python scripts/evaluate.py outputs/<batch> --backend hf --model Qwen/Qwen3.8-27B --seed 42
python scripts/analyze_evaluations.py <evaluation.json ...> --output <dir>   # inspect single runs
```

`--backend` also accepts `ollama`, `deepinfra` and `compatible` (API key from `LLM_API_KEY`).

## Layout

| Path | Contents |
|---|---|
| `src/patient_speaker.py`, `src/persona_profile.py` | patient prompt and Big Five rendering |
| `src/dialogue/` | frozen script loading, the interview loop, transcript output |
| `src/evaluation/` | judge calls, validation, behavior counts, reports |
| `src/data/` | building patient cases from DDXPlus |
| `src/llm_backend.py` | HTTP and Hugging Face backends |
| `scripts/` | runner, evaluator, analysis, Slurm jobs |
| `configs/calibration_set.yaml` | dialogues for the hand-labelled judge calibration |

## DDXPlus

The raw dataset (`data/ddxplus/raw/`) is not versioned. Download `release_conditions.json`,
`release_evidences.json` and `release_test_patients.csv` from the DDXPlus release
(Fansi Tchango et al., 2022) into that folder.
