#!/bin/bash
#SBATCH --job-name=interactive
#SBATCH --partition=compute
#SBATCH --gres=gpu:3
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=slurm-%x-%j.out

set -euo pipefail

# starts three servers and generates consultations; evaluate them separately
# usage: sbatch scripts/run_interactive.sbatch <patient-model> [run_interactive.py args...]
# smoke test:
# sbatch scripts/run_interactive.sbatch Qwen/Qwen3.5-27B --case jakob --persona-profile b5_moderate
for candidate in "$PWD" "$PWD/scripts" \
    "${SLURM_SUBMIT_DIR:-$PWD}" "${SLURM_SUBMIT_DIR:-$PWD}/scripts"; do
    if [[ -f "$candidate/run_interactive.py" ]]; then
        cd "$candidate"
        break
    fi
done
if [[ ! -f run_interactive.py ]]; then
    echo "Submit from the repository root or scripts/." >&2
    exit 1
fi

PATIENT_MODEL="${1:?Pass the patient model as the first argument}"
shift
DOCTOR_MODEL="mistralai/Mistral-Small-3.2-24B-Instruct-2506"
JUDGE_MODEL="Qwen/Qwen3.8-27B"

source /storage/home/sibsan/nobackup/env/bin/activate
export HF_HOME=/storage/home/sibsan/nobackup/hf_models
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

OUTPUT_ROOT="../outputs"
mkdir -p "$OUTPUT_ROOT"
OUTPUT_FOLDER=$(cd "$(mktemp -d "$OUTPUT_ROOT/interactive_${SLURM_JOB_ID}_XXXXXX")" && pwd)
echo "Patient: $PATIENT_MODEL | doctor: $DOCTOR_MODEL | judge: $JUDGE_MODEL"
echo "Output folder: $OUTPUT_FOLDER"
nvidia-smi --query-gpu=name,memory.total --format=csv

# uses assigned GPUs and derives server ports from the job ID
IFS=, read -ra GPUS <<< "${CUDA_VISIBLE_DEVICES:?No GPUs assigned}"
if [[ ${#GPUS[@]} -lt 3 ]]; then
    echo "Need 3 GPUs, got ${CUDA_VISIBLE_DEVICES}" >&2
    exit 1
fi
BASE_PORT=$((20000 + SLURM_JOB_ID % 10000 * 3))
PATIENT_PORT=$BASE_PORT
DOCTOR_PORT=$((BASE_PORT + 1))
JUDGE_PORT=$((BASE_PORT + 2))

PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null || true' EXIT

start_server() {  # gpu port model max-model-len
    CUDA_VISIBLE_DEVICES="$1" vllm serve "$3" --port "$2" --max-model-len "$4" \
        --gpu-memory-utilization 0.90 --generation-config vllm > "$OUTPUT_FOLDER/vllm_$2.log" 2>&1 &
    PIDS+=($!)
}

wait_for_server() {  # port pid
    for _ in $(seq 1 180); do
        if curl -sf "http://localhost:$1/v1/models" > /dev/null; then
            return 0
        fi
        if ! kill -0 "$2" 2>/dev/null; then
            echo "vLLM server on port $1 exited; see $OUTPUT_FOLDER/vllm_$1.log" >&2
            exit 1
        fi
        sleep 10
    done
    echo "vLLM server on port $1 not ready after 30 minutes" >&2
    exit 1
}

start_server "${GPUS[0]}" "$PATIENT_PORT" "$PATIENT_MODEL" 16384
start_server "${GPUS[1]}" "$DOCTOR_PORT" "$DOCTOR_MODEL" 16384
start_server "${GPUS[2]}" "$JUDGE_PORT" "$JUDGE_MODEL" 32768
wait_for_server "$PATIENT_PORT" "${PIDS[0]}"
wait_for_server "$DOCTOR_PORT" "${PIDS[1]}"
wait_for_server "$JUDGE_PORT" "${PIDS[2]}"
echo "All servers ready"

python -u run_interactive.py \
    --patient-model "$PATIENT_MODEL" --patient-url "http://localhost:$PATIENT_PORT/v1" \
    --doctor-model "$DOCTOR_MODEL" --doctor-url "http://localhost:$DOCTOR_PORT/v1" \
    --checker-model "$JUDGE_MODEL" --checker-url "http://localhost:$JUDGE_PORT/v1" \
    --output-dir "$OUTPUT_FOLDER" \
    "$@"
