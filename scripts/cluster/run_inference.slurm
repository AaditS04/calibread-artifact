#!/bin/bash
#SBATCH --job-name=r5-infer
#SBATCH --output=../logs/r5-inference-%j.out
#SBATCH --error=../logs/r5-inference-%j.err
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --gres=gpu:a100-80gb:1
#SBATCH --partition=gpu-short

set -euo pipefail

# Submit from: $CALIBREAD_ROOT/calibread
if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/cluster"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

CONFIG="${1:-configs/inference/r5_ollama_qwen25_14b_cluster_development_pilot.toml}"
PHASE="${2:-all}"

mkdir -p "${CALIBREAD_LOGS}"
cd "${CALIBREAD_REPO}"
bash "${CALIBREAD_REPO}/scripts/cluster/run_r5_phase.sh" "${CONFIG}" "${PHASE}"
