#!/bin/bash
#SBATCH --job-name=r5-infer-2g
#SBATCH --output=../logs/r5-inference-%j.out
#SBATCH --error=../logs/r5-inference-%j.err
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=90G
#SBATCH --gres=gpu:a100-80gb:2
#SBATCH --partition=gpu-long

set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

CONFIG="${1:?usage: run_inference_2gpu.slurm <config.toml> [run|score|report|composition|all]}"
PHASE="${2:-all}"

mkdir -p "${CALIBREAD_LOGS}"
cd "${CALIBREAD_REPO}"
bash "${CALIBREAD_REPO}/scripts/cluster/run_r5_phase.sh" "${CONFIG}" "${PHASE}"
