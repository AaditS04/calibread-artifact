# R3 data card draft — knowledge recency

Status: Week 1 freeze required; no research evidence is registered yet.

- Time-stamped source snapshot, license, and validity-interval construction:
- Model-specific documented cutoff source and uncertainty:
- Query as-of-date convention:
- Frozen bands: pre_cutoff, post_0_3_months, post_4_12_months, post_13_plus_months:
- Boundary convention: pre_cutoff includes delta <= 0; first post band is 0 < delta <= 3:
- Stale-answer, future-leakage, fabrication, refusal, and abstention labels:
- Immutable-fact negative controls and retrieval-disabled check:
- Matching variables: event type, update rate, popularity, domain, prompt form:
- Development/calibration/test counts and connected-component split hash:
- Provenance audit and unresolved-cutoff exclusions:

Post-cutoff failure is temporal distribution shift, not proof that a model hallucinated if its Read
policy correctly abstained.
