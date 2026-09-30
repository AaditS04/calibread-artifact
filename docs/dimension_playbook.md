# CalibRead P03 dimension playbook

Protocol snapshot: 11 August 2026. This is a proposed 16-week compression of the professor's P03
sequence, pending explicit Week-1 professor sign-off. All R1-R7 dimensions remain first-class.

## Experimental scope

Every R1-R7 dimension is a first-class experiment. R1-R6 describe the query or workload, while R7 describes the policy applied to cached outputs.

We will not estimate an underpowered seven-way Cartesian product. The design has three layers:

1. Vary each R1-R6 dimension while matching or blocking the others, and compute the full R7 curve in every condition.
2. Freeze three confirmatory interactions: R1 x R5, R3 x R6, and R4 x R7. Any higher-order interaction is explicitly exploratory.
3. Calibrate on one frozen workload mixture and test both that mixture and held-out mixtures. Never recalibrate on test labels.

This covers all dimensions while avoiding the 3 x 3 x 4 x 3 x 4 x 3 = **1,296-cell** R1-R6
factorial. R7 reuses those outputs at five policies; it does not create independent query cells.
Every claim must name the controlled panel from which it came.

## Common Read contract and lineage

For query q, record the typed gold object Y(q), response y, score s, R1-R6 values, and one R7 action:

```text
Read(q, tau, manifest) -> ANSWER(y) / SET({y_i}) / ABSTAIN(reason)
```

The immutable manifest identifies model revision, prompt, decoding, documented cutoff, dataset and knowledge-base snapshots, correctness function, candidate generator, calibration split, and calibration-object hash. Each example retains source, entity, template, chain, and constituent identifiers. This is database lineage for reproducing a Read decision, not merely its displayed answer.

Use entity-, template-, chain-, and source-document-disjoint development/calibration/test splits. Freeze correctness rules before viewing test outputs. Fit temperatures, isotonic maps, multicalibrators, conformal quantiles, group definitions, and thresholds using development/calibration data only.

Across all panels report typed correctness, Brier score, log loss, ECE, ACE, error-ranking AUROC,
risk-coverage and AURC, action rates, prediction-set coverage, mean/median/p90 set size, and global
plus worst-predeclared-group results. Use paired bootstrap differences clustered by lineage family,
Holm-adjust planned comparison families, and use exact Clopper-Pearson intervals for binomial
coverage. A nominal conformal level is a marginal finite-sample statement under declared
exchangeability assumptions, not per-answer confidence.

## R1 - Knowledge frequency

**Operational variable.** Primary: log fact-support document count in the model's actual pretraining corpus. Record subject count, object count, co-occurrence count, and relation-support count separately. Assign the frozen confirmatory levels `head`, `middle`, and `tail` from preregistered corpus quantiles, with `middle` as anchor. Keep the continuous count and zero-support cases as diagnostics; zero support is not a fourth confirmatory level. Wikipedia page views, knowledge-graph degree, or entity count are labelled popularity proxies, never training frequency.

**Datasets.** Build the primary panel against [Dolma](https://aclanthology.org/2024.acl-long.840/) and an OLMo-family model whose training data are inspectable. Use [ComparisonQA-Hard](https://aclanthology.org/2025.findings-acl.212/) for matched high/low-frequency prompts. Use [PopQA](https://aclanthology.org/2023.acl-long.546/) and [Head-to-Tail](https://aclanthology.org/2024.naacl-long.18/) only as external popularity-based panels.

**Construction and controls.** Freeze a Wikidata snapshot and select facts valid before the training-data snapshot. Count support in the exact deduplicated corpus using normalized subject/object aliases plus relation cues, then manually audit a stratified sample. Match relation, object type, answer length, prompt template, temporal stability, domain, and R2/R5 level across bins. Split by entity family, not row.

Main confounders are popularity versus exposure, alias coverage, relation difficulty, web duplication, instruction-tuning data, benchmark contamination, and unobserved corpora for closed models. Run closed models as external replication only; never attach exact-frequency claims to them.

**Correctness and baselines.** Score normalized entity IDs plus audited aliases. Compare token likelihood, P(True), sample repetition/semantic entropy, temperature and isotonic calibration, global conformal, R1-Mondrian conformal, and multicalibration. Report accuracy and calibration against continuous log count as well as bins.

**Claim boundary.** [Kandpal et al.](https://proceedings.mlr.press/v202/kandpal23a.html) establish a relationship between QA performance and pretraining support, but neither that work nor a four-month observational panel establishes the proposal's universal capacity-normalized critical threshold. We may estimate model-specific change points with uncertainty; universality needs controlled training runs across corpora and scales.

**Database interpretation.** R1 is workload skew and statistics quality: a global contract can hide tail-key failures just as aggregate query statistics hide rare-key behavior.

## R2 - Precision requirement

**Operational variable.** Vary requested answer granularity while holding the underlying fact fixed. Assign the frozen confirmatory levels `coarse`, `medium`, and `fine`, with `medium` as anchor. Retain typed raw granularity (`year`, `month`, or `day` for dates; requested significant digits and numeric tolerance for quantities), units, uncertainty bounds, and rounding rules. Freeze the raw-to-level mapping in the data card. This is answer precision, not the numerical precision of model weights or arithmetic.

**Datasets.** Construct the paired core from Wikidata time and quantity values; its official [data-type documentation](https://www.wikidata.org/wiki/Help:Data_type) stores time precision and quantity uncertainty. [Wiki-Measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC12284226/) supplies a secondary quantity/context panel. [NumericBench](https://aclanthology.org/2025.findings-acl.1026/) and [DROP](https://aclanthology.org/N19-1246/) are external numeracy/reasoning checks, not substitutes for factual-precision control.

**Construction and controls.** Keep only referenced values whose stored precision supports every derived prompt. Generate paired prompts from one fact, then derive each coarser gold value deterministically. Balance magnitude, digit length, unit, date era, entity frequency, relation, and domain. Audit source disagreement and never invent day-level truth from year-only evidence.

Parse responses into typed dates or quantities. Numeric closeness and written precision are separate
checks: a quantity must first lie within the frozen unit-normalized tolerance, then meet the requested
significant-digit floor. A predeclared maximum significant-digit ceiling flags unsupported extra
digits as false precision even when the numerical value is close. A date must match at the requested
granularity. Preserve decimal-place rules for scale-sensitive fields; do not silently substitute them
for significant digits.

Confounders include tokenization, unit conversion, arithmetic, formatting, source revisions, and the possibility that exact and rounded strings have different corpus frequencies.

**Baselines.** Add an oracle fact plus deterministic formatter to isolate formatting loss; unconstrained and typed/constrained decoding; likelihood, P(True), sampling uncertainty; pooled and R2-group calibration/conformalization. Report exact, tolerance-aware, and false-precision rates.

**Claim boundary.** Do not assume monotonic hallucination: a finer prompt can expose missing detail, while a coarser string may be less frequent in training. [Feng et al.](https://aclanthology.org/2025.findings-acl.3/) study arithmetic under finite internal numerical precision, an adjacent but different variable. CalibRead can claim a requested-granularity curve only under its typed scorer.

**Database interpretation.** R2 is schema/type semantics: DECIMAL scale, measurement bounds, and timestamp granularity are part of answer correctness, not cosmetic formatting.

## R3 - Knowledge recency

**Operational variable.** Let delta be signed continuous months between a fact's validity/start
timestamp and the model's documented knowledge cutoff. The exact gap-free boundaries are:
`pre_cutoff` for delta <= 0; `post_0_3_months` for 0 < delta <= 3;
`post_4_12_months` for 3 < delta <= 12; and `post_13_plus_months` for delta > 12.
The labels 4-12 and 13+ are calendar shorthand, not integer-rounding instructions. The anchor is
`pre_cutoff`. Retain signed months and finer pre-cutoff age as raw diagnostics. Every question
includes an explicit as-of date and every gold answer has a validity interval.

**Datasets.** Use time-stamped questions from [StreamingQA](https://proceedings.mlr.press/v162/liska22a.html) for the primary dated panel, adapted to a closed-book Read track. Use [SituatedQA](https://aclanthology.org/2021.emnlp-main.586/), [RealTime QA](https://papers.neurips.cc/paper_files/paper/2023/hash/9941624ef7f867a502732b5154d30cb7-Abstract-Datasets_and_Benchmarks.html), and [FreshQA](https://aclanthology.org/2024.findings-acl.813/) as external checks. TempLAMA/LAMA-TK test temporally scoped facts rather than simple freshness.

**Construction and controls.** Prefer models with public data snapshots; treat vendor cutoffs as approximate. Freeze dated source evidence and answer histories. Match event type, update frequency, entity popularity, domain, and prompt form. Include immutable facts as a negative control. Separate closed-book parametric Read from a retrieval-augmented diagnostic.

Score the answer valid at the query's as-of date. Label wrong outputs as stale prior answer, future leakage, fabrication, or other error; report correct abstention separately. Main confounders are pre-release information, repeated/current-event popularity, uncertain cutoff, later instruction tuning, answer transitions, and accidentally enabled retrieval.

**Baselines.** Compare static most-likely answer, last-known pre-cutoff answer, raw uncertainty methods, a recency-only abstention rule, pooled versus temporal-group conformal, and an evidence-retrieval oracle reported on a separate track.

**Claim boundary.** Post-cutoff inability is expected for a closed model and is not itself hallucination if the system abstains. Durability should be claimed for dated answer versions, not immutable facts. Results cannot locate an undocumented model cutoff exactly, and current-event datasets must be versioned to remain reproducible.

**Database interpretation.** R3 is temporal querying and snapshot semantics: the contract must bind an answer to an as-of time, source version, and validity interval.

## R4 - Query ambiguity

**Operational variable.** Use the adjudicated number K of materially distinct valid interpretations. Map K to the frozen levels `unambiguous`, `two_way`, and `three_plus`, with `unambiguous` as anchor, while retaining K as a raw diagnostic. Retain each interpretation, disambiguated rewrite, valid answer set, and evidence. The committed Read actions are SET or ABSTAIN when one answer is unjustified; a clarification question is an optional diagnostic/baseline output, not a fourth contract action.

**Datasets.** [AmbigNQ/AmbigQA](https://aclanthology.org/2020.emnlp-main.466/) is the primary open-domain source. [CAmbigNQ](https://aclanthology.org/2023.findings-emnlp.772/) adds clarification questions, while [CLAMBER](https://aclanthology.org/2024.acl-long.578/) supplies an ambiguity taxonomy. [AmbiQT](https://aclanthology.org/2023.emnlp-main.436/) is a database-facing external check with two plausible SQL interpretations.

**Construction and controls.** Create matched ambiguous questions and their disambiguated rewrites. Balance interpretation count, dominant-answer popularity, answer-set size, question length, ambiguity type, R1, and domain. Obtain two independent annotations plus adjudication; K is a lower bound on documented readings, not all imaginable readings.

Score interpretation-set precision, recall, and F1; answer coverage within each interpretation; overcommitment to one reading; clarification-question validity and expected ambiguity reduction; and semantic consistency across repeated samples. Response variation alone does not prove ambiguity, and stable repetition does not prove correctness.

**Baselines.** Compare greedy direct answering, always clarify, AmbigQA-style enumeration, an explicit ambiguity detector, P(True), semantic entropy, and sample repetition. Repetition is essential because [Cole et al.](https://aclanthology.org/2023.emnlp-main.35/) found it more reliable than likelihood or self-verification in their selective ambiguous-QA setting. Add conformal sets over interpretations where the candidate universe is audited.

**Claim boundary.** Marginal single-label accuracy is invalid for multi-reading questions. CalibRead may claim coverage of annotated interpretations and measured clarification utility, not recovery of every pragmatically possible intent.

**Database interpretation.** R4 corresponds to multiple query plans/denotations and possible worlds. The Read contract must expose alternatives or request missing predicates instead of silently choosing one.

## R5 - Synthesis depth

**Operational variable.** Count indispensable atomic facts/hops in the derivation DAG, not sentences or generated reasoning tokens. Use the frozen levels `one_hop`, `two_hop`, `three_hop`, and `four_plus_hop`, with `one_hop` as anchor. Retain the raw indispensable-fact count plus every constituent question, answer, edge, and final derivation.

**Datasets.** Use [SOCRATES](https://aclanthology.org/2025.findings-acl.205/) as the primary closed-book shortcut-controlled panel. Use [MuSiQue](https://aclanthology.org/2022.tacl-1.31/) for 2-4-hop questions built from constituent single-hop questions. A new P03 cross-panel may extend chains to five facts only after filtering shortcuts and auditing every derivation.

**Construction and controls.** Match per-edge R1, relation family, answer type, domain, prompt length, and final-answer popularity. Remove head-answer co-occurrence shortcuts and answer-prior-solvable chains. Split by entire derivation graph. Never place a chain in one split and a constituent or paraphrase in another.

Score final typed correctness, per-constituent correctness, all-constituents-correct rate, and synthesis loss: final error among cases where all separately probed constituents are correct. Report that conditional quantity as descriptive because conditioning can select easier examples. Compare observed chain behavior with a labelled product diagnostic and a union-bound diagnostic.

**Baselines.** Direct answer, explicit chain-of-thought, question decomposition, oracle intermediate answers, likelihood/P(True)/semantic entropy, pooled conformal, R5-Mondrian, and crossed R1 x R5 group conformal.

**Claim boundary.** The proposal's 1-(1-H1)^d curve assumes equal independent hop errors and is a falsifiable diagnostic, not a guarantee. SOCRATES reports large relation-type variation, including strong country intermediates and weak year intermediates, so depth alone cannot explain composition.

**Database interpretation.** R5 is join/derivation depth. Constituent IDs and edges provide provenance, while the final contract records whether uncertainty propagation assumptions held.

## R6 - Domain specificity and transfer

**Operational variable.** Domain identity is categorical, but the canonical R6 raw field is a
normalized specificity score in [0,1]. Map that score through preregistered cut points to the frozen
levels `general`, `specialized`, and `expert`, with `general` as anchor. Store the domain label,
taxonomy/version, ontology depth, cut-point hash, and any calibration-to-test domain-distance
diagnostic in provenance rather than overloading the numeric raw field. The score orders specificity
within the frozen taxonomy; it does not claim that medicine is intrinsically more specific than law.

**Datasets.** Use [MALAMUTE](https://aclanthology.org/2025.findings-acl.209/) for expert-written concepts organized into domains and subdomains, and [MMLU](https://openreview.net/forum?id=d7KBjmI3GmQ) for a common multiple-choice format across subjects. Use [GPQA](https://openreview.net/forum?id=Ti67584b98), [PubMedQA](https://aclanthology.org/D19-1259/), and [LegalBench](https://papers.neurips.cc/paper_files/paper/2023/hash/89e44582fd28ddfea1ea4dcb0ebbf4b0-Abstract-Datasets_and_Benchmarks.html) as separate external panels; their scores are not pooled because their tasks differ.

**Construction and controls.** Build a source-domain by target-domain transfer matrix. Compare pooled calibration, same-domain calibration, leave-one-domain-out calibration, and held-out-domain tests at equal calibration sizes. Keep response format, answer balance, R1, R2, and R5 as matched as each panel allows.

Confounders include intrinsic difficulty, format, reasoning load, domain vocabulary, training-corpus mix, safety refusals, expert-label quality, and model specialization. Report accuracy and calibration per domain, worst-domain coverage, cross-domain coverage gap, and transfer regret relative to equal-size target-domain calibration.

**Baselines.** Pooled/global calibration, same-domain calibration, leave-one-domain-out, domain-group conformal, multicalibration, and importance-weighted conformal when weights are known. Raw likelihood and P(True) remain uncertainty baselines.

**Claim boundary.** The professor's transfer hypothesis is tested, not presumed. A within-MMLU transfer result does not establish medical or legal deployment safety. Ontology depth is a reproducible specificity proxy, while embedding distance is model-dependent and must be reported as such.

**Database interpretation.** R6 is workload partitioning and contract portability. A certificate is bound to its calibrated domain workload unless a transfer experiment supports a wider scope.

## R7 - Confidence threshold and Read policy

**Operational variable.** R7 is not a new question set. Apply the named score-threshold policies `tau_0_50`, `tau_0_70`, `tau_0_90`, `tau_0_95`, and `tau_0_99` (thresholds 0.50, 0.70, 0.90, 0.95, and 0.99), with 0.70 as anchor, to cached R1-R6 outputs. A denser sweep is diagnostic. Map the score to ANSWER, SET, or ABSTAIN under a predeclared loss/cost function; tau is not automatically a conformal alpha or coverage target.

**Datasets and construction.** Every R1-R6 test panel produces an R7 curve. [Selective QA under domain shift](https://aclanthology.org/2020.acl-main.503/) is the external policy benchmark. Choose thresholds only on calibration data; never regenerate answers for favorable thresholds. Evaluate in-distribution, changed workload mixtures, and unsupported groups. Unsupported conformal groups fail closed or use a separately declared fallback.

Report risk-coverage and AURC, answer rate at fixed risk budgets, risk at fixed coverage, action rates, set coverage/size, and utility under at least two transparent cost settings. Use confidence intervals for the entire curve or predeclared operating points.

**Baselines.** Raw likelihood, [P(True)](https://www.anthropic.com/research/language-models-mostly-know-what-they-know), sample repetition, semantic entropy, temperature/isotonic scaling, a selective-QA calibrator, global/group conformal, and [Conformal Risk Control](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html).

**Claim boundary.** A policy may be empirically non-dominated among compared methods; it is not globally Pareto-optimal without defining and solving over a policy class and loss. Set coverage is not conditional per-answer correctness. Minimal set size can be claimed only relative to a fixed candidate universe, score, and comparator.

**Database interpretation.** R7 is admission control and an SLA operating point: it trades availability against error while recording why the Read was committed, widened, or rejected.

## How the seven panels fit together

One versioned fact store can support R1, paired R2 prompts, dated R3 versions, R6 taxonomy labels, and R5 derivation edges. R4 adds separately adjudicated interpretation sets. The model is run once per frozen prompt/decoding condition; R7 consumes those cached records.

The three frozen confirmatory interactions are R1 x R5 on matched derivation chains, R3 x R6 on dated facts across domain levels, and R4 x R7 on cached ambiguous-question outputs under every named policy threshold. A balanced endpoint R1 x R2 x R5 x R6 panel may be run only as an exploratory appendix after the confirmatory analyses are complete; it cannot change the primary analysis. Do not force examples across panels when doing so breaks typed matching.

The primary statistical model includes model family as a block, main effects, predeclared interactions, and cluster-robust uncertainty by lineage family. It does not turn a proxy into a causal variable; exact exposure analyses and proxy/popularity analyses remain separate.

## Sample-support rules

Determine final sample sizes by a frozen simulation-based power analysis using pilot error rates and
paired effects. Exact full-study targets after exclusions are 80 development, 120 calibration, and
200 test examples per main-effect level (400 total), and 60 development, 90 calibration, and 150
test examples per dataset-interaction cell (300 total). Pilot and breadth-tier levels target
20 development, 30 calibration, and 50 test examples. Hard floors are 100 test examples per
main-effect level and 75 per interaction cell; below a floor, use a declared pooled fallback or mark
the result unsupported. Counts may increase after the development-only power analysis. Any decrease
after test access is a protocol deviation.

Target 0.90 and 0.95 conformal coverage as confirmatory operating points. The R7 policy `tau_0_99` is a score threshold, not a claim of 99% coverage. A separate 99%-coverage experiment is exploratory unless much larger calibration and independent test samples support it. Always publish calibration/test counts, errors, interval widths, empty/singleton set rates, and unsupported-group rates. Synthetic data verify software only and never count as evidence.

## Required output per dimension

Each R1-R6 directory must contain a frozen data card, construction log, audit sample, split hashes, prompt and scorer specification, baseline configuration, per-model records, marginal curve, R7 curves, confidence intervals, and a limitations note. The combined report adds the R1 x R5, R3 x R6, and R4 x R7 confirmatory analyses, transfer matrices, workload-mixture shifts, and machine-readable Read certificates. Any higher-order interaction is labelled exploratory.
