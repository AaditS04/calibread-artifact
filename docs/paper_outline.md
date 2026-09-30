# Paper outline

## Working identity

**Title:** *CalibRead: Reliability Contracts for LLM Reads Across Seven Database-Relevant Dimensions [Experiment, Analysis & Benchmark]*

**One-sentence claim:** Aggregate LLM reliability can conceal dimension-specific failure surfaces
across frequency, precision, recency, ambiguity, synthesis, and domain, while explicit R7
answer/set/abstain policies expose the resulting reliability-efficiency trade-offs.

This sentence is provisional until the primary tables exist. Replace “can reduce” with the measured result or a boundary/null statement; never write the conclusion in advance of evidence.

## Contributions

1. A controlled benchmark of all seven P03 dimensions: six frozen main-effect sweeps, a complete R7 policy frontier, and leakage-resistant splits with dimension-specific annotation contracts.
2. Three predeclared interaction studies--R1 x R5 long-tail composition, R3 x R6 specialist temporal shift, and R4 x R7 ambiguity-sensitive policy--without claiming a seven-way factorial.
3. An executable Read contract that binds target reliability to a declared workload/calibration snapshot and returns answer, finite set, or abstention with explicit unsupported-group semantics.
4. A tiered evaluation over exactly ten total model families: complete R1-R7 evidence on the first
   three, and a frozen breadth profile on all ten containing every R1-R3 level, R4-R6 anchor/hard
   pairs, and all five fixed R7 policies.
5. A reproducible comparison of point, global conformal, group-aware, conditional/multicalibrated, and shift-aware baselines, preserving the distinction between finite-label guarantees and open-ended candidate stress tests.

## Figure plan

- **Figure 1 -- Contract and study map:** request metadata R1-R6 -> candidate/scoring -> calibration -> R7 answer/set/abstain, with guarantee assumptions attached only to the finite-label branch.
- **Figure 2 -- Seven-dimension reliability atlas:** aligned small multiples for each R1-R6 level and the R7 frontier, showing accuracy/risk, calibration, coverage, and support.
- **Figure 3 -- Predeclared interactions:** R1 x R5 composition, R3 x R6 temporal-domain shift, and R4 x R7 ambiguity-policy surfaces with uncertainty and cell counts.
- **Figure 4 -- Reliability-efficiency Pareto frontiers:** answer rate/risk and coverage/set-size/abstention by model and method; unsupported regions are visible.
- **Figure 5 -- Model replication and breadth:** complete effects on the first three of exactly ten
  total families beside the frozen all-ten breadth profile: all R1-R3 levels, R4-R6 anchor/hard
  pairs, and all five fixed R7 policies. Distinguish full-suite replication from partial-dimension
  breadth evidence.
- **Figure 6 -- Support/cost:** calibration count or effective sample size versus worst-level gap, set size, abstention, latency, and tokens.

Each figure has a single question in its caption and displays uncertainty intervals or cell sample sizes.

## Table plan

- **Table 1:** R1-R7 operational definitions, level counts, anchors/matches, provenance, annotation agreement, leakage checks, and licenses.
- **Table 2 (primary):** Tier A main-effect contrasts for R1-R6 and R7 fixed operating points, with paired intervals and multiplicity-adjusted results.
- **Table 3 (primary):** nominal versus empirical finite-label coverage, worst-level coverage, set efficiency, abstention, and separately reported open-ended oracle recall.
- **Table 4:** R1 x R5, R3 x R6, and R4 x R7 interaction estimates; include composition propagation diagnostics for R1 x R5.
- **Table 5:** complete R7 Pareto operating points and shifted-mixture results, including weighted-method effective sample sizes.
- **Table 6:** exactly ten-family breadth results for all R1-R3 levels, R4-R6 anchor/hard pairs,
  and all five fixed R7 policies; clearly label the seven non-full-tier families' R4-R6 results as
  partial-dimension evidence.
- **Table 7:** ablations and resource cost: calibration size, group granularity, candidate budget, samples, latency, tokens, and annotation time.

## Section skeleton

1. **Introduction:** database Read motivation; why a one-number reliability report is inadequate; the seven P03 axes; contributions and boundaries.
2. **Background and related work:** probabilistic query answers/composition; hybrid LLM-database querying; conformal assumptions; LLM calibration/factuality; long-tail, temporal, ambiguity, precision, multi-hop, and domain evaluation.
3. **Read contract:** input/output semantics, workload declaration, finite-label versus open-ended tracks, unsupported-group behavior, and propagation baselines.
4. **CalibRead workload:** R1-R6 construction and anchors, R7 policy grid, three interaction sets, provenance, splits, contamination, correctness, and annotation audits.
5. **Methods and baselines:** uncertainty scores, calibrators, conformal/group/shift wrappers, policies, implementation and compute.
6. **Experimental protocol:** Tier A/Tier B models, prompts, the preserved P03-H1-H5 registry,
   OP-R1 through OP-R7 and OP-I15/OP-I36/OP-I47 tests, sample floors, metrics, multiplicity plan,
   and frozen gates.
7. **R1-R7 main effects:** one subsection per dimension, always question -> contrast -> interval -> null/reversed evidence -> limitation.
8. **Interactions and contract policy:** R1 x R5, R3 x R6, R4 x R7, shifted mixtures, R7 Pareto frontiers, and unsupported-group decisions.
9. **Ablations, breadth, and cost:** support size, candidate recall, group granularity, weighting stability, Tier B transfer, and serving/annotation overhead.
10. **Discussion and limitations:** guarantee scope; frequency/domain proxies; cutoff uncertainty; ambiguity completeness; candidate omission; judge/alias error; contamination; generalization; and data-management implications.
11. **Conclusion:** measured answer for all seven dimensions without expanding beyond the frozen evidence.

## Writing rules

Maintain a claim-to-evidence table while drafting: claim, hypothesis, figure/table cell, interval, assumptions, counterexample, and owner. Every use of “guarantee,” “conditional,” “robust,” “significant,” “first,” or “optimal” requires an explicit check. Keep failed hypotheses in the paper when they clarify a boundary. The abstract is written last from frozen results.
