# P03 all-dimensions experiment matrix

Status: proposed 16-week compression and freeze candidate, 11 August 2026, pending explicit Week-1
professor sign-off. This file converts the professor's R1–R7 proposal into an executable four-month
matrix. Every dimension is confirmatory. The design uses controlled sweeps because the complete
3 x 3 x 4 x 3 x 4 x 3 R1-R6 factorial has 1,296 query cells before policy evaluation; R7 reuses
cached outputs rather than creating five more independent query panels.

## Shared anchor workload

The shared anchor profile is R1 `middle`, R2 `medium` under a frozen typed exact or
declared-tolerance scorer, R3
`pre_cutoff`, R4 `unambiguous`, R5 `one_hop`, and R6 `general`; the R7 anchor policy is
`tau_0_70`. The query is closed-book and short-answer, but its answer type follows the focal panel
rather than being forced to categorical scoring. The R2 sweep changes requested date/numeric
precision and its registered scorer constraints while holding the underlying fact fixed. Any other
dimension sweep changes only its declared variable where matching is possible. Relation family,
answer type, prompt template, token budget,
decoding, and model revision remain fixed or stratified and reported.

R7 is fully evaluated but is not a new question generator: thresholds are swept on immutable
outputs from every R1–R6 cell.

## Confirmatory cells

| ID | Levels in the main sweep | Frozen controls | Primary contrast |
|---|---|---|---|
| R1 frequency | head, middle, tail | stable one-hop facts; matched relation and answer type | tail minus head reliability |
| R2 precision | coarse, medium, fine | same underlying quantity/entity where possible | change per precision step |
| R3 recency | pre-cutoff, 0–3, 4–12, 13+ months post-cutoff | matched event/domain and documented cutoff | reliability decay from pre-cutoff |
| R4 ambiguity | unambiguous, two-way, three-plus | same lexical family and complete answer policy | confident commitment under ambiguity |
| R5 synthesis | one, two, three, four-plus hops | paired atomic constituents and matched frequency | synthesis loss beyond atomic errors |
| R6 domain | general, specialized, expert | matched answer form and approximate frequency | within-domain and cross-domain calibration |
| R7 threshold | 0.50, 0.70, 0.90, 0.95, 0.99 | same cached outputs and calibrated score | risk, answer rate, set size, abstention |

The 20/30/50 split is implemented as exact post-exclusion selection targets, not as a second,
conflicting set of proportions. Each full-study marginal level targets 80 development, 120
calibration, and 200 test examples (400 total). Each full-study interaction cell targets 60
development, 90 calibration, and 150 test examples (300 total). Pilot cells and breadth-tier levels
target 20 development, 30 calibration, and 50 test examples (100 total). The test hard floors are
100 per full-study marginal level and 75 per full-study interaction cell. Counts may increase after
a development-only power and cost analysis, but may not decrease after test access without a logged
protocol deviation.

Split assignment operates on connected components induced jointly by entity, chain, template,
source-fact, and question-hash identifiers. Dimension levels are marginal stratification fields;
they are not leakage-group identifiers. The precomputed R1 × R5 and R3 × R6 interaction-cell labels
are also strata so balancing the marginals cannot hide a crossed-cell imbalance; R4 × R7 reuses R4
questions and therefore adds no query-cell stratum. No connected component may cross development,
calibration, and test. Each declared lineage key must be present on every row unless that specific
key has a validated lineage_exemptions reason and justification. Missing values are not silently
treated as safe singletons; question_hash is always required and recomputed.

## Predeclared interactions

Only three interactions are confirmatory:

1. **R1 × R5:** whether rare atomic knowledge compounds differently under multi-hop synthesis.
2. **R3 × R6:** whether recency-induced shift is larger in specialized and expert domains.
3. **R4 × R7:** whether stricter commitment thresholds actually protect against ambiguity or merely
   reduce answer rate.

Other interactions are exploratory and receive that label in every table. Each interaction needs
matched marginal cells; it cannot be inferred by comparing unrelated datasets.

## Tiered model matrix

The professor's ten-family breadth goal and the four-month deadline are reconciled as follows:

- **Full tier:** exactly three family IDs, drawn from the ten total family slots, run every R1–R7
  level, both evaluation tracks, all primary baselines, and the three interactions.
- **Breadth tier:** all ten families run every R1, R2, and R3 level, preserving the professor's
  Phase-1 breadth study. For R4–R6, the seven families outside the full tier run the predeclared
  anchor/hard pairs: unambiguous/three-plus, one-hop/four-plus-hop, and general/expert. All ten
  families are evaluated at all five fixed R7 thresholds because R7 reuses cached outputs.
- **Escalation tier:** expensive semantic sampling, conditional conformal methods, and repeated
  ablations run on the full tier first and expand only after the Week 8 compute gate.

Model names and immutable revisions are frozen after a 100-example latency, memory, and cost probe.
At least one full-tier model should expose its training-data artifacts so R1 can be more than a
popularity proxy. Model size and instruction tuning are recorded rather than silently mixed with
family effects.

## Run ledger

Before launching inference, calculate questions times models times stochastic samples times prompt
variants. Record estimated and actual GPU-hours, API cost, input/output tokens, failures, and cache
hashes.

The first scope cut is repeated prompt variants, followed by extra stochastic samples and optional
baselines. No cut may remove a dimension, leakage audit, correctness audit, or the three full-tier
model families without an explicit professor-approved protocol amendment.

## Required outputs

Produce one global table, one table per R dimension, three interaction tables, risk–coverage/Pareto
curves for R7, finite-label coverage/efficiency tables, open-ended candidate-oracle tables, and a
cost table. Primary results are keyed to OP-R1 through OP-R7, OP-I15, OP-I36, OP-I47, OP-CPR, and
OP-CONTRACT in the hypothesis registry; accuracy, Brier score, log loss, ECE, ACE, AURC, coverage,
set size, and answer rate are secondary metrics unless named inside an operational estimand. Every
table includes sample size, uncertainty interval, model revision, calibration snapshot, and whether
the analysis was confirmatory or exploratory.

## Provisional base-query budget

The six generated dimensions contain 20 marginal levels. The full-tier marginal allocation is
3 families × 20 levels × 400 questions = 24,000 model-question pairs. The generated interactions
contain 12 R1 × R5 cells plus 12 R3 × R6 cells, so their allocation is
3 × 24 × 300 = 21,600 pairs. R4 × R7 adds no base inference because it sweeps thresholds over the
already cached R4 outputs.

For the seven additional families, the breadth schedule contains all 10 R1–R3 levels plus six
predeclared R4–R6 anchor/hard levels. Its allocation is therefore
7 × 16 × 100 = 11,200 pairs. The pre-overlap base planning budget is
24,000 + 21,600 + 11,200 = 56,800 model-question pairs. Shared anchor/marginal queries may reduce
that figure; extra collection needed to fill targets after connected-component assignment is
tracked separately rather than hidden in the arithmetic.

R7 reuses these outputs. Semantic entropy or self-consistency multiplies only the prespecified
sampling subset, not automatically every pair. The Week 1 probe converts this ledger into GPU-hours
and cost before model names or sampling counts are frozen.
