# CalibRead

CalibRead is a Python library for **parametric LLM Read contracts**: typed
`answer` / `set` / `abstain` actions, workload metadata (R1–R6), conformal and
selective-risk tooling, Read certificates, and a closed-book inference pipeline
(calibration, R7 policies, composition diagnostics).

This repository ships the **prototype implementation** and tests. It does **not**
include large-scale experiment configs, model run outputs, or calibrators from
published empirical studies.

## Requirements

- Python 3.11+
- Core library and tests: no required pip dependencies (see optional extras in
  `pyproject.toml`)

## Verify the installation

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m calibread.demo
```

`calibread.demo` reads `configs/pilot.toml` and uses **synthetic** examples only
(`research_evidence: false`).

## Repository layout

```text
src/calibread/           contract, conformal, evaluation, data pipeline
src/calibread/inference/ CLI, calibration, R7, providers
configs/pilot.toml       dimension grid for the smoke demo
configs/inference/       smoke TOML for tests and local runs
data/                    source registry, typed record examples
docs/hypothesis_registry.md   estimand IDs referenced by pilot.toml
tests/
```

## Components

| Area | Location |
|------|----------|
| Typed records, workload dimensions | `schema.py`, `dimensions.py`, `data/EXAMPLE_*_RECORD.jsonl` |
| Lineage-safe splits | `splits.py`, `leakage.py` |
| Finite-label / Mondrian conformal | `conformal.py`, `read_contract.py` |
| Fail-closed read policy | `read_contract.py`, `inference/decisions.py` |
| R7 thresholds on cached scores | `inference/decisions.py` |
| Read certificate | `certificate.py`, `data/EXAMPLE_READ_CERTIFICATE.jsonl` |
| Composition diagnostics | `composition.py`, `inference/composition_report.py` |
| Inference, isotonic calibration | `inference/runner.py`, `inference/calibration.py` |
| Providers (OpenRouter, Ollama, mock) | `inference/providers/` |
| CSV evaluation | `evaluate.py`, `metrics.py` |
| Dataset fetch and refine | `data_pipeline.py`, `data/source_registry.toml` |

SQL `CALIBREAD(...)` and planner integration are **not** in this codebase.

## Inference

```powershell
$env:PYTHONPATH = "src"
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_smoke.toml
```

Details: [`src/calibread/inference/README.md`](src/calibread/inference/README.md).

## Data

Licenses and fetch commands: [`DATA_SOURCES_AND_LICENSES.md`](DATA_SOURCES_AND_LICENSES.md).

Raw and processed datasets are written under `data/raw/` and `data/processed/`
(gitignored).

## What this repo does not reproduce

- End-to-end replication of reported benchmark numbers (requires frozen run configs,
  hardware, and cached generations not stored here).
- Hybrid SQL operator or optimizer costing (specified separately from this library).

## License

See `pyproject.toml`.
