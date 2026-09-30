# R5 data card — synthesis depth

Status: structurally materialized and lineage-checked; SOCRATES and MuSiQue
atomic human audits remain pending. The pending audits are a STOP gate for the
confirmatory study and publication claims.

R5 asks whether factual reliability and calibrated confidence degrade when a
question requires composing more indispensable facts. Depth is a property of
the audited evidence graph, not the number of reasoning tokens a model happens
to generate.

## Sources and roles

- `socrates_v1` supplies paired one-hop facts and two-hop composites from the
  same synthetic chains. It is the primary controlled one-hop versus two-hop
  comparison.
- `musique` supplies natural-language two-hop, three-hop, and four-plus-hop
  composite questions.
- `musique_atomic` materializes the MuSiQue decomposition steps as standalone
  one-hop probes. They are used to ask whether a composite succeeds when all
  of its constituent facts are individually answerable.

Source licensing, redistribution permission, attribution, revisions, and raw
hashes are recorded in the source registry and each processed source card.
SOCRATES is redistributed under CC BY 4.0. The MuSiQue derivative retains its
upstream licensing and attribution requirements.

## Frozen R5 levels

```text
one_hop        audited depth = 1
two_hop        audited depth = 2
three_hop      audited depth = 3
four_plus_hop  audited depth >= 4
```

The raw depth and canonical level are stored in every `WorkloadRecord`. A
multi-hop workload also stores its chain ID, ordered constituent example IDs,
and a hash of the chain specification.

## MuSiQue atomic construction

Run from the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m calibread.r5_atoms
```

The current `ATOMIC_MANIFEST.json` records the result of this deterministic
materialization:

- 22,355 input composite chains;
- 22,126 strict retained composite chains;
- 229 excluded chains touching 41 atomic question hashes reused across splits;
- 17,118 unique standalone atomic probes;
- 52,500 retained decomposition occurrences and parent links; and
- zero final resolved-question hashes crossing splits.

These are the current versioned artifact counts, not universal properties of
MuSiQue. Regenerate the manifest and inference plans after any input or
materializer change.

Structural references such as `#1` are replaced with the earlier gold step
answer to create an independently answerable question. Stable upstream step IDs
deduplicate facts while `parent_chain_links` preserves every retained parent,
step position, source row, and split. The model never receives the replacement
process, parent chain, supporting paragraph, decomposition, or gold answer.

The materializer fails closed on unresolved or forward placeholders, malformed
positions, constituent mismatches, conflicting answers or supporting titles,
cross-split stable facts, and cross-split resolved-question hashes. It removes
an entire parent chain rather than reassigning it when strict question-hash
separation would otherwise fail.

## Exact inference inputs

The complete R5 configs use:

```text
data/processed/socrates_v1/examples.jsonl
data/processed/socrates_v1/workloads.jsonl

data/processed/musique_atomic/examples.jsonl
data/processed/musique_atomic/workloads.jsonl

data/processed/musique_atomic/composite_examples.jsonl
data/processed/musique_atomic/composite_workloads.jsonl
```

The last two paths are the strict filtered MuSiQue panel. Do not substitute the
unfiltered `data/processed/musique/` composites in a confirmatory run.

`chain_complete = true` makes selection take the transitive constituent closure
of every selected multi-hop question. It rejects missing or cross-split
constituents. A per-level limit counts chain units, not individual generated
rows, so the output of `python -m calibread.inference.cli plan <config>` is the
authoritative request count.

## Split and lineage controls

Development, calibration, and test are separated by transitive lineage. The
protected identities include chain, source fact, and normalized question hash.
MuSiQue atomic construction additionally removes parent chains responsible for
cross-split resolved-question reuse. The inference manifest freezes:

- ordered selected-example hash;
- selected-chain hash;
- chain-membership hash;
- exact Example and WorkloadRecord hashes; and
- model, prompt, decoding, provider, and raw-score identity.

The required experimental order is development, then calibration, then sealed
test. The runner processes one-hop, two-hop, three-hop, and four-plus-hop in
that order, but test labels must not be inspected between levels.

## Human-audit STOP gate

Two deterministic review samples remain pending:

```text
data/processed/socrates_v1/audit_sample.csv
data/processed/musique_atomic/audit_sample.csv
```

The corresponding manifests currently record `checks.human_audit = pending`.
Reviewers must verify question validity, answer equivalence, chain/decomposition
links, hop labels, shortcut or ambiguity problems, and split assignment. A
small inference pilot may be used as a non-evidentiary software diagnostic, but
do not run the confirmatory calibration/test sequence or make publication
claims until the reviews are completed in a versioned audit record. Human
approval cannot be generated automatically by this repository. After genuine
review, a person must explicitly set `checks.human_audit = approved` in both
versioned manifests. The full-run configs enforce those values before any model
request and freeze the manifest hashes as run evidence; the pilot remains
available only as a non-evidentiary diagnostic.

## Scoring and reports

Atomic and composite answers use the same deterministic accepted-alias exact
match, with token F1 retained as a diagnostic. The primary raw confidence is
mean generated-token log probability. A level-balanced weighted isotonic
calibrator is fitted on the calibration split only.

The chain-aware report includes:

- atomic accuracy and chain accuracy;
- all-constituents-correct rate;
- synthesis loss conditional on all atoms being correct;
- product/factorized and empirical union-bound diagnostics;
- optional product-confidence diagnostics from calibrated atom scores; and
- 95% bootstrap intervals clustered by connected chains sharing an atom.

The factorized and union-bound quantities are diagnostics, not independence
facts or guarantees. Conditioning synthesis loss on all atoms correct is also
descriptive rather than causal.

## Interpretation limits

Analyze SOCRATES and MuSiQue separately. SOCRATES supports its internal paired
one-hop/two-hop contrast. MuSiQue supports its internal depth gradient and
atomic-versus-composite chain diagnostics. A pooled SOCRATES one-hop versus
MuSiQue four-plus-hop contrast is source-confounded and cannot be reported as a
pure causal effect of depth.

For exact commands and artifact paths, see
`src/calibread/inference/R5_COMPLETE_RUN.md`.
