# CalibRead (artifact)

Python prototype for the **CalibRead Read contract** described in the PVLDB vision paper
*CalibRead: Reliability Contracts for Parametric LLM Databases [Vision]*. The paper specifies
SQL and planner integration as future work; this repository implements the **library** in
Section “Prototype”: typed actions, two tracks, conformal utilities, R7 on cached scores,
Read certificates, and closed-book inference adapters.

Sealed empirical probes in the paper (PopQA, SOCRATES, MuSiQue) are **not** shipped here—no
run results or cluster experiment configs.

## Requirements

- Python 3.11+
- Core tests and library: no required pip dependencies (`pyproject.toml` lists optional extras)

## Quick start

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m calibread.demo
```

The demo uses `configs/pilot.toml` and **synthetic** data only (`research_evidence: false`).

## What maps to the paper

| Paper claim | Code |
|-------------|------|
| Workload $W$ (R1–R6), evaluation track | `schema.py`, `dimensions.py`, `data/EXAMPLE_*_RECORD.jsonl` |
| Lineage-safe splits | `splits.py`, `leakage.py` |
| Track A: finite-label / Mondrian conformal | `conformal.py`, `read_contract.py` |
| Track B: open-ended stress (answer/abstain) | `read_contract.py`, `inference/decisions.py` |
| Fail-closed policy (Table fail-closed) | `read_contract.py`, `inference/decisions.py` |
| R7 thresholds 0.50 … 0.99 on cached generations | `inference/decisions.py`, `dimensions.py` |
| Read certificate $C$ | `certificate.py`, `data/EXAMPLE_READ_CERTIFICATE.jsonl` |
| Composition fail-closed / union-bound diagnostics | `composition.py`, `inference/composition_report.py` |
| Generation + isotonic calibration + manifests | `inference/runner.py`, `calibration.py`, `manifest.py` |
| OpenRouter / Ollama adapters | `inference/providers/` |
| Offline evaluation / risk–coverage | `evaluate.py`, `metrics.py` |
| Data for SOCRATES, PopQA, MuSiQue (fetch only) | `data_pipeline.py`, `data/source_registry.toml` |

Operational test IDs (Table OP): `docs/hypothesis_registry.md` (config validation only).

Listings for SQL `CALIBREAD(...)` are **not** implemented.

## Layout

```text
src/calibread/           contract, conformal, evaluation, data pipeline
src/calibread/inference/ CLI, calibration, R7, providers
configs/pilot.toml       dimension grid for the smoke demo
configs/inference/       smoke TOML for provider/CLI tests only
data/                    registry, typed examples, certificate fixture
tests/
```

## Inference

```powershell
$env:PYTHONPATH = "src"
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_smoke.toml
```

See [`src/calibread/inference/README.md`](src/calibread/inference/README.md).

## Data

[`DATA_SOURCES_AND_LICENSES.md`](DATA_SOURCES_AND_LICENSES.md) — licenses for datasets named in the prototype (SOCRATES, PopQA, MuSiQue).

## License

See `pyproject.toml`.

## PVLDB / VLDB 2027 submission notes

Official rules: [Submission Guidelines](https://vldb.org/2027/submission-guidelines.html).

| Topic | Rule | This repo |
|-------|------|-----------|
| **Review model** | **Single-blind** — put **names and affiliations on page 1 of the PDF**; do not anonymize the paper | Paper `main.tex` includes authors; artifact may name authors in metadata |
| **Artifact URL** | Public archival repo (e.g. GitHub); no personal homepages; link must be accessible to reviewers | `https://github.com/AaditS04/calibread-artifact` |
| **Vision + no artifact block** | Vision papers with no experiments may omit `\vldbavailabilityurl` if you explain in CMT | Paper leaves artifact URL empty; optional supplemental link to this prototype |
| **“Anonymity of access”** | Broken, login-walled, or suspicious URLs delay review — **not** author blind review | Repo is public; no secrets in tree |
| **CMT** | Every author registers, declares conflicts, one account per author | Match PDF author list exactly |
| **After acceptance** | Author list cannot change | Freeze before camera-ready |

**Scan (Mar 2026):** no author emails or affiliations in tracked artifact files. Internal codenames (`P03`, `p03-*` in configs/tests) remain in code comments only — not a VLDB violation, but rename if you want a cleaner public face.

**Not in this repo (keep private):** `calibread` full research tree, PC review notes, sealed `results/`, cluster configs — those can expose advisor plans or unreleased numbers unrelated to single-blind rules but risky for accidental submission links.
