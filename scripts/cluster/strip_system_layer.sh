#!/usr/bin/env bash
# Build a CalibRead-safe Ollama manifest without the embedded SYSTEM layer.
#
# Usage:
#   bash scripts/cluster/strip_system_layer.sh <target-name> [source-tag]
#
# Example:
#   bash scripts/cluster/strip_system_layer.sh calibread-qwen25-14b-instruct-q4 qwen2.5:14b-instruct-q4_K_M
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

TARGET_NAME="${1:?usage: strip_system_layer.sh <target-name> [source-tag]}"
SOURCE_TAG="${2:-qwen2.5:14b-instruct-q3_K_M}"

IFS=':' read -r source_family source_variant <<< "${SOURCE_TAG}"
SOURCE_MANIFEST="${OLLAMA_MODELS}/manifests/registry.ollama.ai/library/${source_family}/${source_variant}"
TARGET_MANIFEST="${OLLAMA_MODELS}/manifests/registry.ollama.ai/library/${TARGET_NAME}/latest"

if [[ ! -f "${SOURCE_MANIFEST}" ]]; then
  echo "ERROR: source manifest missing: ${SOURCE_MANIFEST}" >&2
  echo "Pull the model first: sbatch scripts/cluster/pull_model.slurm ${SOURCE_TAG}" >&2
  exit 1
fi

export TARGET_NAME SOURCE_MANIFEST TARGET_MANIFEST
python3 - <<'PY'
import json
import os
from pathlib import Path

source = Path(os.environ["SOURCE_MANIFEST"])
target = Path(os.environ["TARGET_MANIFEST"])
target_name = os.environ["TARGET_NAME"]

manifest = json.loads(source.read_text(encoding="utf-8"))
layers = manifest.get("layers", [])
filtered = [
    layer
    for layer in layers
    if layer.get("mediaType") != "application/vnd.ollama.image.system"
]
if len(filtered) == len(layers):
    raise SystemExit("No SYSTEM layer found to strip")
manifest["layers"] = filtered
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(manifest), encoding="utf-8")
print(f"Wrote {target} with {len(filtered)} layers for {target_name}")
PY

echo "Stripped manifest for ${TARGET_NAME} (from ${SOURCE_TAG})"
