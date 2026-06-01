# nodeLockRows.c

- **Source:** `source/src/backend/executor/nodeLockRows.c` (≈360 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Applies `SELECT … FOR UPDATE/SHARE/NO KEY UPDATE/KEY SHARE` row locks.
Receives rows from its child, and for each row, for each rowmark (one per
locked RTE), locks the underlying tuple. On version conflict it triggers
EvalPlanQual to re-run a child copy on the latest tuple version.
[from-comment INTERFACE]

## Mechanics

`ExecLockRows`: pull row from outerPlan. For each `ExecRowMark`:

1. Extract junk-column `ctid` / `tableoid` (for partitioned/inheritance
   targets) / `wholerow` (for non-table RTEs) from the slot.
2. Call `table_tuple_lock(rel, &tid, snapshot, slot, cid, lockmode, waitpolicy, &flags)`.
3. Handle return:
   - TM_Ok → continue.
   - TM_Updated/TM_Deleted under READ COMMITTED → set up EPQ for the
     updated tuple, rerun the child plan against locked versions,
     re-fetch updated columns. Loop.
   - TM_WouldBlock with SKIP LOCKED → discard this outer row, continue.
   - TM_WouldBlock with NOWAIT → ereport(ERROR).

## Foreign tables

If the rowmark's relation is foreign, calls `RefetchForeignRow` /
`RecheckForeignScan` instead of `table_tuple_lock`.

## Tags

- [verified-by-code] table_tuple_lock contract + EPQ trigger.
- [from-README] EvalPlanQual integration narrative.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
