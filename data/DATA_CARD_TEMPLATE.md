# CalibRead dataset card: <dataset/version>

## Source and rights

- Source URL and immutable revision:
- License and redistribution decision:
- Download/construction date:
- Construction script and code revision:
- Raw and derived manifest hashes:

## P03 dimension coverage

| Dimension | Raw field/source | Frozen levels represented | Missingness/exclusions |
|---|---|---|---|
| R1 knowledge frequency | | | |
| R2 precision requirement | | | |
| R3 knowledge recency | | | |
| R4 query ambiguity | | | |
| R5 synthesis depth | | | |
| R6 domain specificity | | | |
| R7 policy threshold | derived from cached scores | declared thresholds | not applicable |

For R1, state whether the value is actual training-corpus exposure or a named proxy. For R3, cite
the model cutoff evidence and retain event dates. For R4, attach interpretation annotations. For
R5, retain chain and constituent IDs. For R6, version the taxonomy and specificity rule.

## Question and answer construction

- Prompt-independent question source:
- Answer types and alias policy:
- Numeric tolerance/date granularity rules:
- Candidate universe or generator:
- Ambiguity resolution/clarification policy:
- Atomic constituent construction:

## Splits and leakage

- Development/calibration/test counts by every dimension level:
- Entity, chain, template, source-fact, and question-hash presence checks:
- Per-key lineage exemptions, reason codes, and substantive justifications:
- Confirmation that no row supplies both an identifier and its exemption:
- Canonical question-hash recomputation/mismatch count (must be zero):
- Cross-split overlap checks for every declared lineage key:
- Confirmation that strict mode, not the permissive legacy reader, produced the split:
- Contamination search procedure:
- Exclusions decided before test access:

## Quality audit

- Stratified human-audit sample and annotators:
- Alias/judge disagreement and adjudication:
- Invalid or disputed examples:
- Candidate-oracle recall by dimension:

## Limitations

Document frequency-proxy error, cutoff uncertainty, ambiguity incompleteness, shortcut risk,
domain-taxonomy subjectivity, and any level with insufficient calibration support.
