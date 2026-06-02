# fmgr-and-spi skill — FINAL

## Status

Skill is shipped and complete. Two iterations of eval-driven review;
no factual errors discovered across either iteration.

## Results

| | with-skill | baseline |
|---|---|---|
| Iteration 1 | 21 / 21 (100%) | 12 / 21 (57%) |
| Iteration 2 | 21 / 21 (100%) | 13 / 21 (62%) |

Iter-2 baseline gained 1 point on Eval 3 (popped-SPI-frame rule) — best
read as run-to-run variance, not a real shift, since the model has no
skill state between baseline runs.

## What iteration 2 changed in the skill

Five small refinements from `iteration-1/proposed-edits.md` were applied
(see `iteration-2/edits-applied.md` for the exact placements):

1. §1.12 — backlink: "do not use fn_extra in a value-per-call SRF (see §1.9)"
2. §2.3 — "Cached on fn_extra — the full pattern" example combining
   `fn_mcxt` palloc + `SPI_keepplan`
3. §2.7 — "Capturing diagnostics from a failed SPI call" paragraph
   making explicit that `CopyErrorData` before `FlushErrorState` is the
   supported channel, and that partial rows must be `SPI_palloc`'d out
   before rollback
4. §1.10 — MAT_SRF flags promoted from one-liner to a 2-row mini-table
5. §2.5 — names `AtEOSubXact_SPI` with a pointer to §2.7

All edits are tightening of cross-reference web. No content was
corrected — iter-1 found nothing wrong.

## Where the skill consistently beats baseline

The reliably skill-only assertions are:

- File:line citations (`funcapi.c:100-122`, `spi.c:977-1001`,
  `spi.c:482-572`).
- Named internal functions: `AtEOSubXact_SPI`, `SaveCachedPlan`,
  `fn_mcxt`, the MAT_SRF flags.
- Cross-cutting rules the baseline tends to miss:
  - `fn_extra` is reserved by the SRF machinery (`SRF_IS_FIRSTCALL`
    tests `fn_extra == NULL`).
  - `SPI_commit` / `SPI_rollback` forbidden inside a PL exception
    block — same root cause as the SPI_tuptable rule (open subxact).
  - "Materialize SRF pitfall is the single most common SRF bug" framing.

## Files

- `iteration-1/` — initial eval pass, proposed edits, summary
- `iteration-2/` — applied edits, re-graded eval pass
- `.claude/skills/fmgr-and-spi/SKILL.md` — the skill itself (post-edits)

## Recommendation

Skill is in good shape. No further iterations planned. Future work
would be domain expansion (e.g. cover trigger.c invocation, PL handler
boilerplate, datatype I/O function templates) rather than refining the
current scope.
