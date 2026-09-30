# Publication strategy

Verified against official venue pages on 10 August 2026. Recheck dates and policies immediately before submission.

## Recommendation

Primary target: **PVLDB Volume 20, Experiment, Analysis & Benchmark (EA&B), 1 December 2026 cycle**. Register the mandatory abstract by **25 November 2026**; the full deadline is **1 December at 5:00 p.m. Pacific Time**. The rolling process usually returns initial reviews on 15 January and can request one revision, so this is a submission target—not a promise of acceptance within four months. The [research-track call](https://vldb.org/2027/call-for-research-track.html) explicitly values new evaluation methods, workload characterization, and reusable artifacts; the [submission rules](https://www.vldb.org/2027/submission-guidelines.html) require an EA&B reproducibility package at initial submission; and the [official date table](https://www.vldb.org/2027/important-dates.html) establishes the monthly abstract/full-paper cycle.

Fallback PVLDB cycle: **1 January 2027**, with abstract registration by **25 December 2026**. Use it if the December package misses an evidence or reproducibility gate. A one-month delay is better than locking a weak submission into PVLDB's 12-month resubmission embargo after rejection.

The provisional title should carry the required category suffix at submission: **“CalibRead:
Reliability Contracts for LLM Reads Across Seven Database-Relevant Dimensions [Experiment,
Analysis & Benchmark]”.**

## Why PVLDB can fit—and when it does not

PVLDB requires a substantive data-management contribution and non-superficial engagement with
database literature. CalibRead fits only if the main object is an executable/auditable Read contract
and workload artifact: R1-R6 query metadata, reliability target, calibration snapshot, R7
answer/set/abstain semantics, interaction/shift behavior, provenance, and reproducibility. The
evaluation must connect the seven dimensions to query execution, routing, validation, or fallback
decisions rather than presenting them as seven unrelated QA slices.

It is out of scope if it becomes only an LLM calibration benchmark, a new confidence score without a data-management abstraction, or a collection of QA accuracy/ECE tables. Keep the probabilistic-database and hybrid relational–LLM lineage central, and complete PVLDB's scope self-assessment.

EA&B requires all experimental data and related software plus reproducibility evaluation; an inability to redistribute a source dataset needs to be solved through derived manifests/scripts before choosing this category, not after submission.

## Alternative paths

### ICDE 2027 EAB — conditional alternative

The [official ICDE 2027 research call](https://icde2027.github.io/cf-research-papers.html) lists a second-round deadline of **11 November 2026, 5:00 p.m. Pacific Time**, rebuttal 8–15 January 2027, and accept/reject notification around 10 February 2027. It explicitly includes uncertain/probabilistic data, LLMs for data engineering, and an Experimental, Analysis, and Benchmark category.

Choose ICDE only if main results, correctness audit, full draft, and reproducibility package are stable by **8 November**. ICDE offers no revision option. Its EAB artifact requirement and data-engineering scope gate are also strict. Because submission on 11 November would prevent concurrent PVLDB submission while under review, this is a fork, not a backup submitted at the same time.

### TMLR — rolling fallback

[Transactions on Machine Learning Research](https://jmlr.org/tmlr/) offers rolling submission, flexible timing, and an emphasis on technically correct claims. It is a journal, not the requested conference, but it is a strong fallback if the result is primarily ML calibration/analysis or needs another experimental cycle. Use the [official author guide](https://www.jmlr.org/tmlr/author-guide.html) and check current dual-submission rules before acting.

### Later NLP/ML venue

If the strongest result is open-ended factuality or uncertainty rather than a Read/workload abstraction, revise for an ACL-family or ML venue whose next announced deadline allows proper review. Do not force a database framing around an NLP-only contribution. ICLR 2027 and the 12 October 2026 ARR cycle are too early for this project schedule.

## Venue decision on 8 November 2026

Submit to PVLDB December when all are true:

- every R1-R7 confirmatory sweep is complete on three Tier A model families with uncertainty intervals;
- the R1 x R5, R3 x R6, and R4 x R7 matched workloads and annotations are reusable artifacts;
- Tier B breadth is either completed at the frozen compute-gated size or transparently reported as incomplete;
- the Read contract changes a meaningful execution decision and reports costs;
- database related work is technically integrated rather than cited in passing;
- one command reproduces every main table/figure from immutable outputs;
- licenses permit an EA&B-compliant package; and
- the professor/coauthors approve the exact claims.

If these hold earlier and the paper is clearly data-engineering work, ICDE is possible. If the DB
abstraction is weak but ML evidence is solid, choose TMLR/later NLP/ML. If any R dimension misses
its sample, provenance, annotation, or three-model replication gate, do not claim the full benchmark;
prefer the January PVLDB cycle or a later venue.

## Policy warnings

PVLDB and ICDE prohibit concurrent submission; never place the same work under review at both. Cite overlapping and conflicting papers plainly. Keep author lists and conflict declarations ready early. “Acceptance in four months” is not a controllable deliverable: the controllable target is a strong, compliant submission with all evidence and artifacts complete.
