# Query Lifecycle — `psql -c 'SELECT 1'` end-to-end

What actually happens when a client sends "SELECT 1". Every step is cited.
Read this alongside `overview.md` (subsystem map) and `process-model.md`
(who forks whom).

## Step 0 — `psql` opens the connection

`psql` calls `libpq` (`PQconnectdb`), which opens a TCP or Unix-socket
connection to the postmaster's listening port and sends a **StartupPacket**
(protocol version, user, database, options).
[from-docs](https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-START-UP)

## Step 1 — Postmaster accepts and forks

- `ServerLoop` (`postmaster.c:1678`) `poll`s on listening sockets.
- When a connection arrives, it calls `BackendStartup` (`postmaster.c:3576`),
  which builds `BackendStartupData` and calls `postmaster_child_launch` with
  `B_BACKEND`.
- `postmaster_child_launch` (`launch_backend.c:204-272`) `fork()`s. The child
  sets `MyBackendType = B_BACKEND`, closes the postmaster's sockets, attaches
  to shared memory (because `child_process_kinds[B_BACKEND].shmem_attach` is
  true), and calls the registered `main_fn` — `BackendMain`, which immediately
  calls `PostgresMain`.
  [verified-by-code] `launch_backend.c:225-268`.

The postmaster has now lost interest in this client. **Auth happens in the
child**, not the parent — by design, so a hanging TLS handshake or PAM call
cannot DoS other clients.
[from-comment] `postmaster.c:25-32`

## Step 2 — Startup packet + authentication (in the new backend)

In the freshly-forked child:

- `ProcessStartupPacket` reads the protocol/version/SSL/GSS negotiation and
  fills in the `Port` struct with user, database, etc.
  [verified-by-code] `tcop/backend_startup.c:486` (definition), called from
  `BackendInitialize` at `:295`.
- Backend then transitions into `InitPostgres` (full init: attach to shmem
  slot, load HBA, look up the role and database in catalogs, run on-connect
  hooks, etc.).
  [verified-by-code] `utils/init/postinit.c:716` (`InitPostgres` definition);
  `:262` `ClientAuthentication(port)` — "might not return, if failure".
- `ClientAuthentication` runs the appropriate method (trust / md5 /
  scram-sha-256 / cert / LDAP / GSS / PAM …) per `pg_hba.conf`. On success it
  sends `AuthenticationOk` then `ReadyForQuery`. On failure the backend exits.

At this point the backend is **ready** and sitting in the `PostgresMain`
command-read loop.

## Step 3 — `PostgresMain` reads the next protocol message

`PostgresMain` (`tcop/postgres.c:4274`) is the per-backend main loop. Each
iteration:

1. Resets per-message memory context.
2. Sends `ReadyForQuery` if needed.
3. Blocks on `ReadCommand(&input_message)` (`postgres.c:4788`).
4. Dispatches on the first byte:
   - `'Q'` (PqMsg_Query) → `exec_simple_query` (`postgres.c:4840-4856`).
   - `'P'`/`'B'`/`'E'` → extended-protocol path (`exec_parse_message`,
     `exec_bind_message`, `exec_execute_message`).
   - Others: `Close`, `Describe`, `Sync`, `Terminate`, `CopyData`, …

For `SELECT 1` via `psql -c`, the message is `'Q'` with the literal SQL.
[verified-by-code] `postgres.c:4838-4856`.

## Step 4 — `exec_simple_query` runs the whole 5→7 pipeline

`exec_simple_query` (`postgres.c:1029-1320`) is a tour of the entire query path
in 200 lines. The annotated stages:

| Phase | Call | File:line |
|---|---|---|
| Start xact command | `start_xact_command()` | `postgres.c:1063` |
| **Parse (raw)** | `pg_parse_query(query_string)` | `postgres.c:1082` |
| Optionally push snapshot | `PushActiveSnapshot(GetTransactionSnapshot())` | `:1179` |
| **Analyze + Rewrite** | `pg_analyze_and_rewrite_fixedparams(...)` | `:1206` |
| **Plan** | `pg_plan_queries(querytree_list, ...)` | `:1209` |
| Wrap plan in a portal | `CreatePortal("", true, true)` / `PortalDefineQuery` / `PortalStart` | `:1232-1251` |
| Pick output format | `PortalSetResultFormat(portal, 1, &format)` | `:1273` |
| Create dest receiver (sends rows to client) | `CreateDestReceiver(dest)` | `:1278` |
| **Execute** | `PortalRun(portal, FETCH_ALL, ...)` | `:1290` |
| Drop portal + finish xact | `PortalDrop`, `finish_xact_command` | `:1299-1314` |

[verified-by-code] all of the above are line-for-line in `tcop/postgres.c`.

### 4a. Parse — `pg_parse_query` (`postgres.c:616`)

Runs the Bison grammar (`parser/gram.y`) + flex scanner. Output is a
`List *` of `RawStmt`. **No catalog access** — this must be safe in an aborted
transaction.
[from-comment] `postgres.c:1078-1082`.

For `SELECT 1`: one `RawStmt` wrapping a `SelectStmt` whose target list has a
single `A_Const` of integer 1.

### 4b. Analyze — `parse_analyze_fixedparams` (called by
`pg_analyze_and_rewrite_fixedparams`)

In `parser/analyze.c`. Transforms `RawStmt` → `Query`. Catalog lookups for
relations, columns, functions, types happen here (via syscache:
`SearchSysCache*`). Range-table entries are built; expressions get their types
resolved.
[from-docs](https://www.postgresql.org/docs/current/parser-stage.html)
[verified-by-code] `postgres.c:699` `parse_analyze_fixedparams` callsite.

For `SELECT 1`: a `Query` with empty `rtable`, a single target entry of type
`int4`.

### 4c. Rewrite — `QueryRewrite` (`rewrite/rewriteHandler.c:4781`)

Applies rules (`pg_rewrite`); view expansion is implemented as
"ON SELECT DO INSTEAD". Returns `List<Query>` (a single rule can fire-and-also
produce extra queries).
[verified-by-code] `rewrite/rewriteHandler.c:4772-4781`.

For `SELECT 1`: no rules fire, one `Query` in, one out.

### 4d. Plan — `pg_plan_queries` → `pg_plan_query` (`postgres.c:899`) → `planner`

`pg_plan_query` calls the planner (`optimizer/plan/planner.c:planner` →
`standard_planner` or a hook). For non-trivial queries this runs:

- Preprocessing (constant folding, subquery pull-up).
- `query_planner` / `grouping_planner` — generate paths.
- Join order search: dynamic programming for ≤ `geqo_threshold` rels (default
  12), otherwise the **GEQO** genetic search.
  [from-docs](https://www.postgresql.org/docs/current/geqo.html)
- Cost model uses `pg_statistic` (filled by `ANALYZE`): MCV lists, histograms,
  ndistinct, correlation, plus `pg_class.reltuples`/`relpages`.
  [from-docs](https://www.postgresql.org/docs/current/planner-stats.html)

Output: `PlannedStmt` containing a tree of `Plan` nodes (`SeqScan`,
`IndexScan`, `BitmapHeapScan`, `HashJoin`, `Sort`, `Agg`, `Gather`, …).

For `SELECT 1`: a `Result` node with no children — the value is computed
inline, no relations scanned.

### 4e. Execute — `PortalRun` → `ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd`

- `PortalRun` (`tcop/pquery.c`) drives execution.
- The four executor entry points are pluggable hooks (used by
  `pg_stat_statements`, `auto_explain`, etc.). The defaults are
  `standard_ExecutorStart` etc. in `executor/execMain.c`.
  [from-comment] `executor/execMain.c:7-26`.
- `ExecutorStart` builds the runtime `PlanState` tree mirroring the `Plan`
  tree. Each node has an `ExecProcNode` function that returns the next
  `TupleTableSlot` from its child.
- `ExecutorRun` pulls tuples through the tree, feeding each finished tuple to
  the destination receiver.
- The destination receiver for a regular client is `printtup.c`'s remote
  receiver, which writes `DataRow` messages back over libpq.

For `SELECT 1`: one tuple, then end-of-scan.

### 4f. Send result tuples + CommandComplete + ReadyForQuery

- For each output tuple: `DestReceiver->receiveSlot` formats it (text or
  binary per `format`) and writes `DataRow` ('D') to the wire.
- After the executor returns: `CommandComplete` ('C') with the tag
  ("SELECT 1").
- After `finish_xact_command` and any error reporting: `ReadyForQuery` ('Z')
  with the current xact status ('I' idle / 'T' in-block / 'E' in-failed-block).

`exec_simple_query` returns; `PostgresMain` loops back to `ReadCommand`.

## Step 5 — Tear-down (only on disconnect)

When the client sends `'X'` (Terminate) or the socket closes, `PostgresMain`
breaks the loop, the backend runs shmem/exit hooks (release locks, free
`PGPROC` slot, drop temp tables, …), and the process exits. Postmaster reaps
the child via `SIGCHLD`.

## The extended-protocol variant (for context)

`psql` sends `'Q'`, but most drivers use the extended protocol:

- `Parse` (P) — store a named *prepared statement*: parse + analyze, store the
  `Query` (no plan yet).
- `Bind` (B) — supply parameters, create a *portal*, run plan if not cached
  (`plan_cache.c` decides custom vs generic plan).
- `Execute` (E) — run the portal, return rows.
- `Sync` (S) — close implicit xact, send `ReadyForQuery`.

This separates parse/analyze (catalog-dependent, cacheable) from plan
(parameter-dependent) from execute (per-call). The simple-query path collapses
all three into `exec_simple_query`.
[from-docs](https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-EXT-QUERY)

## Memory & resource cleanup along the way

- Each loop iteration through `PostgresMain` resets `MessageContext`.
- Parse/analyze/plan trees live in `MessageContext` (or a per-parsetree child
  context if there are multiple statements).
  [from-comment] `postgres.c:1183-1204`.
- Executor state lives in a `EState`-owned context; per-tuple temp allocations
  live in the executor's per-tuple context, which is reset on each tuple.
- On `ERROR`, `AbortTransaction` rolls back, releases locks, drops the snapshot,
  resets relevant memory contexts. The loop continues with `ignore_till_sync`
  set until a `Sync`.

## Open Questions / Unverified

- The exact handoff between `BackendMain` and `PostgresMain` (whether
  `BackendInitialize` is still its own phase or has been folded in) varies
  by version. [unverified] — confirm by reading `backend_startup.c` end-to-end
  when working on the connection-handling subsystem.
- For `SELECT 1` specifically, the plan may not need a snapshot at all
  (`analyze_requires_snapshot` returns false for parameter-free constant
  selects). [inferred] — verify by tracing `analyze_requires_snapshot` for a
  bare `SELECT 1`.

## Citation index

- `tcop/postgres.c:13-15` — "this is the 'main' module … the 'traffic cop'".
- `tcop/postgres.c:616` — `pg_parse_query`.
- `tcop/postgres.c:899` — `pg_plan_query`.
- `tcop/postgres.c:1029` — `exec_simple_query`.
- `tcop/postgres.c:4274` — `PostgresMain`.
- `tcop/postgres.c:4788` — `ReadCommand` callsite (the loop's blocking read).
- `tcop/postgres.c:4838-4856` — message-type switch, `'Q'` → `exec_simple_query`.
- `tcop/backend_startup.c:486` — `ProcessStartupPacket`.
- `utils/init/postinit.c:262` — `ClientAuthentication`.
- `utils/init/postinit.c:716` — `InitPostgres`.
- `postmaster/postmaster.c:1678` — `ServerLoop`.
- `postmaster/postmaster.c:3576` — `BackendStartup`.
- `postmaster/launch_backend.c:204` — `postmaster_child_launch` (the fork point).
- `rewrite/rewriteHandler.c:4781` — `QueryRewrite`.
- `executor/execMain.c:7-26` — executor entry-point contract.
