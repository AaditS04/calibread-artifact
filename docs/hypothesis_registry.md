# Operational tests (vision paper)

Authoritative IDs for `configs/pilot.toml` validation. Definitions match Table “Falsifiable
operational tests” in the CalibRead vision paper (contrasts, not reported results).

| ID | Expectation |
|---|---|
| OP-R1–R6 | Tail, fine, post-cutoff, multi-interpretation, deeper hops, and expert queries degrade vs. matched anchors (risk, set size, or abstention). |
| OP-R5 synth. | Report P(chain wrong \| every atom correct); product/union-bound are diagnostics. |
| OP-R7 policy | Raising τ from 0.50 to 0.99 cuts answer rate; whether risk falls is measured. |
| OP-I15 / OP-I36 / OP-I47 | R1×R5 interaction; R3×R6 specialist drop; R4-dependent R7 region. |
| OP-CONTRACT | Workload-aware wrapper beats global calibration on worst-cell risk, at set-size or abstention cost. |

These estimands belong to the follow-on **measurement** paper; the vision submission reports
prototype machinery and sealed probes separately.
