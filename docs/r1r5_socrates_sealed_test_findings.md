# R1 × R5 SOCRATES sealed-test findings

**Status:** engineering-complete, not publication-final (SOCRATES human audit pending).  
**Date:** 2026-09-24.  
**Conditions:** `r5_qwen25_72b_cluster_forced_v1`, `r5_mixtral_8x22b_cluster_forced_v1`.  
**Panel:** `data/processed/socrates_r1r5/` (`socrates_development_atom_tertiles_min_chain_v1`).

This interaction uses the answers already written by the sealed R5 runs. No new
generation was submitted. R1 bins were frozen from development atom counts, then
joined to those scored files. Registered test: **OP-I15**. Protocol context:
[`experiment_matrix.md`](experiment_matrix.md),
[`hypothesis_registry.md`](hypothesis_registry.md). The R5 depth findings remain
in [`r5_cluster_sealed_test_findings.md`](r5_cluster_sealed_test_findings.md).
The PopQA popularity sweep remains in
[`r1_popqa_cluster_sealed_test_findings.md`](r1_popqa_cluster_sealed_test_findings.md).

---

## 1. What was tested

**OP-I15** asks whether frequency and synthesis depth have a non-additive effect
on reliability: whether rare atomic knowledge compounds differently once the
question is multi-hop.

The panel is SOCRATES only. MuSiQue has no frequency proxy and is excluded.
The proxy is the SOCRATES WIMBD Dolma-1.7 atom co-occurrence count. It is a
corpus co-occurrence score shipped with the dataset. It is not a document count
from the Qwen or Mixtral training mix, and it is not the PopQA `s_pop` axis.

Cutpoints were inclusive tertiles of development one-hop atoms only
(2,546 atoms):

| Level | Rule |
|---|---|
| tail | Dolma-1.7 count ≤ 114 |
| middle | 114 < count ≤ 1,138 |
| head | count > 1,138 |

A two-hop chain takes the minimum of its two atom counts, then the same
cutpoints. The composed triple field `wimbd.dolma(e1,e2,e3)` is 0 on every
chain in this extract (development 1,273, calibration 2,399, test 3,560), so
it cannot separate head from tail and was not used.

Cell counts after that rule:

| Cell | Development | Calibration | Test |
|---|---:|---:|---:|
| one-hop head | 849 | 1,692 | 2,457 |
| one-hop middle | 845 | 1,482 | 2,134 |
| one-hop tail | 852 | 1,624 | 2,529 |
| two-hop head | 9 | 26 | 32 |
| two-hop middle | 413 | 750 | 1,001 |
| two-hop tail | 851 | 1,623 | 2,527 |

The protocol floor is 75 examples per interaction cell. **Head × two-hop is
below that floor on every split** and is not a confirmatory cell. The
confirmatory contrast therefore pools middle and head:

- gap = tail accuracy − (middle + head) accuracy, within one hop and within two hops
- interaction = two-hop gap − one-hop gap

A negative gap means the tail is less accurate than the pooled rest. A positive
interaction means that tail penalty is smaller at two hops than at one hop.
Intervals are percentile bootstrap, 2,000 resamples, seed 7, independent within
cell. The three-level table is still reported. Bins were not moved after the
join.

Each scored file contributes its `socrates_v1` rows only: development 3,819,
calibration 7,197, test 10,680. Atoms and the composed question share a split.

---

## 2. Hypothesis scorecard

| Claim | Result |
|---|---|
| Frequency and hop depth are non-additive on the sealed test | **Held for Qwen.** Interaction +42.8 pp, interval +40.6 to +45.0. **Not held for Mixtral.** Interaction +2.1 pp, interval −0.3 to +4.3 |
| The interaction is an extra penalty for rare chains | **Not what the cells show.** Qwen's one-hop tail penalty is about −42 pp. At two hops both the tail and the pooled rest sit near 2%, so the gap disappears because accuracy is at the floor |
| Head × two-hop can be read as the "common multi-hop" cell | **Unsupported.** Test n = 32, below the floor of 75 |
| Synthesis still fails after both atoms are correct, inside supported R1 bins | **Held** for middle and tail, both models. Test synthesis loss is 92.8–98.5% |
| That synthesis loss is worse in the tail than in the middle | **No stable extra tail penalty.** Test differences are a few points, and Mixtral's tail loss (97.9%) is slightly lower than its middle loss (98.5%) |
| The axis is training frequency for these models | **Not tested.** The axis is Dolma-1.7 co-occurrence |
| The PopQA popularity gradient transfers to this panel | **Only for Qwen one-hop.** Mixtral one-hop accuracy is 72–79% across all three bins |
| Full OP-I15 gate (three families, audited matched sets, head × two-hop supported) | **Not met.** Two families, human audit pending, one cell unsupported |

---

## 3. Exact match by bin

### 3.1 Sealed test

| Model | Hop | Head | Middle | Tail |
|---|---|---:|---:|---:|
| Qwen 72B | one | 62.8% (1,544/2,457) | 48.7% (1,040/2,134) | 13.8% (349/2,529) |
| Qwen 72B | two | 0/32, unsupported | 2.2% (22/1,001) | 2.5% (63/2,527) |
| Mixtral 8×22B | one | 71.7% (1,762/2,457) | 79.5% (1,696/2,134) | 74.3% (1,879/2,529) |
| Mixtral 8×22B | two | 0/32, unsupported | 1.0% (10/1,001) | 2.1% (52/2,527) |

Qwen one-hop declines with the Dolma tertile: head, then middle, then tail.
That is a steeper one-hop frequency curve than the same model showed on PopQA
popularity, where middle and tail were close. Mixtral one-hop does not decline.
Its middle bin is the most accurate of the three (79.5%), and tail (74.3%)
sits above head (71.7%).

Two-hop exact match is about 1–2.5% in every supported cell. The 32 head
chains are all wrong for both models. That cell stays out of the contrast.

### 3.2 Confirmatory gaps (tail minus pooled middle+head)

| Model | Split | One-hop gap | Two-hop gap | Interaction |
|---|---|---:|---:|---:|
| Qwen | Development | −48.2 pp (−51.2, −45.1) | −0.0 pp (−1.9, +1.7) | +48.2 pp (+44.4, +51.9) |
| Qwen | Calibration | −40.8 pp (−43.1, −38.5) | +1.1 pp (−0.0, +2.2) | +41.9 pp (+39.2, +44.6) |
| Qwen | Test | −42.5 pp (−44.5, −40.6) | +0.4 pp (−0.7, +1.4) | +42.8 pp (+40.6, +45.0) |
| Mixtral | Development | −5.1 pp (−8.8, −1.6) | +1.3 pp (+0.2, +2.5) | +6.4 pp (+2.8, +10.1) |
| Mixtral | Calibration | −0.0 pp (−2.8, +2.6) | −0.5 pp (−1.8, +0.8) | −0.4 pp (−3.4, +2.4) |
| Mixtral | Test | −1.0 pp (−3.1, +1.0) | +1.1 pp (+0.2, +1.9) | +2.1 pp (−0.3, +4.3) |

Qwen's interaction is the same fact on every split: a large one-hop tail
penalty, and no tail penalty once the question is two-hop. The two-hop
interval includes zero on the sealed test.

Mixtral's development split shows a small interaction whose interval excludes
zero. Calibration and the sealed test do not repeat it. The sealed-test
one-hop gap includes zero. The two-hop gap excludes zero only because the tail
is 1.1 points *above* the pooled rest, on a base rate near 2%.

---

## 4. Synthesis loss inside each R1 bin

Synthesis loss is the fraction of chains where both atoms are correct and the
composed answer is still wrong. This is the composition diagnostic. Raw two-hop
accuracy mixes unknown atoms with failed composition.

### 4.1 Sealed test

| Model | R1 bin | Chains | Both atoms correct | Synthesis loss | Supported |
|---|---|---:|---:|---:|---|
| Qwen | middle | 1,001 | 207 (20.7%) | 92.8% | yes |
| Qwen | tail | 2,527 | 220 (8.7%) | 95.9% | yes |
| Qwen | head | 32 | 5 | 100% | no |
| Mixtral | middle | 1,001 | 606 (60.5%) | 98.5% | yes |
| Mixtral | tail | 2,527 | 1,371 (54.3%) | 97.9% | yes |
| Mixtral | head | 32 | 19 | 100% | no |

Qwen's frequency effect shows up in the atoms. Both atoms are correct on 20.7%
of middle chains and 8.7% of tail chains. After that gate, composition still
fails about 93–96% of the time. Mixtral clears both atoms on 54–61% of the
supported chains, including the tail, and then fails the composed question
about 98% of the time. Knowing the rare atoms does not produce the chain.

Development and calibration tell the same story on the supported cells.
Qwen synthesis loss stays between 91.9% and 96.3%. Mixtral stays between
97.1% and 99.2%.

---

## 5. What can be said

1. On this Dolma-1.7 proxy, Qwen's one-hop accuracy falls from 62.8% in the
   head tertile to 13.8% in the tail. The sealed-test tail-versus-rest gap is
   −42.5 percentage points, and the interval excludes zero. The same shape is
   already present on development and calibration.
2. That frequency gap does not survive the hop. Supported two-hop cells are
   about 2% exact match for Qwen and about 1–2% for Mixtral, tail and middle
   alike. Qwen's interaction of +42.8 percentage points is that collapse. It
   is a floor, not an additional rare-chain penalty on top of depth.
3. Mixtral's SOCRATES one-hop accuracy is high across all three tertiles
   (71.7–79.5% on the test split). The sealed-test interaction interval
   includes zero. A Dolma co-occurrence tertile is not a reliability axis for
   this model on this panel, which is a different result from its PopQA
   popularity gradient.
4. When both atoms are already correct, synthesis loss remains above 92% in
   every supported test cell. Mixtral's advantage is atomic recall, including
   in the tail. It does not become a multi-hop read.

## 6. What this bundle leaves open

- Head × two-hop as a confirmatory cell. The min-atom rule leaves 32 test
  chains there.
- Three-hop and four-hop crosses. This cache stops at SOCRATES two-hop.
- MuSiQue, which has no R1 proxy.
- A claim that Dolma-1.7 co-occurrence is the training frequency of either model.
- The factorized residual `observed H_d − [1 − (1 − H_1)^d]` inside each R1
  bin. This bundle reports synthesis loss and the accuracy interaction.
- A third model family, and the SOCRATES human audit.

---

## 7. Artifact hashes

Reports are under `results/r1r5/<condition>/<split>_r1r5_report.json`.

| Artifact | Qwen SHA-256 | Mixtral SHA-256 |
|---|---|---|
| Development report | `67bd5d8a38523567f3e17a8bd4f1d19f6c780a002c5e222359f810346c04bf63` | `3a3142deb599542eed9f4ed82b818c2341c60ca0eb9f624819d13645435fb46b` |
| Calibration report | `5f4096d9344521e621e57c23e773d1a3cfb0198a0cd84a52e2230683ad4c4263` | `4324a3104e703cdd18bbfb9995acaff0b692ff20ed76516e01d02092e075f266` |
| Test report | `8fb94a5fa89f5a12a732af70059d18023f875d585ad72c1d02c5eb00a481c085` | `82560de3426579c804f2a7970d11875303b8ed99c11a5dd75256112ba270c0d5` |
| Test `scored_results.csv` | `3db3141462b1542b79760c407bee1d258b91305f419be24e5e5c0ab337633dd9` | `f6bb074cf5fbeabec3befae03a303d8be1c490e31a7587bcfb57dd3f80f84823` |

Panel manifest: `data/processed/socrates_r1r5/BIN_MANIFEST.json`. Source
examples SHA-256
`643a34b2ddf887d863e2fe5a92fc146facf14c614ba00619820cb7d24f24beae`.
Source seeds SHA-256
`666abf5e1229c866703974d70863de60c0b270c39d676ca4b9f22ff438687dd6`.
