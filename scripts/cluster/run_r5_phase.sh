#!/usr/bin/env bash
# Runs inside a Slurm GPU allocation. Starts Ollama, then CalibRead CLI phases.
set -euo pipefail

CONFIG="${1:?usage: run_r5_phase.sh <config.toml> [run|score|report|composition|all]}"
PHASE="${2:-all}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

export PATH="${CALIBREAD_BIN}:${PATH}"
export OLLAMA_HOST="127.0.0.1:11434"
export PYTHONPATH="${CALIBREAD_REPO}/src"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

cd "${CALIBREAD_REPO}"

if command -v module >/dev/null 2>&1; then
  module load python/3.13.7 2>/dev/null || true
fi

# shellcheck disable=SC1091
source "${CALIBREAD_VENV}/bin/activate"

if ! curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
  ollama serve &
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
fi

if ! curl -sf "http://${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
  echo "ERROR: Ollama did not become ready on ${OLLAMA_HOST}" >&2
  exit 1
fi

echo "Ollama ready:"
curl -sf "http://${OLLAMA_HOST}/api/version"
ollama list || true

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
  composition)
    run_cli composition-report "${CONFIG}" --bootstrap-samples 2000
    ;;
  all)
    run_cli validate-config "${CONFIG}"
    run_cli plan "${CONFIG}"
    run_cli run "${CONFIG}"
    run_cli score "${CONFIG}"
    run_cli report "${CONFIG}"
    run_cli composition-report "${CONFIG}" --bootstrap-samples 2000
    ;;
  *)
    echo "Unknown phase: ${PHASE}" >&2
    exit 2
    ;;
esac

echo "Phase ${PHASE} finished for ${CONFIG}"
