# Operational estimands

Frozen operational test IDs referenced by `configs/pilot.toml`
(`evaluation.primary_estimand_registry`). Short definitions:

| ID | Contrast |
|---|---|
| OP-R1–R6 | Each reliability dimension vs. a matched anchor (risk, set size, or abstention). |
| OP-R5 synth. | P(chain wrong \| every atomic read correct); product/union bounds are diagnostics. |
| OP-R7 policy | Effect of R7 thresholds from 0.50 through 0.99 on answer rate and risk. |
| OP-I15 / OP-I36 / OP-I47 | Predeclared R1×R5, R3×R6, and R4×R7 interactions. |
| OP-CONTRACT | Workload-aware calibration vs. global calibration on worst-cell risk. |
