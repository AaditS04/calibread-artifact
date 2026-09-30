# CalibRead data sources, licenses, and provenance

This is the human-readable acquisition policy. The versioned machine registry is
in `data/source_registry.toml`. Every dataset must pass its license gate before
automated download or experimental use.

## Research dimensions supported by the data

- **R1 frequency:** likely representation of a fact in training data.
- **R2 precision:** exactness required by the requested answer.
- **R3 recency:** whether an answer changed near or after a model cutoff.
- **R4 ambiguity:** number of plausible interpretations.
- **R5 synthesis:** facts or hops that must be composed.
- **R6 domain:** specialization of the required knowledge.

R1 and R3 are model-dependent. Refinement therefore emits traceable proxy values
as condition seeds; it does not label a proxy as exact training frequency or
recency. R2, R4, R5, and R6 live on strict CalibRead `WorkloadRecord` objects.

## Source inventory

| ID | Research role | License/status | Acquisition |
|---|---|---|---|
| `socrates_v1` | R5 multi-hop; corpus co-occurrence proxy for R1 | CC BY 4.0 data / approved | Automated pinned GitHub file |
| `popqa` | Popularity proxy for R1; factual single-hop QA | MIT repository / approved | Automated pinned GitHub file |
| `streamingqa_valid` | Time-stamped R3 questions | CC BY 4.0 / approved | Automated official GCS object |
| `wikidata_snapshot` | R2 variants and entity lineage | CC0 1.0 / approved | Manual frozen dated subset |
| `musique` | Explicit two-, three-, and four-hop R5 validation | CC BY 4.0 / approved | Automated official Drive bundle pinned by SHA-256 |
| `malamute` | R3 temporal QA | MIT repository / approved | Automated archive; schema review needed |
| `mmlu_cf` | R6 specialist validation | CDLA-Permissive-2.0 / approved | Manual pinned snapshot |
| `freshqa` | Fresh/dynamic R3 stress test | Repository Apache-2.0; sheet terms need confirmation | Manual, non-redistributable by default |
| `ambigqa` | Candidate R4 source | License unresolved / review required | Blocked from automated use |
| `comparisonqa` | Candidate precision/comparison source | License unresolved / review required | Blocked from automated use |
| `calibread_authored_r4_r6` | Matched R2 precision, R4 ambiguity, and R6 specialization | Project-owned; release review pending | AI-authored candidates followed by independent human annotation |

`approved` means acquisition is permitted under the recorded terms, not that all
derived artifacts may be relicensed. `review_required` and `blocked` sources fail
closed in the downloader.

## Reproducibility and storage policy

1. GitHub branches and tags are resolved to an exact commit.
2. Each download records requested and resolved URLs, resolved revision, byte
   count, UTC time, SHA-256, and MD5 in `FETCH_MANIFEST.json`.
3. A registry hash, when present, must match before the file is accepted.
4. `data/raw/` and `data/processed/` stay outside Git. Only source definitions,
   code, documentation, and small synthetic test fixtures are versioned.
5. Refinement produces strict workload and evaluation records, model-condition
   seeds, lineage-aware splits, a data card, and a deterministic audit sample.
   The primary split protects chain, fact, and normalized-question IDs;
   entity/template overlaps are measured for stricter holdout studies.
6. Released derivatives must retain upstream attribution and license obligations.

## Commands

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline list
python -m calibread.data_pipeline fetch socrates_v1
python -m calibread.data_pipeline refine socrates_v1 --limit 1000
python -m calibread.data_pipeline prepare popqa
python -m calibread.data_pipeline prepare musique
python -m calibread.authoring validate data/raw/calibread_authored_r4_r6/annotations.jsonl
python -m calibread.authoring refine data/raw/calibread_authored_r4_r6/annotations.jsonl
```

Raw files are stored under `data/raw/<source-id>/`. Generated artifacts are under
`data/processed/<source-id>/`. `prepare` performs both fetch and refinement.

## Gate before any model run

A source is model-ready only after its license and hash pass; all records validate;
R1-R6 routing is present; the declared profile has no protected-key leakage;
entity/template overlap is disclosed and excluded from unsupported generalization
claims; the data card is complete; and a human reviews the audit sample.
Training or fine-tuning is not required for the core experiment: these workloads
are intended to evaluate existing pretrained models.

## Primary upstream pages

- SOCRATES: <https://github.com/google-deepmind/latent-multi-hop-reasoning>
- PopQA: <https://github.com/AlexTMallen/adaptive-retrieval>
- StreamingQA: <https://github.com/google-deepmind/streamingqa>
- Wikidata: <https://www.wikidata.org/wiki/Wikidata:Data_access>
- MuSiQue: <https://github.com/stonybrooknlp/musique>
- MALAMUTE: <https://github.com/Shaier/MALAMUTE>
- MMLU-CF: <https://github.com/microsoft/MMLU-CF>
- FreshQA: <https://github.com/freshllms/freshqa>
- AmbigQA: <https://github.com/shmsw25/AmbigQA>
- ComparisonQA: <https://github.com/HKUST-KnowComp/ComparisonQA>
