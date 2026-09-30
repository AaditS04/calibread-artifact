# R5 Mixtral 8×22B q4 cluster run — record and insights

Canonical record for the complete R5 pipeline on the BITS GPU cluster with
**Mixtral 8×22B Instruct v0.1 q4** (MoE) via Ollama on **2× A100 80 GB**.
For cluster operations see [`BITS_CLUSTER.md`](BITS_CLUSTER.md); for protocol
order see
[`src/calibread/inference/R5_COMPLETE_RUN.md`](../src/calibread/inference/R5_COMPLETE_RUN.md).

Compare with the dense Qwen 72B condition:
[`r5_qwen25_72b_cluster_run.md`](r5_qwen25_72b_cluster_run.md).  
Cross-condition findings synthesis:
[`r5_cluster_sealed_test_findings.md`](r5_cluster_sealed_test_findings.md).

## Parent experiment

| Field | Value |
|-------|-------|
| `parent_experiment_id` | `r5_mixtral_8x22b_cluster_forced_v1` |
| Model (CalibRead alias) | `calibread-mixtral-8x22b-instruct-q4` |
| Ollama pull tag | `mixtral:8x22b-instruct-v0.1-q4_K_M` |
| Model digest | `sha256:de58127cf2675b72a8abf9811768a36e8500e8ea52a5ae393ded274ada7cd8c8` |
| Architecture | MoE 141B total / ~39B active |
| Prompt | `r5-closed-book-forced-short-v3` |
| `max_tokens` | 32 |
| `temperature` | 0.0 |
| `require_logprobs` | true |
| Hardware | **2×** NVIDIA A100 80 GB (`gpu-long` / `gpu-1day`) |
| SYSTEM strip | Not required (copy manifest to `calibread-` alias) |

## Pipeline completed (2026-09-11 — 2026-09-18)

| Phase | Run ID | Requests | Slurm job | Status |
|-------|--------|----------|-----------|--------|
| Development pilot | `…_development_pilot` | 287 | 10879 | complete |
| Development | `…_development` | 11,640 | 11369 | complete |
| Calibration | `…_calibration` | 18,913 | 11370 | complete |
| Fit calibrator | — | — | 11371 | complete |
| Test (blind generation) | `…_test` | 30,387 | 11372 | complete |
| Test unblind | — | — | 11373 | complete |

**Full-pipeline chain (2026-09-17 submit):** 11369 → 11370 → 11371 → 11372 → 11373.

### Configs

```text
configs/inference/r5_ollama_mixtral_8x22b_cluster_development_pilot.toml
configs/inference/r5_ollama_mixtral_8x22b_cluster_development.toml
configs/inference/r5_ollama_mixtral_8x22b_cluster_calibration.toml
configs/inference/r5_ollama_mixtral_8x22b_cluster_test.toml
```

### Cluster scripts

```text
scripts/cluster/run_inference_2gpu.slurm              # 2× GPU inference
scripts/cluster/submit_mixtral_8x22b_full_pipeline.sh # chained submit helper
scripts/cluster/run_fit_calibrator.slurm
scripts/cluster/run_unblind_test.slurm
```

Submit the full chain:

```bash
cd $CALIBREAD_ROOT/calibread
bash scripts/cluster/submit_mixtral_8x22b_full_pipeline.sh
```

Or manually (development uses `gpu-long`; test generation uses `gpu-1day` / 24 h):

```bash
DEV=$(sbatch --parsable scripts/cluster/run_inference_2gpu.slurm \
  configs/inference/r5_ollama_mixtral_8x22b_cluster_development.toml all)
# … see submit_mixtral_8x22b_full_pipeline.sh for dependencies
```

**Slurm note:** `run_inference_2gpu.slurm` requests `--mem=90G` (96G exceeded
`MaxMemPerNode=96000` on this cluster).

## Result tree

```text
results/r5/r5_mixtral_8x22b_cluster_forced_v1/
├── development_pilot/
├── development/
├── calibration/
│   └── calibration/
│       ├── CALIBRATOR.json
│       ├── CALIBRATION_MANIFEST.json
│       └── calibration_metrics.json
└── test/
    ├── generations.jsonl
    ├── scored_results.csv
    ├── calibrated_results.csv
    ├── r7_decisions.csv
    ├── r5_report.json
    ├── r5_composition_report.json
    └── calibration_report.json
```

### Key artifact hashes (local copy, 2026-09-18)

| Artifact | SHA-256 |
|----------|---------|
| `test/r5_report.json` | `65bc96a81680c310345e6762d21e021ef0de531f94a8114ee93354958fadec85` |
| `test/r5_composition_report.json` | `1dd37eb214187018df3dd353f2f4d48aa9f3f8f0cfd0b82fa8e2cbc9dd897e62` |
| `calibration/calibration/CALIBRATOR.json` (object) | `173c61149f2887acb5efe084ebc2a79493066c87e930ca7abe48ca4761f51b63` |
| Calibrator ID | `r5-isotonic-051eff823d91639990a7` |
| Test selection (`selected_example_ids_sha256`) | `16713fb19eae07eb58fa707828350ae8312cccb4c9afd8626e8bf29234257633` |

## Exact-match accuracy (raw, pre-calibration)

### Overall by split

| Split | N | Overall EM | Abstention |
|-------|---|------------|------------|
| Development pilot | 287 | 31.4% | 0% |
| Development | 11,640 | 29.0% | 0% |
| **Test (sealed)** | **30,387** | **29.3%** | **0%** |

Development and test agree within 0.3 pp — stable generalization.

### Per-cell exact match — development vs test

| Cell | Development | Test |
|------|-------------|------|
| SOCRATES one-hop | 74.8% | **75.0%** |
| SOCRATES two-hop | 1.3% | 1.7% |
| MuSiQue atomic one-hop | 32.1% | 29.8% |
| MuSiQue two-hop | 8.2% | 8.9% |
| MuSiQue three-hop | 7.8% | 8.1% |
| MuSiQue four+ hop | 7.9% | 5.9% |

### Comparison to Qwen 72B q4 (sealed test)

| Metric | Mixtral 8×22B | Qwen 72B |
|--------|---------------|----------|
| **Overall EM** | **29.3%** | 22.4% |
| SOCRATES one-hop | **75.0%** | 41.2% |
| SOCRATES two-hop | 1.7% | 2.4% |
| MuSiQue atomic one-hop | 29.8% | 29.4% |
| MuSiQue two-hop | 8.9% | 10.7% |
| MuSiQue three-hop | 8.1% | 13.8% |
| MuSiQue four+ hop | 5.9% | 10.3% |

Mixtral wins overall (+6.9 pp) and on SOCRATES one-hop; Qwen 72B remains stronger
on MuSiQue multi-hop cells. Both models remain near floor on SOCRATES two-hop.

## Composition insights (test split)

| Metric | Mixtral | Qwen 72B (test) |
|--------|---------|-----------------|
| Chain accuracy | 6.9% | 9.2% |
| All-atoms-correct rate | **18.3%** | 7.7% |
| Atomic accuracy | **37.1%** | 32.0% |
| Synthesis loss | 0.90 | 0.74 |

Mixtral improves all-atoms-correct and atomic accuracy but has **lower** full-chain
accuracy than Qwen on this split — composition failure modes differ by architecture.

## Calibration and R7 (test split)

| Metric | Calibration (in-sample) | Test (held-out) |
|--------|-------------------------|-----------------|
| Correctness AUROC | 0.905 | **0.900** |
| ECE (10 bins) | 0.030 | 0.035 |
| Mean calibrated confidence | — | 0.26 |

**R7 selective-answer frontier (test):**

| Threshold τ | Coverage | Accuracy on accepted |
|-------------|----------|----------------------|
| 0.50 | **25.2%** | **79.5%** |
| 0.70 | **16.4%** | **89.3%** |
| 0.90 | **7.0%** | **96.0%** |

Mixtral calibration is stronger and higher-coverage than Qwen 72B (Qwen at τ=0.50:
7.9% coverage / 69.4% accuracy). Raw logprobs separate correct from incorrect
better on this MoE condition.

## Operational notes

- **1× GPU pilot (job 10879):** ~85 GB q4 with CPU offload; ~1–30 s/request.
- **2× GPU full run (jobs 11369–11373):** ~0.5–1 s/request; no offload needed.
- **Disk:** ~85 GB model weights under `$OLLAMA_MODELS`.

## Publication and evidence status

**Completed:** Full R5 pipeline with frozen calibrator and sealed test unblinding.

**Still pending for publication-grade claims:**

1. Human audit gate (`checks.human_audit = pending` on both source manifests).
2. Configs omit `required_human_audit_manifests` (engineering runs).

## Monitoring

```bash
ssh $CLUSTER_USER@$CLUSTER_HOST
export CALIBREAD_ROOT=/path/from/cluster.env
squeue -u $USER
wc -l $CALIBREAD_ROOT/calibread/results/r5/r5_mixtral_8x22b_cluster_forced_v1/test/generations.jsonl
```
