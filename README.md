# CalibRead

CalibRead implements evaluation, conformal calibration, and Read-contract tooling for
studying when parametric LLM **Read** operations can be trusted under declared workload
and reliability targets.

This repository is the **public artifact** for conference submission. It contains source
code, unit tests, data schemas, and license metadata. Experiment **configs** and **results**
from the paper runs are not included; contact the authors for frozen run manifests.

## Requirements

- Python 3.11+
- No required runtime dependencies for core library and tests (see `pyproject.toml` for optional `analysis`, `llm`, and `dev` extras)

## Quick start

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Install editable (optional):

```powershell
pip install -e ".[dev]"
```

## Layout

```text
src/calibread/     core library and inference CLI
tests/             unit tests
data/              source registry, example records, templates
scripts/cluster/   Slurm helpers (expects local configs)
```

## Evaluate cached results

CSV rows must include `example_id`, `correct`, `confidence`, `condition_hash`, and
consistent run linkage fields (`run_id`, `model_snapshot_id`, `evaluation_track`, etc.).
See `src/calibread/evaluate.py` and `tests/test_evaluate.py`.

```powershell
$env:PYTHONPATH = "src"
python -m calibread.evaluate results.csv --group-column group --bins 10
```

## Inference pipeline

Closed-book inference, scoring, isotonic calibration, R7 policies, and composition
reports are under `src/calibread/inference/`. Entry point:

```powershell
$env:PYTHONPATH = "src"
python -m calibread.inference.cli --help
```

Provider setup and command summary: [`src/calibread/inference/README.md`](src/calibread/inference/README.md).

## Data acquisition

License gates and upstream sources: [`DATA_SOURCES_AND_LICENSES.md`](DATA_SOURCES_AND_LICENSES.md).
Machine registry: `data/source_registry.toml`.

```powershell
$env:PYTHONPATH = "src"
python -m calibread.data_pipeline list
```

## License

See `pyproject.toml` (research use; choose a release license before publication).
