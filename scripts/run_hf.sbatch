#!/bin/bash
#SBATCH --job-name=dialogue_gen_eval
#SBATCH --partition=compute
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00

set -euo pipefail
# Work from scripts/ (starting from the repository root also works).
if [[ -f scripts/runner.py ]]; then
    cd scripts
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

nvidia-smi --query-gpu=name,memory.total --format=csv

python -u runner.py \
    --backend hf \
    --model "mistralai/Mistral-Small-3.2-24B-Instruct-2506" \
    --case anna_103370 \
    --seed 42 \
    --persona-profile all || true

BATCH=$(ls -td ../outputs/*/ | head -n 1)

# Evaluation uses four annotation batches and one global realism call per dialogue.
python -u evaluate.py "$BATCH" \
    --backend hf \
    --model "Qwen/Qwen3.8-27B" \
    --seed 42 \
    --temperature 0 \
    --top-p 1 \
    --max-new-tokens 6000

echo "done: $BATCH"
