# lockoptions.h

- **Source:** `source/src/include/nodes/lockoptions.h` (~60 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Shared header for the row-locking enums used in both parse trees
and plan trees — kept here to avoid a `parsenodes.h` ↔ `plannodes.h`
include cycle.

## Types

### `LockClauseStrength` `:22-29`

```
LCS_NONE              -- no FOR clause (also used in PlanRowMark and
                         ON CONFLICT DO SELECT)
LCS_FORKEYSHARE       -- FOR KEY SHARE
LCS_FORSHARE          -- FOR SHARE
LCS_FORNOKEYUPDATE    -- FOR NO KEY UPDATE
LCS_FORUPDATE         -- FOR UPDATE
```

**Numeric ordering is significant:** higher value wins when an RTE
gets multiple FOR clauses. See `applyLockingClause`. `:19-20`
`[from-comment]`

### `LockWaitPolicy` `:39+`

```
LockWaitBlock         -- default; wait
LockWaitSkip          -- SKIP LOCKED
LockWaitError         -- NOWAIT
```

Same "higher value wins" rule.

## Cross-references

- Used by `LockingClause` (parsenodes.h), `PlanRowMark`/`ExecRowMark`
  (plannodes.h/execnodes.h), `RowMarkType` (plannodes.h).
- Locking implementation: `executor/nodeLockRows.c`,
  `access/heap/heapam.c heap_lock_tuple`.
