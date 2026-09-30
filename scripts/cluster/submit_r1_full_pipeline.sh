#!/usr/bin/env bash
# Submit one complete R1 PopQA sealed pipeline.
# Usage, from $CALIBREAD_ROOT/calibread:
#   bash scripts/cluster/submit_r1_full_pipeline.sh qwen
#   bash scripts/cluster/submit_r1_full_pipeline.sh mixtral
set -euo pipefail

MODEL="${1:?usage: submit_r1_full_pipeline.sh qwen|mixtral}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

case "${MODEL}" in
  qwen)
    SLURM="scripts/cluster/run_r1_inference.slurm"
    DEV_CONFIG="configs/inference/r1_ollama_qwen25_72b_cluster_development.toml"
    CAL_CONFIG="configs/inference/r1_ollama_qwen25_72b_cluster_calibration.toml"
    TEST_CONFIG="configs/inference/r1_ollama_qwen25_72b_cluster_test.toml"
    CALIBRATOR="results/r1/r1_popqa_qwen25_72b_cluster_v1/calibration/calibration/CALIBRATOR.json"
    ;;
  mixtral)
    SLURM="scripts/cluster/run_r1_inference_2gpu.slurm"
    DEV_CONFIG="configs/inference/r1_ollama_mixtral_8x22b_cluster_development.toml"
    CAL_CONFIG="configs/inference/r1_ollama_mixtral_8x22b_cluster_calibration.toml"
    TEST_CONFIG="configs/inference/r1_ollama_mixtral_8x22b_cluster_test.toml"
    CALIBRATOR="results/r1/r1_popqa_mixtral_8x22b_cluster_v1/calibration/calibration/CALIBRATOR.json"
    ;;
  *)
    echo "Unknown model ${MODEL}; use qwen or mixtral" >&2
    exit 2
    ;;
esac

DEV="$(sbatch --parsable "${SLURM}" "${DEV_CONFIG}" all)"
CAL="$(sbatch --parsable --dependency="afterok:${DEV}" "${SLURM}" "${CAL_CONFIG}" all)"
FIT="$(sbatch --parsable --dependency="afterok:${CAL}" scripts/cluster/run_fit_calibrator.slurm "${CAL_CONFIG}")"
TEST="$(sbatch --parsable --dependency="afterok:${FIT}" --partition=gpu-1day --time=24:00:00 \
  "${SLURM}" "${TEST_CONFIG}" run)"
UNBLIND="$(sbatch --parsable --dependency="afterok:${TEST}" scripts/cluster/run_unblind_r1.slurm \
  "${TEST_CONFIG}" "${CALIBRATOR}")"

echo "MODEL=${MODEL}"
echo "DEVELOPMENT=${DEV}"
echo "CALIBRATION=${CAL}"
echo "FIT_CALIBRATOR=${FIT}"
echo "TEST_RUN=${TEST}"
echo "UNBLIND=${UNBLIND}"
