# CalibRead R5 data readiness

Updated: 2026-08-11

R5 measures synthesis depth: the number of factual or reasoning steps that must
be composed to answer a question. All four configured R5 levels now have
processed inference workloads.

## Available records

| Source | One hop | Two hop | Three hop | Four-plus hop | Total |
|---|---:|---:|---:|---:|---:|
| PopQA | 14,267 | 0 | 0 | 0 | 14,267 |
| SOCRATES v1 | 14,464 | 7,232 | 0 | 0 | 21,696 |
| StreamingQA | 9,939 | 0 | 0 | 0 | 9,939 |
| MuSiQue | 0 | 15,628 | 5,147 | 1,580 | 22,355 |
| **Total** | **38,670** | **22,860** | **5,147** | **1,580** | **68,257** |

The strongest R5 comparisons are within-source:

- SOCRATES: one hop versus two hops.
- MuSiQue: two hops versus three hops versus four hops.

A combined one-to-four-hop curve is useful as a secondary analysis, but source
identity must be modeled or stratified because one-hop and four-hop endpoints do
not come from the same benchmark.

## MuSiQue refinement

- Upstream bundle: official MuSiQue v1.0 Google Drive file.
- License: CC BY 4.0; attribution and redistribution status are recorded in the
  source registry.
- Raw bytes: 272,049,578.
- Raw SHA-256:
  `98f839bf2fd5319f5c688aed77901a6d5c30b3b9f9f691ab9a8ecafb045ee0cd`.
- Raw MD5: `2f16c88e333b9a3452f3f81eb09eb0c0`.
- Included: labeled MuSiQue-Ans train and development rows.
- Excluded: 2,459 unlabeled official test rows.
- MuSiQue-Full is omitted because it duplicates answerable questions and adds a
  different answerability task.

Every included row passed these checks:

1. The composition ID declares 2, 3, or 4 hops.
2. Decomposition length exactly equals the declared hop count.
3. Every decomposition step has a nonempty question and intermediate answer.
4. Every step points to an existing paragraph marked as supporting evidence.
5. Constituent single-hop IDs are unique within the composition.
6. Shared constituent IDs cannot cross CalibRead splits.
7. The strict `WorkloadRecord` schema validates.

Four-hop MuSiQue questions map to CalibRead's inclusive `four_plus_hop` level.
No claim is made that MuSiQue contains more than four hops.

## MuSiQue splits

| Split | Two hop | Three hop | Four-plus hop | Total |
|---|---:|---:|---:|---:|
| Development | 3,125 | 1,029 | 317 | 4,471 |
| Calibration | 4,689 | 1,544 | 474 | 6,707 |
| Test | 7,814 | 2,574 | 789 | 11,177 |

Splits use connected components over `chain_id`, constituent `source_fact_id`,
and normalized `question_hash`, stratified by R5 level. This prevents a shared
single-hop constituent from appearing in more than one partition.

Entity and graph-template overlap remain under the primary profile and are
reported in the manifest. Claims about unseen entities or unseen graph templates
require the stricter holdout profile.

## Inference inputs

- `data/processed/musique/examples.jsonl`: questions, answers, split, dimensions,
  and lineage for inference and scoring.
- `data/processed/musique/workloads.jsonl`: strict workload contracts, including
  decompositions in provenance and constituent IDs.
- `data/processed/musique/condition_seeds.jsonl`: unresolved model-specific R1/R3
  routing; these fields are not R5 evidence.
- `data/processed/musique/audit_sample.csv`: deterministic 60-row human review
  queue.
- `data/processed/musique/REFINEMENT_MANIFEST.json`: hashes and validation gates.
- `data/processed/musique/DATA_CARD.md`: source-specific limitations.

For prompt-only parametric-memory evaluation, send only the `question` to the
model. Do not include MuSiQue paragraphs, decompositions, intermediate answers,
or accepted answers in the prompt. They are gold metadata for lineage and audit,
not model input.

## Remaining human gate

The data is technically ready for development inference. Before publication or
the final locked test run, a human should review the 60-row audit sample for:

- answer correctness and aliases;
- whether each step is genuinely necessary;
- unnatural or ambiguous wording;
- accidental answer leakage in the question;
- whether hop count represents synthesis rather than merely available evidence.

Until that review is signed off, the manifest correctly records
`human_audit: pending`.

## Reproduction

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline fetch musique
python -m calibread.data_pipeline refine musique --audit-size 60
python -m unittest tests.test_data_pipeline tests.test_data_sources -v
```
