# CalibRead calibration and R7 decision pipeline

This document explains how CalibRead turns a raw LLM uncertainty score into
an auditable answer or abstention decision. It also explains when a candidate-set
decision is scientifically supported.

## Implementation status

The complete implemented path is:

```text
OpenRouter or Ollama token log probabilities
                    |
                    v
Mean generated-token log probability
                    |
                    v
Raw confidence score stored with the generation
                    |
                    v
Raw score from calibration examples
                |
                v
Level-balanced weighted isotonic fit and frozen object
                |
                v
Apply it to untouched test examples
                |
                v
Estimated probability of correctness
                |
                v
R7 answer / set / abstain decisions and reports
```

The inference CLI implements `fit-calibrator`, `calibrate`, `decide-r7`, and
`calibration-report`. It validates complete cached runs, split identity, input
and configuration hashes, model/prompt/decoding identity, raw-score source,
calibrator hashes, and dataset-by-R5 support. The open-ended R5 path implements
point answer/abstain decisions; a formal set action still requires the
finite-label conditions described below.

## 1. What the raw score is

For the OpenRouter and Ollama adapters, the raw score is the arithmetic mean of
the log probabilities of the generated answer tokens. The provider must return
token log probabilities for the exact generated answer; otherwise confidence
and calibration claims are prohibited.

Suppose the model generates `Paris` as two tokens with log probabilities:

```text
-0.10, -0.30
```

The recorded score is:

```text
(-0.10 + -0.30) / 2 = -0.20
```

A score nearer zero normally represents greater model confidence:

```text
-0.05  higher raw confidence
-0.50  lower raw confidence
-2.00  much lower raw confidence
```

The value is not a probability of answer correctness. In particular, `-0.20`
does not mean that the answer is 80% likely to be correct.

## 2. Discrimination versus calibration

Discrimination asks whether higher scores tend to rank correct answers above
incorrect answers. Correctness AUROC and risk-coverage behavior diagnose this.

Calibration asks whether a probability-valued score agrees with observed group
accuracy. For example, among sufficiently many comparable answers assigned
approximately `0.80`, approximately 80% should be correct.

A raw log-probability can discriminate well while having no direct probability
interpretation. CalibRead therefore records the raw score and the calibrated
probability separately.

## 3. Construct calibration records

Run one frozen model, prompt, decoding configuration, and raw scoring rule on
the calibration split. Join each cached generation to its predeclared gold
answer and record whether it is correct.

The calibrator input is a sequence of pairs:

```text
(raw score, correctness)
(-0.05, 1)
(-0.12, 1)
(-0.20, 0)
(-0.25, 1)
(-0.40, 0)
(-1.10, 0)
```

Here `1` means correct and `0` means incorrect. Calibration examples must remain
disjoint from test examples under the lineage-aware split rules.

## 4. Fit the calibrator

The primary implementation fits one global weighted isotonic calibrator. R5
levels receive balanced total weight so the largest hop group does not determine
the entire mapping. It learns a nondecreasing mapping:

```text
raw score -> estimated probability of correctness
```

An illustrative learned mapping could be:

| Raw-score interval | Observed calibration accuracy |
|---|---:|
| -2.00 to -1.00 | 0.18 |
| -1.00 to -0.50 | 0.42 |
| -0.50 to -0.20 | 0.67 |
| -0.20 to -0.10 | 0.82 |
| -0.10 to 0.00 | 0.94 |

These numbers are examples, not CalibRead results. If a new raw score is
`-0.16`, this illustrative calibrator would return approximately `0.82`.

The interpretation is group-level: among comparable examples receiving a
calibrated value near `0.82`, about 82% should be correct. It is not proof about
the truth of one particular answer.

Model selection and calibrator-family selection belong to development data.
The calibration split fits the frozen method. The test split evaluates it
without refitting.

## 5. Freeze and identify the calibrator

Before test evaluation, save a versioned calibration object and manifest:

```text
results/r5/<calibration-run>/calibration/
|-- CALIBRATOR.json
|-- CALIBRATION_MANIFEST.json
`-- calibration_metrics.json
```

The frozen object must record at least:

- calibrator ID and method;
- exact model snapshot or returned model identity;
- raw score source;
- prompt and decoding identity;
- calibration split and input-example hash;
- fitted parameters;
- calibration support count and supported groups;
- software/configuration hashes.

Derived test records must contain both the raw score and calibrated confidence,
and link to the calibrator ID and object hash. Changing any input requires a new
calibrator ID and a new run.

## 6. Apply the calibrator to test data

For an untouched test generation:

```text
raw score                 = -0.16
calibrated confidence     = 0.82
score kind                = probability
calibrator ID             = r5-model-x-isotonic-v1
```

The frozen mapping is applied without using the test correctness label. Gold
correctness is used only afterward to evaluate Brier score, log loss, ECE,
adaptive calibration error, correctness AUROC, and risk-coverage behavior.

## 7. Apply the R7 threshold policies

R7 is a post-hoc policy axis. It reuses cached outputs and does not call the LLM
again. CalibRead evaluates the frozen thresholds:

```text
0.50, 0.70, 0.90, 0.95, 0.99
```

For a calibrated confidence of `0.82`:

| Threshold | Point-answer decision |
|---:|---|
| 0.50 | answer |
| 0.70 | answer |
| 0.90 | abstain |
| 0.95 | abstain |
| 0.99 | abstain |

The full implementation must additionally fail closed when calibration support
is inadequate, the group was unseen, the score/calibrator identity is mixed, or
the R4 ambiguity audit does not permit a singleton commitment.

For each threshold, report answer rate, selective risk or answered accuracy,
abstention rate, coverage where valid, set size where applicable, and uncertainty
intervals. Higher thresholds are expected to reduce answer rate; whether they
actually reduce risk is measured rather than assumed.

## 8. When the `set` action is valid

The current R5 OpenRouter and Ollama paths generate one free-form answer. Their
initial valid point policy is therefore `answer` or `abstain`.

A formal prediction-set action requires a fixed candidate universe supplied
independently of the model, a score for every candidate, and a frozen conformal
calibration procedure. In that finite-label setting, an output may be:

```text
SET: {Paris, Lyon}
```

For open-ended QA, sampling several generated strings does not automatically
create a set with a coverage guarantee: the correct answer may be absent from
all generated candidates. Such experiments must report candidate-oracle recall
and remain diagnostic unless every missing-mass and exchangeability assumption
of a valid method is implemented and audited.

## 9. Implemented command interface

These commands are runnable. The complete data, development, and test sequence
is in [`R5_COMPLETE_RUN.md`](R5_COMPLETE_RUN.md).

```powershell
$env:PYTHONPATH = 'src'

# Generate and score the calibration split.
python -m calibread.inference.cli run configs/inference/r5_ollama_calibration.toml
python -m calibread.inference.cli score configs/inference/r5_ollama_calibration.toml

# Fit and freeze the calibrator using calibration data only.
python -m calibread.inference.cli fit-calibrator configs/inference/r5_ollama_calibration.toml

$calibrator = 'results/r5/r5_qwen3_4b_forced_v1/calibration/calibration/CALIBRATOR.json'

# Generate and score the untouched test split with the same model and prompt.
python -m calibread.inference.cli run configs/inference/r5_ollama_test.toml
python -m calibread.inference.cli score configs/inference/r5_ollama_test.toml

# Apply the frozen calibrator without refitting.
python -m calibread.inference.cli calibrate `
  configs/inference/r5_ollama_test.toml `
  --calibrator $calibrator

# Produce every R7 decision from the same cached generations.
python -m calibread.inference.cli decide-r7 `
  configs/inference/r5_ollama_test.toml `
  --calibrator $calibrator

# Produce the held-out calibration and selective-risk report.
python -m calibread.inference.cli calibration-report `
  configs/inference/r5_ollama_test.toml `
  --calibrator $calibrator
```

The calibration report creates or verifies the fixed R7 decisions as part of
its derived-artifact pipeline. All of these commands operate on cached
generations; only `run` calls the model.

Applying a calibrator also freezes `CONDITION_IDENTITY_MANIFEST.json` in the
target run directory. Its file SHA-256 is the `condition_table_hash` used by
`calibrated_evaluation.csv` and recorded by
`CALIBRATED_RESULTS_MANIFEST.json`, so evaluator rows cannot be detached from
the exact target-run condition.

## 10. Non-negotiable split discipline

```text
Development split
    choose the raw score, calibrator family, and hyperparameters

Calibration split
    fit and freeze the selected calibrator or conformal threshold

Test split
    apply the frozen object once and report results without refitting
```

This process trains only a small statistical mapping on cached outputs. It does
not train or fine-tune the underlying LLM.
