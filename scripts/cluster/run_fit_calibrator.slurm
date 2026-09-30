#!/bin/bash
#SBATCH --job-name=fit-cal
#SBATCH --output=../logs/fit-calibrator-%j.out
#SBATCH --error=../logs/fit-calibrator-%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

CONFIG="${1:?usage: run_fit_calibrator.slurm <calibration-config.toml>}"

export PYTHONPATH="${CALIBREAD_REPO}/src"
cd "${CALIBREAD_REPO}"

if command -v module >/dev/null 2>&1; then
  module load python/3.13.7 2>/dev/null || true
fi

# shellcheck disable=SC1091
source "${CALIBREAD_VENV}/bin/activate"

python -m calibread.inference.cli fit-calibrator "${CONFIG}"
echo "fit-calibrator finished for ${CONFIG}"
