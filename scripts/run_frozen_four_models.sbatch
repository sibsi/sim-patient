#!/bin/bash
#SBATCH --job-name=frozen_four_models
#SBATCH --partition=compute
#SBATCH --gres=gpu:1
#SBATCH --array=0-7%4
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=slurm-%x-%A_%a.out

set -euo pipefail

# submit from the repository root or scripts/
# sbatch scripts/run_frozen_four_models.sbatch
# requests any GPU type; check the hardware printed below
# eight model/seed tasks, at most four at once, one GPU each
for candidate in "$PWD" "$PWD/scripts" \
    "${SLURM_SUBMIT_DIR:-$PWD}" "${SLURM_SUBMIT_DIR:-$PWD}/scripts"; do
    if [[ -f "$candidate/runner.py" && -f "$candidate/evaluate.py" ]]; then
        cd "$candidate"
        break
    fi
done
if [[ ! -f runner.py || ! -f evaluate.py ]]; then
    echo "Submit from the repository root or scripts/." >&2
    exit 1
fi

source /storage/home/sibsan/nobackup/env/bin/activate
export HF_HOME=/storage/home/sibsan/nobackup/hf_models
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"

MODELS=(
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "Qwen/Qwen3.5-9B"
    "Qwen/Qwen3.5-27B"
    "google/gemma-4-31B-it"
)
SEEDS=(1 2)
JUDGE_MODEL="Qwen/Qwen3.8-27B"
# uses the same judge seed for both patient seeds
JUDGE_SEED=42
CASES=(anna_103370 paul_102620 susanne_131469 jakob_19920
       sabine_60370 marie_93048 felix_85945 jonas_102835)

TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit this script with sbatch as an array.}"
if [[ ! "$TASK_ID" =~ ^[0-7]$ ]]; then
    echo "Expected array task ID 0 through 7, got $TASK_ID" >&2
    exit 1
fi
MODEL="${MODELS[$((TASK_ID / 2))]}"
SEED="${SEEDS[$((TASK_ID % 2))]}"

# creates a separate output folder for each task and requeue
OUTPUT_ROOT="../outputs"
mkdir -p "$OUTPUT_ROOT"
OUTPUT_FOLDER=$(mktemp -d "$OUTPUT_ROOT/frozen_${SLURM_ARRAY_JOB_ID}_${TASK_ID}_seed${SEED}_XXXXXX")
OUTPUT_FOLDER=$(cd "$OUTPUT_FOLDER" && pwd)
echo "Model: $MODEL | patient seed: $SEED | judge seed: $JUDGE_SEED"
echo "Output folder: $OUTPUT_FOLDER"
nvidia-smi --query-gpu=name,memory.total --format=csv

# runner defaults: frozen prompt, temperature 0.7, top-p 0.9,
# 400 new tokens, thinking disabled; 8 x 11 interviews per task
# stops before evaluation if generation fails
python -u runner.py \
    --backend hf \
    --model "$MODEL" \
    --case "${CASES[@]}" \
    --persona-profile all \
    --seed "$SEED" \
    --output-dir "$OUTPUT_FOLDER"

shopt -s nullglob
MANIFESTS=("$OUTPUT_FOLDER"/*/batch.json)
if [[ ${#MANIFESTS[@]} -ne 1 ]]; then
    echo "Expected exactly one batch.json inside $OUTPUT_FOLDER" >&2
    exit 1
fi
BATCH="${MANIFESTS[0]%/batch.json}"
echo "Evaluating batch: $BATCH"

# judge thinking is disabled by default
# generation exits before the judge loads onto the GPU
python -u evaluate.py "$BATCH" \
    --backend hf \
    --model "$JUDGE_MODEL" \
    --seed "$JUDGE_SEED" \
    --temperature 0 \
    --top-p 1 \
    --max-new-tokens 6000

echo "Generation and evaluation completed: $BATCH"
