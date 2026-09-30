# Data sources (vision prototype)

Registry: `data/source_registry.toml`. Raw/processed files stay under `data/raw/` and
`data/processed/` (gitignored).

The vision paper’s prototype section uses **SOCRATES** (composition), **PopQA** (frequency /
R1 probe), and **MuSiQue** (multi-hop family). Other registry entries support the follow-on
measurement program and may be fetched the same way.

| ID | Paper role | License |
|---|---|---|
| `socrates_v1` | SOCRATES composition slice | CC BY 4.0 |
| `popqa` | PopQA frequency split | MIT |
| `musique` | MuSiQue multi-hop panel | CC BY 4.0 |

```powershell
$env:PYTHONPATH='src'
python -m calibread.data_pipeline list
python -m calibread.data_pipeline prepare popqa
python -m calibread.data_pipeline prepare musique
python -m calibread.data_pipeline fetch socrates_v1
```

Upstream: [SOCRATES](https://github.com/google-deepmind/latent-multi-hop-reasoning),
[PopQA](https://github.com/AlexTMallen/adaptive-retrieval),
[MuSiQue](https://github.com/stonybrooknlp/musique).
