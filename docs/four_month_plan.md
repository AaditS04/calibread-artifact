# Four-month execution plan

Window: **10 August–1 December 2026**. Primary deliverable: a reproducible submission-ready paper, not a promised acceptance. Peer-review timing and decisions are outside the project team's control.
This 16-week schedule is a proposed compression of the professor's P03 sequence and requires
explicit Week-1 professor sign-off before it becomes the frozen execution plan.

## Scope that fits the window

The project follows the professor's P03 plan and treats **R1-R7 as first-class confirmatory
studies**. The provisional paper is **CalibRead: Reliability Contracts for LLM Reads Across Seven
Database-Relevant Dimensions**. It uses six frozen one-dimension sweeps, a complete R7 policy
frontier, and three predeclared interactions--R1 x R5, R3 x R6, and R4 x R7--instead of a seven-way
factorial.

The model plan contains exactly ten total family slots. Tier A is the first three families and runs
the complete R1-R7 suite. Tier B is the breadth profile shared by all ten families: every R1, R2,
and R3 level; the frozen R4-R6 anchor/hard pairs; and all five fixed R7 policies on cached outputs.
For the seven families outside Tier A, R4-R6 are partial-dimension breadth evidence, not full-suite
replication. The Week 1 GPU/API benchmark must cost both tiers; breadth runs begin only after Tier A
data and pipeline gates pass. If exactly ten families are not affordable, obtain a professor-approved
protocol amendment before inference rather than silently changing the registered family count.

If local hardware permits, one Tier A candidate is
[OLMo-2-1124-7B-Instruct](https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct), whose open
artifacts make exposure analysis more auditable; confirm corpus access against the
[official OLMo release notes](https://docs.allenai.org/release_notes/olmo-release-notes). Select two
contrasting families after the cost probe. Keep finite-label guarantees separate from open-ended
candidate stress tests throughout all dimensions.

## Non-negotiable gates

- **End Week 2:** R1-R7 definitions, schemas, splits, scorer tests, sample/power plan, compute budget, and synthetic pipeline frozen.
- **End Week 4:** baseline R1-R3 pilot completes on one Tier A model; proxy quality, cutoff provenance, numeric/date scoring, oracle recall, and label quality pass.
- **End Week 6:** CPR/calibration implementation passes simulation tests and runs end to end on R1-R3 cached outputs.
- **End Week 8:** R1-R3 baselines plus calibration complete on all ten registered families; otherwise
  pause further inference and obtain a professor-approved amendment before changing the family count.
- **End Week 10:** R4-R7 data/annotation gates pass and all Tier A generations are cached.
- **End Week 12:** full R1-R7 matrix, three interactions, domain analysis, and R7 reliability/efficiency Pareto frontiers reproduce from immutable caches.
- **End Week 13:** primary analyses are frozen; no new confirmatory hypothesis or test-informed bin change.
- **25 November:** PVLDB abstract registered; **1 December:** primary full-paper submission target.

Any gate missed by more than one week triggers a resource cut in this order: extra datasets,
repeated prompt variants, optional stochastic samples, expensive uncertainty estimators, extra
ablations, then larger-than-frozen sample targets down to the protocol floors. Do **not** change the
registered ten-family count without a professor-approved amendment, or drop an R1-R7 dimension,
one of the three full-suite families, required baselines, leakage checks, correctness/ambiguity
audits, or uncertainty intervals merely to meet a deadline. A failed gate becomes a reported
limitation and may require the January PVLDB cycle.

## Provisional run envelope

Before deduplication, each full-study main-effect level has exact post-exclusion targets of 80
development, 120 calibration, and 200 test examples (400 total). Each independent R1 x R5 or
R3 x R6 interaction cell targets 60 development, 90 calibration, and 150 test examples (300 total).
Pilot and breadth-tier levels target 20/30/50 (100 total). Test hard floors remain 100 per main level
and 75 per interaction cell. The R4 x R7 threshold grid reuses the R4 examples and adds policy
evaluation, not independent model calls. Reuse elsewhere is allowed only when an item truly
satisfies both frozen constructions and clustered analysis accounts for dependence. Week 1 must
estimate tokens, wall time, storage, and money for: one deterministic generation; confidence-score
extraction; any stochastic uncertainty samples; and candidate construction. Freeze separate budgets
for three-family full-suite inference, additional seven-family breadth inference, reruns caused by infrastructure failure,
and human annotation. If the estimate exceeds resources, lower counts before collection to the
protocol floors and remove optional sampling-based scores first.

## Weekly schedule

| Week | Dates (2026) | Work and exit artifact |
|---|---|---|
| 1 | Aug 10–16 | Freeze R1-R7 definitions, anchors, hypotheses, interactions, Tier A/Tier B candidates, and guarantee language; run per-model latency/cost probes. **Exit:** signed protocol, dimension playbook, sample/power targets, and costed run matrix. |
| 2 | Aug 17–23 | Finish common schemas, immutable cache, dimension validators, typed correctness rules, group-disjoint splits, contamination checks, and all-dimension synthetic fixtures. **Exit:** one-command offline pipeline and data-card templates. |
| 3 | Aug 24–30 | Build and audit R1 frequency, R2 precision, and R3 recency pilot manifests under frozen anchors; integrate the first real-model adapter. **Exit:** versioned R1-R3 pilot and 100-item stratified audit. |
| 4 | Aug 31–Sep 6 | Run R1-R3 baseline pilot on Tier A model 1; test frequency proxy, temporal cutoff provenance, typed scorers, oracle recall, runtime, and contamination. **Exit:** baseline R1-R3 report and go/repair decision. |
| 5 | Sep 7–13 | Repair and freeze R1-R3 data; implement confidence baselines, global calibration, finite-label/open-ended track separation, and calibration diagnostics. **Exit:** R1-R3 data v1 and validated scorers. |
| 6 | Sep 14–20 | Implement/test CPR-related baselines: split, Mondrian/group, conditional/multicalibrated, and weighted conformal methods with unsupported-group abstention. **Exit:** simulation coverage checks and R1-R3 end-to-end CPR report. |
| 7 | Sep 21–27 | Cache full R1-R3 outputs for the first three families; fit only on calibration partitions; launch the same frozen R1-R3 breadth cells on the remaining seven. **Exit:** hashed first-three caches and compute ledger. |
| 8 | Sep 28–Oct 4 | Complete R1-R3 outputs and comparative analysis for all ten families; freeze intervals and shift tables. **Exit:** rerunnable professor Phase-1 evidence package and breadth continuation decision. |
| 9 | Oct 5–11 | Build/audit R4 ambiguity, R5 synthesis, and R6 domain manifests; freeze accepted-answer classes, constituent chains, and independent domain taxonomy; define the R7 policy grid. **Exit:** R4-R7 data v1 and audit packet. |
| 10 | Oct 12–18 | Cache R4-R6 outputs on all Tier A families and derive R7 decisions from fixed outputs; finish R1 x R5, R3 x R6, and R4 x R7 matched sets. **Exit:** complete Tier A output cache. |
| 11 | Oct 19–25 | Fit/evaluate all methods across R4-R7 and three interactions; compute global, worst-level, coverage, set-size, abstention, cost, and Pareto results. **Exit:** blinded full R1-R7 results package. |
| 12 | Oct 26–Nov 1 | Complete human audits and prespecified calibration-size, group-definition, candidate-budget, and shift-severity ablations; rerun from immutable caches. **Exit:** frozen full benchmark/domain/Pareto analysis v1. |
| 13 | Nov 2–8 | Draft complete method/results; red-team every R1-R7 claim, interaction, guarantee, leakage path, and venue fit with the professor. **Exit:** full internal draft and written submit/revise decision. |
| 14 | Nov 9–15 | Revise paper and artifact; submit to ICDE on Nov 11 only if the Week 13 package already passes every gate. **Exit:** camera-ready-quality second draft. |
| 15 | Nov 16–22 | Independent reproduction; finish dimension data cards, artifact/data statements, anonymization, license audit, and claim-to-evidence table. **Exit:** release candidate and reproducibility checklist. |
| 16 | Nov 23–29 | Register PVLDB abstract by Nov 25; final professor/coauthor review; proofread every claim against frozen evidence. **Exit:** submission bundle. |
| Delivery | Nov 30–Dec 1 | Upload and validate the PVLDB submission; archive code, configurations, manifests, outputs, tables, and hashes. |

## Weekly operating rhythm

Monday freezes the week's question; Tuesday–Thursday implements/runs; Friday regenerates artifacts and updates the paper; Saturday audits one failure mode; Sunday is buffer. Maintain a one-page lab log containing decisions, failed runs, cost, and next gate. Commit manuscript prose from Week 1 using the [paper outline](paper_outline.md); do not postpone writing to Month 4.

Professor checkpoints occur at the end of Weeks 1, 4, 8, 11, 13, and 16. Bring a decision packet—not raw logs—with the hypothesis, current evidence, uncertainty, failure cases, budget spent, and exact decision requested.

## Four-month definition of done

Done means the paper, code, frozen configurations, split manifests, cached-output hashes, data/model cards, audit report, primary/ablation results, and reproduction instructions agree with each other. “The model ran” is not a milestone; a rerunnable evidence artifact is.
