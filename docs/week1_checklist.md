# Week 1: protocol and feasibility freeze

Dates: 10–16 August 2026. This checklist turns the first week of the professor's P03 plan into concrete, reviewable decisions. Do not run the main experiment until every freeze item has an owner and a recorded answer.

## 1. Professor checkpoint

Bring a one-page decision packet containing:

- the paper question and answer/set/abstain Read contract;
- confirmation that R1–R7 are all confirmatory, using six controlled sweeps and the cached-output R7 frontier;
- confirmation of the three interactions: R1 × R5, R3 × R6, and R4 × R7;
- the exact levels and anchors in `configs/full_study.toml`;
- Tier A (three complete families) and Tier B (ten-family anchor/extreme breadth) scope;
- finite-label versus open-ended guarantee language;
- the proposed primary venue and the resource-dependent fallback.

Record approval or requested amendments in `docs/decision_log.md`. A scope change is not frozen until the protocol, configuration, hypothesis registry, and experiment matrix agree.

## 2. Compute and model probe

For every candidate model, run the same small development-only fixture and record:

- immutable model/tokenizer revisions, license, access method, documented cutoff, and whether training-corpus exposure can be audited;
- deterministic and sampling-based latency, input/output tokens, peak memory, storage per cached record, and monetary cost where applicable;
- availability of token log probabilities or another reproducible confidence source;
- closed-book behavior (verify that retrieval and browsing are disabled);
- failure modes: refusals, malformed typed answers, context overflow, unavailable log probabilities, and nondeterminism.

Record the probe in `results/MODEL_PROBE_TEMPLATE.csv`. Extrapolate the measured cost to the run
envelope in `docs/experiment_matrix.md`, add a 20% infrastructure-rerun reserve, and freeze exactly
ten family IDs plus the first-three full-suite subset before main inference. Model popularity is not
a selection criterion; the three full-suite families must give a useful contrast in data openness,
architecture/provider, or calibration interface.

## 3. Dimension freeze audit

For each R1–R7 row, name one owner, primary source panel, raw variable, frozen label rule, anchor/matching variables, correctness rule, principal confounder, and stop condition. Use `docs/dimension_playbook.md` and `data/DATA_CARD_TEMPLATE.md`.

Required Week 1 evidence:

- R1: exposure measure or explicitly named proxy, corpus/snapshot, and frozen cutpoint procedure;
- R2: paired facts and deterministic coarse/medium/fine typed scoring;
- R3: model-specific cutoff source, uncertainty, as-of semantics, and date bands;
- R4: interpretation annotation guide, two-annotator plan, and accepted-answer policy;
- R5: derivation graph definition, constituent probes, and shortcut audit;
- R6: versioned taxonomy, specificity rule, and source-to-target transfer matrix;
- R7: confidence source, fixed thresholds, unsupported-group behavior, and policy costs.

## 4. Statistical and data feasibility

- Run a simulation-based power/precision analysis using plausible pilot error rates and record it in
  `results/POWER_PRECISION_TEMPLATE.csv`; report detectable paired effects and interval widths, not
  only a power percentage.
- Cost the target and hard-floor sample sizes separately.
- Verify that entity, chain, template, source fact, and normalized-question identifiers can support group-disjoint splitting.
- Verify licenses and redistribution rules in `data/SOURCE_LICENSE_TEMPLATE.csv` before
  downloading or annotating at scale.
- Decide how clustered inference handles examples reused across contrasts.
- Predeclare Holm families, bootstrap cluster unit, candidate-oracle-recall gate, and unsupported-cell rule.

## 5. Week 1 exit packet

The week is complete only when these artifacts agree:

- signed/frozen `docs/research_protocol.md` and `docs/hypothesis_registry.md`;
- validated `configs/full_study.toml` and `configs/pilot.toml`;
- costed `docs/experiment_matrix.md` with named models;
- one data card draft per dimension and a completed `data/SOURCE_LICENSE_TEMPLATE.csv`;
- completed model-probe and power/precision ledgers with measured and extrapolated cost;
- dated decisions and unresolved risks in `docs/decision_log.md`.

The immediate Week 2 input is a frozen design, not real test results. All probe examples remain development-only.
