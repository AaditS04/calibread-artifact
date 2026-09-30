#!/bin/bash
#SBATCH --job-name=r1-infer
#SBATCH --output=../logs/r1-inference-%j.out
#SBATCH --error=../logs/r1-inference-%j.err
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --partition=gpu-long

set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

CONFIG="${1:?usage: run_r1_inference.slurm <config.toml> [run|score|report|r1-report|all]}"
PHASE="${2:-all}"

mkdir -p "${CALIBREAD_LOGS}"
cd "${CALIBREAD_REPO}"
bash "${CALIBREAD_REPO}/scripts/cluster/run_r1_phase.sh" "${CONFIG}" "${PHASE}"
