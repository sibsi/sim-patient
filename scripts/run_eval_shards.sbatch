#!/bin/bash
#SBATCH --job-name=eval_shards
#SBATCH --partition=compute
#SBATCH --gres=gpu:1
#SBATCH --array=0-3
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --output=slurm-%x-%A_%a.out

set -euo pipefail

# Usage (from the repository root or scripts/):
#   sbatch scripts/run_eval_shards.sbatch <batch-dir>
# Splits one batch's judging over 4 GPUs (one shard per array task) and
# skips runs that already have a completed evaluation.json.
# Judge settings are identical to run_frozen_four_models.sbatch.

BATCH_ARG="${1:?Pass the batch directory (the folder containing batch.json)}"
BATCH=$(realpath "$BATCH_ARG")
if [[ ! -f "$BATCH/batch.json" ]]; then
    echo "No batch.json in $BATCH" >&2
    exit 1
fi

for candidate in "$PWD" "$PWD/scripts" \
    "${SLURM_SUBMIT_DIR:-$PWD}" "${SLURM_SUBMIT_DIR:-$PWD}/scripts"; do
    if [[ -f "$candidate/evaluate.py" ]]; then
        cd "$candidate"
        break
    fi
done
if [[ ! -f evaluate.py ]]; then
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

SHARD="${SLURM_ARRAY_TASK_ID:?Submit with sbatch as an array}"
SHARDS="${SLURM_ARRAY_TASK_COUNT:-4}"
echo "Batch: $BATCH | shard $SHARD/$SHARDS"
nvidia-smi --query-gpu=name,memory.total --format=csv

python -u evaluate.py "$BATCH" \
    --backend hf \
    --model "Qwen/Qwen3.8-27B" \
    --seed 42 \
    --temperature 0 \
    --top-p 1 \
    --max-new-tokens 6000 \
    --skip-evaluated \
    --shard "$SHARD/$SHARDS"

echo "Shard $SHARD/$SHARDS finished: $BATCH"
