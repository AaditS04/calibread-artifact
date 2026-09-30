# CalibRead inference

This package runs pretrained language models through OpenRouter or a local
Ollama server. It does not train or fine-tune the LLM. OpenRouter needs an API
key; Ollama can run on a CPU-only computer without a GPU, although local CPU
inference is slower.

For the complete R5 command sequence, including atomic-probe materialization,
development, calibration, held-out test, and composition reporting, use
[`R5_COMPLETE_RUN.md`](R5_COMPLETE_RUN.md). For the raw-score and R7 design,
read [`CALIBRATION_AND_R7.md`](CALIBRATION_AND_R7.md). For Windows installation,
updates, and local model setup, read [`OLLAMA.md`](OLLAMA.md). For the concrete
hosted free-model diagnostic, read
[`OPENROUTER_FREE_GATE.md`](OPENROUTER_FREE_GATE.md).

The primary R5 request sends only the question. Supporting paragraphs,
decompositions, intermediate answers, accepted answers, dataset identity, and
hop level remain hidden gold metadata.

## Package layout

```text
inference/
|-- cli.py              all inference and derived-artifact commands
|-- audit.py            explicit human-review attestation and hash freezing
|-- config.py           fail-closed TOML configuration
|-- runner.py           selection, budgets, checkpointing, and manifests
|-- scoring.py          deterministic alias scoring and token F1
|-- report.py           R5 aggregate report
|-- calibration.py      fit, freeze, load, and apply isotonic calibration
|-- decisions.py        frozen R7 answer/abstain policies
|-- calibration_report.py  calibration and selective-risk report
|-- composition_report.py  chain-aware R5 composition diagnostics
|-- types.py            provider-neutral request/response boundary
`-- providers/
    |-- base.py         provider protocol
    |-- mock.py         offline deterministic test backend
    |-- ollama.py       native local Ollama adapter
    `-- openrouter.py   OpenRouter Chat Completions adapter
```

Outputs go to `results/r5/<run-id>/`, outside this source package.
Each output directory also contains a persistent
`.calibread-inference.lock`. The runner uses an OS-backed exclusive lock so two
processes cannot append to the same cache; contention fails before provider
preflight. The file safely remains after release and must not be deleted.

## Choose a provider

Use OpenRouter for hosted inference across model families. Use Ollama when the
model and inference must remain on this computer. Both use the same R5 example
selection, prompt, result schema, checkpointing, scoring, and reporting flow.

For OpenRouter, use the masked, process-local PowerShell prompt under
**Commands** below. Never put the literal key in shell history, TOML, source
files, manifests, results, or error logs. The runner records only the configured
environment-variable name.

Ollama's loopback API does not require a key. CalibRead requires a loopback URL,
rejects cloud-model names, never pulls a model, sends no tools or retrieved
context, and records the installed model digest. See [`OLLAMA.md`](OLLAMA.md)
for the precise local-only, closed-book guarantees and limits.

## Configure OpenRouter

The concrete zero-cost qualification config uses the exact slug:

```text
google/gemma-4-26b-a4b-it:free
```

It plans 32 chain-complete development records under a 40-record selection cap.
Use `configs/inference/r5_openrouter_gemma4_26b_free_gate.toml` and follow the
promotion criteria in [`OPENROUTER_FREE_GATE.md`](OPENROUTER_FREE_GATE.md).
Never replace the concrete slug with `openrouter/free`.

The official free-tier limits at this freeze are 50 requests per day and 20
per minute. For this config, `max_requests = 40` is both the plan ceiling and
the hard per-invocation HTTP-attempt cap, retries included, while
`minimum_interval_seconds = 3.1` spaces every attempt. The free-gate guide
explains the nominal ten-call margin and why same-day reruns are unsafe.

The gate pins the currently logprob-capable `darkbloom` endpoint with fallbacks
disabled. Darkbloom is not on OpenRouter's ZDR list and its retention/training
policy is uncertain, so the config uses `data_collection = 'allow'` for public
benchmark questions only. Gold answers and decomposition metadata remain
hidden, and tools/web remain disabled. Recheck endpoint capabilities and policy
before running because free endpoints can change.

`configs/inference/r5_openrouter_pilot.toml` remains a generic template for a
separately chosen paid endpoint. Before a real call, replace:

```toml
requested_model = 'replace-with-concrete-openrouter-model'
prompt_usd_per_million = 0.0
completion_usd_per_million = 0.0
```

Use a concrete model slug, not a moving `latest` alias or `openrouter/auto`.
Copy the selected endpoint's current prices immediately before freezing the run.

For stricter routing, choose one endpoint:

```toml
provider_order = ['chosen-provider-slug']
allow_fallbacks = false
require_parameters = true
```

If an endpoint cannot return token log probabilities, choose a capable endpoint.
Without log probabilities, the current raw score is unavailable and confidence
or calibration claims are prohibited.

## Configure Ollama

Install Ollama and pull the selected non-cloud CPU baseline explicitly:

```powershell
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

The smoke config freezes that exact tag. CalibRead resolves and records its
installed digest. The configuration selects five questions, costs no provider
API money, and does not automatically download a model. It permits a
self-`ABSTAIN` response and is therefore only a secondary wiring check. The
primary R5 configs use the forced-answer prompt documented in the complete
runbook.

## Commands

Run commands from the repository root:

```powershell
$env:PYTHONPATH = 'src'
```

Materialize the strict MuSiQue atomic panel before the R5 study:

```powershell
python -m calibread.r5_atoms
```

The human audits in `data/processed/socrates_v1/audit_sample.csv` and
`data/processed/musique_atomic/audit_sample.csv` remain a STOP gate before the
main study. Use the exact development -> calibration -> test commands in
[`R5_COMPLETE_RUN.md`](R5_COMPLETE_RUN.md); do not use the test split while
choosing a prompt or calibrator.

Concrete OpenRouter free-model gate:

```powershell
$gate = 'configs/inference/r5_openrouter_gemma4_26b_free_gate.toml'
python -m calibread.inference.cli validate-config $gate
python -m calibread.inference.cli plan $gate

$secureKey = Read-Host 'Enter the OpenRouter API key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:OPENROUTER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
  python -m calibread.inference.cli run $gate
} finally {
  Remove-Item Env:OPENROUTER_API_KEY -ErrorAction SilentlyContinue
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
  $keyPointer = [IntPtr]::Zero
  $secureKey = $null
}

python -m calibread.inference.cli score $gate
python -m calibread.inference.cli report $gate
python -m calibread.inference.cli composition-report $gate
```

The key is masked during entry, exists only in process memory and the current
process environment, and its unmanaged copy and environment entry are cleared
after the run. Never paste it into a TOML, source file, command argument,
manifest, or result.

Ollama local smoke run:

```powershell
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli plan configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli run configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli score configs/inference/r5_ollama_smoke.toml
python -m calibread.inference.cli report configs/inference/r5_ollama_smoke.toml
```

Installed command equivalents use `calibread-infer` after `pip install -e .`:

```powershell
calibread-infer validate-config configs/inference/r5_ollama_smoke.toml
calibread-infer plan configs/inference/r5_ollama_smoke.toml
calibread-infer run configs/inference/r5_ollama_smoke.toml
calibread-infer score configs/inference/r5_ollama_smoke.toml
calibread-infer report configs/inference/r5_ollama_smoke.toml
```

## Safety gates

Before an OpenRouter API call, execution refuses placeholder, moving, or
auto-router model identifiers; invalid pricing for the selected paid/free
route; missing input artifacts; missing API-key environment variables; request
counts above the cap; and cost estimates above the budget. A concrete `:free`
route must freeze zero prices and a zero budget; ordinary paid slugs still
require positive frozen prices.

Before an Ollama call, execution refuses a placeholder model, a remote base URL,
a cloud model, or a model not present in the local model list. Ollama prices and
the monetary budget remain zero because no provider is billed.

Each successful generation is appended, flushed, and synced before continuing.
With `resume = true`, completed example IDs are skipped. OpenRouter retries
respect `Retry-After` and bounded exponential backoff. A resume is rejected if
its configuration or input hashes do not match the existing run manifest.

## Outputs

```text
results/r5/<run-id>/
|-- RUN_MANIFEST.json    input hashes, prompt, model, and routing
|-- RUN_SUMMARY.json     completion, failure, and cost summary
|-- generations.jsonl    validated GenerationRecord cache
|-- failures.jsonl       exhausted or invalid requests, when present
|-- scored_results.csv   deterministic answer scores
|-- r5_report.json       overall and dataset-by-level summaries
|-- calibrated_results.csv
|-- calibrated_evaluation.csv
|-- CONDITION_IDENTITY_MANIFEST.json
|-- CALIBRATED_RESULTS_MANIFEST.json
|-- r7_decisions.csv
|-- R7_DECISION_MANIFEST.json
|-- calibration_report.json
|-- r5_chain_results.csv
`-- r5_composition_report.json
```

## Claim limits

The returned model identifier is recorded for every call. A concrete OpenRouter
API slug is still weaker provenance than a public weights commit; do not claim
possession of an immutable model checkpoint. For Ollama, the locally installed
model digest is part of the frozen inference condition.

The generation condition hash is provisional while model-specific R1 and R3
records remain unresolved. That permits R5 development inference, but a final
cross-dimension study must replace it with frozen condition-table links.

Reports treat provider scores as raw until `fit-calibrator` and `calibrate` are
run. The CLI now fits a level-balanced weighted isotonic calibrator only from a
complete calibration-split run, freezes it and its hashes, applies it without
refitting, and produces Brier/ECE/risk-coverage and R7 artifacts. A calibrator
belongs to one exact model condition; do not mix Ollama and OpenRouter outputs,
different prompts, or different model digests under one calibrator.
The calibrated evaluator export uses the SHA-256 of the frozen
`CONDITION_IDENTITY_MANIFEST.json` as its `condition_table_hash`; this binds the
probability rows to the exact target-run model, prompt, decoding, routing, and
source artifacts.

## Offline test

The mock backend makes no network requests and spends no money:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_inference -v
```
