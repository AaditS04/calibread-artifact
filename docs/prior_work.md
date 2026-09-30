# Prior work and novelty boundary

Literature snapshot: 11 August 2026. This is a working map, not a substitute for the paper's systematic related-work search.

## Bottom line

CalibRead should **not** claim to invent conformal prediction for language generation, factuality guarantees, black-box uncertainty, multicalibration, conditional/group conformal prediction, or long-tail/multi-hop QA evaluation. Those areas already contain strong published work.

The defensible opportunity is a database-style, typed and versioned Read benchmark across all P03 dimensions R1-R7: frequency, requested precision, recency, ambiguity, synthesis depth, domain transfer, and threshold policy. Its contribution must be controlled failure curves, predeclared interactions, provenance, and workload-bound guarantees. Merely applying conformal prediction or collecting unrelated QA scores across seven datasets is not novel.

## Novelty matrix

| Area | What is already established | Consequence for CalibRead |
|---|---|---|
| Conformal LM output sets | [Conformal Language Modeling](https://openreview.net/forum?id=pzUhfQ74c5) calibrates sampling/stopping and rejection for candidate response sets. | Use as a baseline; a split-conformal wrapper alone is not novelty. |
| Factuality guarantees | [Mohri & Hashimoto, ICML 2024](https://proceedings.mlr.press/v235/mohri24a.html) use progressively less-specific entailment sets for high-probability correctness. | Compare Read actions and specificity/abstention trade-offs; do not claim the first factuality guarantee. |
| Open-ended conformal UQ | [ConU, EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.404/) builds conformal uncertainty sets for free-form generation. | Audit candidate-oracle recall and reproduce it as a baseline where feasible. |
| Query-only black-box sets | [Conformal Prediction Beyond the Seen, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/2e5911cb61db978c225cf62b6c029192-Abstract-Conference.html) treats missing mass when only finite black-box queries are available. | Candidate budget and unseen-answer mass require an explicit baseline and ablation. |
| Conditional validity for LLMs | [Gibbs, Cherian & Candès, NeurIPS 2024](https://openreview.net/forum?id=JD3NYpeQ3R) explicitly targets weaknesses of marginal/topic-varying validity. | CalibRead's group analysis cannot be framed as previously unnoticed. |
| Fine-grained confidence | [Detommaso et al., ICML 2024](https://proceedings.mlr.press/v235/detommaso24a.html) apply multicalibration to LLM confidence across intersecting groupings. | Include multicalibration; position predeclared workload groups and shift as the systems focus. |
| General group coverage | [Kandinsky conformal prediction, ICML 2025](https://proceedings.mlr.press/v267/bairaktari25a.html) covers flexible, overlapping group definitions. | Mondrian groups are a simple baseline, not the theoretical frontier. |
| Shift-aware conformal inference | [Weighted conformal prediction](https://papers.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html) handles specified covariate shift; [SConU](https://aclanthology.org/2025.acl-long.934/) tests uncertainty-distribution outliers; [CoFact, ICLR 2026](https://iclr.cc/virtual/2026/poster/10008295) targets conformal factuality under distribution shift. | Reproduce an applicable shift-aware method; shift robustness itself is not the novelty. |

## Uncertainty and selective-prediction baselines

- [Language Models (Mostly) Know What They Know](https://arxiv.org/abs/2207.05221) motivates the fixed-prompt `P(True)` self-evaluation baseline.
- [SelfCheckGPT, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.557/) uses consistency across black-box samples to flag factuality problems.
- [Semantic entropy, Nature 2024](https://www.nature.com/articles/s41586-024-07421-0) clusters semantically equivalent generations before measuring uncertainty; it is a required strong sampling baseline, with its sampling and entailment costs reported.

Sequence probability, cluster mass, `P(True)`, SelfCheckGPT-style consistency, and semantic entropy are estimators. Calibration or conformalization changes how they are used; it does not make any estimator intrinsically factual.

## Long-tail and composition benchmarks

- [PopQA / When Not to Trust Language Models, ACL 2023](https://aclanthology.org/2023.acl-long.546/) establishes a popularity-linked long-tail factuality gap. It is an external-validity dataset, not evidence that popularity exactly equals a model's training exposure.
- [ComparisonQA, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.212/) controls entity frequency through matched question pairs and is the stronger starting point for R1.
- [MuSiQue, TACL 2022](https://aclanthology.org/2022.tacl-1.31/) constructs multi-hop questions from constituent single-hop questions and targets shortcut resistance.
- [SOCRATES, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.205/) directly probes whether models compose recalled facts while filtering co-occurrence and guessing shortcuts.

The paper still needs an audited cross-product. Running one frequency dataset and one multi-hop dataset side by side cannot identify an R1 × R5 interaction. Every chain should retain its atomic constituent probes so the analysis can separate recall failure from synthesis loss.

## Database lineage and venue fit

Probabilistic databases already treat uncertainty as query semantics rather than decorative confidence. [Conditioning Probabilistic Databases (PVLDB 2008)](https://www.vldb.org/pvldb/vol1/1453894.pdf) and [Approximate Lifted Inference (PVLDB 2015)](https://www.vldb.org/pvldb/vol8/p629-gatterbauer.pdf) are useful lineage for probabilistic query answering and tractable inference/composition. [SWAN / Hybrid Querying over Relational Databases and LLMs (CIDR 2025)](https://www.vldb.org/cidrdb/2025/hybrid-querying-over-relational-databases-and-large-language-models.html) shows that hybrid relational–LLM query execution is already an active data-management topic.

Therefore, a PVLDB paper cannot be only “ECE on QA datasets.” Its systems contribution is a typed, versioned Read contract and workload artifact: declared target, calibration/workload identity, fact/version/interpretation/derivation lineage, execution action (`answer`, `set`, or `abstain`), and auditable behavior when support or exchangeability fails. Clarification remains an R4 diagnostic/baseline, not a fourth committed action.

## Minimum comparison set

For point confidence and abstention, compare length-normalized negative log-likelihood, `P(True)`, modal semantic-cluster mass, semantic entropy, global isotonic calibration, and multicalibration. Report risk versus answer rate and AURC.

For prediction sets, compare global split conformal, a published conformal-LM method applicable to the candidate setup, R1-Mondrian, R5-Mondrian, crossed R1 × R5 Mondrian, a stronger conditional/group method, SConU-style unsupported-input detection, and importance-weighted conformal under known mixture weights. Report global and worst-cell coverage, set size, singleton/empty/abstention rates, and candidate-oracle recall.

For the full P03 study, add typed R2 scorers and a formatter oracle; temporal pooled/group methods plus a retrieval oracle on a separate R3 track; direct/enumerate/clarify baselines for R4; pooled, same-domain, leave-one-domain-out, domain-group, and multicalibrated R6 transfer; and the complete R7 policy family. A single global conformal baseline cannot answer all seven research questions.

For composition, compare observed chain correctness with (1) a clearly labeled factorized/product diagnostic from constituent scores and (2) a conservative union-bound propagation baseline. Neither baseline is itself a guarantee for open-ended generation. Report chain accuracy, all-constituents-correct rate, synthesis loss, and contract/composition gap.

## Contribution boundary to use in the paper

1. A leakage-resistant, typed, versioned workload with controlled curves for every R1-R6 dimension and an R7 policy surface.
2. Three frozen confirmatory interaction panels: R1 x R5, R3 x R6, and R4 x R7. Higher-order interactions remain exploratory.
3. A workload-conditioned Read contract that chooses answer, set, or abstain; records lineage and assumptions; and refuses unsupported groups.
4. A transparent comparison of confidence, global, group-aware, and shift-aware methods, including efficiency and support costs.

Do not use “first” without a refreshed literature search. Do not say “provably minimal,” “per-answer guarantee,” “arbitrary-shift robustness,” or “open-ended coverage” unless a theorem and experimental construction meet the exact assumptions.

## Literature maintenance

Before protocol freeze, search Semantic Scholar/OpenAlex plus proceedings for ICLR, ICML, NeurIPS, ACL-family, SIGMOD, VLDB/PVLDB, ICDE, and CIDR using combinations of `LLM`, `conformal`, `calibration`, `selective prediction`, `factuality`, `long-tail`, `multi-hop`, `composition`, `distribution shift`, and `probabilistic query`. Repeat at analysis freeze and immediately before submission. Record query, date, screened count, and inclusion decision in the lab log. Papers published after the protocol snapshot are discussed and, when feasible, added as baselines without retroactively changing the primary hypothesis.

## Evidence map for all P03 dimensions

### R1 - frequency

[Kandpal et al., ICML 2023](https://proceedings.mlr.press/v202/kandpal23a.html) connect factual QA performance to document support in pretraining data. PopQA and Head-to-Tail show popularity-linked tail gaps, while ComparisonQA argues that unmatched questions confound frequency and difficulty. Dolma makes corpus-count analysis possible for OLMo-family models. Together these motivate exact-corpus and matched-proxy tracks; they do not establish a universal capacity-normalized frequency cliff.

### R2 - requested precision

[Wikidata's typed values](https://www.wikidata.org/wiki/Help:Data_type) and [Wiki-Measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC12284226/) support paired date and numeric granularity. [NumericBench](https://aclanthology.org/2025.findings-acl.1026/) and [DROP](https://aclanthology.org/N19-1246/) show numeracy/reasoning weaknesses, but change reasoning demands rather than only requested factual precision. [Feng et al.](https://aclanthology.org/2025.findings-acl.3/) concern finite internal arithmetic precision, not answer digits; conflating them is a construct-validity error.

### R3 - recency

[StreamingQA](https://proceedings.mlr.press/v162/liska22a.html), [SituatedQA](https://aclanthology.org/2021.emnlp-main.586/), [RealTime QA](https://papers.neurips.cc/paper_files/paper/2023/hash/9941624ef7f867a502732b5154d30cb7-Abstract-Datasets_and_Benchmarks.html), and [FreshQA](https://aclanthology.org/2024.findings-acl.813/) already establish dynamic and time-situated QA. CalibRead must add model-cutoff-relative bins, immutable controls, versioned gold intervals, and confidence/coverage curves. Retrieval improvements in these papers are a contrasting systems track, not evidence about parametric Read alone.

### R4 - ambiguity

[AmbigQA](https://aclanthology.org/2020.emnlp-main.466/) represents plausible answers with disambiguated rewrites; [CAmbigNQ](https://aclanthology.org/2023.findings-emnlp.772/) and [CLAMBER](https://aclanthology.org/2024.acl-long.578/) study clarification and detection. [Selective ambiguous QA](https://aclanthology.org/2023.emnlp-main.35/) favors sampling repetition over likelihood or self-verification in its setting. These tasks already exist; novelty must come from typed Read integration and controlled R4/R7 curves.

### R5 - synthesis

[MuSiQue](https://aclanthology.org/2022.tacl-1.31/) provides constituent questions for connected 2-4-hop QA. [SOCRATES](https://aclanthology.org/2025.findings-acl.205/) controls co-occurrence and guessing shortcuts and finds sharply different latent composability across intermediate types. This is evidence against treating depth as the only cause. The proposal's multiplicative error curve remains a diagnostic whose independence/equal-error assumptions must be tested, not a theorem.

### R6 - domain specificity and transfer

[MALAMUTE](https://aclanthology.org/2025.findings-acl.209/) supplies a granular hierarchy. [MMLU](https://openreview.net/forum?id=d7KBjmI3GmQ) offers one format across subjects; [GPQA](https://openreview.net/forum?id=Ti67584b98), [PubMedQA](https://aclanthology.org/D19-1259/), and [LegalBench](https://papers.neurips.cc/paper_files/paper/2023/hash/89e44582fd28ddfea1ea4dcb0ebbf4b0-Abstract-Datasets_and_Benchmarks.html) add expert panels. Their tasks differ, so cross-dataset decline cannot identify specificity. Use a source-to-target matrix with declared depth and distance.

### R7 - threshold and selective action

[SelectiveNet](https://proceedings.mlr.press/v97/geifman19a) formalizes reject options and risk-coverage; [selective QA under shift](https://aclanthology.org/2020.acl-main.503/) shows raw softmax can fail out of domain. P(True), semantic entropy, conformal LM methods, and [Conformal Risk Control](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html) are strong alternatives. R7 is a policy axis, not new query complexity. Optimality needs a specified loss and policy class.

## Conflicting results are part of the experiment

The literature should not be filtered to support P03. Kadavath et al. report encouraging self-evaluation, while selective QA and selective ambiguous QA find likelihood/self-verification insufficient in shifted or ambiguous settings. SOCRATES finds high composition for some relations and very low composition for others. Domain-specialized datasets can improve measurement while introducing harder questions and different formats. These conflicts motivate stratified tests; they do not license averaging incompatible tasks.

## Repairs to the original P03 claim language

- **H1 frequency threshold:** estimate model-specific change points; call a capacity-normalized threshold universal only after controlled multi-scale training evidence.
- **H2 synthesis compounding:** compare with the product curve, but label it a diagnostic because hop errors need not be independent or identical.
- **H3 CPR tightness:** prediction-set size at alpha = 0.05 is empirical and candidate-dependent. CPR cannot be called the first conformal LM wrapper or universally minimal.
- **H4 domain transfer:** retain as a falsifiable source-to-target matrix; within-domain success and cross-domain failure are outcomes, not premises.
- **H5 abstention optimality:** claim empirical non-dominance only among named baselines and operating points unless a policy class, loss, and proof establish more.

[Calibrated Language Models Must Hallucinate](https://arxiv.org/abs/2311.14648), accepted at STOC 2024, gives a theoretical lower-bound perspective for certain rare arbitrary facts. It reinforces that calibration and factual accuracy are different objectives; a calibrated score reports frequencies and does not eliminate errors.
