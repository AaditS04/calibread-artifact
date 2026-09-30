# Complete R1 PopQA sealed run

Findings from the completed Qwen 72B and Mixtral 8×22B cluster runs:
[`docs/r1_popqa_cluster_sealed_test_findings.md`](../../../docs/r1_popqa_cluster_sealed_test_findings.md).

This is the sealed-test order for the R1 popularity-proxy panel. Cluster job
mechanics follow [`docs/BITS_CLUSTER.md`](../../../docs/BITS_CLUSTER.md). The
phase order is the same contract as
[`R5_COMPLETE_RUN.md`](R5_COMPLETE_RUN.md): development, calibration, freeze
the calibrator, blind test generation, then one unblind.

## What this run is

The dataset is the processed PopQA panel with R1 levels frozen before any
model output is inspected:

```text
tail    s_pop <= 386
middle  386 < s_pop <= 2955
head    s_pop > 2955
```

Those cutpoints are the inclusive tertiles of the **development** split only.
They are recorded in `data/processed/popqa_r1/BIN_MANIFEST.json`. Calibration
and test rows are labeled with the same thresholds. Rebuilding the panel
refuses to replace those cutpoints.

`s_pop` is Wikipedia subject popularity. It is not a document count in Qwen's
or Mixtral's pretraining corpus. Report it as a popularity proxy.

PopQA human audit is still pending, matching the engineering-complete R5
cluster runs. Do not describe the result as publication-final gold.

## Frozen condition

The prompt text, decoding, and score are the promoted R5 forced-short-answer
condition. The template id is `r1-popqa-closed-book-forced-short-v1` so these
rows cannot be pooled with R5. Each model keeps the CalibRead alias already
installed in `$CALIBREAD_ROOT/ollama_models`:

| Model | Alias | GPUs |
|---|---|---|
| Qwen2.5 72B Instruct q4 | `calibread-qwen25-72b-instruct-q4` | 1× A100 80 GB |
| Mixtral 8×22B Instruct q4 | `calibread-mixtral-8x22b-instruct-q4` | 2× A100 80 GB |

`promotion_approved = true` carries that already-promoted model and prompt.
It does not approve a new prompt or a new binning rule.

## Planned requests

| Phase | Requests | tail / middle / head |
|---|---:|---|
| Development | 2,853 | 953 / 950 / 950 |
| Calibration | 4,368 | 1,506 / 1,465 / 1,397 |
| Test | 7,046 | 2,389 / 2,305 / 2,352 |

`plan` is authoritative. If it disagrees with this table, stop and do not
submit.

## Non-negotiable order

```text
Frozen panel already written
        |
        v
Development generation, score, and r1-report
        |
        v
Calibration generation and score
        |
        v
Fit and freeze the calibrator
        |
        v
Test generation only. Do not score.
        |
        v
Unblind once: score, calibrate, R7, r1-report
```

During test generation, inspect only `RUN_SUMMARY.json`, failures, remaining
count, and the returned model identity. Do not open test accuracy before the
unblind job.

## Submit from the login node

```bash
cd $CALIBREAD_ROOT/calibread
module load python/3.13.7
source $CALIBREAD_ROOT/venv/bin/activate
export PYTHONPATH=src

python -m calibread.inference.cli validate-config \
  configs/inference/r1_ollama_qwen25_72b_cluster_development.toml
python -m calibread.inference.cli plan \
  configs/inference/r1_ollama_qwen25_72b_cluster_development.toml

bash scripts/cluster/submit_r1_full_pipeline.sh qwen
bash scripts/cluster/submit_r1_full_pipeline.sh mixtral
```

Results land in:

```text
results/r1/r1_popqa_qwen25_72b_cluster_v1/
results/r1/r1_popqa_mixtral_8x22b_cluster_v1/
```

The confirmatory artifact is `r1_report.json` in each split directory. The
primary contrast is tail accuracy minus head accuracy on the sealed test split.
