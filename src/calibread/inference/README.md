# Inference

Runs **pretrained** models via OpenRouter (API key) or local **Ollama** (loopback).
Does not train models. Outputs go under `results/` (created at run time; not shipped in
the public artifact).

## CLI

```powershell
$env:PYTHONPATH = "src"
python -m calibread.inference.cli validate-config <config.toml>
python -m calibread.inference.cli plan <config.toml>
python -m calibread.inference.cli run <config.toml>
python -m calibread.inference.cli score <config.toml>
python -m calibread.inference.cli report <config.toml>
python -m calibread.inference.cli fit-calibrator <config.toml>
python -m calibread.inference.cli apply-calibrator <config.toml>
python -m calibread.inference.cli r7-decide <config.toml>
python -m calibread.inference.cli composition-report <config.toml>
```

Same commands are available as `calibread-infer` after `pip install -e .`.

TOML configs are **not** in this repository. Author configs locally or request frozen
configs from the paper authors. Configuration schema: `src/calibread/inference/config.py`.

## Providers

| Provider | Use case |
|----------|----------|
| `openrouter` | Hosted models; set `OPENROUTER_API_KEY` |
| `ollama` | Local inference; server must bind to loopback only (enforced in code) |
| `mock` | Offline tests |

OpenRouter and Ollama adapters record model identity, token log-probabilities where
available, budgets, append-only checkpoints, and hash-safe resume.

## Package map

```text
cli.py                 commands
runner.py              selection, checkpoints, manifests
calibration.py         isotonic fit/apply
decisions.py           R7 answer / abstain policies
composition_report.py  R5 chain diagnostics
providers/             openrouter, ollama, mock
```

Each run directory uses `.calibread-inference.lock` for exclusive append access.
