# Complete R5 runbook

This is the canonical runbook for the CalibRead R5 composition experiment with
the committed local Ollama condition. It covers data materialization,
chain-complete inference, scoring, calibration, R7 decisions, and composition
reporting. Run every command from the repository root.

The underlying LLM is not trained or fine-tuned. Only a small weighted isotonic
mapping is fitted on the calibration split after model answers have been cached
and scored.

## Non-negotiable order

```text
Materialize and audit data
            |
            v
Development pilot and full development
            |
            v
Freeze model, prompt, score, calibrator method, and analyses
            |
            v
Calibration generation and scoring
            |
            v
Fit and freeze the calibrator
            |
            v
Untouched test generation, all levels complete
            |
            v
Unblind once: score, calibrate, decide R7, and report
```

Within each inference run, selected examples are ordered as `one_hop`,
`two_hop`, `three_hop`, then `four_plus_hop`. Chain-complete selection may add
one-hop constituents needed by a selected multi-hop chain, so the authoritative
request and cell counts are always the output of `plan`, not
`limit_per_level` multiplied by four.

Never inspect one-hop test accuracy and then change the condition before the
later levels. During test generation, inspect only operational state such as
`RUN_SUMMARY.json`, failures, remaining count, and returned model identity.
Run `score` only after the complete frozen selection has been generated.

## 1. Prepare the environment

```powershell
$env:PYTHONPATH = 'src'
ollama --version
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/version
```

The committed configs use the already-installed local model:

```text
qwen3:4b-instruct-2507-q4_K_M
```

CalibRead does not pull a model. The Ollama adapter requires a loopback URL,
rejects cloud models, sends no tools or retrieved context, and records the
installed model digest.

To qualify the separate hosted free Gemma condition before designing any large
OpenRouter study, use [`OPENROUTER_FREE_GATE.md`](OPENROUTER_FREE_GATE.md). Its
32 development requests, parent experiment, model identity, and eventual
calibrator remain completely separate from this Ollama Qwen condition.

## 2. Materialize the MuSiQue atomic probes

The composition report needs independently answerable one-hop probes for every
retained MuSiQue chain. Build them from the processed MuSiQue records:

```powershell
python -m calibread.r5_atoms
```

The command writes:

```text
data/processed/musique_atomic/
|-- examples.jsonl
|-- workloads.jsonl
|-- composite_examples.jsonl
|-- composite_workloads.jsonl
|-- audit_sample.csv
|-- DATA_CARD.md
`-- ATOMIC_MANIFEST.json
```

It resolves structural `#N` references with earlier gold step answers,
deduplicates stable upstream steps, preserves every parent-chain link, removes
chains that would cause cross-split atomic-question reuse, validates schemas,
and hashes its inputs and outputs. Gold replacements are used only to author a
standalone atomic question; the model receives only that question.

The current materialization starts from 22,355 MuSiQue composite chains,
retains a strict panel of 22,126, and excludes 229 chains touching 41 atomic
question hashes reused across splits. It emits 17,118 unique atomic probes and
finishes with zero cross-split resolved-question hashes. These counts belong to
the current `ATOMIC_MANIFEST.json`; regenerate them after any input change.

All four primary configs pair the atomic records with the strict filtered
composites:

```text
data/processed/musique_atomic/composite_examples.jsonl
data/processed/musique_atomic/composite_workloads.jsonl
```

Do not substitute the unfiltered `data/processed/musique/` composite files.

### Human-audit STOP gate

The materializer deliberately records the human review as pending. Check it:

```powershell
$atomic = Get-Content -Raw data/processed/musique_atomic/ATOMIC_MANIFEST.json | ConvertFrom-Json
$socrates = Get-Content -Raw data/processed/socrates_v1/REFINEMENT_MANIFEST.json | ConvertFrom-Json
@{
  musique_atomic = $atomic.checks.human_audit
  socrates_v1 = $socrates.checks.human_audit
}
```

Review every row in both worksheets:

```text
data/processed/musique_atomic/audit_sample.csv
data/processed/socrates_v1/audit_sample.csv
```

Check them for:

- resolved question grammaticality and independence;
- equivalence of the accepted answer and aliases;
- correct supporting title and parent-chain link;
- accidental ambiguity, shortcut wording, or unresolved placeholder; and
- correct development/calibration/test assignment.

The reviewer must change each worksheet row's `review_status` to `approved`
only after checking it. If even one row cannot be approved, stop: correct or
exclude the affected data in a new materialized version instead of approving
the old artifact. When every row in both worksheets is explicitly approved,
record the two attestations with a named, versioned review protocol:

```powershell
python -m calibread.inference.cli finalize-audit `
  data/processed/socrates_v1/REFINEMENT_MANIFEST.json `
  --reviewer 'Reviewer Name' --protocol 'r5-human-audit-v1'

python -m calibread.inference.cli finalize-audit `
  data/processed/musique_atomic/ATOMIC_MANIFEST.json `
  --reviewer 'Reviewer Name' --protocol 'r5-human-audit-v1'
```

`finalize-audit` never judges or auto-approves a row. It refuses pending or
rejected rows, then freezes the reviewer, protocol, UTC time, reviewed-row
count, worksheet bytes, and SHA-256 in the manifest. It also refuses to
overwrite an existing approval. A later worksheet edit invalidates the run
gate until a new versioned review is produced.

`human_audit = pending` for either source is a hard STOP before the full
development, calibration, or test runs and before any publication claim. A
small pilot may be used only as an engineering diagnostic while review is
pending; label it non-evidentiary. Human approval is intentionally external and
cannot be generated by this code. Do not silently edit questions after
inference. A material change requires a new versioned release, regenerated
hashes, new plans, and new run IDs.

This gate is enforced in code. The full development, calibration, and test
configs list both files under `run.required_human_audit_manifests`; `run` fails
before the first model request unless each manifest explicitly contains
`checks.human_audit = approved`. `validate-config` and `plan` remain available
while review is pending, as does the non-evidentiary pilot. After actual human
review, use the attestation command above; never change the manifest field
merely to bypass the gate. The runner revalidates every approved worksheet and
freezes its manifest path, SHA-256, status, worksheet hash, reviewer, and
review time into `RUN_MANIFEST.json`.

## 3. Validate and plan before generating

The four committed configs share the exact model, prompt, decoding, score, and
parent experiment identity:

```text
configs/inference/r5_ollama_development_pilot.toml
configs/inference/r5_ollama_development.toml
configs/inference/r5_ollama_calibration.toml
configs/inference/r5_ollama_test.toml
```

Validate each config and compute its selection before any long run:

```powershell
$configs = @(
  'configs/inference/r5_ollama_development_pilot.toml',
  'configs/inference/r5_ollama_development.toml',
  'configs/inference/r5_ollama_calibration.toml',
  'configs/inference/r5_ollama_test.toml'
)

foreach ($config in $configs) {
  python -m calibread.inference.cli validate-config $config
  python -m calibread.inference.cli plan $config
}
```

Treat each plan as the authoritative count and budget record. It reports:

- requests and dataset-by-level counts;
- selected example and chain counts;
- hashes of ordered example IDs, chain IDs, and chain membership;
- estimated prompt and maximum completion tokens; and
- the request and monetary caps.

For orientation, fresh plans against the current strict artifacts produced the
following snapshot on 2026-08-14:

| Phase | SOCRATES 1-hop | SOCRATES 2-hop | MuSiQue atomic 1-hop | MuSiQue 2-hop | MuSiQue 3-hop | MuSiQue 4+-hop | Requests |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development pilot | 40 | 20 | 167 | 20 | 20 | 20 | 287 |
| Development | 2,546 | 1,273 | 3,404 | 3,082 | 1,019 | 316 | 11,640 |
| Calibration | 4,798 | 2,399 | 5,102 | 4,617 | 1,525 | 472 | 18,913 |
| Test | 7,120 | 3,560 | 8,612 | 7,753 | 2,556 | 786 | 30,387 |

The three non-pilot splits currently total 60,940 inference requests. This
table is a convenience snapshot, not a frozen substitute for `plan`: if any
input, materializer, seed, level, or chain-selection setting changes, discard
the table and use the newly printed counts and hashes.

Counts can change when the versioned data artifacts change. Do not copy an old
count into a new run. The runner freezes the fresh plan and input hashes into
`RUN_MANIFEST.json`.

The configs set `chain_complete = true`. When a selected chain is multi-hop,
the runner includes every configured constituent atom in the same split. It
also sorts the final request sequence in the canonical hop order.

## 4. Run the development pilot

The pilot uses the forced-answer prompt and a chain-complete sample. It is the
place to detect formatting, runtime, score, and floor/ceiling failures:

```powershell
$pilot = 'configs/inference/r5_ollama_development_pilot.toml'

python -m calibread.inference.cli validate-config $pilot
python -m calibread.inference.cli plan $pilot
python -m calibread.inference.cli run $pilot
python -m calibread.inference.cli score $pilot
python -m calibread.inference.cli report $pilot
python -m calibread.inference.cli composition-report $pilot --bootstrap-samples 2000
```

Before promoting the condition, verify on development data that:

- `RUN_SUMMARY.json` says `completion_status = complete`;
- the returned model identity and Ollama digest are uniform;
- there are no missing token log probabilities;
- outputs are short factual answers rather than explanations;
- both correct and incorrect answers exist;
- raw scores are finite and not constant; and
- accuracy is not at a degenerate floor or ceiling in the intended cells.

### Current local 4B pilot decision

The clean 2026-08-14 pilot completed 287/287 requests with zero provider
failures, but it failed this promotion gate. Overall exact-match accuracy was
10.1%; SOCRATES two-hop and MuSiQue two-/three-hop accuracy were 0%, MuSiQue
four-plus-hop accuracy was 5%, and no sampled composite chain had all of its
atoms correct. Thirty-three outputs hit the 64-token cap. This condition is a
non-evidentiary feasibility baseline, not a candidate for the full study.

Accordingly, the committed full development, calibration, and test configs set
`promotion_approved = false`. They still validate and plan, but `run` refuses
before human-audit evaluation, provider preflight, or any artifact write. Do
not change the flag in place. Create a new parent experiment and phase configs
after a stronger model passes a new development pilot. The exact artifact
hashes and stop decision are preserved in `docs/decision_log.md`.

The old `r5_ollama_smoke.toml` allowed the model to emit `ABSTAIN`. That run is
a secondary transport/wiring check only. Its raw score can be confidence in
emitting `ABSTAIN`, so it must not be pooled with the forced-answer R5 study or
used to fit its calibrator.

## 5. Run full development and freeze choices

After the human-audit gate passes and the pilot is acceptable:

```powershell
$development = 'configs/inference/r5_ollama_development.toml'

python -m calibread.inference.cli validate-config $development
python -m calibread.inference.cli plan $development
python -m calibread.inference.cli run $development
python -m calibread.inference.cli score $development
python -m calibread.inference.cli report $development
python -m calibread.inference.cli composition-report $development --bootstrap-samples 2000
```

Use development results to make and record the last choices about the model,
prompt, answer normalization, raw score, calibrator family, bootstrap settings,
and planned comparisons. Then freeze them. If any of these change later, use a
new `parent_experiment_id`, new run IDs, and a new calibrator.

The committed primary prompt requires the best factual answer and forbids
`ABSTAIN`. R7 abstention is applied post hoc from calibrated confidence, without
another LLM call.

## 6. Generate and score the calibration split

```powershell
$calibration = 'configs/inference/r5_ollama_calibration.toml'

python -m calibread.inference.cli validate-config $calibration
python -m calibread.inference.cli plan $calibration
python -m calibread.inference.cli run $calibration
python -m calibread.inference.cli score $calibration
python -m calibread.inference.cli report $calibration
python -m calibread.inference.cli composition-report $calibration --bootstrap-samples 2000
```

`fit-calibrator` is permitted only when the config says
`run.split = 'calibration'`. It also requires a complete scored run, both
correctness classes, uniform raw-score source, uniform model identity, matching
input hashes, and matching generation/scoring identities.

Fit and freeze the level-balanced global isotonic calibrator:

```powershell
python -m calibread.inference.cli fit-calibrator $calibration
```

With the committed output directory, the frozen object is:

```powershell
$calibrator = 'results/r5/r5_qwen3_4b_forced_v1/calibration/calibration/CALIBRATOR.json'
```

Its directory contains:

```text
calibration/
|-- CALIBRATOR.json
|-- CALIBRATION_MANIFEST.json
`-- calibration_metrics.json
```

The metrics written while fitting are in-sample diagnostics, not held-out
evidence. Applying the calibrator to the calibration run is optional and is
useful only to exercise the downstream pipeline:

```powershell
python -m calibread.inference.cli calibrate $calibration --calibrator $calibrator
python -m calibread.inference.cli decide-r7 $calibration --calibrator $calibrator
python -m calibread.inference.cli calibration-report $calibration --calibrator $calibrator
python -m calibread.inference.cli composition-report $calibration `
  --calibrated results/r5/r5_qwen3_4b_forced_v1/calibration/calibrated_results.csv `
  --bootstrap-samples 2000
```

Do not select a different calibrator after seeing test correctness.

## 7. Generate the untouched test split

Before starting test, record that the development decisions, calibrator object
hash, analysis commands, and expected test selection hashes are frozen. Then:

```powershell
$test = 'configs/inference/r5_ollama_test.toml'

python -m calibread.inference.cli validate-config $test
python -m calibread.inference.cli plan $test
python -m calibread.inference.cli run $test
```

If the process stops, run the same command again:

```powershell
python -m calibread.inference.cli run $test
```

`resume = true` skips completed example IDs. Resume fails closed if the config,
input artifacts, frozen selection, prompt, or manifest identity changes. Do not
delete a partial run, change a TOML, or create a replacement selection because
some test outputs look difficult.

During this stage, inspect only operational fields. Do not inspect answer
correctness or per-level accuracy. Continue until `RUN_SUMMARY.json` reports a
complete run and zero remaining requests.

## 8. Unblind once and produce test artifacts

Only after every test level has finished under the same manifest:

```powershell
python -m calibread.inference.cli score $test
python -m calibread.inference.cli report $test
python -m calibread.inference.cli calibrate $test --calibrator $calibrator
python -m calibread.inference.cli decide-r7 $test --calibrator $calibrator
python -m calibread.inference.cli calibration-report $test --calibrator $calibrator
python -m calibread.inference.cli composition-report $test `
  --calibrated results/r5/r5_qwen3_4b_forced_v1/test/calibrated_results.csv `
  --bootstrap-samples 2000
```

`calibrate` never refits. It requires the test model snapshot, prompt, decoding,
routing, closed-book settings, and raw-score source to match the frozen
calibrator condition. Dataset-by-hop groups absent from calibration support are
marked unsupported. R7 then fails closed to abstention for those rows.

`calibration-report` also materializes the fixed R7 threshold grid
`0.50, 0.70, 0.90, 0.95, 0.99`. Calling `decide-r7` explicitly is useful for a
clear audit trail but does not make another model request.

## 9. Output tree

The parent experiment is written under:

```text
results/r5/r5_qwen3_4b_forced_v1/
|-- development_pilot/
|-- development/
|-- calibration/
|   `-- calibration/
|       |-- CALIBRATOR.json
|       |-- CALIBRATION_MANIFEST.json
|       `-- calibration_metrics.json
`-- test/
```

Depending on the commands run, each inference directory contains:

```text
RUN_MANIFEST.json
RUN_SUMMARY.json
generations.jsonl
failures.jsonl                    # only when failures occurred
scored_results.csv
r5_report.json
calibrated_results.csv
calibrated_evaluation.csv
CONDITION_IDENTITY_MANIFEST.json
CALIBRATED_RESULTS_MANIFEST.json
r7_decisions.csv
R7_DECISION_MANIFEST.json
calibration_report.json
r5_chain_results.csv
r5_composition_report.json
```

`generations.jsonl` is append-only and synced after every successful request.
Manifests bind derived results to the model condition, configuration, inputs,
selection, raw-score source, and calibrator object.
`CONDITION_IDENTITY_MANIFEST.json` is the deterministic target-run condition
table. Its actual file SHA-256 becomes `condition_table_hash` in the
evaluator-ready calibrated CSV and is frozen again in
`CALIBRATED_RESULTS_MANIFEST.json`; changed existing contents cannot be
silently overwritten.

`.calibread-inference.lock` is a persistent OS-backed lock inode, not a result.
Only one process may own a run directory. A concurrent `run` fails immediately
and reports the live owner; normal exit, exceptions, and process death release
the kernel lock. Do not delete the file or launch a second writer to speed up a
run. Resume by invoking the unchanged command only after the prior process has
ended.

## 10. What the reports mean

`r5_report.json` is the raw-score accuracy report. It reports overall and
dataset-by-hop results but does not turn the raw score into a probability.

`calibration_report.json` reports, overall and by supported R5 group:

- accuracy;
- raw-score correctness AUROC;
- Brier score and binary log loss;
- ECE and adaptive calibration error;
- risk-coverage curve and AURC; and
- answer/abstain performance at every frozen R7 threshold.

`r5_composition_report.json` uses complete chains and their atomic probes to
report:

- chain accuracy and all-atoms-correct rate;
- synthesis loss;
- factorized/product diagnostics;
- an empirical atomic-error union-bound diagnostic; and
- connected-chain-cluster bootstrap intervals.

The factorized and union-bound quantities are diagnostics, not assertions that
atomic events are independent. Synthesis loss is descriptive because it
conditions on all atoms being correct.

## 11. Source-confounding limits

Interpret each source internally:

- SOCRATES supports its paired one-hop versus two-hop comparison.
- MuSiQue supports its two-hop, three-hop, and four-plus-hop comparisons, with
  materialized atomic probes used for chain composition diagnostics.

Do not present a pooled comparison such as SOCRATES one-hop versus MuSiQue
four-plus-hop as a pure depth effect. Dataset source, construction, answer type,
and difficulty differ. The composition report therefore exposes
dataset-by-level results and records this limitation.

## 12. Rules for reruns

- A normal interruption: rerun the unchanged `run` command and resume.
- A changed model digest, prompt, decoding option, dataset hash, selection,
  answer scorer, or raw-score definition: create a new parent experiment and
  refit a new calibrator.
- A calibration-only implementation bug found before test unblinding: fix it,
  version the method, refit, and record the change.
- Any analytical change after test unblinding: label it exploratory; do not
  replace the preregistered result.
- Never combine the self-`ABSTAIN` smoke outputs, forced-answer outputs,
  different Ollama digests, or OpenRouter outputs under one calibrator.
