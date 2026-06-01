# execUtils.c

- **Source:** `source/src/backend/executor/execUtils.c` (1525 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (every PG executor user touches these helpers)

## Purpose

Catch-all for executor housekeeping: `EState` lifecycle, `ExprContext` per-tuple
memory contexts, scan-relation open/close, range table materialisation, callback
registration on ExprContext shutdown. [from-comment] `:14-50`

## EState (executor state) lifecycle

- `CreateExecutorState()` — allocates a TopMemoryContext-rooted "ExecutorState"
  AllocSet context, switches into it, palloc0's the EState, sets defaults
  (`es_direction = ForwardScanDirection`, `es_snapshot = InvalidSnapshot`).
  Returns the EState; caller is expected to fill in snapshot/range table.
- `FreeExecutorState(estate)` — destroys the per-query memory context, which
  frees every plan state node, ExprState, ExprContext, slot, etc. en masse.
  This is why ExecEndNode generally only needs to close relations / drop pins.

## ExprContext lifecycle

- `CreateExprContext(estate)` — creates one ExprContext attached to the EState.
  Allocates its `ecxt_per_tuple_memory` as a child AllocSet ("ExprContext").
- `CreateStandaloneExprContext(estate)` — same but the ExprContext is NOT
  linked into `estate->es_exprcontexts` (used by callers that manage their
  own lifetime, e.g. evaluating CHECK constraints).
- `FreeExprContext(econtext, isCommit)` — runs all registered shutdown
  callbacks, then deletes the per-tuple context.
- `ReScanExprContext(econtext)` — resets the per-tuple context AND runs
  shutdown callbacks (so SRFs and similar can release tuplestores between
  rescans).
- `RegisterExprContextCallback(econtext, fn, arg)` — used by SRFs, JsonExpr,
  and others to ensure cleanup at ExprContext shutdown.

## Plan-state init helpers

- `ExecAssignExprContext(estate, planstate)` — boilerplate every Init routine
  uses: creates an ExprContext and stores it on `planstate->ps_ExprContext`.
- `ExecAssignProjectionInfo(planstate, inputDesc)` — builds the node's
  projection from `plan->targetlist` against the input TupleDesc.
- `ExecAssignScanProjectionInfo` / `ExecAssignScanProjectionInfoWithVarno` —
  variants for scan nodes (vartno = INDEX_VAR vs OUTER_VAR vs scanrelid).
- `ExecConditionalAssignProjectionInfo` — skip projection entirely if the
  TLIST is the identity projection on the input (saves work and a slot).

## Range-table interfaces

- `ExecInitRangeTable(estate, rangeTable, permInfos)` — installs the RT into
  the EState and allocates the parallel `es_relations`, `es_rowmarks`,
  `es_result_relations` arrays. Called from ExecutorStart.
- `ExecGetRangeTableRelation(estate, rti, isResultRel)` — lazily opens (and
  locks) the relation for an RT index, caching it in `es_relations[rti-1]`.
  Important: this is the only place that does the lock. `isResultRel`
  controls the lock strength (RowExclusive vs the planner-recorded lockmode).
- `ExecOpenScanRelation` — wrapper for scan nodes; checks that the planner
  already took the lock and just calls table_open(rel, NoLock).
- `ExecCloseRangeTableRelations` — close everything in the array; called at
  ExecutorEnd.

## Result-relation routing

- `ExecInitResultRelation(estate, resultRelInfo, rti)` — fills in a
  ResultRelInfo for a (top-level or partition) target relation, including
  index info, triggers, projection.
- `ExecGetResultRelCheckAsUser`, `ExecGetUpdatedCols`, `ExecGetInsertedCols`,
  `ExecGetExtraUpdatedCols`, `ExecGetAllUpdatedCols` — bitmapset accessors
  used by row-level security, generated columns, and the trigger machinery.

## Other notable helpers

- `executor_errposition(estate, location)` — for ereport() during execution:
  translates a parse-tree location into "LINE n: …" style error position
  using the source text the planner stored.
- `UpdateChangedParamSet(planstate, newParams)` — propagates parameter
  changes downward to mark which subnodes need rescan.
- `ShutdownExprContext(econtext, isCommit)` — runs the registered callback
  list (used internally by FreeExprContext and ReScanExprContext).

## Tags

- [verified-by-code] entry-point names; lock acquisition rule
  (ExecGetRangeTableRelation is the single point of relation open).
- [from-comment] interface listing at top of file.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
