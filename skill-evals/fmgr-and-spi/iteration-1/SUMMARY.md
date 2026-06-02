# fmgr-and-spi skill — iteration 1 summary

## Setup

Three realistic prompts written to `evals.json`:

1. Materialize-mode SRF: where tuplestore + TupleDesc must live.
2. SPI_prepare cached on fn_extra segfaults on second call.
3. Looking at SPI_tuptable after a subxact rollback crashes.

Each was answered twice (baseline vs. with skill) in `answers.md`. Five to
seven assertions were drafted per eval (21 total) and judged in
`grading.json`.

## Results

| | with-skill | baseline |
|---|---|---|
| Eval 1 (Materialize SRF) | 7 / 7 | 4 / 7 |
| Eval 2 (SPI_prepare + fn_extra) | 7 / 7 | 4 / 7 |
| Eval 3 (SPI_tuptable after rollback) | 7 / 7 | 4 / 7 |
| **Total** | **21 / 21 (100%)** | **12 / 21 (57%)** |

## Key findings

- Skill is correct and complete on the three primary footguns. All
  21 assertions passed with skill loaded. No factual errors discovered
  while cross-checking against knowledge/idioms/fmgr.md, spi.md, and
  the cited source files.
- Skill adds clear value over baseline (~57%). Consistently-missed
  baseline assertions cluster around: file:line cites, specific named
  internal functions (AtEOSubXact_SPI, SaveCachedPlan, fn_mcxt), and
  implicit cross-rules (fn_extra owned by SRF machinery; SPI frames
  opened inside a dying subxact are popped; SPI_commit forbidden inside
  PL exception blocks for the same root reason).
- Proposed edits are refinements, not corrections — see
  proposed-edits.md. Nothing in the skill is wrong; the largest gap is
  that some load-bearing facts (fn_extra ownership by SRFs, ErrorData
  as the supported diagnostic channel) appear in only one place and
  benefit from a second pointer.

## Recommendation

Skill is in good shape. Optional iteration-2 work: apply the five edits in
proposed-edits.md. No iteration-2 strictly required.
