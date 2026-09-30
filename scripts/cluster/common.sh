#!/usr/bin/env bash
# Shared cluster paths. Sources cluster.env when present.
set -euo pipefail

_CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${_CLUSTER_DIR}/cluster.env" ]]; then
  # shellcheck disable=SC1091
  source "${_CLUSTER_DIR}/cluster.env"
fi

: "${CALIBREAD_ROOT:=${HOME}/F20220612_Aadit}"

export CALIBREAD_ROOT
export CALIBREAD_REPO="${CALIBREAD_ROOT}/calibread"
export CALIBREAD_LOGS="${CALIBREAD_ROOT}/logs"
export CALIBREAD_VENV="${CALIBREAD_ROOT}/venv"
export CALIBREAD_BIN="${CALIBREAD_ROOT}/bin"
export OLLAMA_MODELS="${CALIBREAD_ROOT}/ollama_models"
