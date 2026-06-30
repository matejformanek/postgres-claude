# executor.h

- **Source:** `source/src/include/executor/executor.h` (818 lines)
- **Last verified commit:** pinned at `02f699c14163` (re-verified +
  re-pinned 2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump
  `4abf411e2328..02f699c14163`; clean re-pin — doc carries no `:NNNN`
  line cites (symbol-only), all documented symbols still present
  (`EXEC_FLAG_*`, `ExecGetRangeTableRelation`, `ExecCheckPermissions`,
  etc.); LOC 820→818. Triggering commit `a40fdf658862` ("Reject child
  partition FDWs in FOR PORTION OF", Peter Eisentraut) did not touch the
  documented declarations.)
- **Depth:** read (fresh pass; supersedes earlier touch)

## Purpose

The canonical public header of the executor. Declares: `eflags` bits,
`ExecutorStart/Run/Finish/End` (+ hooks), `ExecProcNode`, the helper
macros `castNode`/`innerPlanState`/`outerPlanState`, every `ExecAssign*`
plumbing function, slot ops macros for the hot `slot_getsomeattrs` /
`slot_getallattrs` path, and shared inline helpers like `ExecEvalExpr`,
`ExecQual`, `ExecProject`.

## eflags

- `EXEC_FLAG_EXPLAIN_ONLY` — don't really execute; init is enough.
- `EXEC_FLAG_REWIND` — caller will rewind to position 0; cache as needed.
- `EXEC_FLAG_BACKWARD` — caller may scan backward.
- `EXEC_FLAG_MARK` — caller may mark/restore.
- `EXEC_FLAG_SKIP_TRIGGERS` — apply-worker shortcut bypass.
- `EXEC_FLAG_WITH_NO_DATA` — for `CREATE TABLE … AS … WITH NO DATA`.

`eflags` propagates down with some bits stripped where intermediate
materializers (Sort/Material) absorb the requirement.

## Hot-path inline helpers

- `ExecEvalExpr(state, econtext, isnull)` — single-call dispatch to
  `state->evalfunc(state, econtext, isnull)`. The ExecJust* fast paths
  installed by ExecReadyInterpretedExpr land here without dispatch.
- `ExecQual(state, econtext)` — wrapper that pre-asserts EEOP_QUAL output
  semantics (NULL → false).
- `ExecProject(projInfo)` — runs the projection ExprState into
  `projInfo->pi_state.resultslot`.

## Public slot ops

- `slot_getsomeattrs(slot, attnum)` / `slot_getallattrs(slot)` — inline
  wrappers around `slot->tts_ops->getsomeattrs` with a fast path that
  returns immediately if `attnum ≤ tts_nvalid`.
- `ExecMaterializeSlot`, `ExecStoreVirtualTuple`, `ExecForceStoreHeapTuple`
  etc. — the slot-mutation API surface.

## Result-relation / range-table API

- `ExecGetRangeTableRelation(estate, rti, isResultRel)` and friends.
- `ExecCheckPermissions` / `ExecCheckPermissionsModified`.
- `ExecGetTriggerResultRel`, `ExecGetInsertedCols`, `ExecGetUpdatedCols`.

## Parallel/JIT plumbing

Declares `ExecParallelEstimate / InitializeDSM / InitializeWorker /
ReInitializeDSM / RetrieveInstrumentation` glue; per-node implementations
provided by the corresponding node*.c files.

## Tags

- [verified-by-code] symbols + ordering of declarations.
- [from-comment] eflags semantics at top of file.
