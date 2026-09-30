# CalibRead R2/R4/R6 annotation and adjudication protocol

Protocol version: `r2-r4-r6-authoring-v1`

This protocol governs R2/R4/R6 data created by the CalibRead team. A model may help propose
candidates, but it must not act as the only annotator, fact checker, or adjudicator.
Only independently reviewed and accepted rows become research records.

## Roles and independence

- The **author** drafts a question and records its fact sources.
- At least **two annotators** label it independently without seeing each other.
- A separate **adjudicator** resolves the final label and answer set.
- The adjudicator must not be one of the independent annotators.
- Contributors must explicitly permit project use and intended redistribution.

Use stable pseudonymous contributor IDs in public artifacts. Store names and consent
forms separately with restricted access.

## R2: answer precision

R2 uses matched questions about one frozen fact at three requested granularities:

| Level | Rule |
|---|---|
| `coarse` | Rounded category, order of magnitude, year, or broad value |
| `medium` | Conventional reporting precision, month, or standard rounded value |
| `fine` | Source-supported exact digits, day, or explicitly narrow tolerance |

Every R2 row records answer type, required granularity, and numeric tolerance when
numeric. A fine answer must not demand digits unsupported by the source. All three
members of a precision family remain in one split.

## R4: ambiguity

R4 counts plausible interpretations of the exact wording shown to the model:

| Level | Raw count | Rule |
|---|---:|---|
| `unambiguous` | 1 | One reasonable interpretation in context |
| `two_way` | 2 | Exactly two reasonable interpretations |
| `three_plus` | 3 or more | At least three reasonable interpretations |

An interpretation must be natural, meaningfully distinct, and answerable. Typos,
broken grammar, contrived readings, or aliases for one answer do not create R4.
`interpretation_answers` must name every audited reading, and its answer union must
exactly equal `accepted_answers`.

R4 questions belong to matched families. A publishable family contains an
unambiguous control and at least one ambiguity intervention about the same fact
family. All family members remain in one data split.

Example family:

- Control: `Who is the president of the country Georgia?`
- Intervention: `Who is the president of Georgia?`

The annotation must describe the country and U.S.-state readings explicitly. An
answer is not accepted merely because an LLM produced it.

## R6: domain specificity

R6 measures normally required background training, not generic difficulty:

| Level | Frozen raw score | Rule |
|---|---:|---|
| `general` | 0.10 | No formal domain training normally required |
| `specialized` | 0.50 | Usually learned in undergraduate or professional study |
| `expert` | 0.90 | Usually requires advanced study or substantial practice |

Each row declares `domain_name`, an expected prerequisite, and a substantive
expertise rationale. Difficult riddles are not expert questions. Specialized and
expert rows should be reviewed by an annotator competent in that domain.

For each claimed domain, aim for all three levels and match answer type, wording
length, precision, recency, and hop count where practical. The data card reports
imbalances rather than hiding them.

## Fact provenance and licenses

Every accepted row requires a stable fact-source URL and corresponding license or
terms label. Prefer primary or authoritative sources. Do not copy copyrighted
question text: authors write original wording and cite only the factual basis.
`source_fact_id` must stably identify that basis.

The benchmark remains non-redistributable until contributor consent and source
compatibility are confirmed for release. Changing the registry redistribution flag
requires a documented review.

## Workflow

1. Copy `data/authoring/R4_R6_ANNOTATION_TEMPLATE.jsonl` outside Git.
2. Draft candidates with status `draft`.
3. Collect blind labels in `independent_labels`.
4. Record the final level, answer mapping, adjudicator, and `accepted` status.
5. Run `python -m calibread.authoring validate <annotations.jsonl>`.
6. Correct invalid rows without deleting disagreement history.
7. Run `python -m calibread.authoring refine <annotations.jsonl>`.
8. Review the generated audit sample and mark approval separately.
9. Freeze the input SHA-256 and protocol version before model inference.

## Promotion gates

A full publishable dataset requires:

- no invalid accepted records;
- two independent annotators and a separate adjudicator per record;
- all R2 levels in matched precision families;
- all R4 levels and matched unambiguous controls;
- all R6 levels in every claimed domain;
- reported agreement with disagreements retained;
- valid source/license metadata and contributor consent;
- no chain, fact, or normalized-question leakage;
- human approval of the deterministic audit sample.

A pilot may be refined before full coverage, but its data card will say that it is
not promotion-ready.
