# Conference artifact scope

This repository is a **public submission artifact** for CalibRead. It contains:

- `src/` and `tests/` — implementation and unit tests
- `docs/` and root research notes — protocol, findings, and planning documents
- `data/` — schemas, example records, dimension cards, and source registry (not raw or processed datasets)
- `scripts/` — cluster and pipeline helpers (no machine-specific env files)
- `vldb2027-vision/` — paper sources and PDF

**Not included** (maintained in the private research repository):

- `configs/` — experiment and inference TOML configurations
- `results/` — run outputs, calibrators, and sealed-test artifacts

To reproduce full cluster runs, request configs and result manifests from the authors or use the runbooks under `src/calibread/inference/` with locally authored configs matching the frozen protocol in `docs/research_protocol.md`.
