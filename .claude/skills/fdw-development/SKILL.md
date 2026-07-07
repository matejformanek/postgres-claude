---
name: fdw-development
description: Building or modifying a Foreign Data Wrapper (FDW) — the SQL/MED interface for accessing external data as if it were PG tables. Covers the `FdwRoutine` callback set (`GetForeignRelSize` / `GetForeignPaths` / `GetForeignPlan` / `BeginForeignScan` / `IterateForeignScan` / `ReScanForeignScan` / `EndForeignScan` for scans, `BeginForeignInsert` / `ExecForeignInsert` / … for DML), the `postgres_fdw` reference implementation, plan pushdown (WHERE / JOIN / AGG / LIMIT), extended-explain support, and the FDW-related core code (`src/backend/foreign/foreign.c`, foreign-table catalog, user mappings). Loads when the user asks about writing an FDW, `CREATE FOREIGN TABLE`, why postgres_fdw is fast, pushdown decisions (`use_remote_estimate`, `fdw_startup_cost`), user mappings and password security (`password_required`), the loopback-back-to-self bypass-RLS pattern from postgres_fdw, or adding a new pushdown-shape. Skip when the ask is about specific non-postgres_fdw wrappers (file_fdw, oracle_fdw external, mysql_fdw external) — those are separate implementations.
when_to_load: Write a new FDW; extend an existing one; add pushdown support; understand the `postgres_fdw` architecture; audit FDW security (password leakage, loopback bypasses); investigate why the planner isn't pushing a qual to the foreign side.
companion_skills:
  - executor-and-planner
  - catalog-conventions
  - error-handling
---

# fdw-development — Foreign Data Wrappers

An FDW lets a PG backend access external data (another PG, MySQL, files, HTTP APIs) as if it were a local relation. The system supports:

- SELECT (with pushdown of quals, joins, aggregates, LIMITs).
- INSERT / UPDATE / DELETE (with pushdown for `postgres_fdw`).
- TRUNCATE.
- COPY FROM.
- Async scans (PG 14+).
- Extended-explain output.

The **core FDW support** is small — `src/backend/foreign/foreign.c` (22 KB) — and lives around the `FdwRoutine` callback struct. The heavy work is in per-wrapper contrib modules (`contrib/postgres_fdw/` for PG-to-PG, `contrib/file_fdw/` for CSV/text files).

## The file map

| File | Role |
|---|---|
| `src/backend/foreign/foreign.c` | Core FDW support — foreign-table cache, GetForeignServer / GetUserMapping helpers, wrapper's `handler` fn is looked up + cached here. |
| `src/backend/commands/foreigncmds.c` | CREATE / ALTER / DROP for SERVER / USER MAPPING / FOREIGN TABLE. |
| `src/backend/executor/nodeForeignscan.c` | `ForeignScan` executor node — dispatches to the FDW's Begin/Iterate/End callbacks. |
| `src/backend/optimizer/util/appendinfo.c` + `plancat.c` | Planner-side foreign-table hooks. |
| `src/include/foreign/fdwapi.h` | The FdwRoutine struct definition — 30+ callback pointers. |
| `contrib/postgres_fdw/postgres_fdw.c` | Reference implementation. Big and non-trivial (has to handle pushdown + connection pooling + prepared statements + async). |
| `contrib/postgres_fdw/deparse.c` | Deparse — turn PG parse-tree back into SQL text to send to the remote. Where "shipping expressions" lives. |
| `contrib/postgres_fdw/option.c` | Server/user-mapping/foreign-table options parsing. |
| `contrib/postgres_fdw/connection.c` | Libpq connection cache — one connection per (user, server) tuple, kept warm. |

## The FdwRoutine callback taxonomy

Grouped by lifecycle stage:

### Planner-time
- `GetForeignRelSize` — populate `baserel->rows` estimate.
- `GetForeignPaths` — add ForeignPath entries to `baserel->pathlist`.
- `GetForeignPlan` — build the ForeignScan node from a picked Path.
- `EstimateDSMForeignScan` / `InitializeDSMForeignScan` / `InitializeWorkerForeignScan` — parallel-aware FDW support (rare).

### Executor-time, scan
- `BeginForeignScan` — one-time setup (open connection, prepare remote statement).
- `IterateForeignScan` — return the next tuple (or NULL for end-of-stream).
- `ReScanForeignScan` — restart if re-iterated in a nested loop.
- `EndForeignScan` — clean up (release connection back to pool).

### Executor-time, DML
- `BeginForeignInsert` / `ExecForeignInsert` / `EndForeignInsert` — INSERT path.
- `BeginForeignModify` / `ExecForeignUpdate` / `ExecForeignDelete` / `EndForeignModify` — UPDATE + DELETE.
- Also: `BeginDirectModify` / `IterateDirectModify` / `EndDirectModify` — for pushed-down "delete this whole range" queries.

### Planner-time, pushdown decisions
- `GetForeignJoinPaths` — add ForeignPath for a foreign-side JOIN.
- `GetForeignUpperPaths` — add ForeignPath for GROUP BY / DISTINCT / LIMIT / etc. that can be pushed to the foreign side.
- `IsForeignRelUpdatable` — is UPDATE/DELETE supported on this table?

### Extras
- `ExplainForeignScan` / `ExplainForeignModify` — populate the EXPLAIN output with FDW-specific info.
- `AnalyzeForeignTable` — support for local ANALYZE of a foreign table (sample rows).
- `ImportForeignSchema` — for `IMPORT FOREIGN SCHEMA` — return CreateForeignTableStmt list.

## The postgres_fdw pushdown philosophy

By default, `postgres_fdw` tries to push as much work as possible to the remote:

- **Quals** — `WHERE` predicates that are `shippable` (see `is_foreign_expr`) go to the remote. Deterministic + non-volatile + no local-only functions.
- **Joins** — foreign-to-foreign joins on the same server get pushed as a subquery.
- **Aggregates** — `GROUP BY` / `SUM` / `COUNT` on foreign-only data pushed via `GetForeignUpperPaths`.
- **LIMIT** — pushed as long as ORDER BY is also shippable.
- **UPDATE / DELETE** — `DirectModify` — if the WHERE clause is shippable, PG sends one UPDATE/DELETE statement instead of scanning + updating row-by-row.

`use_remote_estimate` (server option) toggles whether to run `EXPLAIN` on the remote to get better cost estimates (slower to plan; better plans).

## The `password_required` two-layered defense

A recurring security concern with postgres_fdw: an unprivileged user's foreign-table access could be abused to send commands as the FDW's connecting user (potentially a superuser on the remote).

Two-layered protection:

1. **`password_required = true`** (default) — the user mapping MUST provide a password. Excludes trust / peer auth from being used.
2. **User mapping ownership** — only the mapping's owner can use it (unless PUBLIC). Superuser + application user split.

Non-superusers who create user mappings CAN'T set `password_required = false`. This is the gold-standard defense pattern; audit any FDW you write for equivalent.

## Common patch shapes

### Write a new FDW (minimum viable)

1. `_PG_init` in the extension registers the wrapper via `pg_foreign_data_wrapper` (create-time SQL).
2. Handler function returns `FdwRoutine *` filled with your callbacks.
3. Minimal callbacks: `GetForeignRelSize`, `GetForeignPaths`, `GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`, `EndForeignScan`, `ReScanForeignScan`.
4. `ExplainForeignScan` — even a stub — makes debugging much easier.
5. Test via `CREATE EXTENSION my_fdw; CREATE SERVER ...; CREATE USER MAPPING ...; CREATE FOREIGN TABLE ...`.
6. See `contrib/file_fdw/` for the simplest example.

### Add a new pushdown

Consider carefully — pushdown is where FDWs get correctness bugs:

- Add a case in `is_foreign_expr` for the expression you want to push.
- Verify the deparse.c handles it — `deparseExpr` needs to know how to write it back as SQL.
- Add regression coverage — every pushdown case needs a test that verifies:
  - Result correctness.
  - `EXPLAIN` shows the pushed-down form.
  - It DOESN'T push when a non-shippable qual is involved.

### Cache connection to remote

- Per-user, per-server connection cache in `contrib/postgres_fdw/connection.c`.
- Held in the backend's process-lifetime (no shmem).
- Re-established on subtransaction abort — connection state is torn down.
- If you're writing an FDW that talks to something with expensive connection setup (HTTP, etc.), copy this pattern.

### Debug "postgres_fdw isn't pushing my WHERE clause"

- EXPLAIN VERBOSE — shows the exact SQL being sent to remote as `Remote SQL`.
- Common blockers: qual uses a volatile function, references a local table, uses a subquery not shippable.
- `SET postgres_fdw.debug_pushdown = on` — logs pushdown decisions.
- Check if the qual is a JOIN condition — join pushdown has stricter rules.

## Pitfalls

- **User mapping password can leak** — if the FDW forwards the password to a debug/error message. `postgres_fdw` scrubs but a naive new FDW may not.
- **Loopback to self bypasses RLS** — creating a `postgres_fdw` server pointing at the same cluster with a superuser mapping lets you bypass RLS on your own database. Well-documented but frequently misused.
- **Volatility marking of remote functions** — the planner assumes remote functions have the volatility marked on the local shell function. Mismatch → wrong plans (caching wrong result).
- **Async scans require careful state** — the async API (`ForeignAsyncRequest` etc.) has multiple interleaved iterators. Managing state per-iterator is fiddly.
- **User Mapping owner vs current_user** — some FDWs check the "connect as" user carefully; others don't. Confusing "who owns the mapping" with "who's using it" is a security bug source.
- **`fdw_startup_cost` + `fdw_tuple_cost`** — the planner uses these to decide whether to bother pushing down. Wrong defaults produce nonsensical plans.
- **`use_remote_estimate` for JOINs** — enabling it can turn planning into O(N²) remote round-trips for cross-joins. Enable per-table where it helps.
- **DML doesn't push implicitly** — `INSERT ... SELECT` doesn't push the SELECT's INSERT logic; it fetches the rows to local then re-INSERTs. Only `DirectModify` (UPDATE/DELETE with all-remote WHERE) pushes.
- **`postgres_fdw` prepared-statement cache is per-connection** — if the connection restarts, all prepared statements are re-prepared.

## Related corpus

- **Idioms**: `fdw-iterate-scan` (the pull-next-tuple discipline), `fdw-routine-callbacks` (the FdwRoutine struct), `cursor-and-portal` (foreign-scan portals).
- **Subsystems**: `foreign` (this skill's home subsystem), `executor` (ForeignScan node), `contrib-postgres_fdw` (the reference), `contrib-file_fdw` (the simplest example), `contrib-dblink` (different pattern — imperative not declarative FDW).
- **Sessions**: `2026-06-04-a11-contrib-top.md` (deep-read of the top-4 contrib modules including postgres_fdw's `password_required` gold-standard).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom fdw-routine-callbacks
python3 scripts/corpus-chain.py --file contrib/postgres_fdw/postgres_fdw.c
```

Second surfaces the reference implementation's neighborhood: 6 files in the contrib module.

## Boundary

**Use this skill** for FDW architecture + `postgres_fdw` internals + writing new FDWs.

**Don't use** for:
- **Specific non-core FDWs** (oracle_fdw / mysql_fdw / etc.) — external contribs with their own idioms.
- **`dblink`** — different pattern (per-call connection + explicit `dblink('SELECT ...')`), not an FDW.
- **`postgres_fdw` bug fixing at the connection layer** — if you're on the wire protocol level, `wire-protocol` skill has the byte-level details.
- **`ImportForeignSchema` DDL processing** — related but handled by `commands/foreigncmds.c`; that's more DDL-plumbing than FDW-authoring.
