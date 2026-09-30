# Data sources and licenses

Machine registry: `data/source_registry.toml`. The downloader records revision,
hashes, and manifests under `data/raw/<source-id>/`. Refined panels go to
`data/processed/<source-id>/` (both paths are gitignored).

Primary panels used in multi-hop and frequency experiments:

| ID | Role | License |
|---|---|---|
| `socrates_v1` | Multi-hop composition (SOCRATES) | CC BY 4.0 |
| `popqa` | Popularity / frequency proxy | MIT |
| `musique` | Multi-hop QA (MuSiQue) | CC BY 4.0 |

Additional sources in the registry can be listed and fetched with the same CLI.

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline list
python -m calibread.data_pipeline prepare popqa
python -m calibread.data_pipeline prepare musique
python -m calibread.data_pipeline fetch socrates_v1
```

Upstream:

- [SOCRATES](https://github.com/google-deepmind/latent-multi-hop-reasoning)
- [PopQA](https://github.com/AlexTMallen/adaptive-retrieval)
- [MuSiQue](https://github.com/stonybrooknlp/musique)
