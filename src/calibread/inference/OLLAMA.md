# Running CalibRead locally with Ollama

Ollama lets CalibRead run an already-downloaded language model on this computer.
A GPU is optional: Ollama can use the CPU, but larger models can be very slow and
need substantial RAM. Start with a small model and the five-question smoke run.

The project does not train or fine-tune the LLM. It sends each closed-book R5
question to a frozen local model, records the answer and token log probabilities,
then scores cached answers. After local setup, follow
[`R5_COMPLETE_RUN.md`](R5_COMPLETE_RUN.md) for the complete development,
calibration, test, R7, and composition workflow.

## 1. Install Ollama on Windows

The simplest supported installation is the [official Windows
installer](https://docs.ollama.com/windows). If Windows Package Manager offers
Ollama on your machine, install it from PowerShell:

```powershell
winget install --id Ollama.Ollama --exact
```

Alternatively, download `OllamaSetup.exe` from the official Ollama Windows page
and run it. Close and reopen PowerShell after installation so the updated `PATH`
is visible.

Verify the command and local API:

```powershell
ollama --version
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/version
```

If the API is not running, launch Ollama from the Start menu. Recent Windows
installations normally run it in the background.

## 2. Update an existing installation

The Windows app normally downloads updates and applies them after it is
restarted. Exit Ollama from its taskbar icon, start it again, and check:

```powershell
ollama --version
Invoke-RestMethod http://127.0.0.1:11434/api/version
```

If that does not update it, run the latest official `OllamaSetup.exe` over the
existing installation, or use:

```powershell
winget upgrade --id Ollama.Ollama --exact
```

## 3. Download one model explicitly

CalibRead never pulls models automatically. This is deliberate: a research run
must not silently switch weights or start a cloud-backed model. Choose and pull a
model yourself. The current 8 GB CPU-only laptop baseline uses:

```powershell
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama list
```

This exact Q4 tag is the selected resource-constrained research baseline, not a
claim that it is sufficient as the study's only model. Do not use a cloud model.
Confirm the exact installed name shown by `ollama list`; the committed smoke
configuration currently contains:

```toml
requested_model = 'qwen3:4b-instruct-2507-q4_K_M'
```

## 4. What strict local-only closed-book means here

For an Ollama run, CalibRead:

- accepts only a loopback Ollama URL such as `127.0.0.1` or `localhost`;
- rejects known cloud-model naming forms;
- requires the model to already appear in the local model list;
- never calls the Ollama pull endpoint;
- sends only the system instruction and question, with no tools, web search,
  RAG documents, supporting paragraphs, decompositions, or gold answers;
- records the installed model digest in the run provenance; and
- requires returned token log probabilities when confidence analysis is enabled.

These controls establish closed-book behavior at the inference application
boundary. They do not prove that a model never memorized a benchmark during its
original pretraining, so benchmark contamination remains a separate research
limitation.

Model digest pinning identifies the exact local artifact used in a run. If a tag
later points to different weights, its digest changes and it must be treated as a
new model condition and a new run.

## 5. Run the five-request smoke test

Run every command from the repository root. Set the Python package path for the
current PowerShell session:

```powershell
$env:PYTHONPATH = 'src'
```

Validate the TOML without generating answers:

```powershell
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_smoke.toml
```

Inspect the selected cells, token bound, request count, and zero provider cost:

```powershell
python -m calibread.inference.cli plan configs/inference/r5_ollama_smoke.toml
```

Run or resume local inference:

```powershell
python -m calibread.inference.cli run configs/inference/r5_ollama_smoke.toml
```

Score the cached answers:

```powershell
python -m calibread.inference.cli score configs/inference/r5_ollama_smoke.toml
```

Generate the R5 aggregate report:

```powershell
python -m calibread.inference.cli report configs/inference/r5_ollama_smoke.toml
```

The smoke configuration selects one example from each available R5 cell:

```text
SOCRATES one-hop: 1
SOCRATES two-hop: 1
MuSiQue two-hop: 1
MuSiQue three-hop: 1
MuSiQue four-plus-hop: 1
```

That is five local inference requests. It is a wiring check, not enough data for
a scientific result. It also uses the older self-`ABSTAIN` prompt, so its raw
score may measure confidence in emitting `ABSTAIN`. Do not pool it with the
forced-answer R5 runs or use it to fit their calibrator.

## 6. Move from smoke to the complete R5 workflow

The committed primary configs are:

```text
configs/inference/r5_ollama_development_pilot.toml
configs/inference/r5_ollama_development.toml
configs/inference/r5_ollama_calibration.toml
configs/inference/r5_ollama_test.toml
```

They share one forced-answer prompt and parent experiment identity, request
complete constituent chains, and process one-hop before two-hop, three-hop, and
four-plus-hop records. The small development pilot starts with:

```powershell
$env:PYTHONPATH = 'src'
python -m calibread.r5_atoms
python -m calibread.inference.cli validate-config configs/inference/r5_ollama_development_pilot.toml
python -m calibread.inference.cli plan configs/inference/r5_ollama_development_pilot.toml
python -m calibread.inference.cli run configs/inference/r5_ollama_development_pilot.toml
python -m calibread.inference.cli score configs/inference/r5_ollama_development_pilot.toml
python -m calibread.inference.cli report configs/inference/r5_ollama_development_pilot.toml
python -m calibread.inference.cli composition-report configs/inference/r5_ollama_development_pilot.toml
```

The SOCRATES and materialized-atomic human audits remain a STOP gate before the
full study. Do not open the test labels while tuning on development or fitting
on calibration. The full commands, calibrator path, resume rules, and output
tree are in the complete runbook.

The 2026-08-14 local 4B forced-answer pilot completed but failed the promotion
gate because multi-hop accuracy was at a floor. The committed full 4B phase
configs are now execution-blocked with `promotion_approved = false`. Keep this
result as a CPU feasibility baseline; choose a stronger development condition
instead of enabling those configs in place.

## 7. Outputs and reproducibility

Outputs are written under `results/r5/r5_ollama_smoke_001/`. Preserve the run
manifest, generation cache, and installed-model digest. Do not reuse the output
directory after changing the model, digest, prompt, decoding options, datasets,
or selection seed; create a new run ID instead.

Ollama has no per-token API charge, so the configured monetary budget and token
prices are zero. Local computation still consumes time, electricity, RAM, and
possibly GPU resources.

## 8. Calibration rule

A calibrator is tied to one exact model digest, prompt, decoding configuration,
and raw-score definition. Do not fit a global calibrator with one Ollama model
and apply it to another model, or mix Ollama and OpenRouter outputs under one
calibrator. Fit and freeze a separate calibrator for each model condition; only
then evaluate its transfer across R1-R6 complexity groups.

## 9. Common problems

`ollama` is not recognized:

- close and reopen PowerShell;
- check `%LOCALAPPDATA%\Programs\Ollama`;
- reopen Ollama from the Start menu; or
- rerun the official installer.

The local API cannot be reached:

- start the Ollama desktop app;
- verify `Invoke-RestMethod http://127.0.0.1:11434/api/version`; and
- keep `base_url = 'http://127.0.0.1:11434/api'` in the CalibRead config.

The model is not installed:

- run `ollama list`;
- explicitly pull the desired non-cloud model; and
- copy its exact name into `requested_model`.

Inference is too slow or runs out of memory:

- use a smaller model;
- keep the smoke run at one example per level; and
- close memory-heavy applications before retrying.

Token log probabilities are missing:

- update Ollama;
- verify the selected model/runtime combination supports log probabilities; and
- do not make confidence or calibration claims from a run that lacks them.

Do not set `require_logprobs = false` for a scientific calibration run merely to
bypass this check. Without the generated-token log probabilities, CalibRead's
current raw confidence score is unavailable.
