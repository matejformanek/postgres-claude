# pg_duckdb — swapping PostgreSQL's execution engine for DuckDB via a planner-hook query rewrite

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `duckdb/pg_duckdb` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-07 (see Sources footer).

## Domain & purpose

pg_duckdb embeds **DuckDB's columnar-vectorized analytics engine inside a
PostgreSQL backend** and transparently re-routes analytical queries to it
(`README.md:20-35`) `[from-README]`. With `SET duckdb.force_execution = true`,
an ordinary `SELECT ... GROUP BY ...` over regular Postgres tables is silently
planned and executed by DuckDB instead of Postgres' own executor; it also
exposes data-lake table functions (`read_parquet`, `read_csv`, `iceberg_scan`,
`delta_scan`), a `USING duckdb` table-storage option, and MotherDuck cloud
integration. It is the maximal example of the question cstore_fdw only gestured
at: *can an extension replace Postgres' entire planner+executor for a query
class while keeping the SQL surface unchanged?* The answer pg_duckdb gives is
"yes — intercept at `planner_hook`, round-trip the query back to SQL text, and
hand it to DuckDB, returning the whole thing as one `CustomScan` node." Built in
C++ (it links libduckdb), supports PG 14–18 (`README.md:242`).

## How it hooks into PG

pg_duckdb **must** be in `shared_preload_libraries` — `_PG_init` hard-errors
otherwise (`src/pgduckdb.cpp:30-33`) `[verified-by-code]` — because it installs
planner/executor hooks and a background worker that have to exist before the
first backend statement (see `extension-development` skill §"lazy vs preload").
`_PG_init` is tiny and delegates to six initializers
(`src/pgduckdb.cpp:28-41`): `InitGUC` + `InitGUCHooks`, `DuckdbInitHooks`,
`DuckdbInitNode` (registers the custom scan), `InitBackgroundWorkersShmem`, and
`RegisterDuckdbXactCallback` (transaction callback bridging PG xacts to
DuckDB). It uses the modern `PG_MODULE_MAGIC_EXT(.name=..., .version=...)` form
(`src/pgduckdb.cpp:23`).

`DuckdbInitHooks` chains **five** hooks, each saving the prior value or the
`standard_*` default (`src/pgduckdb_hooks.cpp:495-513`) `[verified-by-code]`:

| Hook | Role |
|---|---|
| `planner_hook` (`DuckdbPlannerHook`) | The payload: decide per-query whether DuckDB should run it, and if so replace the entire plan with a DuckDB `CustomScan` (`:264-296`). |
| `ExecutorStart_hook` / `ExecutorFinish_hook` | Track executor nesting depth + claim a command id for DuckDB writes / detect non-top-level execution (`:341-409`). |
| `ExplainOneQuery_hook` | Capture EXPLAIN format/analyze flags into globals so the custom node can render DuckDB's own plan (`:411-429`). |
| `emit_log_hook` | Rewrite specific error hints (e.g. `read_parquet` column-syntax) and re-trigger MotherDuck catalog sync on stale-catalog errcodes (`:450-493`). |

Plus a `ProcessUtility` hook (`DuckdbInitUtilityHook`, `:512`), a custom-scan
node (below), a stub **table access method** `USING duckdb`
(`src/pgduckdb_table_am.cpp`), and a **background worker** for MotherDuck
catalog sync (`src/pgduckdb_background_worker.cpp`). Cross-ref
`[[knowledge/subsystems/optimizer]]`, `[[knowledge/subsystems/executor]]`,
`[[knowledge/subsystems/tcop]]`, `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/architecture/access-methods]]`.

## Where it diverges from core idioms

### 1. The planner hook discards the Postgres plan and replaces it with a single `CustomScan` that *is* a DuckDB query

This is the load-bearing divergence. `DuckdbPlannerHook_Cpp` decides — via
`NeedsDuckdbExecution` (query references a DuckDB-only function/table) or
`ShouldTryToUseDuckdbExecution` (`duckdb.force_execution` + has FROM clause + is
an allowed statement) — whether to call `DuckdbPlanNode` instead of the normal
planner (`src/pgduckdb_hooks.cpp:264-296`) `[verified-by-code]`. `DuckdbPlanNode`
→ `CreatePlan` does something no core planner path does: it **serializes the
`Query` back to SQL text** with `pgduckdb_get_querydef` and feeds that string to
DuckDB's own prepared-statement engine to discover result types
(`src/pgduckdb_planner.cpp:41-54`, `:56-122`). It then builds a lone
`CustomScan` node whose `custom_private` stashes the original `Query`
(`:118`), whose target list is synthesized from DuckDB's result types mapped
back to Postgres type OIDs (`:74-116`), and wraps it in a `PlannedStmt` with a
**single fabricated RTE** of kind `RTE_NAMEDTUPLESTORE` — chosen precisely
because `RTE_RELATION` would trip asserts on fields pg_duckdb never fills
(`:124-142`, `:188-242`). So the entire Postgres plan tree — joins, aggregates,
scans — collapses into one opaque node; Postgres' executor is reduced to
pulling tuples out of DuckDB. Cross-ref `[[knowledge/architecture/planner]]`,
`[[knowledge/architecture/query-lifecycle]]`, `[[knowledge/idioms/node-types-and-lists]]`.

### 2. The CustomScan node drives a foreign vectorized engine through a tuple-at-a-time slot interface

`DuckdbInitNode` registers `duckdb_scan_scan_methods` /
`duckdb_scan_exec_methods` (`src/pgduckdb_node.cpp:31-34`, `:65-72`). The
exec-state struct `DuckdbScanState` keeps a live `duckdb::Connection`,
`duckdb::PreparedStatement`, and a `duckdb::DataChunk` cursor alongside the core
`CustomScanState css` (which must be the first field, `:36-49`)
`[verified-by-code]`. `Duckdb_ExecCustomScan` pulls DuckDB `DataChunk`s and
converts each cell into a Postgres `TupleTableSlot`, i.e. it adapts DuckDB's
columnar/vectorized output back into Postgres' row-at-a-time `ExecProcNode`
contract — bridging two fundamentally different execution models at the
node boundary. `IsDuckdbPlan` even peers through a `Material` wrapper (added for
scrollable cursors, since the custom node can't scan backward) to recognize its
own node by method-table identity (`src/pgduckdb_hooks.cpp:303-328`). Cross-ref
`[[knowledge/subsystems/executor]]` (CustomScan is core's sanctioned
extensibility seam — pg_duckdb uses it for a whole engine, not one operator).

### 3. `USING duckdb` is a deliberately-unimplemented table AM — a catalog shim whose storage lives in DuckDB

pg_duckdb registers a table access method (`duckdb_am_handler`,
`src/pgduckdb_table_am.cpp:38`) but **most callbacks `ereport(ERROR,
ERRCODE_FEATURE_NOT_SUPPORTED, "duckdb does not implement %s")`** via a
`NOT_IMPLEMENTED()` macro (`:35-36`) `[verified-by-code]`: `scan_rescan`,
`scan_getnextslot`, `tuple_insert`, `tuple_insert_speculative` all throw
(`:89-101`, `:167-173`). `slot_callbacks` returns `TTSOpsMinimalTuple` only "to
make sure ANALYZE does not fail" (`:45-53`), and `scan_getnextslot` returns an
empty tuple during `ALTER TABLE` so DDL doesn't crash (`:95-100`). The AM exists
to give a `USING duckdb` table a `pg_class` row and `relfilenode` so the catalog
and DDL machinery are satisfied, while every real read/write is rerouted through
the planner hook to DuckDB. This is the **inverse of cstore_fdw**: where
cstore_fdw bent the *FDW* API into a storage engine, pg_duckdb registers a
*table AM* it intentionally doesn't implement, and does the real work via plan
substitution. Cross-ref `[[knowledge/ideologies/cstore_fdw]]`,
`access-method-apis` skill (the 37 mandatory table-AM callbacks pg_duckdb stubs).

### 4. Two parallel catalogs and two transaction managers, kept in uneasy sync

Because DuckDB has *its own* `pg_catalog`, pg_duckdb explicitly refuses to run
queries touching Postgres catalog tables in DuckDB —
`ContainsCatalogTable`/`IsCatalogTable` reject `pg_catalog`/`pg_toast`
namespaces with "DuckDB does not support querying PG catalog tables"
(`src/pgduckdb_hooks.cpp:46-66`, `:213-217`, `:254-257`) `[verified-by-code]`.
It also forbids mixing DuckDB and Postgres writes in one transaction block
(`IsAllowedStatement` → `DidDisallowedMixedWrites`, `:238-241`, `:280-282`) and
forbids DuckDB execution inside functions unless a GUC overrides it (`:244-247`)
— because the executor-nesting tracking and command-id claiming
(`ClaimCurrentCommandId`, `AutocommitSingleStatementQueries`,
`MarkStatementNotTopLevel` at `:341-409`) only reason correctly at the top
level. Reconciling two independent storage+transaction engines under one SQL
session forces a thicket of "is this safe to delegate?" guards that core never
needs because it owns the whole stack. Cross-ref `[[knowledge/architecture/mvcc]]`,
`[[knowledge/architecture/process-model]]`.

### 5. A background worker syncs the MotherDuck catalog into Postgres' catalog

`InitBackgroundWorkersShmem` (`src/pgduckdb.cpp:39`) + the 1300-line
`src/pgduckdb_background_worker.cpp` run a worker that periodically pulls remote
MotherDuck table metadata and materializes it as Postgres catalog entries, so
cloud tables "appear automatically" (`README.md:144-145`). The `emit_log_hook`
restarts this sync when a query fails with `ERRCODE_UNDEFINED_TABLE/COLUMN/SCHEMA`
and the user is allowed to use DuckDB (`src/pgduckdb_hooks.cpp:431-441`,
`:478-492`) — i.e. it treats Postgres parser "relation does not exist" errors as
a *cache-miss signal* to refresh an external catalog, an inversion of the normal
error contract. The worker disables `duckdb_force_execution` for its own queries
because they depend on Postgres execution (`regclass` name resolution)
(`:197-203`). Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/idioms/error-handling]]`.

### 6. Every C-facing entry point is wrapped to translate C++ exceptions into `ereport`

DuckDB is C++ and throws; Postgres is C and `longjmp`s via `ereport`. pg_duckdb
funnels each hook through `InvokeCPPFunc` (e.g.
`src/pgduckdb_hooks.cpp:298-301`, `:364-376`, `:398-409`) which catches DuckDB
C++ exceptions and re-raises them as Postgres errors, bridging the two
incompatible error/unwind models at every boundary. This per-call C++/C
trampoline has no core analogue — core is uniformly C with one `setjmp`/`longjmp`
discipline (see `error-handling` skill). Cross-ref
`[[knowledge/idioms/error-handling]]`.

## Notable design decisions (cited)

- **Constant-only SELECTs stay in Postgres even under `force_execution`.**
  `ContainsFromClause` blocks forwarding `SELECT current_setting('work_mem')`
  and friends to DuckDB, because DuckDB would warn or return wrong results for
  Postgres-introspection queries (`src/pgduckdb_hooks.cpp:121-140`,
  `:205`).
- **Materialized-view refresh ignores `force_execution`.**
  `ShouldTryToUseDuckdbExecution` returns false during `REFRESH MATERIALIZED
  VIEW` to avoid type-mismatch data corruption between the two engines'
  results (`src/pgduckdb_hooks.cpp:182-196`) — a candid admission that DuckDB
  and Postgres can type the same query differently.
- **View permission checks are re-implemented by hand.** Since the plan is
  replaced wholesale, normal RTE-permission checking is bypassed, so
  `check_view_perms_recursive` manually walks the query's rtable+CTEs and calls
  `ExecCheckOneRelPerms`/`aclcheck_error` itself (`src/pgduckdb_planner.cpp:144-186`,
  `:192`) — re-deriving a security check that core would have done for a normal
  plan. Cross-ref `[[knowledge/idioms/catalog-conventions]]`.
- **`relocatable = false`** (`pg_duckdb.control:4`) — unlike cstore_fdw's
  `relocatable = true`; pg_duckdb pins its schema because its UDFs and AM are
  tightly coupled.
- **Hardcoded `varno = 1` / `INDEX_VAR` in the synthesized scan tlist**
  (`src/pgduckdb_planner.cpp:93-113`) — a comment records the history of having
  used `varno 0` and filling it in later; the single-RTE invariant is what lets
  them hardcode it.

## Links into corpus

- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]` —
  the `planner_hook` + `PlannedStmt`/`CustomScan` machinery pg_duckdb hijacks to
  substitute a whole-query DuckDB plan; the single most important cross-reference.
- `[[knowledge/subsystems/executor]]` — `CustomScan`/`CustomScanState` is core's
  sanctioned extension seam; pg_duckdb uses it to host an entire foreign engine
  and adapt DuckDB `DataChunk`s into `TupleTableSlot`s.
- `[[knowledge/architecture/access-methods]]` + `access-method-apis` skill — the
  stub `USING duckdb` table AM (most callbacks `NOT_IMPLEMENTED()`), a catalog
  shim whose real storage lives in DuckDB.
- `[[knowledge/ideologies/cstore_fdw]]` — the mirror case: cstore_fdw bent the
  FDW API into a storage engine; pg_duckdb registers an unimplemented table AM
  and swaps the *execution* engine instead. Two opposite ways to smuggle a
  non-heap engine into PG.
- `[[knowledge/idioms/bgworker-and-parallel]]` — the MotherDuck catalog-sync
  background worker + its shmem init.
- `[[knowledge/idioms/error-handling]]` — `InvokeCPPFunc` C++↔`ereport` bridging
  and the `emit_log_hook` that turns "relation not found" into a catalog-refresh
  trigger.
- `[[knowledge/architecture/mvcc]]` — the two-transaction-manager reconciliation
  (mixed-write bans, command-id claiming, executor-nesting guards).
- `[[knowledge/subsystems/tcop]]` — the `ProcessUtility` + `ExplainOneQuery`
  hooks.
- `.claude/skills/extension-development/SKILL.md` — `shared_preload_libraries`
  requirement, multi-hook chaining, `PG_MODULE_MAGIC_EXT`, bgworker registration.

## Sources

Fetched 2026-06-07 (branch `main`):

- `https://api.github.com/repos/duckdb/pg_duckdb/git/trees/main?recursive=1`
  @ 2026-06-07 → HTTP 200 (tree listing).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/README.md`
  @ 2026-06-07 → HTTP 200 (260 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/pg_duckdb.control`
  @ 2026-06-07 → HTTP 200 (4 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb.cpp`
  @ 2026-06-07 → HTTP 200 (42 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb_hooks.cpp`
  @ 2026-06-07 → HTTP 200 (513 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb_planner.cpp`
  @ 2026-06-07 → HTTP 200 (242 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb_node.cpp`
  @ 2026-06-07 → HTTP 200 (453 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb_table_am.cpp`
  @ 2026-06-07 → HTTP 200 (529 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/pgduckdb_background_worker.cpp`
  @ 2026-06-07 → HTTP 200 (1357 lines, skimmed for worker role).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/include/pgduckdb/pgduckdb_hooks.hpp`
  @ 2026-06-07 → HTTP 200 (12 lines).
- `https://raw.githubusercontent.com/duckdb/pg_duckdb/main/src/scan/postgres_scan.cpp`
  @ 2026-06-07 → HTTP 200 (645 lines, skimmed).

All cites are `[verified-by-code]` against the fetched `.cpp`/`.hpp` (hook
installs, planner rewrite, CustomScan registration, table-AM stubs, catalog/xact
guards) except the end-user feature narrative, data-lake/MotherDuck workflow, and
PG-version support, which are `[from-README]`. The DuckDB-side execution
(`DuckDBManager`, `DataChunk`→slot conversion in `pgduckdb_types.cpp`) and the
background worker's internal sync loop were skimmed, not deep-read; claims about
*that* the worker syncs MotherDuck catalogs and *that* exec converts DataChunks
rest on the hook/struct call sites plus README, tagged where they exceed a
declaration.
