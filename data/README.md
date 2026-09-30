# Data policy

Keep only small, redistributable manifests in version control. Raw benchmark downloads and model
generations must be cached outside commits and identified by content hash.

For every dataset, record its source URL, immutable revision, license, construction script, answer
aliases, entity/relation/template/chain identifiers, split, and every applicable R1–R7 field:
frequency value/source, precision type/tolerance, event and model-cutoff dates, ambiguity
interpretations, hop count and constituents, domain taxonomy/specificity, and confidence-policy
metadata. Preserve raw values as well as frozen level labels.

Development, calibration, and test entities, chains, templates, source facts, and normalized
question hashes must never overlap. Every record must carry a nonblank scalar or nonempty scalar
sequence for all five keys. Missing identifiers are errors, not automatically safe singleton
groups. A genuinely inapplicable key requires this exact per-key metadata shape:

    {
      "lineage_exemptions": {
        "chain_id": {
          "reason_code": "not_applicable_by_construction",
          "justification": "Atomic one-hop item has no evidence chain."
        }
      }
    }

The only reason codes are not_applicable_by_construction and not_defined_by_source_schema; a
justification must be substantive. Never provide both a value and exemption for one key.
question_hash cannot be exempted and must match sha256_nfkc_casefold_whitespace_v1. The permissive
legacy reader is for historical fixtures only and cannot produce a frozen pilot or study split.

A missing dimension value must likewise be explicit and justified; it must not be silently mapped
to an easy or default level. See [the dimension playbook](../docs/dimension_playbook.md) and
[experiment matrix](../docs/experiment_matrix.md).

`EXAMPLE_RECORD.jsonl` is the backward-compatible `Example` shape. The typed
`EXAMPLE_WORKLOAD_RECORD.jsonl` freezes model-independent R2/R4/R5/R6 evidence once, while
`EXAMPLE_MODEL_CONDITION_RECORD.jsonl` binds model-dependent R1/R3 readings to one immutable
model snapshot. Both are development-only and must never count as evidence. R7 is intentionally
absent from question and condition records: apply its named threshold policies to immutable,
condition-linked cached predictions and record those decisions in result/run artifacts.

The `cards/` directory contains separate Week 1 freeze drafts for R1–R7. Complete the applicable
source, construction, scoring, split, audit, and limitation fields before promoting any panel from
development to the frozen pilot. Use `SOURCE_LICENSE_TEMPLATE.csv` to make the Week 1
license/provenance decision explicit before any large download or annotation effort.

## Self-authored R2/R4/R6 data

Use `authoring/R4_R6_ANNOTATION_TEMPLATE.jsonl` with
`docs/r4_r6_annotation_protocol.md`. Keep completed annotations under the ignored
`data/raw/calibread_authored_r4_r6/` directory, not beside the versioned template.
The authoring CLI validates independent labels, adjudicator separation, contributor
consent, fact-source licenses, R2 precision metadata, R4 interpretation mappings, and R6 expertise rationale
before accepted rows can become strict workload records. Draft template rows are
examples only and must never be counted as research evidence.
