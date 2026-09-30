#!/usr/bin/env bash
# One-time setup on the BITS login node. Safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

mkdir -p "${CALIBREAD_ROOT}" "${CALIBREAD_BIN}" "${CALIBREAD_LOGS}" "${OLLAMA_MODELS}"

if [[ ! -d "${CALIBREAD_REPO}" ]]; then
  echo "ERROR: ${CALIBREAD_REPO} not found."
  echo "Copy or clone the calibread repository into ${CALIBREAD_ROOT}/calibread first."
  exit 1
fi

cd "${CALIBREAD_REPO}"

PYTHON_BIN=""
if command -v module >/dev/null 2>&1; then
  module load python/3.13.7 2>/dev/null || true
fi
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    version="$("${candidate}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    major="${version%%.*}"
    minor="${version#*.}"
    if (( major > 3 || (major == 3 && minor >= 11) )); then
      PYTHON_BIN="${candidate}"
      break
    fi
  fi
done

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: Python >= 3.11 not found. Try: module load python/3.13.7"
  exit 1
fi

echo "Using ${PYTHON_BIN} ($(${PYTHON_BIN} --version))"

if [[ ! -d "${CALIBREAD_VENV}" ]]; then
  "${PYTHON_BIN}" -m venv "${CALIBREAD_VENV}"
fi

# shellcheck disable=SC1091
source "${CALIBREAD_VENV}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e ".[analysis]"

if [[ ! -x "${CALIBREAD_BIN}/ollama" ]]; then
  echo "Installing user-local Ollama into ${CALIBREAD_ROOT} ..."
  tmp="$(mktemp -d)"
  curl -fsSL \
    https://github.com/ollama/ollama/releases/download/v0.34.0/ollama-linux-amd64.tar.zst \
    -o "${tmp}/ollama.tar.zst"
  zstd -d -f "${tmp}/ollama.tar.zst" -o "${tmp}/ollama.tar"
  tar -xf "${tmp}/ollama.tar" -C "${CALIBREAD_ROOT}"
  chmod +x "${CALIBREAD_BIN}/ollama"
  rm -rf "${tmp}"
fi

cat <<EOF

Setup complete.

Optional ~/.bashrc additions:

  export CALIBREAD_ROOT="${CALIBREAD_ROOT}"
  export PATH="${CALIBREAD_BIN}:\${PATH}"
  export OLLAMA_MODELS="${OLLAMA_MODELS}"

Then:

  cd "${CALIBREAD_REPO}"
  sbatch scripts/cluster/pull_model.slurm qwen2.5:14b-instruct-q4_K_M

EOF
