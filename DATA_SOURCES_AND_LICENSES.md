# Data sources and licenses

Human-readable policy for dataset acquisition. Machine registry: `data/source_registry.toml`.
Each source must pass its license gate before download or experimental use.

## Source inventory

| ID | Role | License / status |
|---|---|---|
| `socrates_v1` | Multi-hop QA; R1 proxy | CC BY 4.0 / approved |
| `popqa` | Popularity proxy; single-hop QA | MIT / approved |
| `streamingqa_valid` | Time-stamped questions (R3) | CC BY 4.0 / approved |
| `wikidata_snapshot` | Entity lineage (R2) | CC0 1.0 / approved (manual snapshot) |
| `musique` | Multi-hop R5 validation | CC BY 4.0 / approved |
| `malamute` | Temporal QA (R3) | MIT / approved |
| `mmlu_cf` | Specialist validation (R6) | CDLA-Permissive-2.0 / approved (manual) |
| `freshqa` | Dynamic R3 stress | Terms need confirmation / manual |
| `ambigqa`, `comparisonqa` | Candidates | License unresolved / blocked |
| `calibread_authored_r4_r6` | Project-authored R4/R6 | Release review pending |

`approved` permits acquisition under recorded terms; derived artifacts may still carry
upstream obligations. Blocked sources fail closed in the downloader.

## Storage

- Raw and processed datasets live under `data/raw/` and `data/processed/` (gitignored).
- Downloads record revision, hashes, and manifests via `calibread.data_pipeline`.

## Commands

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline list
python -m calibread.data_pipeline fetch socrates_v1
python -m calibread.data_pipeline refine socrates_v1 --limit 1000
python -m calibread.data_pipeline prepare popqa
python -m calibread.data_pipeline prepare musique
```

## Upstream

- SOCRATES: https://github.com/google-deepmind/latent-multi-hop-reasoning
- PopQA: https://github.com/AlexTMallen/adaptive-retrieval
- StreamingQA: https://github.com/google-deepmind/streamingqa
- Wikidata: https://www.wikidata.org/wiki/Wikidata:Data_access
- MuSiQue: https://github.com/stonybrooknlp/musique
- MMLU-CF: https://github.com/microsoft/MMLU-CF
- FreshQA: https://github.com/freshllms/freshqa
