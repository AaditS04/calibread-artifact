#!/usr/bin/env bash
# Submit the full Mixtral 8x22B q4 R5 pipeline on 2x A100 80GB.
# Run from: $CALIBREAD_ROOT/calibread
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

DEV_CONFIG='configs/inference/r5_ollama_mixtral_8x22b_cluster_development.toml'
CAL_CONFIG='configs/inference/r5_ollama_mixtral_8x22b_cluster_calibration.toml'
TEST_CONFIG='configs/inference/r5_ollama_mixtral_8x22b_cluster_test.toml'
CALIBRATOR='results/r5/r5_mixtral_8x22b_cluster_forced_v1/calibration/calibration/CALIBRATOR.json'
CALIBRATED='results/r5/r5_mixtral_8x22b_cluster_forced_v1/test/calibrated_results.csv'

DEV="$(sbatch --parsable scripts/cluster/run_inference_2gpu.slurm "${DEV_CONFIG}" all)"
CAL="$(sbatch --parsable --dependency="afterok:${DEV}" scripts/cluster/run_inference_2gpu.slurm "${CAL_CONFIG}" all)"
FIT="$(sbatch --parsable --dependency="afterok:${CAL}" scripts/cluster/run_fit_calibrator.slurm "${CAL_CONFIG}")"
TEST="$(sbatch --parsable --dependency="afterok:${FIT}" --partition=gpu-1day --time=24:00:00 \
  scripts/cluster/run_inference_2gpu.slurm "${TEST_CONFIG}" run)"
UNBLIND="$(sbatch --parsable --dependency="afterok:${TEST}" scripts/cluster/run_unblind_test.slurm \
  "${TEST_CONFIG}" "${CALIBRATOR}" "${CALIBRATED}")"

echo "DEVELOPMENT=${DEV}"
echo "CALIBRATION=${CAL}"
echo "FIT_CALIBRATOR=${FIT}"
echo "TEST_RUN=${TEST}"
echo "UNBLIND=${UNBLIND}"
