# nodeModifyTable.c

- **Source:** `source/src/backend/executor/nodeModifyTable.c` (≈5500 lines, 186 KB)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (entry points + per-op pro/act/epi triplet)

## Purpose

The driver for **all DML**: INSERT, UPDATE, DELETE, MERGE. Receives input
rows from its outer plan (data to insert / new column values + row-locator
junk for UPDATE / row-locator junk for DELETE / source-join rows for MERGE)
and applies the operation against the appropriate result relation
(possibly a partition, possibly a foreign table, possibly via INSTEAD OF
triggers on a view). [from-comment] `:15-60`

## The driver: `ExecModifyTable(pstate)` `:4619`

A loop that:
1. Pulls one row from `outerPlanState(mtstate)`.
2. Reads the row-identity junk columns (CTID, tableoid for partitioned
   targets, the `wholerow` for views with INSTEAD triggers, MERGE's source
   markers).
3. For partitioned targets: `ExecFindPartition` (execPartition.c) routes to
   the leaf ResultRelInfo.
4. Dispatches: `ExecInsert` / `ExecUpdate` / `ExecDelete` / `ExecMerge`.
5. Optionally projects RETURNING and emits to parent.

Each per-op routine follows the **Prologue / Act / Epilogue** pattern
(introduced for MERGE in PG 15): factor out trigger firing + permission
checks (Prologue) from the actual heap-API call (Act) from the index-update
+ after-trigger queuing (Epilogue), so MERGE can share them per-action.

## Per-operation flow

### INSERT (`ExecInsert` `:872`)

- BEFORE ROW triggers; if they returned NULL skip.
- BEFORE STATEMENT (fired once per stmt; `fireBSTriggers` `:4448` at top).
- `ExecCheckIndexConstraints` (for ON CONFLICT path) to find an existing
  conflict TID before the heap insert.
- `table_tuple_insert` (with `HEAP_INSERT_SPECULATIVE` if ON CONFLICT).
- `ExecInsertIndexTuples` — returns conflict list; if conflict and ON
  CONFLICT, `heap_abort_speculative` + go to `ExecOnConflictUpdate` `:3134`.
- AFTER ROW triggers, queue RETURNING projection.

### UPDATE (`ExecUpdatePrologue` `:2383` / `Act` `:2461` / `Epilogue` `:2614`)

- Prologue: BEFORE ROW UPDATE triggers, generate-by-storage default fill,
  RLS check.
- Act: `table_tuple_update`, returns
  `TM_Ok | TM_Updated | TM_Deleted | TM_SelfModified`. On TM_Updated/Deleted
  with READ COMMITTED, run EvalPlanQual; on TM_SelfModified, raise the
  classic "tuple to be updated was already modified by an operation
  triggered by the current command".
- Epilogue: `ExecUpdateIndexTuples` for indexes that touched changed columns
  only (the "summarizing" check), AFTER triggers.

### CROSS-partition UPDATE: `ExecCrossPartitionUpdate` `:2218`

When the new partition key sends the row to a different partition: turn
the UPDATE into a DELETE on the old + INSERT on the new (via
`ExecFindPartition`). Important detail: **UPDATE row triggers fire on the
old partition only**, not the new one; INSERT row triggers do NOT fire on
the new partition for this case (this is debated; current PG behavior is
that BEFORE/AFTER UPDATE row triggers on the new-partition target are
skipped, and INSERT triggers also fire). See the long comment block at
`:2218+`. Foreign-key checks are handled specially in
`ExecCrossPartitionUpdateForeignKey` `:2669`.

### DELETE (`ExecDeletePrologue` `:1739` / `Act` `:1771` / `Epilogue` `:1798`)

Same shape as UPDATE; concurrency handling identical.

### MERGE (`ExecMerge` `:3394`)

For each row from the source-vs-target join:
- If target side is NULL (LEFT join unmatched) → `ExecMergeNotMatched`
  `:4065`: evaluate each WHEN NOT MATCHED clause's qual; first matching
  drives action.
- Else → `ExecMergeMatched` `:3520`: evaluate WHEN MATCHED clauses; first
  match drives action. On TM_Updated/Deleted concurrent change → EvalPlanQual
  reloads the row and re-starts the WHEN MATCHED clause loop (per SQL spec /
  the executor README's MERGE section).

DO NOTHING is a valid action that simply skips.

### ON CONFLICT … DO UPDATE: `ExecOnConflictUpdate` `:3134`

Re-fetches the conflicting tuple from heap by the CTID returned by index
check, locks it (`table_tuple_lock(LockTupleExclusive)`), runs WHERE
predicate, then ExecUpdate against it.

## Init: `ExecInitModifyTable` `:5101`

Builds `ResultRelInfo` per relation (top-level plus partitions if any),
compiles projection ExprStates for INSERT TLIST / UPDATE new-value
expressions / MERGE per-action expressions, sets up indexes, triggers, RLS
checks, FK enforcement, FDW Modify state for foreign tables, the optional
JunkFilter for RETURNING, and `transition_capture` info for STATEMENT-level
transition tables.

## Statement-level triggers

- `fireBSTriggers` `:4448` — before-stmt; runs once per per-statement
  flush across all partitions (uses the root rel for BEFORE STMT).
- `fireASTriggers` `:4485` — after-stmt; queued during the run, fired at
  ExecModifyTable's exit / `ExecPostprocessPlan`.

## Tags

- [verified-by-code] all entry points + the Prologue/Act/Epilogue pattern.
- [from-comment] top-of-file narrative + MERGE specifics.
- [from-README] EvalPlanQual interaction for UPDATE/DELETE/MERGE.
