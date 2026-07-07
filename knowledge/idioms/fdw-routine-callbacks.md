# FDW routine callbacks — the FdwRoutine struct

A **Foreign Data Wrapper** (FDW) is a C-level extension that
lets PostgreSQL execute SQL queries against external data
sources: another PG cluster (`postgres_fdw`), a flat file
(`file_fdw`), a different DBMS, an HTTP API, etc. The whole
contract is the `FdwRoutine` struct in
`src/include/foreign/fdwapi.h` — ~40 callback pointers covering
scan planning, scan execution, modification, remote join,
EXPLAIN, ANALYZE, parallel-query integration, and async
execution. A new FDW implements the mandatory subset (6 scan
callbacks) and as many optional ones as needed.

Anchors:
- `source/src/include/foreign/fdwapi.h:208-290` — FdwRoutine
  struct [verified-by-code]
- `source/src/include/foreign/fdwapi.h:213-219` — mandatory
  scan callbacks [verified-by-code]
- `source/src/include/foreign/fdwapi.h:234-247` — modify
  callbacks (optional) [verified-by-code]
- `knowledge/idioms/fdw-iterate-scan.md` — companion
- `knowledge/idioms/fdw-direct-modify.md` — companion
- `.claude/skills/extension-development/SKILL.md` — companion

## The FdwHandler entry

An FDW is registered by:

```sql
CREATE FOREIGN DATA WRAPPER my_fdw HANDLER my_fdw_handler;
```

`my_fdw_handler` is a C function returning `FdwRoutine *`. It
allocates an FdwRoutine struct, fills in the callback
pointers, returns it. PG calls it lazily via `GetFdwRoutine`
when first touching the FDW.

## The 6 mandatory scan callbacks

[verified-by-code `fdwapi.h:213-219`]

```c
GetForeignRelSize_function   GetForeignRelSize;
GetForeignPaths_function     GetForeignPaths;
GetForeignPlan_function      GetForeignPlan;
BeginForeignScan_function    BeginForeignScan;
IterateForeignScan_function  IterateForeignScan;
ReScanForeignScan_function   ReScanForeignScan;
EndForeignScan_function      EndForeignScan;
```

The lifecycle:
1. **`GetForeignRelSize(root, baserel, foreigntableid)`** —
   planner asks: "how big is this relation?". FDW estimates
   row count + width.
2. **`GetForeignPaths(root, baserel, foreigntableid)`** —
   planner asks: "what Paths are available?". FDW returns
   ForeignPath nodes with costs.
3. **`GetForeignPlan(root, baserel, foreigntableid, best_path,
   tlist, scan_clauses, outer_plan)`** — planner picks one
   Path; FDW turns it into a ForeignScan Plan node.
4. **`BeginForeignScan(node, eflags)`** — executor inits; FDW
   opens connections, prepares cursors.
5. **`IterateForeignScan(node)`** — return next tuple.
6. **`ReScanForeignScan(node)`** — restart from beginning
   (for nested-loop, set ops).
7. **`EndForeignScan(node)`** — cleanup; close connections.

These 6 alone enable read-only foreign tables.

## Optional callbacks — modify

[verified-by-code `fdwapi.h:233-247`]

```c
AddForeignUpdateTargets_function     /* add resjunk cols to query */
PlanForeignModify_function            /* prepare DML plan */
BeginForeignModify_function           /* open DML state */
ExecForeignInsert_function            /* INSERT one row */
ExecForeignBatchInsert_function       /* batched INSERT */
GetForeignModifyBatchSize_function    /* batch size advice */
ExecForeignUpdate_function            /* UPDATE one row */
ExecForeignDelete_function            /* DELETE one row */
EndForeignModify_function             /* close DML state */
BeginForeignInsert_function           /* per-relation INSERT init */
EndForeignInsert_function
IsForeignRelUpdatable_function        /* report updatability */
```

Without these, the foreign table is read-only. For postgres_fdw
all are implemented; for file_fdw, none (file is read-only).

## Direct modify — bypassing per-row callbacks

```c
PlanDirectModify_function            /* "can we push down whole DML?" */
BeginDirectModify_function
IterateDirectModify_function
EndDirectModify_function
```

For an UPDATE / DELETE that can be entirely shipped to the
foreign server (no local processing needed), the FDW can
implement direct-modify. Example: `UPDATE remote_table SET
col = 5 WHERE id = 7` — postgres_fdw sends one SQL statement
to the remote, no per-row callbacks.

See `fdw-direct-modify` companion.

## EXPLAIN / ANALYZE / IMPORT

```c
ExplainForeignScan_function     /* extend EXPLAIN output */
ExplainForeignModify_function
ExplainDirectModify_function
AnalyzeForeignTable_function    /* gather statistics */
ImportForeignSchema_function    /* IMPORT FOREIGN SCHEMA */
```

EXPLAIN callbacks add FDW-specific lines (e.g., "Remote SQL:
SELECT ... FROM ..."). ANALYZE callbacks sample rows for
statistics. ImportForeignSchema implements the
`IMPORT FOREIGN SCHEMA` SQL command.

## Parallel + async

```c
IsForeignScanParallelSafe_function
EstimateDSMForeignScan_function
InitializeDSMForeignScan_function
InitializeWorkerForeignScan_function
/* ... */
IsForeignPathAsyncCapable_function
ForeignAsyncRequest_function
ForeignAsyncConfigureWait_function
ForeignAsyncNotify_function
```

For parallel-safe FDWs (postgres_fdw is), the parallel callbacks
let the FDW share state across workers via DSM. For
async-capable FDWs, the async callbacks let multiple foreign
scans interleave (e.g., parallel queries across multiple remote
servers).

## Remote join + upper-rel pushdown

```c
GetForeignJoinPaths_function       /* "can we join these foreign rels remotely?" */
GetForeignUpperPaths_function      /* "can we push aggregate/sort/limit?" */
```

Advanced FDWs (postgres_fdw) implement these to push down
joins, aggregates, GROUP BY, ORDER BY, LIMIT to the remote
side — minimizing data shipped over the wire.

## SELECT FOR UPDATE — row locking

```c
GetForeignRowMarkType_function     /* what locking does the remote support? */
RefetchForeignRow_function          /* re-fetch with new snapshot */
RecheckForeignScan_function         /* re-check qual after EPQ */
```

Lets `SELECT ... FOR UPDATE` work over foreign rows. The FDW
declares the lock strength it can supply (full lock, value-only,
none).

## Path reparameterization

```c
ReparameterizeForeignPathByChild_function
```

For partitionwise foreign-table joins: a path parameterized on
the parent relid may need rewriting if it's chosen as a child's
join path.

## Common FDW implementations

| FDW | Source location |
|---|---|
| `postgres_fdw` | contrib/postgres_fdw/ |
| `file_fdw` | contrib/file_fdw/ |
| `dblink` | contrib/dblink/ (older, not strictly FDW) |
| Third-party: `tds_fdw`, `oracle_fdw`, `multicorn`, etc. |

## Common review-time concerns

- **Mandatory 6 scan callbacks** must all be implemented for
  any FDW.
- **Modify callbacks are optional** — read-only FDWs skip
  them.
- **Direct modify is a perf optimization** — skip per-row
  trips for whole-DML-pushable operations.
- **Parallel + async are advanced** — most FDWs leave them
  NULL.
- **Adding a new callback** requires the FdwRoutine struct
  field + caller-side change in PG core; rare but possible.
- **GetFdwRoutine is the entry** — called lazily; cache the
  result.

## Invariants

- **[INV-1]** Handler returns a fresh FdwRoutine struct on
  first call; callbacks set in the struct.
- **[INV-2]** 6 scan callbacks mandatory; rest optional.
- **[INV-3]** Modify callbacks define read-write FDW.
- **[INV-4]** Direct modify bypasses per-row callbacks.
- **[INV-5]** Parallel + async require explicit opt-in via
  IsForeignScanParallelSafe / IsForeignPathAsyncCapable.

## Useful greps

- The struct:
  `grep -n 'FdwRoutine\|GetForeignRelSize\|GetForeignPaths' source/src/include/foreign/fdwapi.h | head -20`
- postgres_fdw handler:
  `grep -n '^postgres_fdw_handler\|fdwroutine->' source/contrib/postgres_fdw/postgres_fdw.c | head -15`
- Callers in core:
  `grep -RIn 'GetFdwRoutine\|fdwroutine->IterateForeignScan' source/src/backend | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`contrib/postgres_fdw/postgres_fdw.c`](../files/contrib/postgres_fdw/postgres_fdw.c.md) | — | reference FDW |
| [`src/include/foreign/fdwapi.h`](../files/src/include/foreign/fdwapi.h.md) | 208 | FdwRoutine struct |
| [`src/include/foreign/fdwapi.h`](../files/src/include/foreign/fdwapi.h.md) | 213 | mandatory scan callbacks |
| [`src/include/foreign/fdwapi.h`](../files/src/include/foreign/fdwapi.h.md) | 234 | modify callbacks (optional) |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/fdw-iterate-scan.md` — IterateForeignScan
  + ReScanForeignScan details.
- `knowledge/idioms/fdw-direct-modify.md` — PlanDirectModify
  flow.
- `knowledge/data-structures/plannerinfo.md` — PlannerInfo
  passed to planner callbacks.
- `knowledge/idioms/parallel-worker-coordination.md` —
  parallel FDW callbacks.
- `knowledge/subsystems/foreign.md` — foreign-tables
  subsystem.
- `.claude/skills/extension-development/SKILL.md` — FDW
  packaging.
- `source/src/include/foreign/fdwapi.h:208` — full struct.
- `source/contrib/postgres_fdw/postgres_fdw.c` — reference
  FDW.
