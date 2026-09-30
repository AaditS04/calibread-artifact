#!/usr/bin/env bash
# Runs inside a Slurm GPU allocation. Starts Ollama, then the R1 sealed phases.
set -euo pipefail

CONFIG="${1:?usage: run_r1_phase.sh <config.toml> [run|score|report|r1-report|all]}"
PHASE="${2:-all}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

export PATH="${CALIBREAD_BIN}:${PATH}"
export OLLAMA_MODELS="${CALIBREAD_ROOT}/ollama_models"
export PYTHONPATH="${CALIBREAD_REPO}/src"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
OLLAMA_BIN="${CALIBREAD_BIN}/ollama"

cd "${CALIBREAD_REPO}"

if command -v module >/dev/null 2>&1; then
  module load python/3.13.7 2>/dev/null || true
fi

# shellcheck disable=SC1091
source "${CALIBREAD_VENV}/bin/activate"

# Compute nodes may already have a shared Ollama on 11434. Never use it:
# it does not see this user's model store.
OLLAMA_PORT="${OLLAMA_PORT:-$((20000 + (${SLURM_JOB_ID:-0} % 20000)))}"
export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"
export CALIBREAD_OLLAMA_BASE_URL="http://${OLLAMA_HOST}"
"${OLLAMA_BIN}" serve &
OLLAMA_PID=$!
cleanup() {
  kill "${OLLAMA_PID}" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 90); do
  if curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
  echo "ERROR: ${OLLAMA_BIN} did not become ready on ${OLLAMA_HOST}" >&2
  exit 1
fi

echo "Ollama ready on ${OLLAMA_HOST}:"
curl -sf "http://${OLLAMA_HOST}/api/version"
echo
"${OLLAMA_BIN}" list || true

run_cli() {
  python -m calibread.inference.cli "$@"
}

case "${PHASE}" in
  run)
    run_cli run "${CONFIG}"
    ;;
  score)
    run_cli score "${CONFIG}"
    ;;
  report)
    run_cli report "${CONFIG}"
    ;;
  r1-report)
    run_cli r1-report "${CONFIG}"
    ;;
  all)
    run_cli validate-config "${CONFIG}"
    run_cli plan "${CONFIG}"
    run_cli run "${CONFIG}"
    run_cli score "${CONFIG}"
    run_cli report "${CONFIG}"
    run_cli r1-report "${CONFIG}"
    ;;
  *)
    echo "Unknown phase: ${PHASE}" >&2
    exit 2
    ;;
esac

echo "Phase ${PHASE} finished for ${CONFIG}"
