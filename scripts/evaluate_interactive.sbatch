#!/bin/bash
#SBATCH --job-name=eval_interactive
#SBATCH --partition=compute
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=slurm-%x-%j.out

set -euo pipefail

# starts one judge server and evaluates a saved batch
# usage: sbatch scripts/evaluate_interactive.sbatch <batch-or-run-dir> [evaluate_interactive.py args...]
for candidate in "$PWD" "$PWD/scripts" \
    "${SLURM_SUBMIT_DIR:-$PWD}" "${SLURM_SUBMIT_DIR:-$PWD}/scripts"; do
    if [[ -f "$candidate/evaluate_interactive.py" ]]; then
        cd "$candidate"
        break
    fi
done
if [[ ! -f evaluate_interactive.py ]]; then
    echo "Submit from the repository root or scripts/." >&2
    exit 1
fi

TARGET=$(realpath "${1:?Pass a batch or run directory}")
shift
JUDGE_MODEL="Qwen/Qwen3.8-27B"

source /storage/home/sibsan/nobackup/env/bin/activate
export HF_HOME=/storage/home/sibsan/nobackup/hf_models
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

PORT=$((20000 + SLURM_JOB_ID % 10000 * 3))
LOG="$TARGET/vllm_judge_${SLURM_JOB_ID}.log"
echo "Judge: $JUDGE_MODEL | target: $TARGET"
nvidia-smi --query-gpu=name,memory.total --format=csv

vllm serve "$JUDGE_MODEL" --port "$PORT" --max-model-len 32768 \
    --gpu-memory-utilization 0.90 --generation-config vllm > "$LOG" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 180); do
    curl -sf "http://localhost:$PORT/v1/models" > /dev/null && break
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "vLLM server exited; see $LOG" >&2
        exit 1
    fi
    sleep 10
done
curl -sf "http://localhost:$PORT/v1/models" > /dev/null || { echo "vLLM not ready after 30 minutes" >&2; exit 1; }

python -u evaluate_interactive.py "$TARGET" --model "$JUDGE_MODEL" --base-url "http://localhost:$PORT/v1" "$@"
