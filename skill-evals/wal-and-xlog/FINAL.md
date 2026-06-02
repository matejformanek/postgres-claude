# `wal-and-xlog` — Skill Eval Final Report

## Headline

- **Iter-1 with_skill**: 21/21 (100%) | baseline: 5/21 (~24%)
- **Iter-2 with_skill**: 21/21 (100%) | baseline: 5/21 (~24%)

Scores unchanged at ceiling. Iter-2 was a robustness pass, not a coverage
pass: every iter-1 `[unverified]` that could be retired with a one-line grep
has been retired with a code cite.

## What iter-2 changed in the skill

All seven proposals from `iteration-1/proposed-edits.md` applied. Concrete
values were verified against `source/...` before writing.

| # | Proposal | Verification |
|---|---|---|
| P1 | Inline `MAX_GENERIC_XLOG_PAGES` value | = `XLR_NORMAL_MAX_BLOCK_ID` = **4** (`generic_xlog.h:23`, `xloginsert.h:28`) |
| P2 | Explain why `record->EndRecPtr` for `PageSetLSN` in redo | added rationale paragraph |
| P3 | Document `XLogReadBufferForRedo` return-value triad | 4-row table cited to `xlogutils.h:74-78` |
| P4 | Add writer↔redo symmetry to pre-commit checklist | new bullet |
| P5 | Retire `rm_decode` mandatoryness `[unverified]` | optional; called only when non-NULL (`decode.c:116-117`) |
| P6 | Cross-link companion skills in description | mentions `locking` + `error-handling` |
| P7 | Fix the `_PG_init` ereport snippet | now a real `ereport(ERROR, (errcode(...), errmsg(...)))` |

Remaining `[unverified]` after iter-2:

- `XLogRegisterBlock` behaviour — out of scope for a one-line grep, needs a
  read of `xloginsert.c`.

## Why scores didn't move

The assertion set was already saturated at iter-1. The skill's qualitative
robustness improved:

- E3-A3 (`PageSetLSN` uses `record->EndRecPtr`) passed in iter-1 because the
  example code shows it — but the skill never *said why*. Iter-2 adds the
  rationale, so the assertion holds even when a future model paraphrases
  rather than copying the snippet.
- E1 answer no longer carries a `[unverified value — check at use site]`
  hedge on the Generic WAL page cap.
- E3 answer now warns about the writer↔redo symmetry bug class
  (`wal_consistency_checking` blind spot), which is one obvious candidate
  for an A8 in a future iteration.

## Baseline gap that stays

Baseline knows the *shape* of all three answers (Generic WAL exists,
seven-step writer rule, idempotent redo) but consistently misses:

- exact constants (`128..255`, `RM_EXPERIMENTAL_ID = 128`,
  `MAX_GENERIC_XLOG_PAGES = 4`)
- placement rules around the critical section (pre-flight checks outside,
  `MarkBufferDirty` before `XLogInsert`, `XLogEnsureRecordSpace` outside)
- Hot Standby implications for multi-buffer lock order in redo
- the `MarkBufferDirtyHint`-in-redo trap and *why* it's a trap
- `rm_mask` + `wal_consistency_checking` for test coverage
- contrib pointers (`bloom`)

Net: skill carries the precision needed to actually write correct
WAL-touching code; baseline carries enough to write code that *looks* right
but has known failure modes.

## Recommended next iteration

The skill is at a release-grade quality bar. Future work, in priority order:

1. **Expand assertion set** to cover writer↔redo symmetry, the four
   `XLogReadBufferForRedo` return values, and `record->EndRecPtr` rationale
   (vs example-driven recall).
2. **Resolve the remaining `XLogRegisterBlock` `[unverified]`** with a
   focused read of `xloginsert.c`.
3. **Add an E4** on Generic WAL specifically (current evals are
   custom-rmgr-heavy) — the page-cap-of-4 detail is interesting only if
   asked.
