# Inference

Pretrained models via **OpenRouter** or local **Ollama** (loopback-only). Outputs under
`results/` at run time.

## CLI

```powershell
$env:PYTHONPATH = "src"
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli plan configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli run configs/inference/r5_ollama_smoke.toml
```

See `python -m calibread.inference.cli --help` for score, report, calibrator fit/apply,
R7 decisions, and composition reports.

## Configs in this artifact

Only **smoke** TOML under `configs/inference/` (tests and local sanity checks). Sealed paper
runs used private cluster configs—not included here.

Schema: `src/calibread/inference/config.py`.

## Providers

| Provider | Notes |
|----------|--------|
| `openrouter` | `OPENROUTER_API_KEY` |
| `ollama` | Local; non-loopback URLs rejected |
| `mock` | Offline unit tests |
