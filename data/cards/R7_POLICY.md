# R7 policy card draft — confidence threshold and Read action

Status: Week 1 freeze required; this is a policy card, not a new question dataset.

- Score source and whether it is raw or a fitted calibrated probability:
- Calibrator/method, calibration-object hash, and supported workload/groups:
- Frozen levels: tau_0_50, tau_0_70, tau_0_90, tau_0_95, tau_0_99:
- Allowed actions and unified answer/set/abstain rule:
- Unsupported-group, empty-set, and ambiguity-incomplete behavior:
- Candidate-universe/generator and oracle-recall gate:
- Predeclared answer-rate/risk operating points and cost settings:
- Risk-coverage, AURC, set-size, answer-rate, and abstention estimands:
- Policy comparison/matched-answer-rate procedure and interval method:
- Immutable cached-output and policy-result manifest hashes:

Tau is a score threshold, not automatically a conformal alpha or a per-answer correctness
probability. Threshold selection uses calibration data only.
