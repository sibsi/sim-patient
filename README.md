# SimPatient

LLM-simulated GP consultations using DDXPlus patient cases and Big Five personality profiles.
The project compares personality-conditioned replies in two settings:

| Study | Consultation | Saved experiment |
|---|---|---|
| Part 1: frozen interviews | 16 fixed doctor turns; selected facts supplied at each turn | 8 cases, 11 profiles, 4 patient models, 2 seeds: 704 interviews |
| Part 2: interactive consultations | 15 doctor turns; patient planning and private memory; a checker requests factual repairs | 8 cases, 6 profiles, 2 patient models, 2 seeds: 192 consultations |

Both studies use Qwen3.8-27B to judge disclosure, factual errors, added communication behavior,
and conversational realism. Part 2 also records which facts the doctor asks for and judges changes
in behavior. These are model annotations, not clinical assessments.

## Setup

Run commands from the repository root with Python 3.10 or newer. Create and activate an environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On Linux, activate it with `source .venv/bin/activate`. Install the core dependencies:

```text
python -m pip install -r requirements.txt
```

| Task | Additional requirements |
|---|---|
| Use an existing HTTP model server or run tests | None |
| Generate analysis tables and figures | `python -m pip install numpy matplotlib` |
| Load models locally with `--backend hf` | Suitable PyTorch/CUDA installation, then `python -m pip install -r requirements-hf.txt` |
| Launch the interactive Slurm jobs | vLLM and cached model weights on the cluster |
| Rebuild cases from raw DDXPlus data | `python -m pip install pandas` and the raw files described below |

Prepared cases and profiles are included. Running consultations does not require the raw DDXPlus
files. Inspecting or analysing saved results does not require a GPU or model access.

## Read or reproduce the saved results

Start with `outputs/Part1_ANALYSIS/tables.md` and `outputs/Part2_ANALYSIS/tables.md`.
Their directories also contain CSVs and figures. Part 1's `dialogues.csv` has one row per interview;
Part 2's `conversations.csv` and `turns.csv` provide conversation and turn-level measures.

To inspect transcripts or recompute the analysis, extract the archives:

```text
python -m zipfile -e outputs/Part1_RESULTS.zip outputs
python -m zipfile -e outputs/Part2_RESULTS.zip outputs
```

This creates `outputs/Part1_RESULTS/` and `outputs/Part2_RESULTS/`. Extraction overwrites matching
files, so keep separate re-evaluations outside these directories.

Rebuild the tables and figures from the saved evaluations:

```text
python scripts/thesis_tables_part1.py
python scripts/thesis_figures_part1.py
python scripts/analyze_interactive.py outputs/Part2_RESULTS --output-dir outputs/Part2_ANALYSIS
python scripts/thesis_figures_part2.py
```

These commands make no model calls and replace the derived analysis files. The figure scripts
write PDF and PNG versions under each analysis directory's `figures/` folder.

The archives already contain corrected evaluations. To replay the corrections from raw judge
responses, use the commands below. They **overwrite evaluation files** without model calls.
For Part 2, pass the actual batch directories containing `batch.json`, not the outer results directory.

```text
python scripts/apply_fixes_part1.py
python scripts/apply_fixes_part2.py <batch-directory> [<another-batch-directory> ...]
```

The scripts contain validation repairs and reviewed label corrections. Raw judge logs remain
available; the three completed Part 2 behavior lists also retain their original failures and
AI-assisted review records. Rerun the analysis commands after replaying corrections.

## Generate and evaluate new consultations

Each runner prints its new batch directory. Substitute that path for `<batch-directory>` below.
Generation and evaluation are separate Python commands. Use `--help` for further options.

### Part 1: frozen interviews

```text
python scripts/runner.py --backend hf --model Qwen/Qwen3.5-27B --case anna --persona-profile b5_moderate --seed 1
python scripts/evaluate.py <batch-directory> --backend hf --model Qwen/Qwen3.8-27B --seed 42
```

`--case` accepts patient names, full case names, JSON paths, or `all` for the eight active cases.
`--persona-profile all` selects the moderate baseline and ten single-trait profiles; combination
profiles are selected by name. Omitting the profile runs without a personality instruction.
The runner accepts multiple models, cases, and profiles; use a separate invocation for each seed.

Other backends are `ollama`, `deepinfra`, and `compatible`. Supply the server's model name and,
where needed, `--base-url`. DeepInfra and the compatible backend read `LLM_API_KEY`; a local
server without authentication can use a dummy key. Ollama defaults to `http://localhost:11434/v1`.

To analyse a custom selection of Part 1 evaluations:

```text
python scripts/analyze_evaluations.py <evaluation.json> [<another-evaluation.json> ...] --output outputs/my-analysis
```

### Part 2: interactive consultations

Start OpenAI-compatible servers for the patient, doctor, and checker. Defaults expect
`mistralai/Mistral-Small-3.2-24B-Instruct-2506` for the doctor and `Qwen/Qwen3.8-27B` for the
checker. Model names must match the endpoints. Set `VLLM_API_KEY` if authentication is enabled.

For servers on ports 8000, 8001, and 8002:

```text
python scripts/run_interactive.py --patient-model Qwen/Qwen3.5-27B --patient-url http://localhost:8000/v1 --doctor-url http://localhost:8001/v1 --checker-url http://localhost:8002/v1 --case anna --persona-profile b5_moderate --seed 1
python scripts/evaluate_interactive.py <batch-directory> --base-url http://localhost:8002/v1 --seed 42
python scripts/analyze_interactive.py <batch-directory> --output-dir outputs/my-interactive-analysis
```

The checker server can serve as the judge after generation. `--workers` controls parallel
consultations or evaluations (default 16). The runner accepts multiple seeds, e.g. `--seed 1 2`.

The saved experiment uses Qwen3.5-27B and gemma-4-31B-it with `b5_moderate`, `b5_N_high`,
`b5_N_low`, `b5_A_high`, `b5_A_low`, and `b5_O_low`. Its condition is `plan`, the default.
The optional `--condition no_plan` omits patient planning and private memory; it is not part of
these saved results.

### Slurm jobs

Edit the environment path, Hugging Face cache path, and resource requests for your cluster.
The scripts use offline mode, so model weights must already be cached.

| Script in `scripts/` | Task | GPU allocation |
|---|---|---|
| `run_frozen_four_models.sbatch` | Generate and evaluate Part 1: four models, two seeds | Eight array tasks, at most four at once; one GPU each |
| `run_eval_shards.sbatch` | Evaluate a saved Part 1 batch across four shards | Four array tasks; one GPU each |
| `run_interactive.sbatch` | Start patient, doctor, checker servers; generate Part 2 consultations | Three GPUs |
| `evaluate_interactive.sbatch` | Start a judge server and evaluate a saved Part 2 batch | One GPU |

Submit from the repository root; use absolute batch paths for evaluation:

```bash
sbatch scripts/run_frozen_four_models.sbatch
sbatch scripts/run_eval_shards.sbatch /absolute/path/to/batch
sbatch scripts/run_interactive.sbatch Qwen/Qwen3.5-27B --case anna --persona-profile b5_moderate --seed 1
sbatch scripts/evaluate_interactive.sbatch /absolute/path/to/batch
```

`run_hf.sbatch` is an older single-case smoke job. It selects the newest output directory for
evaluation; use `run_frozen_four_models.sbatch` for the full experiment.

## Output files and reruns

| File | Contents |
|---|---|
| `batch.json` | Run directories, settings, and generation status |
| `<run>/conversation.json` | Turns, metadata, input and source snapshots; Part 2 also records plans, state, and repairs |
| `<run>/model_calls.jsonl` | Generation requests and responses |
| `<run>/evaluations/<timestamp>/evaluation.json` | Validated annotations, settings, and evaluation status |
| `<run>/evaluations/<timestamp>/evaluation_calls.jsonl` | Raw judge requests and responses |

Run directories also contain readable transcripts; Part 1 evaluations include a Markdown report.
Snapshots preserve the inputs and source files used for a run when working files change later.

Runners create new batches; they do not resume interrupted generation automatically. Evaluators
accept a run or batch directory and select completed generation entries from a batch. Each
evaluation creates a separate timestamped directory.

`--skip-evaluated` skips runs with a **finished judge pass**, including passes with unresolved
annotations. Check `evaluation.json` for `status: completed`; completed generation alone does
not imply complete evaluation. Omit `--skip-evaluated` to re-evaluate such runs.

## Code layout

| Path | Purpose |
|---|---|
| `src/agents/` | Interactive doctor, patient planning/replies, factual checker |
| `src/dialogue/orchestrator.py` | Interactive turn order, memory updates, repair attempts |
| `src/dialogue/conversation_fixed.py`, `frozen_exchange.py` | Frozen interview loop and per-turn facts |
| `src/dialogue/case_facts.py` | Full case facts, topic checklist, sensitive facts for Part 2 |
| `src/patient_speaker.py`, `src/persona_profile.py` | Frozen patient prompting and Big Five rendering |
| `src/evaluation/` | Judge calls, annotation validation, counts, reports |
| `src/llm_backend.py` | HTTP requests and local Hugging Face inference |
| `prompts/`, `persona/profiles/` | Agent/judge instructions and personality conditions |
| `data/patient_cases/` | Eight active cases and frozen scripts; other prepared cases under `unused_cases/` |
| `scripts/` | Run, evaluate, correct, analyse, and plot results |
| `tests/` | Offline checks for evaluation, disclosure, and behavior annotation |

The case builder in `src/data/` uses `data/ddxplus/translations/`, reviewed statement overrides,
and life-background facts to turn structured evidence into patient statements. To rebuild cases,
place DDXPlus files `release_conditions.json`, `release_evidences.json`, and
`release_test_patients.csv` in `data/ddxplus/raw/` (not versioned).
`python -m scripts.cases_selection` selects cases; `python -m src.data.case_builder` rebuilds them.
These preparation steps can replace case files and are not needed to reproduce the analysis.
`python -m scripts.script_overviews` generates readable frozen-script overviews.

## Tests and release contents

The small offline suite checks evidence validation, missing annotations, behavior counts, judge
blinding, reported metrics, and saving evaluations. It does not assess the quality of a live judge.

```text
python -m unittest discover -s tests -p "test_*.py"
```

The code release includes tests, prompts, prepared data, result archives, and analysis scripts.
Local notes under `docs/` and writing under `SimPatient Thesis/` are excluded by `.gitignore`.
New runs are ignored by default; only the named Part 1 and Part 2 archives and analysis directories
are included under `outputs/`.
