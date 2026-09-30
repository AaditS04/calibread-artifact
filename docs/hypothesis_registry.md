# P03 hypothesis registry

Status: freeze candidate, 11 August 2026.

This registry preserves the professor's original P03 H1-H5 identities. The quoted sentences below
are verbatim from the CalibRead section of [the proposal](../Proposal.html). Their operational tests
are narrower because four-month experiments cannot establish universality, global optimality, or a
finite-label conformal guarantee for an open-ended candidate generator.

**Complete** means the frozen experiment, audits, models, metrics, and intervals were reported,
regardless of outcome. **Supports the operational claim** means the stated numerical gate was met.
Neither term silently proves every clause of the stronger original hypothesis.

## Original-to-operational crosswalk

| Original ID | Principal coverage | Registered operational test |
|---|---|---|
| P03-H1 Frequency Threshold | R1; R1 x R5 as modifier | OP-R1 and OP-I15 |
| P03-H2 Synthesis Compounding | R5; R1 x R5 | OP-R5 and OP-I15 |
| P03-H3 CPR Tightness | CPR across R1-R6; R7 set/abstain policy | OP-CPR, with finite-label and open-ended tracks separated |
| P03-H4 Domain Calibration Transfer | R6; R3 x R6 | OP-R6 and OP-I36 |
| P03-H5 Abstention Optimality | R7; R4 x R7 | OP-R7 and OP-I47 |

R2, R3, and R4 are required P03 dimensions but have no separate original numbered hypothesis.
They retain the operational IDs OP-R2, OP-R3, and OP-R4 below rather than being relabelled as the
professor's H numbers.

## P03-H1 -- Frequency Threshold

> **H1 (Frequency Threshold)** H(θ, Q_k) transitions from near-zero to near-one at a critical training frequency threshold f* that is universal across model families when normalized by model capacity.

- **Defensible operational test:** treat the named R1 exposure measure as a proxy, retain its
  continuous value, and freeze `head`, `middle`, and `tail` bins on development data. Fit the
  change-point rule on development/calibration only; compare its held-out log loss with a frozen
  smooth/no-change-point alternative. Test R1 x R5 separately rather than pooling hop depths.
- **Primary contrast/metric:** tail-minus-head hallucination/selective-risk difference with a paired
  95% interval; held-out change-point versus smooth-model log-loss difference; model-family
  threshold heterogeneity.
- **Complete gate:** all R1 levels meet sample floors on three Tier A families; continuous proxy,
  source date, bin edges, capacity normalization, fits, thresholds, and intervals are released.
- **Supports the operational claim when:** tail risk is higher with its paired 95% interval above
  zero and the frozen change-point model improves held-out log loss on every Tier A family.
- **Allowed claim:** the measured exposure proxy exhibits evidence of a nonlinear reliability
  transition in the tested models. Do not claim the model's true training frequency, a near-zero to
  near-one phase transition, or a universal capacity-normalized threshold from three families.

## P03-H2 -- Synthesis Compounding

> **H2 (Synthesis Compounding)** H for d-hop synthesis queries ≈ 1 − (1−H_1)^d where H_1 is the per-hop hallucination rate, confirming multiplicative error compounding — falsifiable via direct measurement vs. prediction.

- **Defensible operational test:** for every matched chain, measure the composed query and all
  atomic constituents at `one_hop`, `two_hop`, `three_hop`, and `four_plus_hop`. Compare observed
  chain risk with the proposal's factorized diagnostic and with a conservative union-bound baseline.
- **Primary contrast/metric:** residual
  `observed H_d - [1 - (1 - H_1)^d]`, synthesis loss conditional on all constituents being correct,
  and paired residual intervals, stratified by R1 for OP-I15.
- **Complete gate:** every R5 level and the R1 x R5 cells pass sample/audit floors on all Tier A
  families, constituent coverage is complete, and residual/union-bound results are reported.
- **Supports the operational claim when:** the 95% interval for the factorized residual lies inside
  the predeclared equivalence band of -0.05 to +0.05 for each tested depth on at least two Tier A
  families, without a contradictory pooled effect on the third.
- **Allowed claim:** the factorized expression is, or is not, an adequate empirical diagnostic on
  these matched chains. Agreement alone does not prove independent per-hop errors or a new coverage
  guarantee.

## P03-H3 -- CPR Tightness

> **H3 (CPR Tightness)** Conformal Parametric Read achieves coverage guarantee (1−α) with prediction sets of average size ≤ 3 on knowledge-intensive QA for α = 0.05, outperforming temperature-based uncertainty by >30% in efficiency.

- **Defensible operational test:** on the finite-label track at `alpha = 0.05`, compare the frozen
  CPR implementation with temperature-scaled scores using the same calibration/test records and
  candidate universe. Evaluate marginal and predeclared group-marginal results across every R1-R6
  level. On the open-ended track, report candidate-oracle recall first and do not transfer the
  finite-label guarantee.
- **Primary contrast/metric:** empirical coverage with exact binomial interval, mean/median/90th
  percentile set size, abstention, and relative mean-set-size reduction among methods evaluated at
  the same nominal target. R7 reports how set/abstain policy changes efficiency.
- **Complete gate:** finite label universe and exchangeability assumptions are audited; all Tier A
  levels meet calibration/test floors; unsupported groups abstain; open-ended oracle recall is
  separate; results at 95% nominal coverage reproduce from immutable caches.
- **Supports the operational claim when:** finite-label empirical coverage is at least 0.95, average
  set size is at most 3, and the paired 95% interval for relative mean-set-size reduction versus the
  frozen temperature baseline lies above 30% on the pooled primary workload. Group results and
  failures remain visible even if the pooled gate passes.
- **Allowed claim:** under the audited finite-label assumptions, CPR attained the nominal marginal
  target and the measured efficiency on this workload. Do not claim per-answer correctness,
  automatic minimal sets, coverage for generated open-ended candidates, or performance “for any
  alpha” from the single `alpha = 0.05` experiment.

## P03-H4 -- Domain Calibration Transfer

> **H4 (Domain Calibration Transfer)** Domain-specific calibration (fine-tuned on domain validation set) transfers within domains but not across: medical calibration does not reduce H for legal queries, enabling domain-partitioned reliability specifications.

- **Defensible operational test:** fit each calibrator on one domain's calibration partition and
  evaluate it without refitting on held-out records from the same domain and from predeclared other
  domains. Repeat both transfer directions and stratify the R3 x R6 interaction. Calibration alone
  is evaluated with ECE/Brier; any hallucination-risk change is attributed to a frozen R7 selection
  policy, not to score calibration by itself.
- **Primary contrast/metric:** within-domain minus cross-domain improvement in ECE and Brier, plus
  paired selective-risk difference at the same answer rate. Report coverage, set size, and effective
  calibration support when conformal wrappers are used.
- **Complete gate:** `general`, `specialized`, and `expert` levels, at least two predeclared directed
  domain pairs, all four R3 bands, and three Tier A families meet sample and provenance gates; no
  target-domain test labels are used for fitting.
- **Supports the operational claim when:** within-domain calibration improves the primary
  calibration metric with its paired 95% interval excluding zero, while cross-domain improvement
  remains within the predeclared -0.02 to +0.02 absolute equivalence band on at least two Tier A
  families.
- **Allowed claim:** calibration transfer was stronger within than across the tested domain pairs,
  supporting domain-partitioned contracts for those models and taxonomies. Do not generalize to all
  medical/legal data or infer domain distance causally from model error.

## P03-H5 -- Abstention Optimality

> **H5 (Abstention Optimality)** There exists a threshold-based abstention policy derived from CPR that achieves optimal precision-recall tradeoff on the H–R Pareto frontier, certifiably dominating temperature sampling and verbalized uncertainty approaches.

- **Defensible operational test:** derive decisions from the same cached outputs at the fixed R7
  levels `tau_0_50`, `tau_0_70`, `tau_0_90`, `tau_0_95`, and `tau_0_99`. Compare CPR,
  temperature-based, and verbalized-uncertainty policies at matched answer rates; test R4 x R7
  separately because ambiguity can change the useful operating region.
- **Primary contrast/metric:** full risk-coverage curve and AURC; selective risk at frozen answer
  rates; answer rate at frozen risk targets; prediction-set size and abstention; paired method
  differences with 95% intervals.
- **Complete gate:** all five thresholds are evaluated on every R4 level and all R1-R6 strata using
  identical cached generations on three Tier A families; every frontier includes uncertainty and
  no unsupported group is silently pooled.
- **Supports the operational claim when:** CPR has lower AURC with the paired 95% interval below
  zero versus both baselines and is no worse at every predeclared matched-answer-rate point, with a
  strict improvement at least one point, on at least two Tier A families without a contradictory
  pooled effect on the third.
- **Allowed claim:** CPR empirically Pareto-dominated the named baselines on the tested finite grid
  and workloads. Do not call it globally optimal or “certifiably dominating” all policies; an
  evaluated grid cannot establish either statement.

## OP-CPR -- Coverage and efficiency contract

- **Frozen estimand:** on the finite-label track, the empirical coverage gap from the nominal
  target and mean/median/p90 prediction-set size for CPR versus the frozen baselines, using exact
  Clopper-Pearson coverage intervals and paired lineage-clustered differences. On the open-ended
  track, candidate-oracle recall is reported first and never merged into a coverage guarantee.
- **Complete gate:** every R1-R6 level has the registered calibration/test support or is explicitly
  unsupported; the fixed candidate universe, alpha, score, calibration snapshot, and group fallback
  are immutable; all efficiency and coverage outputs reproduce from cached records.
- **Allowed claim:** finite-label coverage and efficiency under the audited assumptions and tested
  workload. Do not claim conditional per-query coverage, automatic transfer to generated candidate
  sets, or tightness outside the registered comparator and alpha.

## OP-CONTRACT -- Answer/set/abstain decision contract

- **Frozen estimand:** risk, answer/set/abstain rates, set size, and utility under each predeclared
  cost setting, including unsupported-group decisions. Compare methods on identical cached outputs
  at the five fixed R7 policies with paired lineage-clustered intervals.
- **Complete gate:** the action mapping, cost functions, fixed R7 grid, unsupported-group behavior,
  and workload mixtures are frozen before test access; every action and reason code is retained.
- **Allowed claim:** an empirical fixed-grid contract comparison on the tested workload. A lower
  AURC or higher registered utility does not establish global policy optimality or deployment
  safety outside the declared workload and costs.

## Operational dimension and interaction IDs

These tests complete the seven-dimension plan without overwriting P03-H1-H5:

| ID | Frozen levels or cells | Primary contrast |
|---|---|---|
| OP-R1 | `head`, `middle`, `tail` | tail minus head risk/calibration |
| OP-R2 | `coarse`, `medium`, `fine` | fine minus coarse typed-error risk; preserve raw date/digit/tolerance granularity |
| OP-R3 | `pre_cutoff`, `post_0_3_months`, `post_4_12_months`, `post_13_plus_months` | each post-cutoff band minus pre-cutoff risk/calibration |
| OP-R4 | `unambiguous`, `two_way`, `three_plus` | ambiguity-level risk, set-size, and consistency differences |
| OP-R5 | `one_hop`, `two_hop`, `three_hop`, `four_plus_hop` | depth trend, synthesis loss, and factorized residual |
| OP-R6 | `general`, `specialized`, `expert` | expert minus general risk/calibration |
| OP-R7 | `tau_0_50`, `tau_0_70`, `tau_0_90`, `tau_0_95`, `tau_0_99` | risk/coverage, answer rate, set size, abstention, and AURC |
| OP-I15 | R1 x R5 | non-additive long-tail synthesis effect |
| OP-I36 | R3 x R6 | recency effect difference by domain specificity |
| OP-I47 | R4 x R7 | ambiguity-dependent policy-frontier difference |
| OP-CPR | finite-label R1-R6 coverage; open-ended oracle recall separate | finite-label coverage gap and efficiency with open-ended oracle recall separate |
| OP-CONTRACT | R7 answer, set, abstain, and unsupported actions | risk and action utility under answer, set, abstain, and unsupported decisions |

The canonical machine-readable values live in
[`configs/full_study.toml`](../configs/full_study.toml). A level-name change requires a versioned
config update, protocol amendment, and decision-log entry before real-model inference.
