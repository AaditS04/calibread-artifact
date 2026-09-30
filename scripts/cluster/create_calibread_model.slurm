#!/bin/bash
#SBATCH --job-name=ollama-create
#SBATCH --output=../logs/ollama-create-%j.out
#SBATCH --error=../logs/ollama-create-%j.err
#SBATCH --time=00:30:00
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

TARGET="${1:-calibread-qwen25-14b-instruct-q3}"
SOURCE_TAG="${2:-qwen2.5:14b-instruct-q3_K_M}"
MODELFILE="${CALIBREAD_LOGS}/${TARGET}.Modelfile"

export PATH="${CALIBREAD_BIN}:${PATH}"
export OLLAMA_HOST="127.0.0.1:11434"

mkdir -p "${CALIBREAD_LOGS}"
printf 'FROM %s\n' "${SOURCE_TAG}" > "${MODELFILE}"

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
echo "Creating ${TARGET} from ${SOURCE_TAG} ..."
ollama create "${TARGET}" -f "${MODELFILE}"
ollama show "${TARGET}" --modelfile
curl -sf "http://${OLLAMA_HOST}/api/show" -d "{\"model\":\"${TARGET}\"}" > "${CALIBREAD_LOGS}/${TARGET}.show.json"
ollama list
echo "Wrote ${CALIBREAD_LOGS}/${TARGET}.show.json"
echo "Done."
