# R2 data card draft — precision requirement

Status: Week 1 freeze required; no research evidence is registered yet.

- Source snapshot, reference, license, and stored source precision:
- Typed panels included (date, quantity, categorical/name):
- Raw-to-level map for coarse/medium/fine and mapping hash:
- Date granularity rules (year/month/day):
- Significant-digit, rounding, unit-conversion, tolerance, and uncertainty rules:
- False-precision policy for unsupported extra detail:
- Paired-prompt construction from the same underlying fact:
- Matching variables: entity, relation, magnitude/era, R1, R5, R6:
- Formatter-oracle and typed-scorer versions/tests:
- Development/calibration/test counts and connected-component split hash:
- Manual audit and disputed-source exclusions:

Never derive a finer gold value than the source supports. Freeze all parsing and tolerance rules
before test outputs are viewed.
