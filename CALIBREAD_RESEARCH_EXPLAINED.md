# CalibRead Research Topic: An Easy and Detailed Explanation

## 1. The research question in one sentence

CalibRead asks:

> When should we trust an LLM's answer, when should it return several possible answers, and when should it admit that it cannot answer reliably?

More formally, the project asks:

> When an LLM is used like a database `Read` operation, how do its answer quality, calibration, prediction-set behavior, and answer/set/abstain decisions change as the question becomes rarer, more precise, newer, more ambiguous, more compositional, or more specialized, and as the required confidence threshold changes?

The short project slogan is:

> **When can an LLM Read be trusted?**

This slogan covers the complete project: reliability may change with knowledge
frequency, required precision, recency, ambiguity, synthesis depth, domain
specificity, and the confidence policy. The narrower question **Do calibrated
LLM Reads compose?** belongs specifically to R5, the synthesis-depth study.

This question matters because an LLM can produce a fluent, plausible answer even when the answer is wrong. A conventional database is expected to return the value that is stored in it. An LLM does not store and retrieve knowledge in the same explicit way: its knowledge is distributed across model parameters, and generation is probabilistic. CalibRead studies whether we can nevertheless wrap an LLM in a careful, measurable reliability contract.



## 2. A simple motivating example

Consider these two questions:

> What is the capital of France?

and:

> What is the capital of Tuvalu?

The model may answer:

```text
France -> Paris, confidence 0.97
Tuvalu -> Funafuti, confidence 0.97
```

Both answers are correct, but the two confidence scores may not be equally trustworthy. The France fact is likely to be represented very frequently in general text, while the Tuvalu fact is less common. Across a large collection of similar questions, the model might be correct 98% of the time on common facts but only 65% of the time on rare facts, even though it reports high confidence for both.

A single overall accuracy number could hide this difference. For example, a model with 90% average accuracy might still fail badly on rare facts, recent events, expert questions, or multi-step questions. CalibRead therefore treats reliability as a function of the workload:

\[
\text{Reliability} = f(\text{frequency, precision, recency, ambiguity, synthesis, domain, policy})
\]

The project tries to discover where reliability degrades and whether a calibrated decision system can recognize those boundaries.

---

## 3. What does it mean to use an LLM like a database Read?

A database `Read` normally means asking for a stored value and receiving that value. For example:

```sql
SELECT capital FROM countries WHERE country = 'France';
```

The expected result is `Paris`. The database is not expected to invent a plausible city when the value is absent.

An LLM behaves differently. If asked for a fact that it does not know, it may still generate a confident-looking answer. Therefore, a useful LLM Read operation needs more than a generated string. It needs a rule governing whether that string is reliable enough to return.

In CalibRead, a request declares:

1. a question or workload;
2. a target error level, such as `alpha = 0.05`;
3. the actions that the application permits.

The wrapper returns exactly one of three actions:

- `answer`: commit to one normalized answer;
- `set`: return a finite set of plausible answers;
- `abstain`: refuse to commit because the risk or calibration support is inadequate.

### Example: returning one answer

```text
Question: What is the capital of Tuvalu?
Target error: 5%

Decision: answer
Answer: Funafuti
```

### Example: returning a candidate set

```text
Question: What is the capital of Georgia?

Decision: set
Candidates: {Tbilisi, Atlanta}
Reason: "Georgia" can mean a country or a US state.
```

### Example: abstaining

```text
Question: What was the exact population of City X on 11 August 2026?

Decision: abstain
Reason: The fact is after the model's knowledge cutoff, and the system lacks
enough calibration evidence to support a reliable answer.
```

This is the proposed **Read contract**: the system should return an answer only when the declared workload and reliability target are supportable. Otherwise, it should return alternatives or abstain.

---

## 4. What does calibrated confidence mean?

Suppose a system assigns confidence `0.80` to 100 answers. If the confidence is well calibrated, approximately 80 of those answers should be correct.

An example of reasonably calibrated behavior is:

| Reported confidence | Observed accuracy |
|---|---:|
| 0.50-0.59 | 54% |
| 0.60-0.69 | 63% |
| 0.70-0.79 | 74% |
| 0.80-0.89 | 82% |
| 0.90-1.00 | 93% |

A dangerously overconfident system might instead behave like this:

| Reported confidence | Observed accuracy |
|---|---:|
| 0.90-1.00 | 61% |

In the second case, the model sounds highly certain but is wrong almost four times out of ten.

Calibration is a repeated-sample or group-level property. A score of `0.80` should not automatically be described as an 80% probability that this particular answer is correct. CalibRead explicitly avoids making that stronger claim unless a separately validated probabilistic interpretation supports it.

The project asks two related questions about a score:

1. **Discrimination:** Does the score rank safer answers above riskier answers?
2. **Calibration:** Do groups of answers with a given score have the corresponding observed accuracy?

A score can rank answers well but still have numerically misleading values. CalibRead measures both properties.

In the current OpenRouter inference implementation, this score is the mean log
probability of the generated answer tokens. It is stored as a raw score, not as
a probability of correctness. A separately fitted and frozen calibrator will
map that raw score to an empirical probability-valued confidence before R7
thresholds are applied. The complete implemented-versus-planned pipeline is
documented in
[`src/calibread/inference/CALIBRATION_AND_R7.md`](src/calibread/inference/CALIBRATION_AND_R7.md).

---

## 5. The seven research dimensions

CalibRead studies seven dimensions, called R1 through R7. R1-R6 describe the question or workload. R7 describes the policy used to decide whether to answer.

## R1: Knowledge frequency

R1 asks whether common facts are more reliable than rare, long-tail facts.

Examples include:

```text
Head/common:  What is the capital of France?
Middle:       What is the capital of Slovenia?
Tail/rare:    What is the administrative capital of Montserrat?
```

The study divides a named exposure proxy into `head`, `middle`, and `tail` levels. It then asks whether tail questions have:

- more incorrect answers;
- worse-calibrated confidence;
- higher error among the answers the system chooses to return;
- larger prediction sets;
- more abstentions.

The original proposal suggests that reliability might deteriorate sharply below a frequency threshold. The operational study tests for evidence of a nonlinear transition, but it does not assume the transition exists.

There is an important limitation: for a proprietary LLM, the project usually cannot observe the exact number of times a fact appeared in training. It therefore uses a named and versioned exposure proxy and does not claim that the proxy is the model's true training frequency.

### What this dimension teaches us

If a model is reliable on common knowledge but unreliable on rare knowledge, an overall accuracy score will be misleading. A useful Read contract may need different rules or thresholds for common and long-tail queries.

## R2: Precision requirement

R2 asks what happens when the same kind of information must be returned at increasing levels of precision.

For dates:

```text
Coarse: In which decade was the treaty signed?
Medium: In which year was the treaty signed?
Fine:   On what exact date was the treaty signed?
```

For numerical values:

```text
Coarse: What is the approximate population?
Medium: Give the population to the nearest million.
Fine:   Give the exact census value.
```

A model may possess enough knowledge to answer a coarse question correctly while lacking the detail needed for the fine question. CalibRead tests whether finer precision leads to:

- higher factual or typed-answer error;
- poorer calibration;
- larger candidate sets;
- more abstention at the same reliability target.

This distinction matters because an approximate answer can be useful in casual conversation but unacceptable in scientific, financial, legal, or database settings that require an exact value.

## R3: Knowledge recency

R3 studies how reliability changes for facts that occur before or after a model's training cutoff.

Suppose a model has a December 2025 knowledge cutoff:

```text
Pre-cutoff:              Who won the 2024 tournament?
0-3 months post-cutoff:  Who won the January 2026 tournament?
4-12 months post-cutoff: Who won the August 2026 tournament?
```

For post-cutoff questions, the model may:

- repeat an older fact;
- extrapolate from a pattern;
- confuse expected and actual events;
- fabricate a plausible answer;
- express unjustified confidence.

The study compares several cutoff-relative recency bands. It measures whether accuracy and calibration deteriorate and whether the wrapper responds appropriately by widening its set or abstaining.

Cutoff information is recorded per model. If a cutoff is uncertain, the uncertainty must be reported rather than silently assigning a precise date.

## R4: Query ambiguity

R4 asks how reliability changes when a question has multiple valid interpretations.

For example:

```text
Unambiguous: What is the capital of the country Georgia?
Ambiguous:   What is the capital of Georgia?
```

The ambiguous question can refer to:

- Georgia the country, whose capital is Tbilisi;
- Georgia the US state, whose capital is Atlanta.

If the system returns only `Tbilisi`, it may be correct under one interpretation but still fail to handle the query properly. A better response may be a set, an explanation, or a clarification request.

CalibRead uses independently annotated valid interpretations and accepted-answer classes. It examines whether ambiguity produces:

- less consistent answers;
- higher risk;
- larger sets;
- more abstention;
- a different useful confidence-threshold region.

The key lesson is that uncertainty can arise from the wording of the question, not only from missing model knowledge. Raising a numerical confidence threshold may not solve semantic ambiguity.

## R5: Synthesis depth

R5 is the clearest expression of the question "Do Reads compose?"

A one-hop question retrieves one fact:

```text
Question: What is the capital of France?
Chain: France -> Paris
```

A two-hop question combines two facts:

```text
Question: What river runs through the capital of France?
Chain: France -> Paris -> Seine
```

A three-hop question combines another step:

```text
Question: Into which body of water does the river that runs through
the capital of France flow?
Chain: France -> Paris -> Seine -> English Channel
```

The model may answer each atomic question correctly when the questions are asked separately:

```text
What is the capital of France? -> Paris
What river runs through Paris? -> Seine
Where does the Seine reach the sea? -> English Channel
```

Yet it may still answer the combined question incorrectly. This is a **composition failure** rather than a basic knowledge failure.

CalibRead measures **synthesis loss**:

\[
P(\text{composed query is wrong} \mid
\text{all atomic constituents are correct})
\]

This separates two kinds of failure:

- **knowledge failure:** at least one required component fact is not answered correctly;
- **synthesis failure:** the component facts are available, but the model fails to combine them.

The original proposal gives a factorized diagnostic:

\[
H_d \approx 1-(1-H_1)^d
\]

Here:

- \(H_1\) is the one-hop hallucination or error rate;
- \(d\) is the number of hops;
- \(H_d\) is the predicted error rate for a depth-\(d\) query.

For example, if the error rate at each hop is 10%, the diagnostic predicts for three hops:

\[
H_3 \approx 1-(1-0.10)^3
= 1-0.9^3
= 0.271
\]

The predicted three-hop error rate is therefore 27.1%.

The study compares this prediction with the observed result. Agreement would show that the expression is a useful empirical diagnostic on the tested chains. It would not prove that hop errors are independent or create a new formal guarantee.

## R6: Domain specificity

R6 asks whether calibration and reliability change as questions move from general knowledge to specialized or expert knowledge.

For example:

```text
General:
What organ pumps blood through the body?

Specialized:
Which valve separates the left atrium from the left ventricle?

Expert:
Which echocardiographic criteria distinguish severe primary mitral
regurgitation in a specified clinical setting?
```

A model may be accurate and well calibrated on general questions but overconfident on specialized questions. CalibRead uses a frozen domain taxonomy and an error-independent specificity proxy to compare `general`, `specialized`, and `expert` levels.

The project also studies **domain calibration transfer**:

1. fit a calibrator on a medical calibration partition;
2. evaluate it on unseen medical questions;
3. evaluate the same calibrator, without refitting, on legal questions;
4. repeat in the other direction;
5. compare within-domain and cross-domain calibration.

If medical calibration improves medical performance but does not help legal performance, that supports domain-partitioned contracts for the tested domains. It does not prove a universal boundary between all medical and legal data.

## R7: Confidence and decision-policy threshold

R7 changes the decision rule rather than changing the question.

Suppose a system assigns a score of `0.82` to an answer:

```text
Threshold 0.50 -> answer
Threshold 0.70 -> answer
Threshold 0.90 -> abstain
Threshold 0.95 -> abstain
```

CalibRead evaluates five fixed thresholds:

```text
0.50, 0.70, 0.90, 0.95, 0.99
```

As the threshold rises, the system will normally answer fewer questions. The central question is whether the retained answers actually become safer and what the system pays in lost answer rate, larger sets, or additional abstention.

The project reports the full **risk-coverage frontier**:

- **answer rate or coverage:** how often the system commits to an answer;
- **selective risk:** the error rate among committed answers;
- **prediction-set size:** how many candidates are returned;
- **abstention rate:** how often the system declines to answer;
- **AURC:** a summary of performance across the risk-coverage curve.

A high threshold does not automatically create reliability. If the underlying score is poor, the system may abstain more without successfully separating correct answers from incorrect ones.

---

## 6. What is Conformal Parametric Read?

The proposal calls the calibrated wrapper **Conformal Parametric Read**, or CPR. Its purpose is to use calibration data to decide which labels belong in a prediction set at a requested error level.

Imagine a question with a fixed answer universe:

```text
Question: Which of these cities is the capital of France?
Labels: {Paris, Lyon, Marseille, Bordeaux}
```

For an easy question, a 95%-target prediction set might be:

```text
{Paris}
```

For a less certain question, it might be:

```text
{Paris, Lyon}
```

Under the required assumptions—particularly exchangeability between the calibration and test examples, a fixed scoring rule, and a label universe supplied independently of the model—split conformal prediction provides a **marginal coverage** guarantee over future examples.

At a nominal 95% target, the long-run goal is for the correct label to appear in the returned set at least 95% of the time under those assumptions.

Coverage alone is not sufficient. A system could return every possible label and obtain perfect coverage, but the result would be useless. CalibRead therefore measures efficiency:

- average set size;
- median set size;
- large-set behavior, such as the 90th percentile;
- singleton rate;
- empty-set rate;
- abstention rate.

The research asks whether CPR can achieve the requested finite-label coverage with useful sets and whether it is more efficient than the registered baselines.

### What conformal coverage does not mean

It does not automatically provide:

- a correctness probability for one particular answer;
- coverage for every possible subgroup;
- protection under arbitrary distribution shift;
- a guarantee when the correct answer is absent from a model-generated candidate list;
- automatic minimality of the returned set.

These limitations are essential to the research question, not minor implementation details.

---

## 7. Why the project has two evaluation tracks

CalibRead separates finite-label evaluation from open-ended question answering because the two settings support different conclusions.

## Track A: Finite-label certified evaluation

In this track, the possible labels are fixed independently of the model, and the correct answer is known to lie in that universe.

Example:

```text
Question: Which country contains Paris?
Candidates supplied by the task: {France, Germany, Spain, Italy}
Correct answer: France
```

Because `France` is guaranteed to be in the label universe, conformal prediction can form a set and support a marginal-coverage claim if all registered assumptions hold.

## Track B: Open-ended candidate stress evaluation

In open-ended QA, the model or another generator produces the candidates:

```text
Question: Which scientist introduced Theory X?
Generated candidates: {Scientist A, Scientist B, Scientist C}
True answer: Scientist D
```

No method that only ranks A, B, and C can return D. Therefore, before discussing set coverage, the project measures **candidate-oracle recall**:

> How often does the generated candidate collection contain the true answer anywhere?

If oracle recall is 80%, no selection method over those candidates can exceed 80% unconditional answer coverage. CalibRead therefore reports candidate generation failure separately and does not incorrectly transfer the finite-label conformal guarantee to open-ended generated candidates.

The two tracks must never be merged into one "certified accuracy" score.

---

## 8. The three predeclared interactions

The main experiment changes one R1-R6 dimension at a time while holding other dimensions at anchor conditions. This makes each main effect easier to interpret. The study also includes three scientifically important interactions.

## R1 x R5: Frequency and synthesis depth

Rare facts may become especially unreliable when several of them must be composed.

Consider four conditions:

| Condition | Example difficulty |
|---|---|
| Common, one hop | Retrieve one widely represented fact |
| Rare, one hop | Retrieve one long-tail fact |
| Common, four hops | Combine several common facts |
| Rare, four hops | Combine several long-tail facts |

Suppose the error rates are:

```text
Common, one hop:  5%
Rare, one hop:   15%
Common, four hops: 20%
Rare, four hops:   55%
```

The rare four-hop result may be worse than we would expect by simply adding the separate frequency and depth effects. CalibRead tests for this non-additive long-tail composition effect.

## R3 x R6: Recency and domain specificity

Recent expert knowledge may be especially difficult.

For example:

```text
Old general knowledge:     low risk
Recent general knowledge:  moderate risk
Old expert knowledge:      moderate risk
Recent expert knowledge:   very high risk
```

The experiment asks whether post-cutoff degradation is larger in specialized or expert domains than in the general-domain anchor.

## R4 x R7: Ambiguity and policy threshold

A threshold that works for unambiguous questions may not work for ambiguous questions.

For an unambiguous query, increasing the threshold might successfully remove many incorrect answers. For an ambiguous query, the model may be highly confident in one interpretation and still ignore another valid interpretation. In that setting, returning a set or asking for clarification may be more appropriate than merely increasing the threshold.

This interaction tests whether the useful answer/set/abstain operating region changes with ambiguity.

---

## 9. The five original P03 hypotheses

The original proposal contains five major hypotheses. The experiment translates them into narrower, falsifiable operational tests.

## H1: Frequency Threshold

The proposal suggests that hallucination risk may change sharply below a critical knowledge-frequency level.

The operational study asks whether:

- tail questions have higher risk than head questions;
- a prespecified change-point model predicts held-out data better than a smooth or no-change-point alternative;
- the pattern is visible across the tested model families.

Even a positive result would support only a measured nonlinear transition for the tested exposure proxy and models. It would not establish a universal threshold for all LLMs.

## H2: Synthesis Compounding

The proposal suggests that multi-hop errors may approximately follow:

\[
H_d \approx 1-(1-H_1)^d
\]

The experiment measures every composed query and its atomic components, calculates synthesis loss, and compares observed depth-specific error with both the factorized diagnostic and a conservative union-bound baseline.

The formula is supported operationally only if the observed and predicted risks agree within the predeclared equivalence range. A disagreement is also an important finding because it shows that composition cannot be understood from one-hop accuracy alone.

## H3: CPR Tightness

The proposal predicts that, at `alpha = 0.05`, CPR can achieve:

- at least 95% finite-label empirical coverage;
- an average prediction-set size no larger than 3;
- more than 30% efficiency improvement over the frozen temperature-based baseline.

These conditions are evaluated on the same calibration and test records. Any coverage statement is limited to the finite-label track and audited assumptions. Open-ended candidate recall is reported separately.

## H4: Domain Calibration Transfer

The proposal expects calibration to transfer better within a domain than across domains.

For example, a calibrator fitted on medical validation data may improve performance on unseen medical data but fail to improve legal data. The experiment tests both transfer directions and measures calibration with metrics such as Brier score and calibration error.

Calibration alone does not change the model's answer. Any reduction in hallucination risk must be attributed to a fixed selection or abstention policy that uses the calibrated score.

## H5: Abstention Performance

The proposal predicts that CPR-derived policies will have a better risk-coverage trade-off than temperature-based and verbalized-uncertainty baselines.

The experiment applies every policy to the same cached generations and compares:

- AURC;
- selective risk at matched answer rates;
- answer rate at matched risk targets;
- prediction-set size;
- abstention.

If CPR performs better at all registered comparison points, the study may say that it empirically Pareto-dominated the named baselines on the tested grid and workloads. It cannot claim global optimality over every possible policy.

---

## 10. How the experiment isolates the effects

The project does not run every possible combination of all seven dimensions. Such a seven-way Cartesian product would be too large and difficult to interpret.

Instead, R1-R6 use controlled one-dimension-at-a-time sweeps. For example, when studying frequency, the experiment attempts to hold precision, recency, ambiguity, synthesis depth, and domain at their anchor conditions. R7 is applied afterward to the same cached model outputs, so different thresholds do not require regenerating answers.

The anchor profile is:

```text
R1 frequency:        middle
R2 precision:        medium
R3 recency:          pre-cutoff
R4 ambiguity:        unambiguous
R5 synthesis:        one hop
R6 domain:           general
R7 policy threshold: 0.70
```

When a perfect anchor comparison is scientifically artificial or impossible, the protocol requires matching or stratification and a recorded exception.

This design helps distinguish a real dimension effect from differences caused by unrelated properties of the datasets.

---

## 11. Important measurements

CalibRead reports more than accuracy.

### Answer quality

- Exact or alias-aware accuracy
- Typed numerical or date correctness
- Chain accuracy for composed questions
- Synthesis loss

### Calibration and ranking

- Brier score
- Log loss

- Expected Calibration Error (ECE)
- Adaptive Calibration Error (ACE)
- AUROC for distinguishing correct from incorrect answers

### Selective answering

- Error among answered questions
- Answer rate at a fixed risk target
- Risk at a fixed answer rate
- Full risk-coverage curve
- Area under the risk-coverage curve (AURC)

### Prediction-set behavior

- Empirical finite-label coverage
- Mean, median, and 90th-percentile set size
- Singleton rate
- Empty-set rate
- Abstention rate
- Open-ended candidate-oracle recall

### Workload fairness and robustness

- Worst-level or worst-cell result
- Gap between best and worst levels
- Results under balanced, deployment-like, and stress-weighted mixtures

The aim is to prevent a strong pooled result from hiding a serious failure in a rare or difficult subgroup.

---

## 12. A complete end-to-end example

Imagine a medical assistant built on an LLM. A clinician asks:

> According to a newly issued specialist guideline, what exact dosage should be used for a rare condition in a patient with complication X?

This question is difficult along several dimensions:

- **R1 frequency:** the condition is rare;
- **R2 precision:** an exact dosage is required;
- **R3 recency:** the guideline was issued after the model cutoff;
- **R4 ambiguity:** the patient's complication may allow multiple interpretations;
- **R5 synthesis:** the answer requires combining guideline, condition, and complication facts;
- **R6 domain:** the question is expert medical knowledge;
- **R7 policy:** the application may require a very high reliability threshold.

A normal chatbot might generate one confident dosage. A CalibRead-style wrapper would examine whether the applicable calibration group has adequate support and whether the score satisfies the chosen policy.

Possible result:

```text
Decision: abstain
Reason codes:
- post-cutoff knowledge
- expert-domain calibration support inadequate
- rare multi-hop workload outside certified finite-label region
```

Alternatively, in a finite-label decision problem with an independently supplied set of permitted dosage categories, it might return:

```text
Decision: set
Candidate dosage categories: {Category B, Category C}
Nominal marginal coverage target: 95%
Scope: finite-label workload under recorded exchangeability assumptions
```

This does not make the model medically safe by itself. It demonstrates the kind of explicit boundary and action contract that the research evaluates.

---

## 13. What different outcomes would mean

## A strong positive outcome

The study might find that:

- global averages hide serious failures on rare and compositional questions;
- workload-aware calibration identifies many of these failures;
- finite-label conformal sets attain their nominal target under the audited assumptions;
- the wrapper improves worst-group reliability;
- useful reliability is achieved with reasonably small sets and acceptable abstention.

The conclusion would be:

> A database-like LLM Read contract is feasible for specified workloads under explicit assumptions, but reliability must be conditioned on query characteristics.

## A mixed outcome

The wrapper might make the retained answers safer but abstain frequently:

```text
Global policy:
Answer rate: 90%
Error among answers: 14%

Workload-aware policy:
Answer rate: 55%
Error among answers: 5%
```

This is neither a simple success nor a failure. It exposes the cost of meeting a reliability target. An application must decide whether the lower risk is worth answering fewer questions.

## A negative outcome

The study might find that:

- confidence cannot distinguish correct from incorrect answers in hard groups;
- calibration breaks under temporal or domain shift;
- open-ended candidate recall is too low;
- prediction sets become too large to be useful;
- low risk requires nearly universal abstention.

This would still be a valuable answer. It would show where current LLMs cannot support a practical database-like Read contract.

## Null or reversed hypotheses are still valid results

The study is complete when the frozen experiments, comparisons, intervals, audits, and failures are reported—not when a preferred method wins. For example, finding no sharp frequency threshold or finding that a simple baseline beats CPR would still answer the registered research question.

---

## 14. What the research can and cannot claim

If the evidence supports it, the study may conclude that:

- one-number reliability summaries hide failures in difficult subgroups;
- controlled R1-R7 sweeps reveal where reliability changes;
- frequency and synthesis, recency and domain, or ambiguity and policy interact;
- workload-aware calibration trades answer efficiency for improved worst-cell behavior;
- an explicit Read record makes assumptions and unsupported regions visible.

The study cannot conclude that:

- a confidence value is automatically the probability that one particular answer is correct;
- an exposure proxy equals the exact proprietary training frequency;
- a finite-label conformal guarantee applies automatically to open-ended generated candidates;
- coverage survives arbitrary distribution shift;
- prediction sets are automatically minimal;
- better results on the tested policy grid prove global optimality;
- observational dataset differences establish causal effects.

These boundaries keep the conclusions scientifically defensible.

---

## 15. Final plain-language summary

Most LLM evaluations ask, "How often is the model correct?" CalibRead asks a deeper set of questions:

- On what kinds of questions is it correct?
- Does it know when it is likely to be wrong?
- Does its confidence remain meaningful for rare, recent, ambiguous, multi-step, or expert questions?
- Can several individually reliable facts be composed into a reliable answer?
- Can a calibrated wrapper return a small candidate set when one answer is unsafe?
- Can it abstain when the requested reliability cannot be supported?
- What answer-rate or efficiency cost must we pay to reduce risk?

The central idea is that LLM reliability is not one fixed number. It depends on the question, the workload, the calibration evidence, and the decision policy. CalibRead aims to map those dependencies and turn them into an explicit, auditable answer/set/abstain contract.

In the simplest possible words:

> CalibRead is trying to teach an LLM-based system not only to answer questions, but also to recognize the boundaries of when its answers are reliable enough to use.

---

## 16. Authoritative project documents

This explanation is based on the repository's frozen research materials:

- `README.md` — concise project framing and implementation status;
- `docs/research_protocol.md` — authoritative paper question, experiment design, measurements, and claim limits;
- `docs/hypothesis_registry.md` — mapping from the original P03 hypotheses to defensible operational tests;
- `Proposal.html` — original CalibRead proposal and hypotheses.
