# R5 cluster sealed-test findings — comprehensive synthesis

**Status:** engineering-complete, not publication-final (human audits pending).  
**Date:** 2026-09-18.  
**Conditions:** `r5_qwen25_72b_cluster_forced_v1`, `r5_mixtral_8x22b_cluster_forced_v1`.  
**Shared test selection hash:** `16713fb19eae07eb58fa707828350ae8312cccb4c9afd8626e8bf29234257633`.

This document synthesizes confirmatory evidence from the first two complete R5
pipelines on the BITS GPU cluster. Per-condition runbooks:

- [`r5_qwen25_72b_cluster_run.md`](r5_qwen25_72b_cluster_run.md)
- [`r5_mixtral_8x22b_cluster_run.md`](r5_mixtral_8x22b_cluster_run.md)

Registered hypothesis definitions: [`hypothesis_registry.md`](hypothesis_registry.md).  
Research protocol: [`research_protocol.md`](research_protocol.md).

---

## 1. Scope — what these runs test and what they do not

### 1.1 Research questions in play

CalibRead's overarching question is **when can an LLM Read be trusted** under a
declared workload and reliability target. The narrower R5 sub-question — **do
calibrated LLM Reads compose?** — is what these two conditions primarily measure.

Both runs share:

| Frozen element | Value |
|----------------|-------|
| Prompt | `r5-closed-book-forced-short-v3` |
| `max_tokens` | 32 |
| `temperature` | 0.0 |
| `require_logprobs` | true |
| Score | `mean_generated_token_log_probability` |
| Calibrator | Level-balanced global isotonic (PAVA), fit on calibration split only |
| Datasets | SOCRATES v1 + MuSiQue (atomic + composite chains) |
| Splits | Development pilot (287), development (11,640), calibration (18,913), test (30,387) |

They differ only in model identity and hardware:

| | Qwen2.5 72B q4 | Mixtral 8×22B q4 |
|--|----------------|------------------|
| Alias | `calibread-qwen25-72b-instruct-q4` | `calibread-mixtral-8x22b-instruct-q4` |
| GPUs | 1× A100 80 GB | 2× A100 80 GB |
| Calibrator ID | `r5-isotonic-a32da9f620227c07da93` | `r5-isotonic-051eff823d91639990a7` |

### 1.2 What was completed

For each condition, the full sealed pipeline executed without provider failures:

```text
development_pilot → development → calibration → fit_calibrator → test (blind) → unblind
```

Artifacts include `r5_report.json`, `r5_composition_report.json`,
`calibration_report.json`, `r7_decisions.csv`, and frozen `CALIBRATOR.json`.

### 1.3 What was not in scope

These runs are **not** the complete P03 R1–R7 study. The following registered
gates were **not** evaluated:

| Registered test | Why not closed |
|-----------------|----------------|
| **OP-R1 / P03-H1** (frequency threshold) | No R1 head/middle/tail stratification in these reports |
| **OP-I15** (R1 × R5 interaction) | Not in the original R5 reports. Later cross: [`r1r5_socrates_sealed_test_findings.md`](r1r5_socrates_sealed_test_findings.md). Head × two-hop stays under the cell floor |
| **OP-CPR / P03-H3** (conformal prediction sets) | Isotonic point calibration only; no finite-label CPR sets |
| **OP-R6 / P03-H4** (domain transfer) | Single-domain R5 panels; no cross-domain calibrator transfer |
| **OP-R7 / P03-H5** (abstention optimality) | No temperature-scaled or verbalized-uncertainty baselines on identical cache |
| **Three Tier A families** | Two families (one condition each); gate needs ≥2 families per hypothesis cell |
| **Human audit finalization** | SOCRATES and MuSiQue atomic manifests remain `pending` |

Configs deliberately omit `required_human_audit_manifests`. Label all claims
here **engineering-complete**, not publication-final, until `finalize-audit` on
both source manifests.

---

## 2. Hypothesis mapping and gate scorecard

| Original / operational ID | Question | Sealed-test verdict | Notes |
|---------------------------|----------|---------------------|-------|
| **P03-H2 / OP-R5** | Does error compound like \(H_d \approx 1-(1-H_1)^d\)? | **Mixed — not supported at full gate** | Pooled residual in band for both models; **SOCRATES two-hop strongly contradicts** on both |
| **OP-R5 depth trend** | Does reliability degrade with hop depth? | **Supported phenomenologically** | Large drops, especially SOCRATES one-hop → two-hop |
| **R5 composition** | Is failure synthesis, not just weak atoms? | **Supported** | High synthesis loss on SOCRATES two-hop; atoms ≫ chains |
| **Partial R7 / calibration** | Can logprobs rank correctness for selective answer? | **Supported for Mixtral; modest for Qwen** | Test AUROC 0.90 vs 0.81; very different coverage at τ=0.50 |
| **P03-H1** | Frequency threshold | **Not tested** | — |
| **P03-H3** | CPR tightness | **Not tested** | — |
| **P03-H4** | Domain calibration transfer | **Not tested** | — |
| **P03-H5** | CPR dominates baselines on risk–coverage | **Not tested** | No baseline policies on same cache |

Per the hypothesis registry, **complete** means reported regardless of outcome;
**supports the operational claim** means the predeclared numerical gate was met.
This synthesis reports both.

---

## 3. Primary outcomes (sealed test, n = 30,387)

### 3.1 Overall exact-match accuracy

| Split | Qwen 72B | Mixtral 8×22B |
|-------|----------|---------------|
| Development pilot (287) | 28.6% | 31.4% |
| Development (11,640) | 22.6% | 29.0% |
| **Test (sealed)** | **22.4%** | **29.3%** |
| Dev → test delta | −0.2 pp | +0.3 pp |

**Finding — seal integrity:** Development and test agree within 0.3 pp for both
conditions. Pilot overshoots full-split accuracy (small-sample optimism). The
sealed test is trustworthy confirmatory evidence for these frozen conditions.

**Finding — model ranking:** Mixtral exceeds Qwen by **+6.9 pp** overall on the
identical test selection hash. This is a real architecture/scale effect under
the frozen prompt, not a split artifact.

### 3.2 Per-cell exact match (test)

| Cell | Qwen 72B | Mixtral 8×22B | Δ (Mixtral − Qwen) |
|------|----------|---------------|---------------------|
| SOCRATES one-hop | 41.2% | **75.0%** | **+33.8 pp** |
| SOCRATES two-hop | 2.4% | 1.7% | −0.7 pp |
| MuSiQue atomic one-hop | 29.4% | 29.8% | +0.4 pp |
| MuSiQue two-hop | 10.7% | 8.9% | −1.8 pp |
| MuSiQue three-hop | 13.8% | 8.1% | −5.7 pp |
| MuSiQue four+ hop | 10.3% | 5.9% | −4.4 pp |

**Finding — scale helps atoms on SOCRATES, not multi-hop:** Mixtral's gain is
almost entirely SOCRATES one-hop (+34 pp). Two-hop remains near floor (~2%) for
both models. MuSiQue multi-hop is **weaker** for Mixtral than Qwen on this test
split.

**Finding — depth penalty:** Within each dataset family, deeper hops are weaker
(MuSiQue one-hop ~30% → four+ ~6–10%). SOCRATES shows the most extreme cliff:
75% one-hop vs ~2% two-hop (Mixtral).

**Confound warning (protocol):** SOCRATES and MuSiQue differ in source and
construction; depth and dataset are confounded. Never pool them into a single
“multi-hop” claim without stratification.

### 3.3 Abstention

| Condition | Test abstention rate | SOCRATES two-hop abstention |
|-----------|---------------------|----------------------------|
| Qwen 72B | 0.28% (~85 / 30,387) | ~1.8% (~64 / 3,560) |
| Mixtral 8×22B | **0%** | **0%** |

The forced-answer prompt forbids `ABSTAIN`. Residual abstentions are fluent
refusals scored as incorrect. Mixtral never triggered abstention detection on
test; Qwen abstained rarely, concentrated in SOCRATES two-hop.

---

## 4. Composition and synthesis findings

Composition metrics come from `r5_composition_report.json` on **multi-hop chains
only** (n = 14,655 chain clusters; 33,438 atomic probe occurrences).

### 4.1 Pooled composition (test)

| Metric | Qwen 72B | Mixtral 8×22B | Interpretation |
|--------|----------|---------------|----------------|
| Chain accuracy | 9.2% | 6.9% | Full composed answers rarely correct |
| All-atoms-correct rate | 7.7% | **18.3%** | Mixtral gets all pieces right more often |
| Atomic accuracy | 32.0% | **37.1%** | Atoms easier than chains for both |
| Chain acc. given all atoms correct | 26.1% | **9.7%** | Even when atoms match, chain often fails |
| **Synthesis loss** | **0.74** | **0.90** | P(chain wrong \| all atoms correct) |
| Observed chain error | 90.8% | 93.1% | — |
| Factorized predicted error | 91.5% | 88.4% | Diagnostic \(1-(1-H_1)^d\) style prediction |
| **Factorized residual** | **−0.007** | **+0.047** | Observed − predicted chain error |
| Within ±0.05 equivalence band? | **Yes** | **Yes** (barely) |

**Finding — composition is the bottleneck:** Atomic accuracy (32–37%) far exceeds
chain accuracy (7–9%). Models more often fail at **synthesis** than at isolated
atomic probes.

**Finding — Mixtral paradox:** Mixtral improves all-atoms-correct (+10.6 pp)
and atomic accuracy (+5.1 pp) but **lowers** full chain accuracy (−2.3 pp) and
**increases** synthesis loss (0.74 → 0.90). Getting every atom right is more
common, yet converting those atoms into a correct composed answer is **harder**
for Mixtral than Qwen.

**Finding — pooled factorized diagnostic is misleading:** Both models' pooled
residuals sit inside the predeclared \([-0.05, +0.05]\) equivalence band, which
would naively suggest H2 is “fine.” Per-cell analysis (§4.3) shows this is an
aggregation artifact.

### 4.2 Synthesis loss by cell (test)

Synthesis loss = P(chain wrong | every constituent atom answered correctly).

| Cell | Qwen 72B | Mixtral 8×22B |
|------|----------|---------------|
| MuSiQue three-hop | 0.43 | 0.56 |
| MuSiQue two-hop | 0.62 | 0.68 |
| **SOCRATES two-hop** | **0.94** | **0.98** |
| MuSiQue four+ hop | n/a (0% all-atoms-correct) | n/a |

**Finding — SOCRATES two-hop synthesis is effectively broken:** When every atomic
constituent is correct, the composed SOCRATES answer is still wrong ~94–98% of
the time. This is the central negative result for “do calibrated Reads compose?”

**Finding — MuSiQue synthesis loss is high but not floor:** Two- and three-hop
MuSiQue show synthesis loss 0.56–0.68 — substantial, but not the near-certainty
failure mode of SOCRATES two-hop.

### 4.3 Factorized compounding residual by cell (H2 / OP-R5)

Residual = observed chain error − factorized diagnostic prediction.  
Equivalence band (predeclared): **±0.05**.

| Cell | Qwen residual | Qwen in band? | Mixtral residual | Mixtral in band? |
|------|---------------|---------------|------------------|------------------|
| **Pooled (all chains)** | −0.007 | **Yes** | +0.047 | **Yes** |
| MuSiQue two-hop | −0.031 | **Yes** | −0.012 | **Yes** |
| MuSiQue three-hop | −0.104 | No | −0.065 | No |
| MuSiQue four+ hop | −0.093 | No | −0.054 | No |
| **SOCRATES two-hop** | **+0.146** | **No** | **+0.544** | **No** |

95% bootstrap intervals for SOCRATES two-hop residuals exclude the equivalence
band on both models (Qwen CI roughly +0.14 to +0.15; Mixtral +0.53 to +0.56).

**Finding — H2 not supported:** The multiplicative compounding model
\(H_d \approx 1-(1-H_1)^d\) is **not** an adequate universal diagnostic. Negative
residuals on MuSiQue (errors **less** than predicted) and large **positive**
residuals on SOCRATES two-hop (errors **worse** than predicted) cancel in the
pool.

**Finding — SOCRATES two-hop errors compound worse than independence:**
Positive residual means observed chain failure exceeds what independent per-hop
errors would predict — consistent with **correlated failure** or **synthesis
collapse** beyond per-atom mistakes.

**Registered gate (OP-R5 / H2):** Requires equivalence band at each tested depth
on **≥2 Tier A families** without contradiction. Here: only MuSiQue two-hop passes
per family; SOCRATES two-hop fails on both; only **one model family per
condition**. Gate **not met**.

### 4.4 Depth trend within MuSiQue (test EM)

| Depth | Qwen 72B | Mixtral 8×22B |
|-------|----------|---------------|
| Atomic one-hop | 29.4% | 29.8% |
| Two-hop | 10.7% | 8.9% |
| Three-hop | 13.8% | 8.1% |
| Four+ hop | 10.3% | 5.9% |

**Finding — non-monotonic depth curve on MuSiQue:** Three-hop slightly exceeds
two-hop for Qwen on this split (possible sampling noise; n differs per cell).
Overall pattern is weak performance beyond one-hop with no clear “graceful
degradation” — more a **plateau near floor** than smooth compounding.

---

## 5. Calibration and R7 selective-answer findings

Calibrator: weighted isotonic on mean token log-probability, fit on calibration
split (18,913 examples), applied frozen to test.

### 5.1 Discrimination and calibration quality (test)

| Metric | Qwen 72B | Mixtral 8×22B |
|--------|----------|---------------|
| Correctness AUROC (calibrated) | 0.812 | **0.900** |
| Raw score AUROC | 0.813 | 0.900 |
| ECE (10 bins) | 0.036 | 0.035 |
| Brier score | 0.136 | **0.107** |
| AURC | 0.596 | **0.438** |
| Mean calibrated confidence | 0.19 | 0.26 |
| Overall EM (same as raw) | 22.4% | 29.3% |

Calibration-split (in-sample diagnostic, not held-out evidence):

| Metric | Qwen 72B | Mixtral 8×22B |
|--------|----------|---------------|
| Correctness AUROC | 0.807 | 0.905 |
| ECE (10 bins) | 0.043 | 0.030 |

**Finding — logprobs are informative:** Both models' token log-probabilities
rank correct vs incorrect answers well above chance (AUROC 0.81–0.90). Mixtral's
raw scores separate correctness more sharply.

**Finding — isotonic calibration is stable:** Test AUROC matches calibration-split
diagnostics within ~0.005; no obvious overfit collapse.

**Finding — low mean confidence reflects difficulty:** Mean calibrated confidence
(0.19–0.26) is far below per-answer accuracy on accepted subsets — the
calibrator correctly spreads mass toward uncertainty on this hard workload.

### 5.2 R7 risk–coverage frontier (test, all five thresholds)

| τ | Qwen coverage | Qwen acc. on accepted | Mixtral coverage | Mixtral acc. on accepted |
|---|---------------|----------------------|--------------------|--------------------------|
| 0.50 | 7.9% | 69.4% | **25.2%** | **79.5%** |
| 0.70 | 0.4% | 70.9% | **16.4%** | **89.3%** |
| 0.90 | 0% | — | **7.0%** | **96.0%** |
| 0.95 | 0% | — | **4.1%** | **97.8%** |
| 0.99 | 0% | — | **0.2%** | **100%** |

**Finding — selective answering works for Mixtral, barely for Qwen:** At τ=0.50,
Mixtral accepts one quarter of items at ~80% accuracy — a usable (though not
deployment-ready) selective-read policy. Qwen at the same threshold accepts <8%
at ~69% accuracy; higher thresholds accept **zero** items.

**Finding — R7 is post-hoc policy, not native abstention:** Generation uses a
forced-answer prompt (0% abstention for Mixtral). R7 thresholds filter **after**
the fact. This measures whether calibration can **recover** a trust policy, not
whether the model voluntarily abstains.

**Finding — partial progress toward Read contract:** The contract requires
answer / set / abstain under a declared risk target. These runs demonstrate
**answer vs abstain** via calibrated thresholds on one model family with
meaningful coverage, but do not evaluate **prediction sets** (CPR) or baseline
policy comparisons required for P03-H5.

---

## 6. Cross-model and scale narrative

### 6.1 Promotion path (pilot → full pipeline)

| Model | Pilot EM (287) | Test EM (30,387) | Pilot → test |
|-------|----------------|------------------|--------------|
| Qwen 72B | 28.6% | 22.4% | −6.2 pp (optimism) |
| Mixtral 8×22B | 31.4% | 29.3% | −2.1 pp |

Both passed operational promotion gates (zero provider failures, logprobs present,
non-degenerate scores). Multi-hop cells were weak in pilot but improved enough
over 4B/7B/14B pilots to advance.

### 6.2 Comparison to smaller pilots (development pilot, n = 287)

| Model | Pilot overall EM |
|-------|------------------|
| Qwen3 4B (local) | 10.1% (failed promotion) |
| Qwen2.5 7B (local) | 16.7% |
| Qwen2.5 14B q3 (cluster) | 20.9% |
| Qwen2.5 72B q4 | 28.6% |
| Mixtral 8×22B q4 | **31.4%** |

**Finding — scale and architecture matter for atomic QA:** Each scale-up improved
pilot EM until 72B/Mixtral, but **confirmatory test EM remains modest** (~22–29%)
because multi-hop and synthesis cells dominate the workload mix.

### 6.3 Error character (from prior error analysis)

Most low-EM failures are **wrong answers**, not strict-matching artifacts (~88%
of errors have token F1 < 0.1). Scoring uses normalized exact match in
`src/calibread/correctness.py`.

---

## 7. Implications for the paper question

> **Do Calibrated LLM Reads Compose?**

### 7.1 What we can claim now

1. **Under a frozen closed-book forced-short-answer contract**, large open models
   achieve **stable** dev/test generalization and reproducible sealed-test metrics.

2. **Reliability degrades sharply with composition depth**, especially SOCRATES
   one-hop (75%) → two-hop (~2%).

3. **Multi-hop failure is largely synthesis failure**, not merely missing atomic
   facts: synthesis loss on SOCRATES two-hop ≈ 0.94–0.98.

4. **The factorized compounding diagnostic is not trustworthy when pooled**; it
   hides catastrophic SOCRATES two-hop deviation.

5. **Isotonic calibration on logprobs provides meaningful selective-answer
   capability** on Mixtral (25% coverage / 80% accuracy at τ=0.50), but does
   **not** fix composition.

6. **Bigger MoE helps SOCRATES atomic reads** but does **not** unlock two-hop
   composition and may **worsen** synthesis loss despite better atoms.

### 7.2 What we cannot claim yet

- Universal frequency thresholds (H1).
- CPR coverage or set-size guarantees (H3).
- Domain-partitioned calibration transfer (H4).
- CPR Pareto-dominance over baselines (H5).
- R1 × R5 as a fully supported three-by-two cell, including head × two-hop.
  The Dolma-proxy cross of this cache is in
  [`r1r5_socrates_sealed_test_findings.md`](r1r5_socrates_sealed_test_findings.md).
- Publication-final evidence (human audits pending).

### 7.3 Plain-language bottom line

**Calibrated single-hop Reads can be partially trusted on a selective subset
(Mixtral). Calibrated multi-hop Reads do not compose reliably in this setting.**
Scale improves atomic knowledge and score ranking; it does not solve synthesis.

---

## 8. Open work and recommended next analyses (no new inference required)

| Priority | Analysis | Addresses |
|----------|----------|-----------|
| 1 | R1 head/middle/tail stratification on cached `scored_results.csv` | Done for SOCRATES in [`r1r5_socrates_sealed_test_findings.md`](r1r5_socrates_sealed_test_findings.md). PopQA OP-R1 is separate |
| 2 | Third Tier A model family (API or cluster) | Hypothesis family gate |
| 3 | CPR finite-label sets + temperature/verbalized baselines on same cache | H3, H5 |
| 4 | `finalize-audit` on SOCRATES + MuSiQue atomic manifests | Publication gate |
| 5 | Per-chain failure taxonomy (wrong atom vs synthesis vs abstention-like refusal) | Composition mechanism |
| 6 | R7 full frontier plots (AURC) with bootstrap CIs across models | OP-CONTRACT |

---

## 9. Artifact index

### 9.1 Result trees (local)

```text
results/r5/r5_qwen25_72b_cluster_forced_v1/
results/r5/r5_mixtral_8x22b_cluster_forced_v1/
```

### 9.2 Key test artifact hashes

| Artifact | Qwen 72B SHA-256 | Mixtral 8×22B SHA-256 |
|----------|------------------|------------------------|
| `test/r5_report.json` | `dc7af4cc7e48dabf7fdb7e90a651ddef7063f5c6e43d469807a6ecd2c700c692` | `65bc96a81680c310345e6762d21e021ef0de531f94a8114ee93354958fadec85` |
| `test/r5_composition_report.json` | `e19fa0e54ab26c14bce76497fb40647ac55fde362bfd6a66842bbee276f020c7` | `1dd37eb214187018df3dd353f2f4d48aa9f3f8f0cfd0b82fa8e2cbc9dd897e62` |
| `CALIBRATOR.json` (object) | `559548139978da6285c02755cd7287bce3138808b52aaf3342b8382624b7df85` | `173c61149f2887acb5efe084ebc2a79493066c87e930ca7abe48ca4761f51b63` |

### 9.3 Slurm jobs (full pipeline)

| Phase | Qwen 72B | Mixtral 8×22B |
|-------|----------|---------------|
| Development | 11335 | 11369 |
| Calibration | 11339 | 11370 |
| Fit calibrator | 11340 | 11371 |
| Test (blind) | 11341 | 11372 |
| Unblind | 11342 | 11373 |

---

## 10. Decision-log cross-reference

Synthesis recorded in [`decision_log.md`](decision_log.md):

- 2026-09-17 — Qwen 72B full pipeline complete
- 2026-09-18 — Mixtral 8×22B full pipeline complete
- 2026-09-18 — R5 sealed-test findings synthesis (this document)
