# CalibRead

> Public **conference artifact** (code + documentation). Experiment configs and run results are not in this repo; see [ARTIFACT.md](ARTIFACT.md).

CalibRead asks: **When can an LLM Read be trusted?** It studies a database-like **Read contract**
that returns an answer when a declared workload/reliability target is supportable and otherwise
returns a candidate set or abstains. The narrower question **Do calibrated LLM Reads compose?**
is the R5 synthesis-depth sub-question, not the slogan for the complete R1-R7 project.

The project deliberately builds on published conformal-language-modeling work. Existing methods are
treated as reproducible baselines. Following the professor's P03 plan, the four-month paper treats
**all seven dimensions (R1-R7) as first-class confirmatory studies**. Feasibility comes from frozen
one-dimension-at-a-time sweeps plus three predeclared interactions--R1 x R5, R3 x R6, and R4 x R7--
rather than an uninterpretable seven-way factorial. R7 remains a deployment-policy axis, but it is
evaluated completely on cached outputs through risk/coverage, answer-rate, set-size, and abstention
curves.

## Current milestone

This repository now contains the research scaffold and a runnable end-to-end R5
pipeline:

- calibration, discrimination, selective-risk, prediction-set, and risk-coverage metrics;
- finite-label split and predeclared-group conformal utilities;
- atomic-to-compositional diagnostics and uncertainty intervals;
- validated R1-R7 metadata, controlled-sweep planning, and policy-frontier schemas;
- typed example/prediction manifests, deterministic splits, JSONL I/O, hashing, and answer scoring;
- a versioned data-source registry with license/redistribution checks, source-specific downloaders,
  raw revision and SHA-256 capture, refinement, data cards, and audit samples;
- processed SOCRATES and MuSiQue R5 panels, including strict lineage-safe MuSiQue composites and
  independently answerable, deduplicated atomic probes;
- closed-book OpenRouter and loopback-only Ollama adapters with token log probabilities, model
  identity capture, budgets, append-only checkpoints, and hash-safe resume;
- chain-complete one-hop through four-plus-hop selection with frozen example, chain, and membership
  hashes;
- calibration-only weighted isotonic fitting, frozen calibration objects, held-out application,
  R7 answer/abstain decisions, probability-calibration reports, and chain-aware composition reports;
- a strict versioned Read certificate binding each decision to its records, calibration support,
  assumptions, policy, evidence hashes, and finalized run manifest;
- a CSV evaluator, pilot configuration, dependency-free unit tests, and frozen research documents.

The local Qwen3 4B development pilot failed its promotion gate (10.1% EM) and
remains execution-blocked. Two cluster conditions have since completed the full
sealed R5 pipeline (development → calibration → frozen calibrator → blind test →
unblind): **Qwen2.5 72B q4** (22.4% test EM) and **Mixtral 8×22B q4** (29.3%
test EM). Cross-condition interpretation, hypothesis gate status, and
composition/calibration findings:
[`docs/r5_cluster_sealed_test_findings.md`](docs/r5_cluster_sealed_test_findings.md).

Both R5 human audit samples are still `pending`; these runs are
engineering-complete but not publication-final.

The same two models have since completed a sealed R1 popularity-proxy run on
PopQA (development → calibration → frozen calibrator → blind test → unblind).
Qwen test exact match is 27.3% and Mixtral is 32.0%, with a tail-minus-head gap
of about −28 to −30 percentage points. Findings:
[`docs/r1_popqa_cluster_sealed_test_findings.md`](docs/r1_popqa_cluster_sealed_test_findings.md).
The PopQA human audit is still pending.

The same R5 answer cache has been crossed with development-frozen SOCRATES
Dolma-1.7 tertiles (OP-I15). Qwen's one-hop tail penalty is about −42
percentage points and disappears at two hops, where supported cells sit near
2% exact match. Mixtral's sealed-test interaction interval includes zero.
Findings:
[`docs/r1r5_socrates_sealed_test_findings.md`](docs/r1r5_socrates_sealed_test_findings.md).
Head × two-hop remains under the cell floor. CPR finite-label sets, the R1
change-point test, baseline policy comparisons, a third Tier A family, and the
remaining R2–R4/R6 condition freezes remain before the complete P03 paper.

## Four-month experiment shape

- R1-R6: controlled one-dimension sweeps under frozen anchor or matching conditions.
- R7: full answer/set/abstain policy frontier on the same cached outputs.
- Confirmatory interactions: R1 x R5, R3 x R6, and R4 x R7.
- Tier A: complete R1-R7 evaluation on three representative model families.
- Breadth profile: exactly ten total families; all R1-R3 levels, R4-R6 anchor/hard pairs, and all
  five fixed R7 policies. The first three families also run the complete R1-R7 suite.

The project does not use a seven-way factorial. All seven dimensions remain confirmatory; the
controlled design is what makes their effects estimable within four months.

## Run without installing dependencies

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m calibread.demo
```

The demo is a deterministic, configuration-driven R1-R7 software smoke artifact. It exercises
every configured R1-R6 level and all fixed R7 policies, and marks `research_evidence` as false;
synthetic coverage values must never be reported as research results.

`ReadCertificate` is the machine-readable handoff for one decision. Build it only from linked
typed records and a finalized manifest; see `src/calibread/certificate.py` and `tests/test_read_certificate.py`. Finite-label coverage remains
conditional on the explicitly recorded assumptions. Open-ended certificates always state that
generated candidates may omit the true answer and therefore carry no automatic coverage guarantee.

Evaluate a cached result file:

```powershell
$env:PYTHONPATH = "src"
python -m calibread.evaluate results.csv --group-column group --bins 10
```

For multiple dimensions and a predeclared crossing:

```powershell
python -m calibread.evaluate results.csv --group-column r1_frequency_level --group-column r5_synthesis_level --interaction r1_frequency_level,r5_synthesis_level --bins 10
```

The CSV must contain `example_id`, `correct`, `confidence`, `condition_hash`, and the requested
grouping columns. Every primary row must also declare the same nonempty `run_id`,
`model_snapshot_id`, `evaluation_track`, `condition_table_hash`, `calibration_object_hash`,
`score_kind`, and `score_source`. Per-example `condition_hash` values may differ. Probability rows
require one common `calibrator_id`; normalized raw-score rows require one common
`normalization_contract`. The evaluator rejects mixed runs, models, tracks, calibration objects,
score sources, calibrators, or normalizers instead of silently pooling or stratifying them. Report
metadata records the validated identities.

Raw scores receive ranking metrics only unless every row names a frozen
`normalization_contract`, in which case normalized values must lie in `[0,1]` before R7 is
evaluated. `--legacy-identity-input` may waive missing run/linkage fields for an audited old file,
but it never permits mixed scoring identities. `--legacy-probability-input` separately handles old
files lacking score semantics; a file lacking both contracts must request both flags explicitly.

## Start here

1. To execute the implemented R5 study, follow the
   [complete R5 runbook](src/calibread/inference/R5_COMPLETE_RUN.md). It contains the exact data,
   development, calibration, sealed-test, R7, composition, resume, and audit-gate commands.
2. Read the [research protocol](docs/research_protocol.md) for the frozen question, controlled
   R1-R7 sweeps, interactions, splits, baselines, metrics, and claim limits.
3. Use the [P03 hypothesis registry](docs/hypothesis_registry.md) to trace the professor's original
   H1-H5 to defensible tests, completion gates, and allowed claims.
4. Use the [dimension playbook](docs/dimension_playbook.md) to construct, validate, and audit each
   dimension consistently.
5. Execute the [Week 1 freeze checklist](docs/week1_checklist.md), then follow the
   [four-month plan](docs/four_month_plan.md) and its weekly exit gates.
6. Cost and populate the [experiment matrix](docs/experiment_matrix.md), then author a
   full-study configuration locally following `docs/research_protocol.md` (configs are not shipped in this artifact).
7. Use the [paper outline](docs/paper_outline.md) to write alongside implementation.
8. Check the [prior-work map](docs/prior_work.md) before making a novelty claim.
9. Review the [venue strategy](docs/venue_strategy.md) and append decisions to the
   [decision log](docs/decision_log.md).

## Experiment contract

Every real-model run should pin and record:

- model repository and immutable revision;
- dataset name, version, license, and split manifest hash;
- full prompt and answer-normalization rule;
- raw and binned R1-R6 metadata, proxy/taxonomy versions, and the frozen R7 policy grid;
- decoding method, temperature, seed, and number of samples;
- correctness evaluator and its version;
- calibration/test split identifiers;
- hardware, runtime, token count, and code revision.

Read [the research protocol](docs/research_protocol.md) before adding a model adapter. The protocol
defines what each R1–R7 dimension means and which claims the experiments may and may not make.

The finite-label track may evaluate marginal or predeclared group-marginal conformal coverage under
its assumptions. The open-ended candidate track must report candidate-oracle recall and does not
inherit that guarantee automatically. Never describe a score as a per-answer correctness
probability.

## Repository layout

```text
docs/                    protocol, prior work, and decisions
src/calibread/           evaluation and conformal implementation
tests/                   dependency-free unit tests
data/                    schemas, cards, and example records (no raw/processed dumps)
vldb2027-vision/         paper sources and PDF
scripts/                 cluster helpers (configs/results omitted from this artifact)
```
