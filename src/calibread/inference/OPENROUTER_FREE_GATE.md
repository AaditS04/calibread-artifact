# OpenRouter free-model qualification gate

This development-only gate checks whether OpenRouter's exact free Gemma route
can satisfy CalibRead's closed-book and raw-confidence requirements before any
larger hosted experiment is designed.

```text
google/gemma-4-26b-a4b-it:free
```

Do not replace it with `openrouter/free`, an auto-router, or a moving `latest`
alias. This gate is an engineering diagnostic, not calibration data, test data,
or publishable R5 evidence.

## Frozen gate configuration

Use:

```text
configs/inference/r5_openrouter_gemma4_26b_free_gate.toml
```

The config freezes:

- the exact model slug above;
- the forced short factual-answer prompt;
- development split only;
- chain-complete one-hop through four-plus-hop selection;
- concurrency 1, timeout 180 seconds, and at most two retries;
- required generated-token log probabilities;
- the current logprob-capable upstream pinned as `darkbloom`, with no routing
  fallbacks;
- no tools, web search, or RAG context;
- `data_collection = 'allow'` for public benchmark questions only; and
- zero token prices and zero provider-cost budget;
- at least 3.1 seconds between HTTP attempts; and
- a 40-attempt per-invocation cap, with retries consuming the same cap.

`promotion_approved = true` authorizes only this small diagnostic run. It does
not approve a later full development, calibration, or test experiment.

The current strict-data dry plan selects 32 records:

| Cell | Records |
|---|---:|
| SOCRATES one-hop | 4 |
| SOCRATES two-hop | 2 |
| MuSiQue atomic one-hop | 20 |
| MuSiQue two-hop | 2 |
| MuSiQue three-hop | 2 |
| MuSiQue four-plus-hop | 2 |
| **Total** | **32** |

The extra one-hop rows are the constituent closure of selected multi-hop
chains. Always rerun `plan`; this table is only the result for the current
versioned artifacts and seed.

The free gate deliberately omits `required_human_audit_manifests`, matching the
local development pilot. It can test transport and model suitability while
human review is pending, but its outputs remain non-evidentiary.

## Data-retention boundary

At this configuration freeze, OpenRouter's live endpoint listing says the
Darkbloom endpoint supports both `logprobs` and `top_logprobs`; the Google AI
Studio route does not. Because CalibRead sets `require_parameters = true`, the
latter is ineligible. The config pins `provider_order = ['darkbloom']`, disables
fallbacks, and uses `data_collection = 'allow'` for the public-data diagnostic.

This is not a zero-data-retention or private-data condition. Send only the
public benchmark questions already selected by the config. Never adapt this
gate for private, proprietary, personal, embargoed, or secret material. Gold
answers, supporting paragraphs, decompositions, and metadata remain hidden by
CalibRead, and closed-book execution still sends `tools = []` and disables the
web plugin. Provider retention and closed-book inference are separate issues.

Darkbloom is not currently on OpenRouter's ZDR provider list, and its precise
retention and prompt-training policy is uncertain. Do not infer either from the
model slug or from another endpoint's policy. Treat provider exposure as an
explicit limitation.

Recheck the exact route's provider and retention policy immediately before a
run because free-route availability, capabilities, and policy can change. The
preflight/run manifest must freeze the returned endpoint identity and advertised
capabilities if the adapter supports doing so. If Darkbloom disappears, loses
logprobs, or its policy is unacceptable, stop or use the local Ollama condition;
do not allow a fallback and do not claim ZDR.

## Zero-price compatibility rule

The exact `:free` route has zero published token prices, so the config records
zero rather than a fake positive number. The execution validator must accept
that combination only for a concrete `:free` model while retaining a zero cost
cap. It must continue rejecting zero prices for ordinary paid OpenRouter slugs.

Start with `validate-config`. If the checkout reports:

```text
OpenRouter execution requires positive frozen pricing values
```

stop. That checkout does not yet support truthful free-route pricing. Do not
insert an invented price, raise the cost budget, or weaken another safety
guard. `plan` is still safe and makes no API request, but `run` must wait for the
free-price validation rule to be implemented and tested.

## Free-tier quota gate

At this configuration freeze, OpenRouter documents 50 free-model requests per
day and 20 requests per minute. The 32 selected records leave room for
retries because `budget.max_requests = 40` is enforced both as the planning
ceiling and as a hard HTTP-attempt cap for one invocation. Retries consume the
same counter. `provider.minimum_interval_seconds = 3.1` spaces all initial and
retry attempts. Together these controls reserve a nominal ten-call daily margin
and stay below 20 attempts per minute.

Before running, verify that `validate-config` accepts these controls and that
`plan` displays the 40-attempt cap and 3.1-second interval. If it does not,
stop: that checkout does not yet enforce the required free-tier safeguards.

CalibRead cannot see calls made by another program or browser using the same
OpenRouter account, so the ten-call margin is not proof that 40 calls remain.
The attempt counter is per invocation, not an account-wide or persistent daily
ledger. Do not use the account concurrently, and do not launch a second
invocation during the same provider quota period after a quota stop or
attempt-cap stop. Resume the unchanged run only after the provider quota has
reset; OpenRouter's public limit statement does not establish a UTC reset
boundary.

A complete R5 development/calibration/test workload cannot fit within this free
tier as one stable experimental condition. The free route is only a 32-record
qualification gate; use a suitably provisioned hosted endpoint or the local
Ollama path for the full experiment.

## Commands

Run from the repository root:

```powershell
$env:PYTHONPATH = 'src'
$gate = 'configs/inference/r5_openrouter_gemma4_26b_free_gate.toml'

python -m calibread.inference.cli validate-config $gate
python -m calibread.inference.cli plan $gate
```

Set the key only in the current process environment. Do not put it in the TOML,
a command argument, source code, documentation, a manifest, or a result file:

```powershell
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
```

The prompt masks keyboard input and avoids placing the literal key in shell
history. The provider still requires plaintext in process memory while the
request is made. The `finally` block removes the environment entry, zeroes and
frees the unmanaged string, and clears the temporary variables.

Only after `RUN_SUMMARY.json` says the complete frozen selection succeeded:

```powershell
python -m calibread.inference.cli score $gate
python -m calibread.inference.cli report $gate
python -m calibread.inference.cli composition-report $gate --bootstrap-samples 2000
```

Outputs are written to:

```text
results/r5/r5_openrouter_gemma4_26b_free_gate_v1/development_gate/
```

## Promotion decision

Promote this model to a separately versioned, larger development condition only
if all of the following pass:

- all 32 planned example IDs complete with no permanent failures;
- one nonempty returned-model identity is used throughout and the routed
  upstream provider identity is recorded;
- every response returns generated-token log probabilities, producing the
  uniform source `mean_generated_token_log_probability`;
- scores are finite and not constant;
- answers are nonempty, short factual responses, with no model-emitted
  `ABSTAIN`, tool call, citation, or web-use evidence;
- deterministic scoring yields at least one correct and one incorrect answer,
  so a later calibration study is not already degenerate;
- the run remains within 40 HTTP attempts for the invocation, respects the
  3.1-second spacing, and reports zero configured provider cost;
  and
- the run manifest records the pinned Darkbloom route, advertised logprob
  capabilities, intentional public-data `data_collection = 'allow'` condition,
  and unknown-retention limitation; and
- manual inspection finds no prompt leakage, explanations, or malformed answer
  pattern that would require changing the prompt.

If any hard gate fails, do not disable log probabilities, tools/web guards, or
identity checks, and do not misrepresent the declared retention condition to
make the model pass. Choose a different concrete endpoint or model and use a
new run ID.

If it passes, record the promotion decision before creating new full
development, calibration, and test configs. Those configs must start with
`promotion_approved = false`; change it only after the decision is documented.
They need their own parent experiment ID and their own calibrator. Never combine
this hosted model's outputs or calibrator with the Ollama Qwen condition.

## Claim limits

An exact OpenRouter slug and returned model identity are still weaker
provenance than a public immutable weights commit. Free-route availability,
routing, rate limits, and upstream infrastructure can change. Preserve the run
manifest and returned identities, and report this limitation even if the gate
passes. Darkbloom's uncertain retention/training policy and non-ZDR status mean
this is not a ZDR experiment. A 32-record diagnostic is not an accuracy or
calibration result.
