# PostgreSQL Architecture — The 2-Page Mental Model

The "first thing a new contributor reads" overview. Concepts and layering, not
deep code. Cite tags follow each load-bearing claim.

## What PostgreSQL is

A single-machine, **process-per-connection** relational DBMS. There is no thread
pool: every client connection is served by its own OS process called a *backend*,
forked from a long-lived supervisor process called the *postmaster*. All
processes share a single block of POSIX shared memory (buffers, locks, WAL
buffers, catalog caches' invalidation channel, etc.) that the postmaster
allocates at startup.
[from-docs](https://www.postgresql.org/docs/current/tutorial-arch.html)
[from-comment] `source/src/backend/postmaster/postmaster.c:5-23`

> "Frontend programs connect to the Postmaster, and postmaster forks a new
> backend process to handle the connection. … The postmaster process creates
> the shared memory and semaphore pools during startup, but as a rule does not
> touch them itself." — `postmaster.c:5-17`
[from-comment]

This shapes everything else: contention is across processes (heavyweight locks,
lightweight locks, spinlocks in shared memory), the catalog cache is per-backend
(invalidated via shared inval queue), and a backend crash can be recovered by
the postmaster resetting shared memory rather than restarting the whole cluster.

## The major layering — one request, top to bottom

A SQL statement traverses these layers in order. Each is its own subsystem
directory under `source/src/backend/`.

| # | Layer | Dir | Entry point | Output |
|---|-------|-----|-------------|--------|
| 1 | Frontend/Backend protocol (libpq wire) | `libpq/` | `pq_*` reads | raw bytes |
| 2 | Traffic Cop — per-backend main loop | `tcop/` | `PostgresMain`, `exec_simple_query` | dispatches by message type |
| 3 | Parser (raw → parsetree) | `parser/` | `pg_parse_query` | `List` of `RawStmt` |
| 4 | Analyzer (semantic check, name resolution, catalog lookups) | `parser/analyze.c` | `parse_analyze_*` | `Query` tree |
| 5 | Rewriter (apply views/rules) | `rewrite/` | `QueryRewrite` | `List<Query>` |
| 6 | Planner/Optimizer (cost-based; GEQO for many-table joins) | `optimizer/` | `pg_plan_query` → `planner` | `PlannedStmt` |
| 7 | Executor (interprets plan tree of `Plan`/`PlanState` nodes) | `executor/` | `ExecutorStart` / `Run` / `Finish` / `End` | tuples |
| 8 | Access methods — heap, btree/hash/gist/gin/spgist/brin, table AM API | `access/` | `heap_*`, `index_*`, `tableam.h` | tuple pages |
| 9 | Buffer manager + storage manager (smgr) | `storage/buffer/`, `storage/smgr/` | `ReadBuffer`, `smgr*` | pages from disk |
| 10 | WAL + crash recovery | `access/transam/xlog*.c` | `XLogInsert`, `StartupXLOG` | durability |

[from-docs](https://www.postgresql.org/docs/current/internals.html)
[verified-by-code] `tcop/postgres.c:1029-1295` walks 3→7 in one function
(`exec_simple_query`).

### Tcop is the per-backend "main"
`postgres.c` calls itself the "traffic cop" — it reads protocol messages in a
loop, dispatches `Q` (simple query) / `P` (parse) / `B` (bind) / `E` (execute)
/ etc., and is responsible for transaction state.
[from-comment] `source/src/backend/tcop/postgres.c:13-15`
[verified-by-code] dispatch switch (`switch (firstchar)`) at `postgres.c:4933`.

### Parser → Analyzer is a hard split
The raw parser (`gram.y`, Bison) does **no catalog access** and must be safe to
run inside an aborted transaction. Catalog lookups, name resolution, and type
resolution happen in the *analyzer* (`parse_analyze_*`), which produces a
`Query` tree.
[from-comment] `postgres.c:1078-1082` ("Do basic parsing … safe even if we are
in aborted transaction state!")
[verified-by-code] `postgres.c:616` `pg_parse_query`, `:699,738,792`
`parse_analyze_*`.

### Rewriter applies rules and view expansion
Views are implemented as `ON SELECT DO INSTEAD` rules; `QueryRewrite` expands
them.
[verified-by-code] `source/src/backend/rewrite/rewriteHandler.c:4772-4781`

### Planner is cost-based + GEQO escape hatch
For small queries, an exhaustive dynamic-programming join search; for queries
with many relations (`geqo_threshold`, default 12) a genetic algorithm replaces
the bottom-up join order search.
[from-docs](https://www.postgresql.org/docs/current/geqo.html)
[from-docs](https://www.postgresql.org/docs/current/planner-stats.html) — the
planner uses `pg_statistic` (per-column MCVs, histograms, ndistinct, correlation)
populated by `ANALYZE`.

### Executor is an iterator tree
The plan is a tree of `Plan` nodes; at runtime each is paired with a
`PlanState` whose `ExecProcNode` returns the next `TupleTableSlot`. The four
entry points (`ExecutorStart`, `ExecutorRun`, `ExecutorFinish`, `ExecutorEnd`)
are pluggable hooks used by extensions like `pg_stat_statements` and
`auto_explain`.
[from-comment] `source/src/backend/executor/execMain.c:7-26`

### Access methods are pluggable
- **Table AM** (`tableam.h`) — heap is the default; the API supports alternates.
- **Index AM** — btree, hash, gist, spgist, gin, brin; extensions can register more.
[from-docs](https://www.postgresql.org/docs/current/indexam.html) (Index Access
Method Interface Definition)

### Storage = buffer manager + smgr + WAL
- Pages are 8 KB (compile-time). The buffer manager (`shared_buffers`) is a
  shared, hashed, clock-sweep cache.
- All data writes go through WAL first (write-ahead logging) so crash recovery
  is `redo` from the last checkpoint.
- `smgr` is the layer below buffer manager that talks to the filesystem.
[from-docs](https://www.postgresql.org/docs/current/storage.html) (Database
Physical Storage) [from-docs](https://www.postgresql.org/docs/current/wal-intro.html)

## The orthogonal axis — processes

The layered story above describes *one backend processing one query*. **Across
the cluster**, multiple kinds of processes coexist, all sharing one shared
memory region. The postmaster supervises them; the `BackendType` enum
enumerates them.
[verified-by-code] `source/src/include/miscadmin.h:340-381` (full enum).

Categories:
- **Regular backends** (`B_BACKEND`) — one per client connection.
- **Auxiliary processes** — singletons (except IO workers): startup,
  checkpointer, bgwriter, walwriter, archiver, wal receiver, wal summarizer,
  io workers, logger.
- **Special workers** — autovac launcher/workers, logical replication launcher,
  logical slot sync worker.
- **Walsenders** — one per connected replica (physical or logical).
- **Background workers** (`B_BG_WORKER`) — generic; used internally for
  parallel query workers and by extensions.

See `process-model.md` for the full table with lifetimes, parents, and
shared-memory channels.

## Catalogs are tables — and the bootstrap is a real chicken/egg

The data dictionary lives in regular heap tables under the `pg_catalog`
namespace (`pg_class`, `pg_attribute`, `pg_proc`, `pg_type`, …). Every backend
accesses them through the normal access methods, but with a per-backend
**syscache** in front to avoid hammering them on every name resolution.
Initial bootstrap (the very first `template1`) is done by a special mode in
`src/backend/bootstrap/` that bypasses most of the stack.
[from-docs](https://www.postgresql.org/docs/current/catalogs.html)

## Function manager and memory contexts — the two cross-cutting idioms

- **fmgr** — all SQL-callable C functions go through a uniform calling
  convention (`PG_FUNCTION_ARGS`, `PG_GETARG_*`, `PG_RETURN_*`) so they're
  invokable by Oid through `FunctionCallInvoke`.
- **Memory contexts** (`palloc`) — hierarchical arenas; the executor leans on
  this heavily so per-tuple, per-query, and per-transaction allocations can be
  freed in bulk on context reset/delete.
[from-docs](https://www.postgresql.org/docs/current/xfunc-c.html)

## What's deliberately *not* in this overview

- MVCC / xid / vacuum details — see future `subsystems/transaction-mvcc.md`.
- WAL record layout, replication slots, archive recovery details.
- Index AM internals.
- Locking lattice (heavyweight vs lightweight vs spin vs predicate).
- Parallel query mechanics (see `process-model.md` for the process side).

## Open Questions / Unverified

- The exact list of process kinds may shift between PG majors. The enum above
  is taken from current HEAD; older versions split things differently (e.g.
  pre-PG 15 had a separate stats collector process; it is now the *cumulative
  statistics system* using shared memory, no dedicated process).
  [from-docs](https://www.postgresql.org/docs/current/monitoring-stats.html)
  [unverified] — need to confirm which PG version `source/` is pointing at.

## Canonical entry-point map (for quick navigation)

| Concept | File | Symbol |
|---|---|---|
| Postmaster main | `postmaster/postmaster.c` | `PostmasterMain`, `ServerLoop`, `BackendStartup` |
| Per-backend main | `tcop/postgres.c` | `PostgresMain` |
| Per-statement simple-query path | `tcop/postgres.c` | `exec_simple_query` (`:1029`) |
| Parse | `tcop/postgres.c:616` | `pg_parse_query` |
| Analyze | `parser/analyze.c` | `parse_analyze_fixedparams` |
| Rewrite | `rewrite/rewriteHandler.c:4781` | `QueryRewrite` |
| Plan | `tcop/postgres.c:899` | `pg_plan_query` → `optimizer/plan/planner.c:planner` |
| Execute | `executor/execMain.c` | `ExecutorStart/Run/Finish/End` |
| Init backend | `utils/init/postinit.c:722` | `InitPostgres` |
| Auth | `utils/init/postinit.c:268` | `ClientAuthentication` (call site) |
| Startup packet | `tcop/backend_startup.c:486` | `ProcessStartupPacket` |
