# PC Review: "CalibRead: Reliability Contracts for Parametric LLM Databases [Vision]"

Reviewer role: senior PVLDB PC member, Vision track. Review written against Vision-track norms, not research-track norms.

---

## 1. Summary of the core claim (in my words)

The paper argues that when an LLM is used as a data source inside a query plan (a "parametric Read"), the engine today receives an untyped fluent string with no contract, which breaks the basic promise a relational Read makes: return a value, mark it missing, or refuse under declared assumptions. CalibRead proposes to make reliability an *operator property* rather than a model property, via four pieces:

1. A typed Read primitive `CALIBREAD(q, alpha, actions, track, W)` returning exactly one of `answer` / `set` / `abstain`.
2. A first-class **certificate object** `C` attached to every committed or refused Read, recording model snapshot, generation, workload metadata, calibrator identity, track, policy, assumptions, and guarantee scope. It is framed as why-provenance for parametric values and supports replay, retraction, and model migration.
3. A hard **two-track split**: Track A (finite label universe, inherits split/Mondrian conformal marginal coverage) versus Track B (open-ended generation, where the paper says no coverage claim is legitimate and only candidate-oracle recall may be reported).
4. **Optimizer-visible contract risk**: the physical planner should cost a parametric Read against index/retrieval/human alternatives by latency and contract risk, analogous to access-path selection, and rewrite the plan when estimated risk exceeds the declared alpha.

Seven workload dimensions (R1 frequency, R2 precision, R3 recency, R4 ambiguity, R5 synthesis, R6 domain, R7 policy) are treated as workload metadata rather than benchmark axes. A Python prototype implements the wrapper, calibrators, fail-closed policy, and certificate emission. An eight-item research agenda (C1 to C8) and a pre-registered measurement protocol (Section 9, Table 6) round out the paper. The explicit novelty claim is "the integration into an execution contract, not any single mechanism."

I believe this reading is correct. The paper is consistent about what it is claiming.

---

## 2. Strengths

- **The framing is genuinely database-native.** The isolation-level analogy for alpha, the access-path analogy for contract risk, the WAL analogy for certificates, and the "possible-worlds relation" reading of `set` are the right vocabulary for this venue. A DB reviewer immediately understands the shape of the proposal.
- **The `answer` / `set` / `abstain` typing with fail-closed semantics is a clean, small idea.** Table 5 (fail-closed policy) is the most convincing artifact in the paper: it states the contract in one place and makes clear that abstention can be an integrity failure, not a low score. That distinction is real and under-appreciated in the LLM-in-SQL literature.
- **The two-track refusal to pool finite-label and open-ended coverage is an honest and useful position.** Many hybrid-query papers quietly report a single accuracy number across both regimes. Insisting the engine keep the metrics separate is a defensible systems stance.
- **The paper differentiates explicitly rather than just citing.** Table 1 has a "what it is not (hence CalibRead)" column. The Limitations section is unusually candid (marginal not per-query, no arbitrary shift, Track B has no coverage).
- **There is an executable sketch.** SQL listings, a policy table, a certificate schema, a named prototype with concrete components (isotonic calibrator, Mondrian groups, lineage-safe splits, OpenRouter/Ollama adapters). This is above the "purely speculative" floor.
- **The agenda items C1 to C8 are mostly concrete database questions** (composition semantics, group support as a resource, optimizer costing, temporal integrity as schema property). C2 and C5 in particular are good.

---

## 3. Weaknesses and risks

### 3.1 Novelty sharpness: is this "conformal + selective prediction + provenance, repackaged"?

Partly yes, and the paper knows it, which is why it repeats the "not a rename" defense at least six times (abstract, intro, Table 1 caption, Table 2 caption, Section 7, Section 8, Section 10). Repetition signals anxiety rather than resolving it. The skeptical reading:

- **The certificate is a manifest.** Table 2's jobs (audit/replay, policy change, retraction, migration, debugging, composition) are all things a well-designed log record plus content hashes gives you. The paper asserts "this is why C is a contribution, not a log line" but never shows a computation over `C` that a log cannot do. If the certificate participated in query semantics (e.g., algebraic rules for composing certificates, a certificate-aware rewrite that is provably sound), it would be an operator artifact. As written it is metadata.
- **Optimizer-visible contract risk is the most novel and most database-flavored claim, and it is the least developed.** Table 4 has symbols only. `r_p` is never defined. Is it the calibrated miscoverage estimate for the group? The abstention rate? An upper confidence bound? How is it estimated *before* running the LLM (otherwise it is not plan-time costing)? What is `r_r` for retrieval or `r_h` for a human? Without at least one concrete estimator and one worked cost comparison, "Table 4 is a database optimization problem" is an assertion, not a mechanism. This is the piece a DB PC most wants to see and will most notice is missing.
- **Track A's guarantee comes entirely from split/Mondrian conformal prediction.** The paper adds nothing statistical. That is fine for a vision paper if the systems contribution is strong, but it means the paper's credibility rests fully on the certificate and optimizer pieces, which are the thin ones.
- **DB-side prior art on statistical guarantees for ML operators is missing entirely.** SUPG (Kang et al., VLDB 2020, approximate selection with precision/recall guarantees), probabilistic predicates (Lu et al., SIGMOD 2018), and the broader "ML inference as a query operator with statistical targets" line are direct ancestors of "reliability as an operator property costed by the planner." A reviewer from that community will call the omission out and will ask why CalibRead's contract is different from a SUPG-style target on an ML UDF. Galois (Saeed et al., 2023, querying LLMs with SQL) is also missing from the hybrid-SQL list.

### 3.2 Executability: prototype, primitive, certificate

- **The SQL primitive is not implemented anywhere.** Listings 1, 4, and 5 show `LATERAL CALIBREAD(...)` and an optimizer rewrite, but Section 7 describes a Python wrapper (`WorkloadRecords`, `read_policy`, `build_read_certificate`). No engine integration, no planner, no rewrite is claimed. The gap between the SQL surface and what exists is never stated, and a reviewer will assume the worst. Say plainly: "the operator exists as a library; the SQL surface and planner integration are the agenda."
- **Zero numbers.** Not a single abstention rate, coverage check, calibration-set size, or latency figure. The paper says "not results we cite here" and "reviewers should judge the operator ... and whether Table 4 is a database optimization problem." Vision papers do not need full evaluations, but almost every accepted one includes at least one motivating measurement (even a 50-question sanity run showing, e.g., that coverage holds on the calibrated group and collapses on an unseen group). Withholding everything reads as either the evaluation is not ready or the results are unflattering. Telling reviewers how to judge the paper does not help.
- **The running example undermines the operator.** Listing 5 falls back to a `capitals` table via `IndexLookup`. If a capitals table exists, the parametric Read of "capital of country" is pointless. Every example in the paper is a lookup the database could answer from a small reference table. Pick an example where the parametric path is genuinely the only path with a finite label universe (industry classification of a company name, country of a supplier from a free-text address, product category from a description).
- **Calibration labels are the unaddressed cost.** Mondrian conformal per group needs labeled (score, correct) pairs *for the declared workload group*. Who produces ground-truth labels for the workload's questions, and if you have them, why is the LLM being asked? The paper treats calibration support like buffer-pool occupancy (C2) but never discusses label acquisition economics. For a DB audience this is the elephant: statistics collection is cheap and label-free; calibration is neither.
- **"Immutable model snapshot" via OpenRouter is not something the caller controls.** Hosted APIs silently update. The certificate hashes what the provider says, not the weights. Say so.

### 3.3 Overreaching or under-supported claims

- "Open-ended generation may not [inherit coverage]" and "mixing the two ... is a category error." Conformal factuality (Mohri and Hashimoto) and ConU do provide guarantees for open-ended output under stated assumptions. The paper's position that these guarantees are about sub-claim retention rather than "true value in set" is defensible, but "may not" overstates it. Hedge to "does not inherit *set-coverage of the true value*; claim-level factuality guarantees are a different statement."
- **The isolation-level analogy breaks at the single tuple, and the paper admits it in Limitations but not where the analogy is made.** Isolation levels hold per transaction. Marginal coverage holds over the workload, and a certificate on one committed tuple certifies nothing about that tuple. The downstream join in Listing 1 consumes one tuple. The contract is a workload-level SLA, not a per-Read guarantee. This should be said in Section 3.1 where the analogy is introduced, not deferred.
- "Hybrid engines such as SWAN still report extraction accuracy far from operational (on the order of 40%)." A single number lifted from one benchmark, used as the motivation for Section 2. Fine as motivation, but attribute precisely and do not let it carry the section.
- Composition is listed as a delivered part of the contract (abstract: "composition, support, physical selection, audit"), but the only delivered composition semantics is "fail closed if any hop abstains" (Listing 4). That is the trivial rule. C1 acknowledges the real question is open. Do not list composition as delivered.
- "We report the operator, the certificate, a working prototype of the contract" (Section 1). A prototype whose open-ended path "currently exposes answer/abstain only" and whose optimizer path does not exist is a partial prototype. Say "partial."

### 3.4 Related-work positioning

Fair in tone, and Table 1 is a good device. Two gaps:

- Missing DB-side statistical-guarantee ancestors (SUPG, probabilistic predicates) as noted above. This is the most damaging omission because it is exactly the community that will review the paper.
- LOTUS cascades and Abacus optimization are dismissed as "fidelity to a reference algorithm, not ground truth." True, but LOTUS's cascade thresholding is a calibration procedure against a target, and Abacus already costs semantic operators by quality and latency. The paper should say precisely what "contract risk" adds over Abacus's quality dimension (answer: ground-truth coverage under a declared alpha, with fail-closed abstention), rather than implying planners today ignore quality entirely.

### 3.5 Writing and structure for a 20-minute skim

- **Eleven sections in six pages** is too fragmented. Sections 2, 4, and 9 are each under half a page and could be folded in.
- **The prose is aphoristic and defensive.** "X is not Y" sentences appear dozens of times ("is not a suggestion," "is a diagnostic, not a theorem," "is not a fourth committed action," "not a log line," "not a leaderboard"). Individually fine; cumulatively they read as the authors arguing with an imagined reviewer instead of explaining the system.
- **Section 9 ("What the measurement paper must falsify") is a pre-registration of a paper that does not exist.** Some reviewers will like the falsifiability. More will read it, alongside the 20/30/50 splits and "200 test examples per main-effect level," as a regular paper missing its evaluation section, which is exactly the failure mode Vision papers are penalized for. Keep Table 6 (it is the falsifiable agenda), cut the methodology detail.
- **Figure 3 duplicates Section 3.5** step for step. One of them can go.
- The abstract spends its second half on "what adjacent mechanisms are not." An abstract should spend that space on what CalibRead *does*.

---

## 4. Score: 5.5 / 10 (borderline, leaning reject as submitted)

**Why not lower:** the direction is right, the vocabulary is right for VLDB, Table 5 and the two-track split are crisp, and there is a real if partial prototype. This is not hand-waving.

**Why not higher:** the two claims that would make this a *database* vision (certificate as operator artifact with composition semantics; contract risk as a plan-time cost) are asserted, not mechanized. The paper has no measurement at all, and its running example makes the operator look unnecessary. The DB-side prior art on statistical guarantees for ML operators is absent.

**What moves it to 7:** define `r_p` and give one worked plan-time cost comparison; include one small motivating measurement (coverage holds on calibrated group, collapses on unseen group, abstention fires); replace the capitals example; add SUPG/probabilistic-predicate positioning; cut Section 9 methodology to Table 6; state the prototype-versus-SQL gap plainly.

**What moves it to 4:** a reviewer who knows conformal prediction concludes the "contract" is a schema around a conformal set and finds no operator-level computation over the certificate. Nothing in the current text prevents that conclusion.

---

## 5. Estimated acceptance probability: 25 to 35%

PVLDB Vision track acceptance is selective, and accepted papers typically have (a) one sharp mechanism a DB person can hold in their head, (b) at least one preliminary measurement, and (c) clear separation of "built" from "proposed." This paper has (a) in the typed Read, is missing (b) entirely, and blurs (c) between the SQL listings and the Python prototype. It is above the typical rejected Vision paper on clarity of direction and honesty, and below the typical accepted one on grounding. With the revisions in Section 6 (which are days of work, not months), I would put it at 45 to 55%.

---

## 6. Prioritized revision suggestions

### Highest impact

1. **Define contract risk and show one plan-time costing.** State what `r_p` is (e.g., calibrated group miscoverage upper bound at alpha for the workload group; or predicted abstention rate) and how it is available before the LLM call (from the workload group's calibration statistics, like a histogram). Then give one concrete row for Table 4 with real numbers from the prototype and a real retrieval alternative. This single addition turns the optimizer claim from assertion into mechanism.
2. **Add one motivating measurement, even tiny.** Two groups, one calibrated and one unseen. Show coverage at alpha = 0.05 on the calibrated group, the unsupported-group abstention firing, and Track B's answer/abstain rates. A quarter-page table. Do not call it an evaluation; call it a sanity check that the contract behaves as specified.
3. **Replace the capitals running example** with a Track A case where no reference table exists but the label universe is finite. Keep the example consistent across Listings 1 to 5.
4. **State the prototype-to-primitive gap in one sentence in Section 7.** "The operator, calibrators, policy, and certificate exist as a Python library; the SQL surface (Listings 1, 4, 5) and planner integration are not implemented and are the agenda."
5. **Add SUPG, probabilistic predicates, and Galois to Table 1 and Section 10**, and say in one sentence what CalibRead adds over an ML UDF with a SUPG-style precision target (typed abstention, workload-scoped certificate, fail-closed integrity conditions, and a planner-visible risk).

### Medium impact

6. **Give the certificate one operator-level operation.** Even a simple composition rule ("the certificate of a join of two Track A Reads carries the union-bound alpha and the intersection of assumption sets; if either atom is Track B, the composed certificate has no coverage bit") would make `C` an algebraic object rather than a manifest. Move this from C1 into Section 3.2.
7. **Address calibration label economics** in C2 or Limitations: where labels come from, per-group cost, and why the LLM is still worth calling when labels exist for a sample.
8. **Move the "marginal, not per-tuple" caveat to Section 3.1** where the isolation-level analogy is introduced.
9. **Hedge the open-ended claim** to distinguish set-coverage of the true value from claim-level factuality guarantees.
10. **Remove composition from the list of delivered contributions** in the abstract and intro. Keep it in the agenda.

### Structural and writing

11. Merge Section 2 into Section 1 (two paragraphs suffice). Merge Section 4 into Section 3 as a subsection. Cut Section 9 to Table 6 plus three sentences; drop split ratios and sample sizes.
12. Drop Figure 3 or Section 3.5's step list; keep one.
13. Remove at least half of the "not a rename" assertions. Make the case once, in Table 1, and let the mechanism do the arguing afterward.
14. Rewrite the abstract's second half to describe what the operator does and what the certificate enables, not what adjacent work is not.
15. Delete "Reviewers should judge the operator, the two-track split, C, and whether Table 4 is a database optimization problem." Instructions to reviewers read badly.
16. Delete "The scientifically honest design—and the one we freeze." Let the design speak.
17. Note that hosted-API "immutable snapshots" are provider assertions, not caller-verifiable.

---

## 7. Rejection-risk flags: specific passages

| Location | Passage (quoted or paraphrased) | Why it triggers skepticism |
|---|---|---|
| Abstract, Intro, Tables 1 and 2, Sections 7, 8, 10 | "not a new uncertainty estimator," "not a log line," "not a leaderboard," "not inventions to rename" | Repeated denial of the X+Y reading without a positive mechanism that rules it out. Reviewers infer the authors share the worry. |
| Table 4 and Section 5 | "The symbols are placeholders for optimizer metadata, not measured runtimes. If r_p > alpha, the optimizer selects retrieval" | `r_p` undefined; no estimator; no cost model. The paper's most DB-specific claim rests on a symbol. |
| Section 7 | "Confirmatory R1–R7 sweeps ... are the measurement program, not results we cite here. Reviewers should judge the operator..." | Zero numbers plus instructions to reviewers. Reads as either unready or unflattering results. |
| Listing 5 | `IndexLookup(capitals, q)` fallback | If the capitals table exists, the LLM Read is unnecessary. The example argues against the operator. |
| Section 3.1 | "The planner sees alpha the way it sees an isolation level" | Isolation is per transaction; marginal coverage is per workload. The analogy is admitted to break only in Section 8. |
| Section 9 | "Splits are 20/30/50 ... targeting 200 test examples per main-effect level (floor 100)" | Methodology of an unwritten paper. Signals "regular paper minus evaluation," the Vision-track failure mode. |
| Section 1 / Table 1 | "None of them is a commit contract that a query processor can route on" | SUPG-style statistical targets on ML predicates are exactly plan-time guarantees a processor routes on. The claim is falsified by uncited prior work. |
| Section 3.3 | "open-ended generation may not [inherit coverage] ... category error" | Overstates; conformal factuality provides a (different) guarantee. Invites a methods reviewer to dispute the premise. |
| Abstract | "the systems agenda (composition, support, physical selection, audit)" | Composition delivered is the trivial fail-closed rule; listing it as delivered overclaims. |
| Section 4 | "The scientifically honest design—and the one we freeze" | Self-assessment of honesty; reviewers react poorly. |
| Section 2 | "SWAN still report[s] extraction accuracy far from operational (on the order of 40%)" | Single benchmark number carrying a whole section's motivation. |

---

## Separate note: should you benchmark against accepted Vision papers?

Yes, and it would help more than another editing pass, because your main risk is calibration of the *evidence bar* and *claim scope*, not the idea. Pick two or three recent PVLDB Vision papers and one CIDR paper in the LLM-plus-data-systems area (semantic operators, LLM query optimization, LLM-as-data-source) and check the following, with a tally:

1. **How many numbers they include.** Count tables and figures with measured values. My expectation is that nearly all accepted Vision papers include at least one small experiment or a motivating micro-benchmark, and none include a pre-registered methodology for a future paper. Compare to your zero.
2. **How they separate built from proposed.** Look for explicit sentences of the form "we have implemented X; Y and Z are open." Note where in the paper that sentence sits (usually early, in the contributions list). Compare to your Section 7, where the gap is implicit.
3. **How many distinct mechanisms they claim.** Accepted Vision papers usually carry one or two mechanisms and a list of open questions. You have four (typed Read, certificate, two tracks, optimizer risk) plus seven workload dimensions plus eight agenda items. Check whether they subordinate secondary ideas to the primary one.
4. **How they do related work.** Check whether they use a comparison table, how many rows, and whether the "difference" column names a mechanism or a framing. Your Table 1's "what it is not" column is mostly framing; theirs will tell you whether that passes.
5. **Section count and length distribution.** Count sections and look at how much space the core mechanism gets versus motivation, agenda, and limitations. Six-page Vision papers that get accepted are typically five to seven sections with one dominant technical section.
6. **How the agenda is phrased.** Open questions ("how should X compose?") versus committed hypotheses with test designs. Your C1 to C8 are closer to the former, which is good; your Section 9 is the latter, which is unusual. See which the accepted papers use.
7. **Tone.** Count sentences of the form "X is not Y" in an accepted paper versus yours. This will be the fastest way to see how much of your defensive prose to cut.

Do not benchmark on topic overlap or on how they use conformal methods. Benchmark only on evidence bar, built-versus-proposed clarity, mechanism count, and structure.
