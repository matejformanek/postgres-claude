# `src/include/foreign/fdwapi.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~299
- **Source:** `source/src/include/foreign/fdwapi.h`

The **entire** foreign-data wrapper (FDW) callback interface. Defines
~40 typedef'd function pointers plus the `FdwRoutine` struct that
groups them. An FDW handler function (declared in pg_proc with
`prorettype = fdw_handler`) returns a populated `FdwRoutine *`; the
planner and executor call into it for every step of scanning,
joining, modifying, EXPLAIN-ing, ANALYZE-ing, and parallelizing a
foreign table. Companion file: `foreign.h` for the data-wrapper /
server / user-mapping records. [verified-by-code] [from-comment]

For Phase D this is the **primary trust boundary surface** for any
patch that touches FDW behavior: every callback below crosses from
core PG into FDW-author code, and the planner/executor must defend
against arbitrary FDW behavior on every call (e.g. PG_TRY around
network I/O, careful memory ownership of returned slots, parallel
safety contracts).

## API / declarations

### Construction

- `FdwRoutine { NodeTag type; … }` — must be created with
  `makeNode(FdwRoutine)` so future-added pointers default to NULL.
  "More function pointers are likely to be added in the future."
  [from-comment]

### Scanning (required: first 7)

- `GetForeignRelSize_function(root, baserel, foreigntableid)` —
  populate `baserel->rows`, `baserel->reltarget->width`.
- `GetForeignPaths_function` — add `ForeignPath`s via `add_path`.
- `GetForeignPlan_function(root, baserel, foreigntableid, best_path,
  tlist, scan_clauses, outer_plan)` → `ForeignScan *`.
- `BeginForeignScan_function(node, eflags)`.
- `IterateForeignScan_function(node)` → `TupleTableSlot *`.
- `ReScanForeignScan_function(node)`.
- `EndForeignScan_function(node)`.

### Join + upper-rel planning (optional)

- `GetForeignJoinPaths_function(root, joinrel, outerrel, innerrel,
  jointype, *extra)` — push joins to remote.
- `GetForeignUpperPaths_function(root, stage, input_rel, output_rel,
  *extra)` — push aggregation/grouping/sort/LIMIT/DISTINCT to remote.

### Modify (UPDATE/DELETE/INSERT)

- Planner: `AddForeignUpdateTargets`, `PlanForeignModify`,
  `PlanDirectModify`.
- Per-statement executor: `BeginForeignModify`, `ExecForeignInsert`,
  `ExecForeignBatchInsert`, `GetForeignModifyBatchSize`,
  `ExecForeignUpdate`, `ExecForeignDelete`, `EndForeignModify`.
- COPY FROM into a foreign table: `BeginForeignInsert`,
  `EndForeignInsert` (called even when no row inserted).
- Direct-modify path (planner pushed UPDATE/DELETE down to remote):
  `BeginDirectModify`, `IterateDirectModify`, `EndDirectModify`.
- `IsForeignRelUpdatable_function(rel)` — bitmask of
  `CMD_INSERT/UPDATE/DELETE` capability.

### SELECT FOR UPDATE / SHARE

- `GetForeignRowMarkType_function(rte, strength)` → `RowMarkType`.
- `RefetchForeignRow_function(estate, erm, rowid, slot, *updated)`.
- `RecheckForeignScan_function(node, slot)` — reused by EvalPlanQual.

### EXPLAIN

- `ExplainForeignScan`, `ExplainForeignModify`,
  `ExplainDirectModify`. (`ExplainState *` is forward-declared at
  the top to avoid pulling in `explain_state.h`.)

### ANALYZE

- `AcquireSampleRowsFunc(relation, elevel, *rows, targrows,
  *totalrows, *totaldeadrows)` — sampler the FDW returns.
- `AnalyzeForeignTable_function(relation, *func, *totalpages)`.
- `ImportForeignStatistics_function(relation, va_cols, elevel)`.

### IMPORT FOREIGN SCHEMA

- `ImportForeignSchema_function(stmt, serverOid)` returns a List of
  CREATE FOREIGN TABLE statements (as strings).

### TRUNCATE

- `ExecForeignTruncate_function(rels, behavior, restart_seqs)`.

### Parallelism (Gather)

- `IsForeignScanParallelSafe_function(root, rel, rte)`.
- DSM cooperative dance:
  `EstimateDSMForeignScan(node, pcxt)` — size,
  `InitializeDSMForeignScan(node, pcxt, coordinate)` — leader,
  `ReInitializeDSMForeignScan(node, pcxt, coordinate)` — on rescan,
  `InitializeWorkerForeignScan(node, toc, coordinate)` — workers,
  `ShutdownForeignScan(node)`.

### Path reparameterization (partitionwise joins)

- `ReparameterizeForeignPathByChild_function(root, fdw_private,
  child_rel)`.

### Async (since PG 14)

- `IsForeignPathAsyncCapable_function(path)`,
- `ForeignAsyncRequest_function(areq)`,
- `ForeignAsyncConfigureWait_function(areq)`,
- `ForeignAsyncNotify_function(areq)`.

### Top-level lookup helpers (in `foreign/foreign.c`)

- `GetFdwRoutine(fdwhandler Oid)`,
- `GetForeignServerIdByRelId(relid)`,
- `GetFdwRoutineByServerId(serverid)`,
- `GetFdwRoutineByRelId(relid)`,
- `GetFdwRoutineForRelation(relation, makecopy)`,
- `IsImportableForeignTable(tablename, stmt)`,
- `GetExistingLocalJoinPath(joinrel)` — companion local Path used by
  EvalPlanQual recheck for pushed-down joins.

## Notable invariants / details

- "Set the pointer to NULL for any [optional callback] that [is] not
  provided." `makeNode(FdwRoutine)` zeroes everything; only the 7
  scan callbacks are required. [from-comment]
- `ExplainState *` is forward-declared rather than including
  `explain_state.h` ("avoid including explain_state.h here") —
  keeps the include footprint of `fdwapi.h` small even though every
  FDW pulls it. [from-comment]
- `ExecForeignBatchInsert` + `GetForeignModifyBatchSize` are paired
  — core executor calls the size hook first, then batches up to that
  many slots before each batch-insert call. [inferred]
- Async API is invoked under a Gather/Append node — only relevant
  for FDWs that can multiplex requests; `IsForeignPathAsyncCapable`
  gates it. [inferred]
- `RefetchForeignRow` mutates `*updated` to tell EvalPlanQual that
  the remote row was concurrently modified.

## Potential issues — Phase D angles

- **Memory ownership** of slots returned by `IterateForeignScan` /
  `Exec(Insert|Update|Delete)` is not stated in the header. Convention
  (from postgres_fdw) is that the FDW owns the slot; core copies what
  it needs. A reviewer checking a new FDW must verify this.
  [ISSUE-undocumented-invariant: slot ownership contract not in
  fdwapi.h (likely)]
- **Parallel-safety contract**: `IsForeignScanParallelSafe` is the
  only hook; an FDW that returns true but uses backend-local FDs or
  non-DSM-safe state will corrupt parallel scans. No invariant
  documented here cross-checks it.
  [ISSUE-undocumented-invariant: parallel-safe contract is FDW's
  honor system (likely)]
- **Async callbacks** are not paired with a documented order; a
  reviewer must read postgres_fdw's implementation to learn the
  expected `Request → ConfigureWait → Notify` sequence.
  [ISSUE-doc-drift: async callback ordering not in header (maybe)]
- **`ExecForeignTruncate`**: a single hook is invoked once with the
  full `rels` list; nothing in the header says whether the FDW is
  allowed to truncate a subset and return, or must be all-or-nothing.
  [ISSUE-question: truncate atomicity contract (nit)]
- **`AcquireSampleRowsFunc`** runs sampling in the backend's memory
  context; an FDW that pallocs into CurrentMemoryContext during
  sampling leaks past ANALYZE end. [ISSUE-question: sampler memory
  scoping (maybe)]
- **`GetFdwRoutineForRelation(makecopy=true)`** — the `makecopy`
  flag is a memory-context hack to let callers get a stable struct
  pointer; not explained in this header. [ISSUE-doc-drift: makecopy
  rationale not in header (nit)]
- **Plain function-pointer struct, no version field**: every patch
  that adds a callback bumps the struct layout silently. There is
  no `fdw_version` field on `FdwRoutine`; loadable FDWs built
  against an older header but loaded against newer PG can read
  past the end of the struct. The "makeNode + zeroed defaults"
  approach helps NEW callbacks (NULL = "not provided") but does
  not protect against REORDERING. [ISSUE-undocumented-invariant:
  FdwRoutine ABI stability is by convention only (likely)]
