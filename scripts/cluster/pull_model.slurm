#!/bin/bash
#SBATCH --job-name=ollama-pull
#SBATCH --output=../logs/ollama-pull-%j.out
#SBATCH --error=../logs/ollama-pull-%j.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --partition=gpu-short

set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

MODEL_TAG="${1:-qwen2.5:14b-instruct-q4_K_M}"

export PATH="${CALIBREAD_BIN}:${PATH}"
export OLLAMA_HOST="127.0.0.1:11434"

mkdir -p "${CALIBREAD_LOGS}" "${OLLAMA_MODELS}"

ollama serve &
OLLAMA_PID=$!
trap 'kill "${OLLAMA_PID}" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  if curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null; then
    break
  fi
  sleep 2
done

curl -sf "http://${OLLAMA_HOST}/api/version"
echo "Pulling ${MODEL_TAG} ..."
ollama pull "${MODEL_TAG}"
ollama list

echo "Done. Model stored under ${OLLAMA_MODELS}"
