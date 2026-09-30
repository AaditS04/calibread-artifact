# Research decision log

Decisions are append-only. A later entry may supersede an earlier one but must preserve the old rationale.

## 2026-08-10 — Four-month scope and claim correction

**Decision.** Make R1 knowledge frequency × R5 synthesis depth the primary experimental surface. Treat R7 as a serving-policy threshold, not an independent data complexity factor. Retain R2 precision, R3 recency, R4 ambiguity, and R6 domain specificity in the record schema, but defer them to secondary/exploratory analysis unless all core gates finish early.

**Rationale.** The proposal's 30-week plan asks for seven dimensions and ten model families. A 16-week window must also cover data licensing, paired atomic/compositional construction, leakage checks, model inference, baselines, human label audit, statistics, writing, and reproducibility. Attempting the full matrix would produce shallow or incomplete evidence. The narrower interaction is scientifically sharper and connects to database query composition.

**Paper question.** “Do Calibrated LLM Reads Compose? Reliability Contracts Across Long-Tail Multi-Hop Queries.” Each multi-hop chain is paired with its atomic constituent probes. Composition analysis includes chain accuracy, all-atoms-correct rate, synthesis loss, a factorized/product diagnostic, and a conservative union-bound propagation baseline.

**Guarantee correction.** Ordinary split conformal prediction supports finite-sample marginal coverage under exchangeability. Predeclared group/Mondrian methods support group-marginal statements for adequately supported groups under their assumptions. They do not provide a probability that one particular answer is correct, arbitrary conditional coverage, or arbitrary-shift protection. Open-ended, model-generated candidate sets are a stress-test track unless a fixed candidate universe and all formal assumptions are established.

**Novelty correction.** Conformal language generation, factuality guarantees, black-box uncertainty sets, multicalibration, and group/conditional conformal methods are prior work and must be cited and compared. CalibRead does not claim automatic minimal prediction sets. Its provisional contribution is the matched workload, composition/shift analysis, and auditable Read contract.

**Venue decision.** Target the 1 December 2026 PVLDB EA&B cycle (abstract 25 November), with 1 January 2027 as quality fallback. Consider ICDE's 11 November EAB deadline only if results and artifacts are already stable by 8 November. Use TMLR/later NLP or ML venue if the final contribution is not substantively data-management research.

**Revisit conditions.** Revisit scope only after two models complete every core cell and the primary analysis reproduces from immutable caches. Any expansion is additive and cannot change frozen primary hypotheses, splits, or test labels.

## 2026-08-11 -- Superseding decision: execute the full P03 R1-R7 plan

**Decision.** At the researcher's explicit direction, supersede the 10 August scope restriction.
R1 knowledge frequency, R2 precision, R3 recency, R4 ambiguity, R5 synthesis depth, R6 domain
specificity, and R7 policy threshold are all first-class confirmatory studies within the four-month
project. R7 remains a post-hoc deployment-policy axis, but it receives a full risk/coverage,
answer-rate, set-size, and abstention analysis rather than being deferred.

**Framing correction.** The project-wide slogan is **When can an LLM Read be trusted?** The
earlier paper question **Do Calibrated LLM Reads Compose?** is retained above as historical record
of the superseded R1 x R5 scope and now denotes only the R5 synthesis-depth sub-question.

**Design correction.** “Cover all dimensions” does not mean estimating a seven-way factorial. Run
frozen one-dimension sweeps under common anchor conditions and test only three predeclared
interactions: R1 x R5, R3 x R6, and R4 x R7. Other interactions are exploratory. This preserves the
professor's scientific scope while keeping sample size, confounding control, and interpretation
defensible.

**Model matrix.** Register exactly ten total model-family IDs. The first three are the full-suite
Tier A subset. All ten run every R1-R3 level, the R4-R6 anchor/hard pairs, and all five fixed R7
policies; the seven families outside Tier A are labelled partial-dimension evidence for R4-R6.
If the Week 1 compute gate cannot support exactly ten, obtain a professor-approved protocol
amendment before inference rather than silently reducing the family count.

**Compressed P03 sequence.** Weeks 1-4 establish baseline R1-R3 evidence; Weeks 5-8 implement and
evaluate CPR/calibration on R1-R3; Weeks 9-12 complete R4-R7, all three interactions, the full
benchmark/domain analysis, and R7 Pareto frontiers; Weeks 13-16 freeze results, write, reproduce, and
package the artifact.

**Non-negotiable scientific boundaries.** Finite-label conformal statements remain marginal or
predeclared group-marginal under their assumptions. Open-ended model-generated candidate results
remain a candidate-oracle stress track unless a generation-aware theorem is implemented. No score
is called a per-answer correctness probability, and existing/conflicting published methods are
cited and used as baselines.

**Schedule consequence.** Do not respond to delay by silently dropping a dimension or changing the
registered ten-family profile. Cut optional datasets, expensive uncertainty scores, and extra
ablations first; lower frozen sample targets only through a professor-approved amendment before main
collection and never below the protocol's confirmatory floors. If a required gate fails, prefer the
January PVLDB cycle or another suitable venue to an incomplete claim.

## 2026-08-14 -- R5 local 4B pilot fails the promotion gate

**Decision.** Do not promote the local
`qwen3:4b-instruct-2507-q4_K_M` condition to full R5 development,
calibration, or sealed test. Retain it as a non-evidentiary CPU feasibility
baseline and select a stronger model condition on development data before any
confirmatory inference.

**Frozen condition.** The completed pilot used Ollama 0.32.11 and model digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
It generated all 287 selected records with zero provider failures and zero API
cost. The selected-example SHA-256 was
`473c377594e6a3d04348643d0a41a638a94220a8d88bb5f91b898e3adc06533a`.
The config SHA-256 was
`777b78c84c2e82265c75be67b717ad09b892d46baa4c53c733690f24dcc381e8`.

**Promotion-gate evidence.** Overall exact-match accuracy was 29/287
(10.10%). SOCRATES one-hop accuracy was 12.5% and its two-hop accuracy was
0%. MuSiQue atomic one-hop accuracy was 13.77%; composite accuracy was 0% at
two hops, 0% at three hops, and 5% at four-plus hops. Across 80 sampled
composite chains, no chain had all constituent atoms correct, so synthesis
loss was undefined. Thirty-three outputs hit the 64-token cap despite the
forced short-answer prompt. Only 12 exact-match errors had token F1 at least
0.5. Raw confidence collection remained technically usable, with 285 distinct
mean generated-token log-probability values. These diagnostics establish a
performance floor, not a calibration or composition result.

**Artifact identities.** `RUN_MANIFEST.json` SHA-256 is
`fc0bb36712e179dd11054bce40bba89dd6f4584ed0a08688d44b31e11b034ef2`;
`r5_report.json` SHA-256 is
`93cf4dc71c27826f6c977dfd7c955ec9ca2350143de314d21a6864eb587e9d68`;
`r5_composition_report.json` SHA-256 is
`1a4f29b57870bbf3efc608ab498724d9e0336ac4f805463be98d482d9472a58f`.
Generated artifacts remain outside Git under the configured result directory.

**Operational incident.** An earlier diagnostic invocation overlapped after a
tool interruption and produced duplicate calls. That cache was preserved
unchanged under `development_pilot_overlap_quarantine_20260814` and is
explicitly forbidden as evidence. The runner now takes an OS-backed exclusive
run-directory lock before provider preflight or artifact writes; process
contention, exception release, and crash recovery are covered by tests. The
clean pilot above was generated only after this lock was installed.

**Next gate.** Complete both human audit attestations, then compare one or more
stronger frozen model conditions using development pilots. Do not change the
current calibration or test configs in place, and do not fit a calibrator or
open test labels for this failed 4B condition.

## 2026-09-17 -- R5 Qwen2.5 72B q4 cluster condition completes full pipeline

**Decision.** Treat `r5_qwen25_72b_cluster_forced_v1` as the first complete
cluster R5 evidence chain for a promoted dense model: development pilot,
development, calibration, frozen isotonic calibrator, blind test generation,
and single unblind scoring/calibration/composition pass. Use test-split results
as the primary confirmatory EM and composition record for this condition until
a new `parent_experiment_id` is opened.

**Frozen condition.** Ollama model
`calibread-qwen25-72b-instruct-q4:latest@sha256:11420ebce5f9e053e48662e8d2fd228d9da2e07a614039e06fe09341ce69dc2d`,
prompt `r5-closed-book-forced-short-v3`, `max_tokens = 32`, `temperature = 0.0`,
`require_logprobs = true`. Calibrator `r5-isotonic-a32da9f620227c07da93` with
object SHA-256
`559548139978da6285c02755cd7287bce3138808b52aaf3342b8382624b7df85`.

**Promotion path.** The 2026-09-11 development pilot (287/287, 28.6% overall EM)
passed operational promotion checks and improved over 4B/7B/14B pilots, though
SOCRATES two-hop remained at 0% in the pilot sample. Full development (11,640)
and sealed test (30,387) both completed with zero provider failures.

**Confirmatory test evidence.** Overall exact-match accuracy was 22.4% on test
vs 22.6% on development (stable generalization). SOCRATES one-hop test accuracy
was 41.2%; SOCRATES two-hop remained 2.4%. MuSiQue atomic one-hop was 29.4%;
composite two-/three-/four-plus-hop accuracies were 10.7%, 13.8%, and 10.3%.
Abstention rate was 0.28% overall (1.8% in SOCRATES two-hop). Composition on
test: chain accuracy 9.2%, all-atoms-correct rate 7.7%, synthesis loss 0.74.
Held-out calibration AUROC 0.812; at R7 τ=0.50, coverage 7.9% with 69.4%
accuracy on accepted rows.

**Artifact identities.** Test `r5_report.json` SHA-256
`dc7af4cc7e48dabf7fdb7e90a651ddef7063f5c6e43d469807a6ecd2c700c692`; test
`r5_composition_report.json` SHA-256
`e19fa0e54ab26c14bce76497fb40647ac55fde362bfd6a66842bbee276f020c7`. Test
selection SHA-256
`16713fb19eae07eb58fa707828350ae8312cccb4c9afd8626e8bf29234257633`. Full
runbook: `docs/r5_qwen25_72b_cluster_run.md`.

**Publication caveat.** These runs omitted `required_human_audit_manifests`
while SOCRATES and MuSiQue atomic human audits remain `pending`. Label the
artifacts engineering-complete but not publication-final until both manifests
are explicitly approved via `finalize-audit` and any required attestation is
recorded.

## 2026-09-18 -- R5 Mixtral 8x22B q4 cluster condition completes full pipeline

**Decision.** Treat `r5_mixtral_8x22b_cluster_forced_v1` as the second complete
cluster R5 evidence chain and the current best overall confirmatory condition on
sealed test exact-match accuracy among cluster runs completed to date. Use its
test artifacts for cross-model comparisons against `r5_qwen25_72b_cluster_forced_v1`
under the same frozen prompt and scoring contract.

**Frozen condition.** Ollama model
`calibread-mixtral-8x22b-instruct-q4:latest@sha256:de58127cf2675b72a8abf9811768a36e8500e8ea52a5ae393ded274ada7cd8c8`,
prompt `r5-closed-book-forced-short-v3`, `max_tokens = 32`, `temperature = 0.0`,
`require_logprobs = true`, **2× A100 80 GB** (`run_inference_2gpu.slurm`).
Calibrator `r5-isotonic-051eff823d91639990a7` with object SHA-256
`173c61149f2887acb5efe084ebc2a79493066c87e930ca7abe48ca4761f51b63`.

**Promotion path.** The 2026-09-11 development pilot (287/287, 31.4% overall EM)
was the highest pilot EM among cluster models tested and showed non-zero SOCRATES
two-hop in the small sample. Full pipeline jobs 11369–11373 completed with zero
provider failures.

**Confirmatory test evidence.** Overall exact-match accuracy was 29.3% on test
vs 29.0% on development. SOCRATES one-hop test accuracy was 75.0%; SOCRATES
two-hop remained 1.7%. MuSiQue atomic one-hop was 29.8%; composite two-/three-/
four-plus-hop accuracies were 8.9%, 8.1%, and 5.9%. Abstention rate was 0%.
Composition on test: chain accuracy 6.9%, all-atoms-correct rate 18.3%,
synthesis loss 0.90. Held-out calibration AUROC 0.900; at R7 τ=0.50, coverage
25.2% with 79.5% accuracy on accepted rows. This exceeds the Qwen 72B test
overall EM (22.4%) by 6.9 percentage points on the same selection hash.

**Artifact identities.** Test `r5_report.json` SHA-256
`65bc96a81680c310345e6762d21e021ef0de531f94a8114ee93354958fadec85`; test
`r5_composition_report.json` SHA-256
`1dd37eb214187018df3dd353f2f4d48aa9f3f8f0cfd0b82fa8e2cbc9dd897e62`. Full
runbook: `docs/r5_mixtral_8x22b_cluster_run.md`.

**Publication caveat.** Same human-audit pending status as the Qwen 72B chain;
engineering-complete, not publication-final until `finalize-audit` on both
source manifests.

## 2026-09-18 -- R5 cluster sealed-test findings synthesis

**Decision.** Treat the paired Qwen 72B and Mixtral 8x22B sealed-test artifacts as
the first confirmatory evidence bundle for the R5 composition question under the
frozen forced-short-answer contract. Use
`docs/r5_cluster_sealed_test_findings.md` as the canonical cross-condition
interpretation layer; per-run hashes and job IDs remain in the condition runbooks.

**Primary scientific conclusions (test split, shared selection hash).**

1. **Seal integrity:** Dev and test overall EM agree within 0.3 pp for both
   conditions (Qwen 22.6% vs 22.4%; Mixtral 29.0% vs 29.3%).
2. **Depth penalty:** SOCRATES one-hop to two-hop collapses from 41–75% to ~2%
   EM; MuSiQue degrades from ~30% one-hop to ~6–11% on deeper hops.
3. **Synthesis failure:** Pooled synthesis loss 0.74 (Qwen) and 0.90 (Mixtral);
   SOCRATES two-hop synthesis loss 0.94–0.98 when all atoms are correct.
4. **H2 / factorized diagnostic:** Pooled residuals inside ±0.05 for both models,
   but SOCRATES two-hop residuals +0.15 (Qwen) and +0.54 (Mixtral) violate the
   band — pooling masks a composition failure mode. Full OP-R5 gate not met.
5. **Selective answer (partial R7):** Mixtral test AUROC 0.900; at τ=0.50,
   coverage 25.2% at 79.5% accuracy. Qwen AUROC 0.812; at τ=0.50, coverage 7.9%
   at 69.4%; higher thresholds accept zero rows.
6. **Scale narrative:** Mixtral +6.9 pp overall vs Qwen on sealed test, driven by
   SOCRATES one-hop (+34 pp), not two-hop composition.

**Answer to the R5 paper question.** Calibrated single-hop reads can support a
selective-answer policy on Mixtral; calibrated multi-hop reads do **not** compose
reliably in this setting. Bigger models improve atoms and score ranking, not
synthesis.

**Not closed by this bundle.** OP-R1, OP-I15, OP-CPR (H3), OP-R6 (H4), full
OP-R7 baseline comparison (H5), third Tier A family, and human audit finalization.

**Next analyses without new inference.** R1-stratified composition on cached CSVs;
CPR and temperature/verbalized baselines on identical generations; third model
family for family-count gates.

## 2026-09-24 -- R1 PopQA popularity-proxy sealed tests complete

**Decision.** Record the Qwen2.5 72B q4 and Mixtral 8×22B q4 PopQA runs as the
engineering-complete R1 popularity-proxy evidence. Treat `s_pop` tertiles frozen
on development (`tail` ≤ 386, `middle` ≤ 2,955, `head` above that) as the R1
axis for these conditions. Do not describe the result as a training-frequency
threshold or as a completed P03-H1 gate.

**Evidence.** Both models answered the same 7,046 test questions
(`selected_example_ids_sha256`
`227dfcc7c1dffb60bab545d2b2485bd9d01363cd5b24d0937dfc8f906ff4d2db`) with zero
provider failures. Test exact match is 27.3% (Qwen) and 32.0% (Mixtral).
Tail-minus-head accuracy is −28.3 pp for Qwen (interval −30.7 to −25.8) and
−29.6 pp for Mixtral (interval −32.1 to −26.9). Pooled isotonic calibration
matches marginal accuracy (test ECE 1.8% and 1.4%). At τ = 0.70, selective
accuracy is 82.4% on 11.3% coverage for Qwen and 80.6% on 19.3% coverage for
Mixtral. Head bins are under-confident, and high thresholds do not make tail
answers reliable.

**Not closed.** The change-point versus smooth log-loss test, training-corpus
frequency, R1 × R5, CPR sets, a third family, and the PopQA human audit.

Full synthesis: [`r1_popqa_cluster_sealed_test_findings.md`](r1_popqa_cluster_sealed_test_findings.md).

## 2026-09-24 -- R1 × R5 scored on the sealed SOCRATES cache

**Decision.** Treat the existing Qwen2.5 72B q4 and Mixtral 8×22B q4 R5
`scored_results.csv` files as the answer cache for OP-I15. Do not launch a new
generation. Freeze R1 on development one-hop WIMBD Dolma-1.7 atom counts
(`tail` ≤ 114, `middle` ≤ 1,138), assign each two-hop chain the minimum of its
two atom counts, and leave `wimbd.dolma(e1,e2,e3)` unused because it is zero
on every chain. Head × two-hop stays below the 75-example floor (test n = 32),
so the confirmatory contrast is tail versus pooled middle+head within each hop.

**Evidence.** Qwen's sealed-test one-hop tail-versus-rest gap is −42.5 pp
(interval −44.5 to −40.6). The two-hop gap is +0.4 pp (interval −0.7 to +1.4).
The interaction is +42.8 pp (interval +40.6 to +45.0) on development,
calibration, and test alike: the frequency penalty is a one-hop fact, and
supported two-hop cells sit near 2% exact match. Mixtral's sealed-test
interaction is +2.1 pp (interval −0.3 to +4.3). Its one-hop accuracy is
71.7–79.5% across the three tertiles. Synthesis loss on supported test cells,
conditional on both atoms being correct, is 92.8–95.9% for Qwen and
97.9–98.5% for Mixtral.

**Not closed.** Head × two-hop, MuSiQue, a training-frequency claim, the
factorized residual inside each bin, a third family, and the SOCRATES human
audit.

Full synthesis: [`r1r5_socrates_sealed_test_findings.md`](r1r5_socrates_sealed_test_findings.md).
