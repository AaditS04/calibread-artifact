# R5 Qwen2.5 72B q4 cluster run — record and insights

Canonical record for the first complete R5 pipeline executed on the BITS GPU
cluster with **Qwen2.5 72B Instruct q4** via Ollama. For cluster operations see
[`BITS_CLUSTER.md`](BITS_CLUSTER.md); for protocol order see
[`src/calibread/inference/R5_COMPLETE_RUN.md`](../src/calibread/inference/R5_COMPLETE_RUN.md).

Cross-condition findings synthesis:
[`r5_cluster_sealed_test_findings.md`](r5_cluster_sealed_test_findings.md).

## Parent experiment

| Field | Value |
|-------|-------|
| `parent_experiment_id` | `r5_qwen25_72b_cluster_forced_v1` |
| Model (CalibRead alias) | `calibread-qwen25-72b-instruct-q4` |
| Ollama pull tag | `qwen2.5:72b-instruct-q4_K_M` |
| Model digest | `sha256:11420ebce5f9e053e48662e8d2fd228d9da2e07a614039e06fe09341ce69dc2d` |
| Prompt | `r5-closed-book-forced-short-v3` |
| `max_tokens` | 32 |
| `temperature` | 0.0 |
| `require_logprobs` | true |
| Hardware | 1× NVIDIA A100 80 GB (`gpu-long` / `gpu-short`) |

## Pipeline completed (2026-09-11 — 2026-09-17)

| Phase | Run ID | Requests | Slurm job | Status |
|-------|--------|----------|-----------|--------|
| Development pilot | `…_development_pilot` | 287 | 10872 | complete |
| Development | `…_development` | 11,640 | 11335 | complete |
| Calibration | `…_calibration` | 18,913 | 11339 | complete |
| Fit calibrator | — | — | 11340 | complete |
| Test (blind generation) | `…_test` | 30,387 | 11341 | complete |
| Test unblind | — | — | 11342 | complete |

**Dependent job chain (calibration → test):** 11339 → 11340 → 11341 → 11342.

### Configs

```text
configs/inference/r5_ollama_qwen25_72b_cluster_development_pilot.toml
configs/inference/r5_ollama_qwen25_72b_cluster_development.toml
configs/inference/r5_ollama_qwen25_72b_cluster_calibration.toml
configs/inference/r5_ollama_qwen25_72b_cluster_test.toml
```

### Cluster scripts added for this run

```text
scripts/cluster/run_fit_calibrator.slurm   # fit-calibrator after calibration
scripts/cluster/run_unblind_test.slurm     # score/report/calibrate/R7/composition on test
```

Submit examples:

```bash
# Full phase (development or calibration)
sbatch --partition=gpu-long --time=12:00:00 \
  scripts/cluster/run_inference.slurm configs/inference/r5_ollama_qwen25_72b_cluster_development.toml all

# Blind test generation only
sbatch --partition=gpu-long --time=12:00:00 \
  scripts/cluster/run_inference.slurm configs/inference/r5_ollama_qwen25_72b_cluster_test.toml run

# Chained pipeline (as used on 2026-09-17)
CAL=$(sbatch --parsable --partition=gpu-long --time=12:00:00 \
  scripts/cluster/run_inference.slurm configs/inference/r5_ollama_qwen25_72b_cluster_calibration.toml all)
FIT=$(sbatch --parsable --dependency=afterok:$CAL \
  scripts/cluster/run_fit_calibrator.slurm configs/inference/r5_ollama_qwen25_72b_cluster_calibration.toml)
TEST=$(sbatch --parsable --dependency=afterok:$FIT --partition=gpu-long --time=12:00:00 \
  scripts/cluster/run_inference.slurm configs/inference/r5_ollama_qwen25_72b_cluster_test.toml run)
sbatch --dependency=afterok:$TEST \
  scripts/cluster/run_unblind_test.slurm configs/inference/r5_ollama_qwen25_72b_cluster_test.toml
```

## Result tree

```text
results/r5/r5_qwen25_72b_cluster_forced_v1/
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

### Key artifact hashes (local copy, 2026-09-17)

| Artifact | SHA-256 |
|----------|---------|
| `test/r5_report.json` | `dc7af4cc7e48dabf7fdb7e90a651ddef7063f5c6e43d469807a6ecd2c700c692` |
| `test/r5_composition_report.json` | `e19fa0e54ab26c14bce76497fb40647ac55fde362bfd6a66842bbee276f020c7` |
| `calibration/calibration/CALIBRATOR.json` (object) | `559548139978da6285c02755cd7287bce3138808b52aaf3342b8382624b7df85` |
| Calibrator ID | `r5-isotonic-a32da9f620227c07da93` |
| Test selection (`selected_example_ids_sha256`) | `16713fb19eae07eb58fa707828350ae8312cccb4c9afd8626e8bf29234257633` |

## Exact-match accuracy (raw, pre-calibration)

### Overall by split

| Split | N | Overall EM | Abstention rate |
|-------|---|------------|-----------------|
| Development pilot | 287 | 28.6% | 0.00% |
| Development | 11,640 | 22.6% | 0.14% |
| **Test (sealed)** | **30,387** | **22.4%** | **0.28%** |

Development and test agree within 0.2 pp — good seal integrity. The 287-example
pilot overshot full-split accuracy (small-sample optimism).

### Per-cell exact match — development vs test

| Cell | Development | Test |
|------|-------------|------|
| SOCRATES one-hop | 44.0% | 41.2% |
| SOCRATES two-hop | 2.4% | 2.4% |
| MuSiQue atomic one-hop | 30.4% | 29.4% |
| MuSiQue two-hop | 9.4% | 10.7% |
| MuSiQue three-hop | 10.4% | 13.8% |
| MuSiQue four+ hop | 16.1% | 10.3% |

SOCRATES one-hop is the strongest cell. SOCRATES two-hop remains near floor on
both splits. MuSiQue multi-hop stays weak; four+ hop regressed slightly on test.

### Comparison to smaller cluster/local pilots (development pilot, n=287)

| Model | Overall EM |
|-------|------------|
| Qwen3 4B (local) | 10.1% |
| Qwen2.5 7B (local) | 16.7% |
| Qwen2.5 14B q3 (cluster) | 20.9% |
| **Qwen2.5 72B q4 (cluster)** | **28.6%** (pilot) / **22.4%** (test) |

72B is the strongest condition tested so far, but confirmatory test EM is still
modest (~22%).

## Abstentions

Forced-answer prompt forbids `ABSTAIN`; residual abstentions are scored as
incorrect outputs that match abstention detection.

| Split | Overall | SOCRATES two-hop |
|-------|---------|------------------|
| Development | 16 / 11,640 (0.14%) | ~13 / 1,273 (1.02%) |
| Test | ~85 / 30,387 (0.28%) | ~64 / 3,560 (1.80%) |

Abstentions are rare but concentrated in SOCRATES two-hop.

## Composition insights (test split)

From `test/r5_composition_report.json` (multi-hop chains only).

| Metric | Test value | Interpretation |
|--------|------------|----------------|
| Chain accuracy | 9.2% | Full composite chains rarely correct |
| All-atoms-correct rate | 7.7% | Rarely all constituent atoms correct |
| Atomic accuracy | 32.0% | Atoms easier than chains |
| Synthesis loss | 0.74 | Even when all atoms correct, chains often fail |
| Factorized residual | within ±0.05 band | Chain error not a naive product of atom errors |
| four+ hop: all-atoms-correct | 0% (n=786) | Deepest hops never fully correct |

**Takeaway:** Multi-hop failure is partly **composition/synthesis**, not only
weak atomic knowledge. This supports the CalibRead R5 composition framing.

## Calibration and R7 (test split)

Calibrator: level-balanced global isotonic on mean generated-token log
probability, fit on calibration split only (`r5-isotonic-a32da9f620227c07da93`).

| Metric | Calibration (in-sample diagnostic) | Test (held-out) |
|--------|-----------------------------------|-----------------|
| Correctness AUROC | 0.807 | 0.812 |
| ECE (10 bins) | 0.043 | 0.036 |
| Overall EM | 23.0% | 22.4% |
| Mean calibrated confidence | — | 0.19 |

**R7 selective-answer frontier (test):**

| Threshold τ | Coverage | Accuracy on accepted |
|-------------|----------|----------------------|
| 0.50 | 7.9% | 69.4% |
| 0.70 | 0.4% | 70.9% |
| 0.90+ | 0% | — |

Calibration **ranks** well (AUROC ~0.81) but scores are generally low, so
high-confidence coverage is tiny. Useful for risk–coverage analysis; not a
high-coverage deployment policy at τ ≥ 0.5.

## Promotion gate (development pilot → full study)

The 2026-09-11 development pilot (287/287, 28.6% EM) passed operational gates
(zero failures, logprobs present, non-degenerate scores, mixed correct/incorrect).
Multi-hop cells remained weak (SOCRATES two-hop 0%) but improved materially vs
4B/14B pilots. The condition was advanced to full development/calibration/test
under the same frozen prompt and model digest.

## Publication and evidence status

**Completed:** Full R5 inference pipeline with frozen calibrator and sealed test
unblinding per [`R5_COMPLETE_RUN.md`](../src/calibread/inference/R5_COMPLETE_RUN.md).

**Still pending for publication-grade claims:**

1. **Human audit gate** — `data/processed/socrates_v1/REFINEMENT_MANIFEST.json`
   and `data/processed/musique_atomic/ATOMIC_MANIFEST.json` remain
   `checks.human_audit = pending`. These cluster configs deliberately omit
   `required_human_audit_manifests` (engineering runs). Before publication,
   complete worksheet review and `finalize-audit` for both sources, then re-run
   or attest that manifest hashes match the runs documented here.

2. **Results not in git** — Large artifacts live under `results/r5/` locally
   and on cluster NFS; sync with `pscp` / `scp` as needed.

## Monitoring (cluster)

```bash
ssh $CLUSTER_USER@$CLUSTER_HOST
export CALIBREAD_ROOT=/path/from/cluster.env

squeue -u $USER
wc -l $CALIBREAD_ROOT/calibread/results/r5/r5_qwen25_72b_cluster_forced_v1/test/generations.jsonl
tail -f $CALIBREAD_ROOT/logs/r5-inference-<jobid>.out
```

## Related runs (same cluster, other models)

| Experiment | Pilot overall EM | Notes |
|------------|------------------|-------|
| `r5_qwen25_14b_cluster_forced_v1` | 20.9% | Dense 14B q3 |
| `r5_mixtral_8x22b_cluster_forced_v1` | 31.4% | MoE; stronger SOCRATES, weaker MuSiQue multi-hop |
| `r5_qwen25_72b_cluster_forced_v1` | 22.4% (test) | This record |
