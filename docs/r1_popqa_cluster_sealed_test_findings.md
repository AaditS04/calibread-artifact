# R1 PopQA sealed-test findings

**Status:** engineering-complete, not publication-final (PopQA human audit pending).  
**Date:** 2026-09-24.  
**Conditions:** `r1_popqa_qwen25_72b_cluster_v1`, `r1_popqa_mixtral_8x22b_cluster_v1`.  
**Shared test selection hash:** `227dfcc7c1dffb60bab545d2b2485bd9d01363cd5b24d0937dfc8f906ff4d2db`.

Both conditions answered the same 7,046 PopQA test questions. They differ only in
model identity. Protocol: [`src/calibread/inference/R1_COMPLETE_RUN.md`](../src/calibread/inference/R1_COMPLETE_RUN.md).
Registered hypothesis: [`hypothesis_registry.md`](hypothesis_registry.md).

Local result trees:

```text
results/r1/r1_popqa_qwen25_72b_cluster_v1/
results/r1/r1_popqa_mixtral_8x22b_cluster_v1/
```

---

## 1. What was tested

**P03-H1** says reliability jumps from near failure to near success at a critical
training-frequency threshold, and that this threshold is universal across model
families once capacity is normalized.

**OP-R1** is the operational version this repository can run. Freeze `head`,
`middle`, and `tail` on development data. On held-out data, tail risk should
exceed head risk, and the 95% interval for that difference should exclude zero.
A second registered piece, a development-fit change-point model beating a smooth
model on held-out log loss, was not fit.

The measurement in this run is PopQA subject popularity, field `s_pop`. Inclusive
tertiles were frozen on the development split only:

| Level | Rule | Development | Calibration | Test |
|---|---|---:|---:|---:|
| tail | `s_pop` ≤ 386 | 953 | 1,506 | 2,389 |
| middle | 386 < `s_pop` ≤ 2,955 | 950 | 1,465 | 2,305 |
| head | `s_pop` > 2,955 | 950 | 1,397 | 2,352 |

Cutpoints and hashes are in `data/processed/popqa_r1/BIN_MANIFEST.json`. Every
question is one-hop. The prompt is the promoted forced-short-answer contract,
template `r1-popqa-closed-book-forced-short-v1`, temperature 0, 32 tokens,
token log probabilities required. The calibrator is a weighted isotonic map fit
on that model's calibration split and applied only after blind test generation.

| | Qwen2.5 72B q4 | Mixtral 8×22B q4 |
|---|---|---|
| Alias | `calibread-qwen25-72b-instruct-q4` | `calibread-mixtral-8x22b-instruct-q4` |
| Digest | `sha256:11420ebce5f9e053e48662e8d2fd228d9da2e07a614039e06fe09341ce69dc2d` | `sha256:de58127cf2675b72a8abf9811768a36e8500e8ea52a5ae393ded274ada7cd8c8` |
| GPUs | 1× A100 80 GB | 2× A100 80 GB |
| Calibrator ID | `r5-isotonic-26c6ea7b73711664b280` | `r5-isotonic-2acfb704ec6d25567857` |
| Test failures | 0 / 7,046 | 0 / 7,046 |

The calibrator ID prefix is the shared isotonic implementation name. These
objects were fit on the R1 calibration rows. They are not the R5 calibrators.

---

## 2. Hypothesis scorecard

| Claim | Result |
|---|---|
| Tail exact-match is below head, and the 95% interval excludes zero | **Held** on development, calibration, and the sealed test, for both models |
| The drop is a near-zero to near-one transition | **Not held.** Head is about 45–49%. Tail is about 17–20% |
| The threshold is a training-corpus frequency | **Not tested.** The axis is Wikipedia subject popularity |
| A frozen change-point model beats a smooth model on held-out log loss | **Not run** |
| The gap is the same kind of curve in both families | **Partly.** The tail-versus-head gap is similar. The middle bin is not |
| Pooled isotonic calibration matches accuracy on the sealed test | **Held** marginally (ECE 1.8% and 1.4%) |
| The same calibrator is reliable inside each R1 bin | **Not held.** Head is under-confident. High thresholds do not make tail answers safe |
| R1 × R5, CPR sets, a third family, human audit | **Not in this bundle** |

---

## 3. Exact match by popularity bin

### 3.1 Sealed test (n = 7,046 each)

| Model | Overall | Head | Middle | Tail | Tail − head (95% interval) |
|---|---:|---:|---:|---:|---|
| Qwen 72B | 27.3% (1,921) | 45.4% (1,068/2,352) | 19.3% (444/2,305) | 17.1% (409/2,389) | −28.3 pp (−30.7, −25.8) |
| Mixtral 8×22B | 32.0% (2,253) | 49.2% (1,158/2,352) | 27.1% (625/2,305) | 19.7% (470/2,389) | −29.6 pp (−32.1, −26.9) |

### 3.2 Seal check against development and calibration

| Model | Split | Overall | Head | Middle | Tail | Tail − head |
|---|---|---:|---:|---:|---:|---:|
| Qwen | Development | 26.4% | 44.4% | 17.2% | 17.5% | −26.9 pp |
| Qwen | Calibration | 26.4% | 43.5% | 18.9% | 17.7% | −25.8 pp |
| Qwen | Test | 27.3% | 45.4% | 19.3% | 17.1% | −28.3 pp |
| Mixtral | Development | 31.4% | 47.2% | 26.5% | 20.7% | −26.5 pp |
| Mixtral | Calibration | 31.9% | 47.5% | 30.3% | 18.9% | −28.7 pp |
| Mixtral | Test | 32.0% | 49.2% | 27.1% | 19.7% | −29.6 pp |

Overall test accuracy is within 1 percentage point of development for both
models. The tail-versus-head interval is negative on every split. The bins were
not moved after seeing test answers.

### 3.3 Shape of the curve

Qwen falls once. Head is about 45%. Middle and tail sit together around 17–19%.
On development the tail was 0.4 points above the middle. On the test set the
middle is 2.1 points above the tail. That is not a stable three-step decline.

Mixtral keeps a gradient on every split. On the test set, middle is 7.4 points
above tail, and head is 22.1 points above middle.

Mixtral's overall advantage over Qwen is 4.7 points on the test set. Almost all
of it is in the middle (+7.9 points) and the head (+3.8 points). The tail
advantage is 2.5 points. A larger model does not repair rare subjects.

---

## 4. Did the calibrator work?

Each model has its own isotonic map, fit on its 4,368 calibration rows and
applied to all 7,046 test rows. Unsupported rows: 0. Metrics below are held-out
test evidence. Development and calibration were scored for exact match before
the test was opened. Probability calibration was applied only at unblind.

### 4.1 Marginal calibration

| | Qwen | Mixtral |
|---|---:|---:|
| Accuracy | 27.3% | 32.0% |
| Mean calibrated confidence | 26.3% | 31.6% |
| ECE (10 equal-width bins) | 1.8% | 1.4% |
| Brier score | 0.136 | 0.131 |
| Brier of a constant at the base rate | 0.198 | 0.218 |
| Log loss | 0.430 | 0.432 |
| Correctness AUROC | 0.830 | 0.862 |

Both maps are close to the observed accuracy, and both beat a constant
base-rate prediction on Brier score. Mixtral ranks correct answers more cleanly.

### 4.2 Selective Read on the sealed test

Answer only when calibrated confidence is at least τ. Accuracy is among the
answered rows.

| τ | Qwen answered | Qwen accuracy | Mixtral answered | Mixtral accuracy |
|---:|---:|---:|---:|---:|
| 0.50 | 1,454 (20.6%) | 71.5% | 1,826 (25.9%) | 76.6% |
| 0.70 | 796 (11.3%) | 82.4% | 1,363 (19.3%) | 80.6% |
| 0.90 | 53 (0.8%) | 84.9% | 87 (1.2%) | 93.1% |
| 0.95 | 2 | 100% | 29 (0.4%) | 96.6% |
| 0.99 | 1 | 100% | 28 (0.4%) | 96.4% |

At the anchor threshold 0.70, refusing about 80–90% of questions raises accuracy
from the high 20s or low 30s into the low 80s. Mixtral answers more questions
at that threshold and keeps roughly the same accuracy. Thresholds 0.95 and 0.99
are not operating points for Qwen: it almost never clears them. Mixtral's 0.95
and 0.99 rows are the same 28 answers, all in the head bin except one middle
answer. These thresholds are score cutoffs. They are not conformal coverage.

### 4.3 Calibration inside each bin

The map is pooled. It was not fit separately for head, middle, and tail.

| Model | Bin | Accuracy | Mean confidence | ECE | AUROC |
|---|---|---:|---:|---:|---:|
| Qwen | Head | 45.4% | 37.3% | 8.3% | 0.839 |
| Qwen | Middle | 19.3% | 21.9% | 2.7% | 0.815 |
| Qwen | Tail | 17.1% | 19.5% | 4.1% | 0.753 |
| Mixtral | Head | 49.2% | 44.7% | 5.2% | 0.875 |
| Mixtral | Middle | 27.1% | 27.9% | 1.3% | 0.845 |
| Mixtral | Tail | 19.7% | 22.2% | 3.2% | 0.811 |

Both models are under-confident on the head and slightly over-confident on the
tail. Ranking is weakest on Qwen's tail (AUROC 0.75).

Selective accuracy at τ = 0.70, the anchor policy:

| Model | Head | Middle | Tail |
|---|---|---|---|
| Qwen | 87.5% of 520 | 73.8% of 145 | 71.8% of 131 |
| Mixtral | 88.4% of 812 | 73.4% of 335 | 62.0% of 216 |

At τ = 0.90 the picture is sharper. Mixtral's 80 head answers are 98.8% correct.
Its tail contributes 4 answers, of which 1 is correct. Qwen's tail contributes
5 answers, of which 3 are correct. The impressive global accuracy at 0.90 is a
head-bin result. A high threshold does not make a rare-subject answer reliable.

---

## 5. What can be said

1. Under this closed-book short-answer contract, both models are much more
   accurate on popular PopQA subjects than on the bottom popularity tertile.
   The sealed-test gap is about 28–30 percentage points, and the interval
   excludes zero for both families.
2. Development, calibration, and test agree. The result is not an artifact of
   looking at the test split and then choosing bins.
3. The curve is not a phase transition from failure to success. Even the head
   bin is correct less than half the time when every question is answered.
4. A pooled isotonic calibrator is a usable global abstention score. At τ = 0.70
   it answers 11% of Qwen questions at 82% accuracy, and 19% of Mixtral
   questions at 81% accuracy.
5. That same calibrator does not give the tail a separate contract. Tail answers
   that pass 0.70 are still wrong 28% of the time for Qwen and 38% of the time
   for Mixtral.

## 6. What this bundle leaves open

- A change-point versus smooth comparison on the continuous `s_pop` value.
- Any claim about training-corpus frequency, including a universal
  capacity-normalized threshold.
- R1 crossed with hop depth on this panel. PopQA has no multi-hop items.
  The SOCRATES cross of the sealed R5 cache is in
  [`r1r5_socrates_sealed_test_findings.md`](r1r5_socrates_sealed_test_findings.md).
- Conformal prediction sets. R7 here is a threshold on an isotonic probability.
- A third model family.
- Human audit of the PopQA panel. The upstream audit status is still pending.

---

## 7. Artifact hashes

| Artifact | Qwen SHA-256 | Mixtral SHA-256 |
|---|---|---|
| `test/r1_report.json` | `828d7a1b7c2ccf621a0ae679a0044ffe2477dbbd4747c4a7c429f1e897dbbb9a` | `6c517fef1c9391485c8788d280f36c69e05e2c002e598c27778e7329e2a4a528` |
| `test/calibration_report.json` | `debf86f614e0646a8bfb76d2592582451e9ce93f087ef96fa6e6ad2d32e8aa25` | `446e2e703f8b56bf7f026ae1bd9638c1aeab687b70cfbf220035c7a46ba57699` |
| `test/calibrated_results.csv` | `6111de2125e466fcb8fc592f5756c2ae1c3197d4c6934fbd530d9469f081a4bc` | `ddbdabb02b8a37aaceab8403f542c3855b66931ae2b89721a7b7e716eccb11c6` |

Slurm chains: Qwen 11864 → 11868; Mixtral 11874 → 11878. An earlier Mixtral
chain, 11869 → 11873, was cancelled before it started and wrote no answers.
