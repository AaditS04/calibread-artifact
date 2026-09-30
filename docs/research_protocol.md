# CalibRead research protocol

Status: all-dimensions protocol freeze candidate, 11 August 2026.

This document is the authority for experiment design. Changes after the first real-model run must be recorded with a dated rationale.

## Paper question and system contract

**Question.** When an LLM is used as a database-like `Read`, how do its answer quality,
calibration, conformal-set behavior, and answer/set/abstain policy change across the seven P03
dimensions: knowledge frequency, precision, recency, ambiguity, synthesis depth, domain specificity,
and policy threshold?

All R1-R7 dimensions are first-class, confirmatory studies in the four-month paper. The design does
not attempt a seven-way Cartesian product. It uses controlled one-dimension sweeps under frozen
anchor conditions, then tests three predeclared interactions: **R1 x R5**, **R3 x R6**, and
**R4 x R7**. R7 is a deployment-policy axis rather than an intrinsic question property, but it is
fully evaluated on cached outputs through the complete risk/coverage and efficiency frontier.

A Read request declares a workload, a target error level `alpha`, and an allowed action. The wrapper returns exactly one of:

1. `answer`: one normalized answer is committed;
2. `set`: a finite candidate set is returned; or
3. `abstain`: the calibration support is inadequate or the policy rejects the risk.

A result record must preserve the raw generation, candidate construction process, score, group labels, calibration split identifier, wrapper decision, reference aliases, and correctness verdict. The score is not itself a probability unless a separately fitted calibrator makes that interpretation valid.

## Two evaluation tracks; two different meanings

### A. Finite-label certified track

The correct label is known to lie in a fixed label universe supplied independently of the model. Split conformal prediction may then form a prediction set. Under exchangeability of calibration and test examples and a fixed scoring rule, the advertised guarantee is **marginal coverage** over future examples. Mondrian/group conformal gives group-marginal coverage only for predeclared groups with adequate calibration support.

This is not a per-query correctness probability, conditional coverage for every subgroup, or a guarantee under arbitrary distribution shift. A finite-sample correction must be used, ties must be handled conservatively, and unsupported groups must abstain or use an explicitly reported fallback.

### B. Open-ended candidate stress track

For free-form QA, the candidate universe is generated and may omit the true answer. Results here diagnose ranking, calibration, selection, and candidate-generation failure. Report candidate-oracle recall before prediction-set coverage. Conformalizing scores over a post-hoc finite candidate list does not by itself provide distribution-free coverage. A generation-aware published procedure may be reported as certified only when its missing-mass treatment and every formal assumption are implemented and audited.

The two tracks must never be pooled into one “certified accuracy” number.

## Operational definitions for R1–R7

Each dimension is metadata, not an explanation of causality. Bins and exclusions are frozen using development data before test evaluation.

| ID | Operational variable | Required construction and scope |
|---|---|---|
| R1 | Knowledge frequency | `head`, `middle`, `tail`; anchor `middle`. Retain the named/versioned continuous exposure proxy. Never equate it with unobserved training frequency. |
| R2 | Precision requirement | `coarse`, `medium`, `fine`; anchor `medium`. Preserve raw typed granularity (for example year/month/day, significant digits, or numeric tolerance) and use deterministic type-specific scorers. |
| R3 | Knowledge recency | `pre_cutoff`, `post_0_3_months`, `post_4_12_months`, `post_13_plus_months`; anchor `pre_cutoff`. Bands are model-cutoff-relative; record source and uncertainty. |
| R4 | Query ambiguity | `unambiguous`, `two_way`, `three_plus`; anchor `unambiguous`. Derive levels from independently annotated valid interpretations/equivalence classes and freeze accepted labels. |
| R5 | Synthesis depth | `one_hop`, `two_hop`, `three_hop`, `four_plus_hop`; anchor `one_hop`. Audit minimal evidence chains and pair every multi-hop item with constituent probes. |
| R6 | Domain specificity | `general`, `specialized`, `expert`; anchor `general`. Use a frozen taxonomy plus a measurable proxy independent of model error. |
| R7 | Confidence/policy threshold | `tau_0_50` (0.50), `tau_0_70` (0.70), `tau_0_90` (0.90), `tau_0_95` (0.95), `tau_0_99` (0.99); anchor threshold 0.70, named `tau_0_70`. Apply post-hoc to fixed outputs and report the complete frontier. |

### Controlled sweeps, interactions, and shifted workloads

For R1-R6, change one focal dimension at a time while holding the canonical anchor profile fixed:
R1 `middle`, R2 `medium`, R3 `pre_cutoff`, R4 `unambiguous`, R5 `one_hop`, and R6 `general`.
R7's anchor threshold is 0.70 (`tau_0_70`). When an anchor is impossible or scientifically artificial, match
or stratify nuisance dimensions and record the exception before test evaluation. R7 reuses fixed
cached outputs and changes only the policy threshold. This gives an identifiable main-effect study
without a seven-way factorial.

The only confirmatory interactions are: R1 x R5 for long-tail composition; R3 x R6 for temporal
shift in specialist domains; and R4 x R7 for ambiguity-sensitive answer/abstention behavior. Other
crossings are exploratory and must be labelled as such.

Exact full-study targets after exclusions are 80 development, 120 calibration, and 200 test
examples per main-effect level, and 60 development, 90 calibration, and 150 test examples per cell
for the R1 x R5 and R3 x R6 dataset interactions. Pilot and breadth-tier levels target 20
development, 30 calibration, and 50 test examples. R4 x R7 reuses each R4 level across the fixed
threshold grid and therefore does not multiply the number of independent examples. A dimension may
collect a buffer for invalid or missing labels, but the selected split targets remain exact. The
Week 1 latency/cost probe and Week 2 development-only power simulation may change targets before
test access; no test-informed revision is allowed. The hard floor is 100 test examples per
main-effect level and 75 per dataset-interaction cell; lower-support results are descriptive rather
than confirmatory.

Evaluate without refitting: a level-balanced mixture for every focal sweep; a frozen
reference/deployment-like mixture; one stress reweighting toward the prespecified hard extreme of
each R1-R6 dimension; and jointly hard mixtures for R1 x R5, R3 x R6, and R4 x R7. R7 policies are
applied to each mixture from the same cached predictions.

Calibration and test examples must remain disjoint in every mixture. Mixture definitions, weights,
overlapping item identifiers, and effective sample sizes are reported.

## Falsifiable operational tests

The professor's original P03 H1-H5 retain their names and wording in the
[hypothesis registry](hypothesis_registry.md). The IDs below are operational test IDs, not replacement
hypothesis numbers.

- **OP-R1 -- frequency:** `tail` items have higher selective risk or calibration error than matched `head` items.
- **OP-R2 -- precision:** `fine` precision increases risk or abstention relative to `coarse` at a fixed reliability target.
- **OP-R3 -- recency:** the post-cutoff bands degrade relative to `pre_cutoff`, with cutoff uncertainty reported.
- **OP-R4 -- ambiguity:** `two_way` and `three_plus` items widen sets or increase abstention relative to `unambiguous` under a complete accepted-label policy.
- **OP-R5 -- synthesis:** deeper levels through `four_plus_hop` degrade reliability, including synthesis loss when all atomic constituents are correct.
- **OP-R6 -- domain:** `expert` queries degrade relative to matched `general` queries under the frozen domain proxy.
- **OP-R7 -- policy:** increasing the threshold from `tau_0_50` through `tau_0_99` reduces answer rate; whether risk falls and at what cost is measured rather than assumed.
- **OP-I15 -- R1 x R5:** frequency and synthesis depth have a non-additive effect on reliability.
- **OP-I36 -- R3 x R6:** temporal degradation is larger in specialist domains than in the general anchor.
- **OP-I47 -- R4 x R7:** the supported answer/set/abstain operating region differs by ambiguity level.
- **OP-CONTRACT:** a predeclared workload-aware wrapper improves worst-level/cell behavior relative to global calibration at a measurable set-size or abstention cost.

Each operational test has a frozen contrast, effect size, 95% interval, and multiplicity family.
Directional language is a testable expectation, not a promised result; null and reversed findings
remain in the paper. The registry defines when the evidence may support a narrowed version of each
original P03 hypothesis without claiming universal thresholds, automatic minimal sets, universal
optimality, or guarantees at untested alpha values.

## Data construction and leakage control

Use a closed-book, short-answer setting for the main study. Freeze model-independent R2/R4/R5/R6
properties once in the workload table. Store R1 exposure and R3 cutoff-relative recency in a
separate model-condition table keyed by question and immutable model snapshot; the joined analysis
view must contain all R1-R6 annotations even when only one is the focal sweep. Candidate
sources may include entity-frequency QA for R1, typed numeric/date records for R2, timestamped facts
for R3, independently annotated multi-answer items for R4, decomposed multi-hop QA for R5, and a
predeclared general-to-specialist domain collection for R6. R7 is derived from fixed predictions.
Separate source datasets do not identify interactions, so create audited matched sets for R1 x R5,
R3 x R6, and R4 x R7.

Each dimension has its own data card, provenance, exclusion rules, anchor/matching variables, level
counts, annotation agreement, and scorer tests. The combined benchmark manifest records dimension,
level, interaction cell, answer type, event date, ambiguity classes, evidence chain, domain label,
and all matching identifiers. No item is silently reused as independent evidence in two primary
contrasts; shared items are handled with clustered inference.

Create data in this order: normalize source records; attach provenance and licenses; derive constituent chains; audit answer aliases; assign entity, relation, template, source-fact, and normalized-question identifiers; validate lineage completeness; then split. No test result may influence alias editing or bins.

Before split assignment or dataset freeze, every row must supply a nonblank scalar or nonempty
scalar sequence for each declared disjoint key: entity_id, chain_id, template_id, source_fact_id,
and question_hash. A missing key is never treated as unique, safe, or skippable. When a key is
genuinely inapplicable, the row must contain a per-key lineage_exemptions entry with exactly a
frozen reason_code and substantive justification. Allowed reason codes are
not_applicable_by_construction and not_defined_by_source_schema. An exemption is invalid when the
row also supplies the key. question_hash is never exemptable and must equal the frozen SHA-256
hash of NFKC-normalized, case-folded, whitespace-collapsed question text.

The primary split uses transitive connected components across all five lineage keys. Near-duplicate
questions, shared entities/chains/templates, alternative ambiguity wordings, and records derived
from the same source fact stay in one partition. Split proportions are development 20%,
calibration 30%, test 50%, stratified by dimension level and confirmatory interaction cell. A
second random split may be reported only as a sensitivity analysis.

Leakage checks must first fail the run on any unexplained missing, blank, empty, malformed,
redundantly exempted, or nonexemptable lineage key, then fail on any protected identifier spanning
partitions. The explicitly named legacy permissive mode exists only to read historical sparse
fixtures and is forbidden for pilot or full-study freeze. Prompt development uses development only.
Calibration fits thresholds only. Test is opened once for the frozen primary analysis; later
analyses are labeled exploratory.

Correctness is deterministic exact/alias matching for the primary metric. Numeric/date questions use
frozen tolerance rules. A blinded human audit covers at least 50 items from each R1-R6 focal sweep
(300 unique items minimum), oversampling scorer disagreements. R4 interpretation/equivalence
classes are independently double-annotated before adjudication, with agreement reported. An LLM
judge, if used, is secondary and its agreement, prompt, model revision, and adjudication rules are
reported.

## Required baselines

All methods use identical cached generations and splits wherever their assumptions permit.

**Point confidence / abstention:** length-normalized sequence log probability; self-reported `P(True)` with a fixed elicitation prompt; modal semantic-cluster mass; semantic entropy; global isotonic calibration; and a multicalibration or subgroup recalibration baseline.

**Prediction sets:** uncalibrated top-k; global split conformal; one predeclared Mondrian/group
baseline for each supported R1-R6 partition; crossed-group baselines for R1 x R5, R3 x R6, and
R4 x R7 where calibration support permits; a conditional/multivalid conformal baseline; and an
importance-weighted conformal baseline for known mixture shift. Unsupported groups abstain or use a
separately reported fallback. Existing conformal language-model methods are baselines, not renamed
as CalibRead inventions.

Use exactly ten total model-family IDs. **Tier A** is the first three families and runs the complete
R1-R7 suite and three interactions, selected to vary training/data openness and model architecture
or provider. The frozen breadth profile runs on all ten: every R1-R3 level, the R4-R6 anchor/hard
pairs, common point-confidence baselines, and all five fixed R7 policies on cached outputs. For the
seven families outside Tier A, R4-R6 results are explicitly partial-dimension breadth evidence.
Breadth inference starts only after the Tier A data, calibration-support, and compute gates pass.
If the Week 1 benchmark cannot support exactly ten families, obtain a professor-approved protocol
amendment before inference; do not silently reduce the registered count. Decoding, prompts,
candidate budget, and sample count are fixed per track.

## Metrics and statistical analysis

Report every metric globally, by every R1-R6 level, across the R7 frontier, by each predeclared
interaction cell, and by workload mixture where defined. Report the first three families for the
full protocol and the all-ten breadth profile separately; do not let the partial R4-R6 anchor/hard
profile masquerade as full R1-R7 replication.

- answer accuracy, Brier score, log loss, fixed-bin ECE, adaptive calibration error, and correctness AUROC;
- selective risk at fixed answer rates, answer rate at fixed risk targets, and the full risk–coverage curve with AURC;
- finite-label empirical coverage at 90% and 95%, average/median/90th-percentile set size, singleton rate, empty-set rate, and abstention rate;
- open-ended candidate-oracle recall, followed separately by conditional coverage among oracle-recalled items and set efficiency;
- worst-cell result, max–min gap, and calibration/test effective sample size for weighted methods.

For every evidence chain, run the matched atomic constituent probes as well as the composed query. Report chain accuracy; the rate at which all atomic constituents are answered correctly; **synthesis loss**, defined as `P(chain wrong | every constituent answered correctly)`; and the **contract/composition gap** between observed chain correctness and a prespecified factorized/product diagnostic. Also evaluate a conservative union-bound propagation rule. The factorized and union-bound calculations are propagation baselines, not independence facts or new guarantees.

Use example-level or cluster-level bootstrap intervals with clustering by entity/evidence chain. Use
paired bootstrap differences because methods share examples. Coverage also receives an exact
binomial interval. Report effect sizes and intervals, not only p-values. Apply Holm correction within
the frozen R1-R7 main-effect family and within each of the three interaction families; mark all other
subgroup exploration as exploratory.

Completion does not mean “beats every method.” A dimension is complete when all frozen levels,
baselines, intervals, audits, and null/reversed findings are reported for all three Tier A families.
The paper-level gate requires (a) a complete R1-R7 evidence matrix, (b) all three interactions or a
predeclared infeasibility report that prevents confirmatory claims for the missing interaction, and
(c) a transparent evaluation of whether the Read contract changes worst-level reliability and at
what efficiency/abstention cost. No favorable outcome is required.

## Claims, nonclaims, and stop rules

Claims the design can support, if the evidence agrees:

- marginal reliability can hide rare/compositional subgroup failures;
- controlled R1-R7 sweeps reveal which reliability effects are obscured by one-number summaries;
- the predeclared R1 x R5, R3 x R6, and R4 x R7 tests reveal interaction effects when supported;
- workload-aware calibration can trade efficiency for better worst-cell behavior;
- the proposed record/certificate makes assumptions and unsupported regions explicit.

Claims this design does **not** support:

- that an output confidence is the probability that this particular answer is correct;
- exact knowledge of a model's proprietary training frequency;
- distribution-free coverage for our post-hoc open-ended candidate sets without a separately implemented generation-aware theorem;
- coverage after arbitrary shift, per-group guarantees for data-chosen groups, or automatic prediction-set minimality;
- a new conformal algorithm merely from applying existing split or Mondrian conformal prediction;
- causal conclusions from unmatched dataset comparisons or observational dimension proxies.

Stop and repair rather than make a confirmatory claim when candidate-oracle recall is below 90% in
a primary open-ended level/cell, any R1-R6 level or interaction cell misses its frozen sample floor,
an R4 accepted-answer policy lacks adequate annotation agreement, R3 cutoff provenance is
unresolved, contamination remains unresolved, correctness-audit error exceeds 5%, or a weighted
method's effective sample size falls below the declared threshold. Repair decisions use
development/calibration data only and are logged.

## Run manifest and artifact contract

Every run records model repository, immutable revision, and canonical snapshot ID; tokenizer
revision; dataset version, license, source URL, and manifest hash; raw prompt template; decoding
parameters and seeds; candidate constructor; scoring and correctness code versions; the canonical
model-condition-table hash; joined R1-R6 raw values, bins, proxy sources, R3 cutoff
source/uncertainty, R4 annotation policy, R5 chain provenance, R6 taxonomy version, and R7 policy
grid; split hash; calibration method and hyperparameters; hardware; runtime; token count; package
lockfile; and code revision. A generation is invalid unless its model snapshot and condition hash
link to the same workload and run manifest.

Cache raw model outputs before calibration. Keep derived scores reproducible from those outputs. Tables must be regenerated by one command from immutable result files. Release split manifests and derived annotations where source licenses permit; otherwise release scripts and hashes. Report failed runs and exclusions.

## Paper artifacts

The minimum submission package is: frozen protocol; one data/annotation card per dimension; the
complete R1-R7 coverage matrix; three interaction reports; model/run manifests; contamination and
correctness audits; primary tables and R7 curves; ablations for group definition, calibration size,
candidate budget, and shift severity; reproducible code; and a limitations/ethics statement. See
[the four-month plan](four_month_plan.md), [the dimension playbook](dimension_playbook.md),
[the P03 hypothesis registry](hypothesis_registry.md), [prior work](prior_work.md),
[venue strategy](venue_strategy.md), and
[the decision log](decision_log.md).
