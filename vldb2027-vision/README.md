# CalibRead vision paper (PVLDB Volume 20 / VLDB 2027)

Source for a **Vision** submission. Official rules (rechecked against
https://vldb.org/2027/submission-guidelines.html and
https://www.vldb.org/2027/formatting-guidelines.html):

- Category: Vision (research track). Limit **6 pages excluding references**.
- Title **must** end with `[Vision]` in the PDF and in CMT (dropped in camera-ready).
- Single-blind: names and affiliations on page 1.
- Use this bundled `acmart.cls` v2.19 + `pvldb.sty`. Do not swap the class.
- Abstract is mandatory by the **25th** of the previous month; full paper by the **1st**, 5:00 p.m. Pacific.
- After acceptance, **authors cannot be added**. Current authors: Aadit Shah and Yash Sinha.
- Vision papers with no experiments may skip artifacts; give that reason in CMT.

## Compile

Requires a TeX Live (or MiKTeX) install with `pdflatex` and `bibtex`:

```text
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

Then check that **content through the conclusion is at most 6 pages**.
References may continue onto later pages.

Upload `main.tex` plus this folder to the official Overleaf template if you
do not have LaTeX locally:
https://www.overleaf.com/latex/templates/official-vldb-template/ptsndjkwxkdr

Copy `main.tex` and `refs.bib` into that project; keep `\usepackage{pvldb}`
and `\vldbtopmatter` unchanged.

## Mandatory PVLDB blocks (verified by compile)

These are **not** typed by hand in the body. They are emitted when you compile
with the bundled template:

| Block | How it appears | Status |
|---|---|---|
| **PVLDB Reference Format** | `\vldbtopmatter` right after `\maketitle` | Present |
| **CC BY-NC-ND license footnote** | same command | Present |
| **PVLDB Artifact Availability** | only if `\vldbavailabilityurl` is non-empty | Omitted (vision; no artifact) |
| **ACM-Reference-Format bibliography** | `\bibliographystyle{ACM-Reference-Format}` | Present |

After `pdflatex` + `bibtex` + `pdflatex` ×2, page 1 must show:

```text
PVLDB Reference Format:
Aadit Shah and Yash Sinha. CalibRead: Reliability Contracts for Parametric
LLM Databases [Vision]. PVLDB, 20(1): XXX-XXX, 2027.
doi:XX.XX/XXX.XX
```

A compiled `main.pdf` is kept in this folder for spot-checking. Recompile before
upload if you edit `main.tex`.

**Figures (vector TikZ in `figures/calibread-figures.tex`):**

1. **Figure 1** — hybrid plan motivation (fluent UDF vs CalibRead contract)
2. **Figure 2** — finite-label vs open-ended evaluation tracks
3. **Figure 3** — layered system architecture (optimizer + certificate log)

For crisper AI-generated versions, use copy-paste prompts in
`figures/SCIFIG_PROMPTS.md` at [scifig.ai](https://scifig.ai/app/text-to-figure).

## Before you submit

1. Confirm emails in the author block (`f20220612@pilani.bits-pilani.ac.in` and `yash.sinha@pilani.bits-pilani.ac.in`) before CMT upload.
2. Complete CMT conflicts and the Self-Assessment of Relevance (data-management focus is the Read contract, not NLP calibration).
3. Do **not** submit this concurrently with an EA&B/full paper on the same contribution.
4. The sealed-probe table reports PopQA ($n=7046$ per model) and the SOCRATES slice of the multi-hop pipeline ($n=30387$ test examples overall). Do not frame exact match, pooled ECE, or forced-prompt thresholds as coverage at $\alpha$. Human audit is still pending.
