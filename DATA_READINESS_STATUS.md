# CalibRead data readiness

Updated: 2026-08-11

This file separates data that is technically prepared from data that is valid
research gold. AI-authored questions remain candidates until humans review them.

## Current status

| Dimension | Available material | Current readiness | What remains |
|---|---:|---|---|
| R1: frequency | 14,267 PopQA proxy seeds and 21,696 SOCRATES proxy seeds | Proxy data prepared | Select exact model snapshots, measure/model-map frequency, freeze cutpoints, and join to R3 dates |
| R2: precision | 12 sourced draft questions: 4 coarse, 4 medium, 4 fine | Candidate review queue prepared | Two independent annotations, adjudication, consent, and answer/tolerance verification |
| R3: recency | 9,939 StreamingQA records with evidence/question date proxies | Downloaded, hash-verified, refined, and split | Validate the date proxy for the intended claim; combine it with model-specific R1 measurements |
| R4: ambiguity | 16 sourced draft questions: 11 unambiguous, 4 two-way, 1 three-plus | Candidate review queue prepared | Two independent annotations, adjudication, consent, and interpretation/answer verification |
| R5: synthesis | 38,670 one-hop, 22,860 two-hop, 5,147 three-hop, and 1,580 four-plus-hop processed workloads across PopQA, SOCRATES, StreamingQA, and MuSiQue | All four levels are technically inference-ready; MuSiQue provides decomposition-verified 2/3/4-hop data | Complete the human audit and keep within-source and cross-source contrasts separate |
| R6: domain expertise | 9 sourced draft questions: 3 general, 3 specialized, 3 expert | Candidate review queue prepared | Two independent annotations, separate adjudication, consent, and qualified expert review |

The R2, R4, and R6 counts are intentionally small seed sets for review and pilot
testing, not a publication-scale benchmark. They are stored as drafts so that an
AI-generated judgment is never presented as human gold.

## Important artifacts

- Source registry, licenses, redistribution policy, and commands:
  `DATA_SOURCES_AND_LICENSES.md`
- Versioned source definitions: `data/source_registry.toml`
- R2/R4/R6 authoring and review protocol:
  `docs/r4_r6_annotation_protocol.md`
- AI-authored review queue: `data/candidates/R2_R4_R6_AI_CANDIDATES.jsonl`
- Candidate pack report: `data/candidates/CANDIDATE_CARD.md`
- StreamingQA refined data: `data/processed/streamingqa_valid/`
- MuSiQue R5 refined data: `data/processed/musique/`
- R5-specific handoff: `R5_DATA_READINESS.md`
- Machine-readable condition audit:
  `data/processed/CONDITION_READINESS.json`

## Verified StreamingQA refinement

- Records: 9,939
- Development/calibration/test: 1,955 / 2,975 / 5,009
- Official MD5: `3570fbba6e2630e0c2bff03b150f9230`
- Download SHA-256:
  `0fe15fca5629a64f2eefefa4056812b25de6e8a18583c018e80f43fe42cd7e7b`
- Raw hash verification: passed
- Workload schema and primary lineage checks: passed
- Human audit: pending

StreamingQA's evidence timestamp is preserved as an R3 proxy. It must not be
described as a guaranteed real-world event date without validation.

## Why model-specific R1/R3 records are not frozen

The freeze gate is currently and correctly closed because:

1. `configs/pilot.toml` still names `pilot_model_tbd` rather than an immutable
   model snapshot.
2. The R1 mapping hash is still `tbd_before_main_inference`.
3. Existing seeds contain either an R1 proxy or an R3 date, but none yet contain
   both for the same fact/model condition.

Creating final records despite these gaps would fabricate experimental metadata.
The condition audit makes this state machine-readable and returns a blocked
result until those requirements are satisfied.

## Reproducible commands

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline fetch streamingqa_valid
python -m calibread.data_pipeline refine streamingqa_valid
python -m calibread.data_pipeline prepare musique --audit-size 60
python -m calibread.candidates
python -m calibread.authoring validate data/candidates/R2_R4_R6_AI_CANDIDATES.jsonl
python -m calibread.condition_audit --config configs/pilot.toml
python -m unittest discover -s tests -v
```

The condition-audit command intentionally exits non-zero while the freeze gate is
blocked; its JSON report contains the exact blockers.
