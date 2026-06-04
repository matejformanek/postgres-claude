# `src/fe_utils/query_utils.c`

- **File:** `source/src/fe_utils/query_utils.c` (91 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

A tiny set of "run one query, handle failure uniformly" wrappers over libpq's
synchronous `PQexec`, shared by frontend maintenance utilities (notably the
`src/bin/scripts/` programs — vacuumdb, reindexdb, clusterdb — and similar
tools). It gives them three flavors: fetch tuples and die on error, run a
command and die on error, and run a maintenance command that returns success
and is cancellable via Ctrl-C. As frontend code it reports through
`pg_log_error`/`pg_log_error_detail` and calls `exit()` directly rather than
using `ereport`. [verified-by-code: includes at `query_utils.c:12-16`]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `executeQuery` | :22 | Run `query`, require `PGRES_TUPLES_OK`, return the `PGresult`; on failure log + `PQfinish` + `exit(1)`. |
| `executeCommand` | :47 | Run `query`, require `PGRES_COMMAND_OK`, `PQclear` and return void; on failure log + `PQfinish` + `exit(1)`. |
| `executeMaintenanceCommand` | :74 | Run `query` with a cancel handler installed; return bool success (no exit on failure). |

## Internal landmarks

- All three optionally echo the SQL to stdout when `echo` is true (`:26`, `:51`, `:79`) — this backs the `--echo`/`-e` flag of the scripts utilities.
- `executeQuery` / `executeCommand` share the same failure idiom: `!res || PQresultStatus(res) != <expected>` then `pg_log_error("query failed: %s", PQerrorMessage(conn))`, `pg_log_error_detail("Query was: %s", query)`, `PQfinish(conn)`, `exit(1)` (`:30`–`:37`, `:55`–`:62`).
- `executeMaintenanceCommand` wraps the `PQexec` between `SetCancelConn(conn)` (`:82`) and `ResetCancelConn()` (`:84`), so a SIGINT/Ctrl-C during a long maintenance command (e.g. VACUUM, REINDEX) is delivered as a query cancel. It returns the boolean `res && PQresultStatus(res) == PGRES_COMMAND_OK` and always `PQclear`s (`:86`–`:88`).

## Invariants & gotchas

- **`executeQuery` returns an unfreed `PGresult`** — the caller owns it and must `PQclear` it. `executeCommand` clears its own result; `executeMaintenanceCommand` clears its result before returning the bool. [verified-by-code] `:39`, `:64`, `:88`
- **`executeQuery`/`executeCommand` terminate the whole program on failure** (`PQfinish` + `exit(1)`), so they are unsuitable where the caller must recover or run further cleanup. `executeMaintenanceCommand` is the recoverable variant — it neither finishes the connection nor exits, leaving error reporting to the caller. [verified-by-code] `:36`, `:90`
- **`executeMaintenanceCommand` does NOT log on failure** — it only returns false. Callers are responsible for emitting a diagnostic (typically via `PQerrorMessage`). [verified-by-code] `:86`
- Only the maintenance variant sets a cancel handler; `executeQuery`/`executeCommand` are not interruptible via the cancel machinery. [verified-by-code] `:82`–`:84`

## Cross-references

- `source/src/include/fe_utils/query_utils.h` — declarations.
- `knowledge/files/src/fe_utils/cancel.c.md` — `SetCancelConn`/`ResetCancelConn` used at `query_utils.c:82,84`.
- `source/src/bin/scripts/` — vacuumdb.c / reindexdb.c / clusterdb.c are the principal consumers of `executeMaintenanceCommand` (cancellable long-running commands) and `executeQuery`.
- `source/src/common/logging.c` — `pg_log_error` / `pg_log_error_detail`.

## Confidence tag tally

- `[verified-by-code]` × 6
- `[inferred]` × 0
