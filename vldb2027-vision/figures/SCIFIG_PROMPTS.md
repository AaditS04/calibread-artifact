# SciFig prompts for CalibRead (VLDB 2027 vision paper)

Use [SciFig Text-to-Figure](https://scifig.ai/app/text-to-figure). Recommended settings:

- **Style:** Scientific (or Line for extra crispness)
- **Aspect:** 16:9 for Figures 1 & 3; 4:3 for Figure 2 (architecture)
- **Export:** SVG or PDF (vector) for LaTeX; otherwise 8K PNG at 300 DPI
- **After generation:** open in Vector Canvas, fix labels, export `fig1-motivation.pdf` etc.

Drop your current TikZ screenshot into [Reference-to-Figure](https://scifig.ai/app/reference-to-figure) if you want SciFig to match layout but look more polished.

---

## Figure 1 — Motivation (hybrid plan vs CalibRead)

**Filename:** `fig1-motivation.pdf`

**Prompt:**

```
Publication-quality database systems architecture diagram for a VLDB/PVLDB paper. Two-column academic figure, white background, crisp vector flat style, subtle shadows, high contrast.

Layout: three columns top row, three columns bottom row, left-to-right data flow with arrows.

TOP ROW:
[Blue box] "Relational subplan" — mini SQL: SELECT country FROM orders WHERE region='EU'. Label above: "stored tuples".
[Coral/salmon box] "Parametric Read (today)" — "LLM UDF: capital of country → fluent string" and warning text "no NULL, no typed set". Label above: "status quo".
[Teal/green box] "CalibRead contract" — "declare W, α, actions A → answer / set / abstain + scoped Read certificate". Label above: "vision".

BOTTOM ROW:
[Blue box] "Downstream join" — "needs typed value or explicit missingness".
[Coral box] "Failure mode" — "wrong tuple poisons plan; lineage = prompt only". Dashed red arrow from status-quo box.
[Green box] "Engine behavior" — "optimizer routes on certificate; retrieve / rewrite / fail". Solid arrow from vision box.

Arrows: solid dark gray between pipeline stages. Color palette: blue #2E86AB, coral #E07A5F, teal #2A9D8F, dark text #1F2937. No photographs, no 3D, no cartoon characters. Sans-serif labels, journal typography, minimal clutter.
```

---

## Figure 2 — System architecture (CalibRead operator in hybrid engine)

**Filename:** `fig2-architecture.pdf`

**Prompt:**

```
Layered system architecture diagram for a database research paper (VLDB style). White background, crisp flat vector scientific illustration, top-to-bottom flow, full width double-column figure.

LAYER 1 (wide blue banner): "Hybrid query interface — SQL + semantic operators → logical plan".

LAYER 2 (two blue boxes side by side):
Left: "Optimizer — cost(tokens, latency, contract risk)" with contract risk in purple.
Right: "Physical planner — parametric Read vs index vs retrieval".

LAYER 3 (wide teal banner): "Parametric Read operator — CalibRead wrapper around frozen generations".

LAYER 4 (four white boxes in a row inside layer 3):
"1. Score — generate & rank" → "2. Calibrate — frozen object" → "3. Policy — R7 threshold" → "4. Act — answer / set / abstain".

LAYER 5 (two boxes):
Left purple box: "Read certificate — track, W, assumptions, hashes, guarantee scope".
Right blue box: "Execution engine — commit tuple, possible set, or plan rewrite".

LAYER 6 (wide amber/gold banner): "Provenance / audit log — replay every committed parametric value to its certificate".

Use consistent rounded rectangles, 2pt borders, soft fill colors (blue #E8F4FA, teal #E6F6F3, purple #EEECFA, amber #FFF6E5). Arrows between layers. Professional, Nature/Cell schematic quality, no stock icons, no gradients-heavy 3D.
```

---

## Figure 3 — Two evaluation tracks

**Filename:** `fig3-tracks.pdf`

**Prompt:**

```
Single-column scientific flowchart for a database paper. White background, crisp vector style, vertical flow, color-coded branches merging at bottom.

TOP (blue section):
Box: "Track A: finite-label — universe Y fixed BEFORE scoring"
Arrow down to white box: "split conformal → set C(q)⊆Y — marginal coverage if assumptions hold"

MIDDLE (amber section):
Box: "Track B: open-ended — candidates GENERATED post hoc"
Arrow down to white box: "report ORACLE RECALL first — no coverage if truth ∉ candidates" (highlight in coral)

BOTTOM (wide purple banner):
"Engine rule: never merge Track A and Track B into one certified accuracy metric"

Arrows from both branches into bottom rule. Colors: blue #2E86AB, amber #E9A319, coral accent #E07A5F, purple #5B4FCF. Clean sans-serif text, minimal decoration, suitable for PVLDB proceedings print.
```

---

## Optional: sketch-to-figure workflow

1. Screenshot the compiled `main.pdf` figures (or sketch on paper).
2. Upload to [Sketch-to-Figure](https://scifig.ai/app/sketch-to-figure).
3. Paste the matching prompt above in the description field.
4. Export SVG → convert to PDF if needed:

```powershell
# If you have Inkscape installed:
inkscape fig1-motivation.svg --export-filename=fig1-motivation.pdf
```

## Wiring exported figures into LaTeX

In `main.tex`, replace `\CalibReadFigMotivation` with:

```latex
\includegraphics[width=\linewidth]{figures/fig1-motivation.pdf}
```

(Repeat for figures 2 and 3.)
