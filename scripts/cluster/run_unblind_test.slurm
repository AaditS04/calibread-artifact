#!/bin/bash
#SBATCH --job-name=r5-unblind
#SBATCH --output=../logs/r5-unblind-%j.out
#SBATCH --error=../logs/r5-unblind-%j.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

CONFIG="${1:?usage: run_unblind_test.slurm <test-config.toml>}"
CALIBRATOR="${2:-results/r5/r5_qwen25_72b_cluster_forced_v1/calibration/calibration/CALIBRATOR.json}"
CALIBRATED="${3:-results/r5/r5_qwen25_72b_cluster_forced_v1/test/calibrated_results.csv}"

export PYTHONPATH="${CALIBREAD_REPO}/src"
cd "${CALIBREAD_REPO}"

if command -v module >/dev/null 2>&1; then
  module load python/3.13.7 2>/dev/null || true
fi

# shellcheck disable=SC1091
source "${CALIBREAD_VENV}/bin/activate"

run_cli() {
  python -m calibread.inference.cli "$@"
}

run_cli score "${CONFIG}"
run_cli report "${CONFIG}"
run_cli calibrate "${CONFIG}" --calibrator "${CALIBRATOR}"
run_cli decide-r7 "${CONFIG}" --calibrator "${CALIBRATOR}"
run_cli calibration-report "${CONFIG}" --calibrator "${CALIBRATOR}"
run_cli composition-report "${CONFIG}" --calibrated "${CALIBRATED}" --bootstrap-samples 2000

echo "Unblind pipeline finished for ${CONFIG}"
