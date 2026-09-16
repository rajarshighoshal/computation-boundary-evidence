# Plot specification — how to draw the figures for this report

Hand this file plus `results/evidence-packet.json` to whoever (or whatever) draws the plots.
The packet carries every number; this file says what to draw and what not to.

## What the experiment is

Two arms attempt the same SWE-bench Science tasks under an identical budget:

- **baseline** — ordinary shell tools only.
- **CBE** — the same tools plus three query endpoints (`science_find`, `science_inspect`,
  `science_note`) over a prepared evidence store of computations, conditions, documented
  definitions and distilled call boundaries. Preparation is static: parsers and analyzers, no
  model call, no code execution.

A **solve** is the official verifier reward for one attempt. `verified` counts attempts that
produced a verifier verdict; attempts lost to provider or container failures are excluded, not
counted as failures. Do not recompute rates with a different denominator.

Partitions in the packet:

| key | tasks | replicate runs | role |
|---|---|---|---|
| `locked89_k3` | 89 | 3 | held out; the only inferential partition |
| `dev30_k4` | 30 | 4 | used for iteration; optimistic by construction |

## Style contract (non-negotiable if the figures must match the report)

Sources of truth: `paper/figures/theme.py` (palette, fonts, rc) and `paper/figures/viz.py`
(primitives). Figures are authored in Matplotlib; these rules are enforced by
`paper/figures/requirements.py`, which refuses to save a violating figure.

1. **Type**: STIX serif (`font.serif = STIXGeneral`), body 8 pt, tick labels 7.2–7.5 pt,
   **nothing below 6 pt** at design size. Design at 5.5 in wide and let the report include it at
   6.5 in (1.18× upscale), or design at 6.5 in and include at natural size. Never design larger
   and shrink.
2. **Colour semantics, fixed paper-wide**:
   - `BLUE #2468A0` = baseline arm, **always a circle**.
   - `TEAL #408F83` = CBE arm when it improves something, **always a square**.
   - `RUST #B5523A` = CBE arm when it worsens something, **always a square**.
   - `INK_SOFT #555555` = neutral text and parity rows; `TIE #C9CED3` = connector lines only;
     `GRID #D9D9D9` = hairline gridlines; light tints (`#EAF4FA`, `#EAF6F4`, `#F3F3F3`) = card
     fills only, never data.
   Shape and colour must both carry the arm; never colour alone.
3. **Layout**: panel letter (bold, 8.6 pt) above a bold left-anchored title (8.4 pt); horizontal
   hairline gridlines only; no top/right/left spines; short x ticks; nothing outside the canvas;
   no two text elements overlapping; ≤ 58 text elements; ink coverage 3.5–45 % of the canvas.
4. **No confidence intervals, no error bars, no boxplots.** With 2–3 attempts per task they are
   decoration. Annotate **counts** (`0/3 → 2/3`) or signed differences in percentage points.
5. Annotate every mark that carries a claim; state the sample size wherever a rate appears.
6. One figure = one claim. Write the claim in the caption's first sentence.

## The figures

### fig_parity — "the same solves, fewer tokens, and only 15 tasks move"
Data: `headline.locked89_k3.*`, `by_task.locked89_k3.*`.
Panel A: for each task whose solve **rate** differs between arms, a horizontal bar of
`cbe_rate − baseline_rate` in percentage points, one row per task, rows sorted by sign then
magnitude, row label = task ID, value printed at the bar end. State the tie count (74) once.
Panel B: two bars of `output_tokens` (12.01M vs 10.36M) with the relative change (−13.7 %)
labelled. Also useful as text: mean output per attempt 45.8k → 39.8k.

### fig_domains — "wins and losses separate by discipline"
Data: `by_domain.locked89_k3` (panel A) and `by_domain.dev30_k4` (panel B).
One row per domain with at least 3 tasks (A) or 2 tasks (B). Per row: baseline rate as a circle,
CBE rate as a square, a connector line, and the signed difference as a number in a column to the
right of each panel (inside its own axes). Row label = domain name plus task count. Show the
`overall` row last, separated by a hairline. Do not draw intervals.

### fig_stability — "most tasks never move; a fifth do"
Data: `replication.histogram`, `by_task.locked89_k3.*`.
Panel A: tasks by number of replicate runs that solved them (0–3), two bars per category.
Panel B: pass@k, k = 1..3 **only** (three locked runs), share of tasks solved by at least one of k
pooled runs, per arm. Label only the end points. A note that ~18 tasks flip inside an arm and the
arms disagree on 15 tasks in total belongs in the caption.

### fig_grounding_flow — "what the agent receives"
Schematic, no data. Left: three cards — static extraction (no model call), queryable evidence
store (computations, conditions, definitions, boundaries), endpoints beside ordinary shell tools.
Right: recorded payloads, verbatim, including one boundary record with `kind`, `provider`,
`assume: correct_interface`, `repair_scope`, and the baseline equivalent (`grep`). If a card is
too short for its text the fix is a taller card or fewer lines, never smaller type.

## Data integrity rules

- Read numbers only from the packet (or the receipts it is built from). Never type a number into
  plot code except layout constants.
- Keep `solved` and `verified` together; a rate without its denominator is not reportable here.
- If a figure would need a statistic the packet does not contain, say so instead of estimating.
