---
source_url: https://www.postgresql.org/docs/current/fdwhandler.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 59: Writing a Foreign Data Wrapper

The contract for a `CREATE FOREIGN DATA WRAPPER` handler. Like the table-AM
chapter, the authoritative spec is the struct comments in `fdwapi.h`, not this
chapter — but the chapter is where the *mandatory vs optional* split and the
sequencing of callbacks is laid out. The corpus already has the canonical
worked implementation (postgres_fdw) read file-by-file, so this doc is mostly a
router into those notes.

## The handler returns an `FdwRoutine`

- The `fdw_handler`-typed function `palloc`s and returns an `FdwRoutine` of
  function pointers. [from-docs]
  [verified-by-code, source/src/include/foreign/fdwapi.h — `typedef struct
  FdwRoutine` with `NodeTag type` first]
- **`.type = T_FdwRoutine`** node tag is set by the handler and checked by core
  (`GetFdwRoutine`). [verified-by-code, source/src/backend/foreign/foreign.c —
  `GetFdwRoutine`; via knowledge/files/.../postgres_fdw notes]

## Mandatory — scan path (7 callbacks)

Every functional FDW must implement, in planning-then-execution order:

1. `GetForeignRelSize` — set `baserel->rows`; size estimate. [from-docs]
2. `GetForeignPaths` — create one or more `ForeignPath` via `add_path`. [from-docs]
3. `GetForeignPlan` — turn the chosen path into a `ForeignScan` plan node. [from-docs]
4. `BeginForeignScan` — executor-time setup (open the remote connection/cursor). [from-docs]
5. `IterateForeignScan` — return one tuple per call into the scan slot; NULL slot at EOF. [from-docs]
6. `ReScanForeignScan` — restart the scan (for nested-loop re-execution). [from-docs]
7. `EndForeignScan` — release executor-time resources. [from-docs]

These mirror the executor's `ExecInitNode`/`ExecProcNode`/`ExecEndNode`/`ExecReScan`
lifecycle — the FDW callbacks are dispatched from `nodeForeignscan.c`. [inferred]
[via knowledge/subsystems/executor.md]

## Optional — write support

- **Row-at-a-time modify:** `AddForeignUpdateTargets`, `PlanForeignModify`,
  `BeginForeignModify`, `ExecForeignInsert`, `ExecForeignUpdate`,
  `ExecForeignDelete`, `EndForeignModify`. Implement all of a coherent subset; a
  read-only FDW omits the whole group. [from-docs]
- **Batch insert:** `ExecForeignBatchInsert` + `GetForeignModifyBatchSize` — lets
  the executor hand the FDW many rows per round-trip (the postgres_fdw
  `batch_size` option). `GetForeignModifyBatchSize` returns the chosen batch
  count. [from-docs] [via postgres_fdw notes in knowledge/files/]
- **Direct modify** (push an entire UPDATE/DELETE to the remote, skipping
  row-by-row): `PlanDirectModify`, `BeginDirectModify`, `IterateDirectModify`,
  `EndDirectModify`. `PlanDirectModify` decides at plan time whether the whole
  statement is shippable; if not, core falls back to the row-at-a-time path.
  [from-docs]

## Optional — locking, schema, stats, async

- **Row locking** (`SELECT ... FOR UPDATE`, EvalPlanQual): `GetForeignRowMarkType`
  + `RefetchForeignRow`. Without these the FDW uses early row locking / can't do
  late locking. [from-docs]
- **`IMPORT FOREIGN SCHEMA`:** `ImportForeignSchema` returns a list of
  `CREATE FOREIGN TABLE` command strings. [from-docs]
- **`ANALYZE`:** `AnalyzeForeignTable` supplies a sampling callback so the local
  planner can hold stats for the foreign table. [from-docs]
- **Async append** (parallel-ish concurrent FDW scans under `Append`):
  `IsForeignPathAsyncCapable`, `ForeignAsyncRequest`, `ForeignAsyncConfigureWait`,
  `ForeignAsyncNotify`. [from-docs]
- **EXPLAIN:** `ExplainForeignScan`, `ExplainForeignModify`,
  `ExplainDirectModify`. [from-docs]
- **Parallel scan:** `EstimateDSMForeignScan`, `InitializeDSMForeignScan`,
  `ReInitializeDSMForeignScan`, `InitializeWorkerForeignScan`,
  `ShutdownForeignScan`. [from-docs]

## Helper functions core gives the FDW

- `GetForeignServerByName`, `GetForeignServer`, `GetForeignDataWrapper` — catalog
  lookups for server/wrapper rows. [from-docs]
- `GetUserMapping` — fetch the credential row for the current user (the
  password/credential surface — see the cross-cluster trust findings in the
  postgres_fdw issue register). [from-docs]
- `GetForeignColumnOptions`, `GetForeignTable` — per-column / per-table option
  access. [from-docs]

## Links into corpus

- [[knowledge/issues/postgres_fdw.md]] — the security-critical findings on the
  reference FDW: two-layered `password_required` defense (gold standard),
  `sslmode=prefer` MITM-downgrade default, name-not-OID shippable-function
  resolution, `parallel_commit` is NOT 2PC.
- [[knowledge/subsystems/foreign.md]] — the FDW/foreign-server subsystem.
- [[knowledge/subsystems/executor.md]] — `nodeForeignscan.c` dispatch the scan
  callbacks hang off.
- [[knowledge/docs-distilled/tableam.md]] — sibling "implement a struct of
  callbacks" chapter (storage side rather than remote side).
- access-method-apis skill — companion contract style (IndexAmRoutine/TableAmRoutine).

## Gaps / follow-ups

- No per-file doc yet for `src/backend/executor/nodeForeignscan.c` or
  `src/backend/foreign/foreign.c`; the callback-dispatch and `GetFdwRoutine`
  validation cites above are `[inferred]`/pointer-only and would harden with a
  direct read.
