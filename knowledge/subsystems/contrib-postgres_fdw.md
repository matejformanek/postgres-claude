# contrib-postgres_fdw (PostgreSQL-to-PostgreSQL FDW)

- **Source path:** `source/contrib/postgres_fdw/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.3` (per `postgres_fdw.control`)
- **Trusted:** no (manages remote connections + credentials)
- **Total size:** ~16,000 LOC (the largest contrib module)

## 1. Purpose

A foreign-data wrapper that lets a local PostgreSQL query reach
into a remote PostgreSQL server's tables via libpq. Supports
SELECT / INSERT / UPDATE / DELETE pushdown, remote-side filter
and join evaluation, aggregate pushdown, partition-wise join, and
asynchronous append-pushdown across multiple foreign servers.
The most feature-rich FDW in the ecosystem and the de-facto
reference implementation for the `FdwRoutine` API
(`src/include/foreign/fdwapi.h`).

## 2. Mental model

- **`postgres_fdw.c` implements every `FdwRoutine` callback.**
  The handler function `postgres_fdw_handler` returns a
  `palloc`'d `FdwRoutine` struct filled with `postgresGetForeignRelSize`,
  `postgresGetForeignPaths`, `postgresGetForeignPlan`,
  `postgresBeginForeignScan`, `postgresIterateForeignScan`, etc.
- **Three planning entry points, three RelOptInfo shapes.**
  - Baserel: `postgresGetForeignRelSize` / `postgresGetForeignPaths`
    set up `PgFdwRelationInfo` in `fdw_private`.
  - Joinrel: `postgresGetForeignJoinPaths` if both sides come from
    the same foreign server.
  - Upperrel: `postgresGetForeignUpperPaths` for aggregate / sort /
    `DISTINCT` pushdown.
  All three use the same `PgFdwRelationInfo` shape (see §4).
- **Deparser** (`deparse.c`) — walks the query / join / upper tree
  and emits a libpq-ready SQL string. The `shippability` table
  (`shippable.c`) gates which functions / operators can be sent
  remotely (defaults to immutable + non-PL).
- **Connection pool** (`connection.c`) — one libpq connection per
  (user mapping, server) pair, kept open for the session.
  Transaction-aware: local `BEGIN` opens a remote `BEGIN`,
  local COMMIT/ROLLBACK propagates.
- **Async append** — supports `Append` nodes that issue remote
  queries in parallel across multiple foreign servers and
  multiplex the results via libpq's async API.

## 3. Key files

- `postgres_fdw.c` — `FdwRoutine` callbacks, plan execution
  (BeginForeignScan / IterateForeignScan / EndForeignScan + the
  DML variants). The bulk (~6000 LOC).
- `postgres_fdw.h` — `PgFdwRelationInfo` (planner-side state),
  `PgFdwScanState` (executor-side state), wire-protocol helpers.
- `connection.c` — libpq connection caching, transaction
  bookkeeping, async-query queue (~2000 LOC).
- `deparse.c` — `deparseSelectStmtForRel`, `deparseInsertSql`,
  `deparseTargetList`, expression deparser (~3500 LOC). The
  must-stay-in-sync-with-the-parser surface.
- `option.c` — `CREATE SERVER` / `CREATE USER MAPPING` options
  validation (`postgres_fdw_validator`).
- `shippable.c` — function shippability cache.

## 4. Key data structures

- **`PgFdwRelationInfo`** (`postgres_fdw.h`, ~line 25-130) —
  planner-side state per foreign rel. Holds: foreign server +
  user mapping OIDs, deparsed clauses (`local_conds` /
  `remote_conds`), cost estimates, pushdown flags, joinrel-only
  fields (`outerrel` / `innerrel` / `joinclauses`).
- **`PgFdwScanState`** — executor-side state. Holds: the libpq
  connection, the current `PGresult`, tuple-conversion info,
  parameter exprs.
- **`PgFdwModifyState`** — DML executor state. Per-row prepared
  statement at the remote side; cleaned up on `EndForeignModify`.
- **Async-state machinery**: `PendingAsyncRequest`, `AsyncRequest`
  — for the async append work; coordinates polling across multiple
  foreign servers.

## 5. SQL surface

- `CREATE EXTENSION postgres_fdw`.
- `CREATE FOREIGN DATA WRAPPER postgres_fdw HANDLER postgres_fdw_handler VALIDATOR postgres_fdw_validator`.
- `CREATE SERVER`, `CREATE USER MAPPING`, `CREATE FOREIGN TABLE` —
  all generic FDW DDL; postgres_fdw validates options.
- `IMPORT FOREIGN SCHEMA` — bulk import of remote tables.
- `postgres_fdw_get_connections()` / `postgres_fdw_disconnect()` /
  `postgres_fdw_disconnect_all()` — connection-pool introspection.

## 6. Invariants and gotchas

- **[INV-1]** Local + remote transaction state must stay in sync.
  `connection.c` registers an xact callback (`pgfdw_xact_callback`)
  that issues remote COMMIT/ROLLBACK in `XACT_EVENT_PRE_COMMIT` /
  `_ABORT`. Don't bypass it on a new code path that opens a
  connection.
- **[INV-2]** Function shippability is conservative. Sending a
  non-shippable function would change semantics (collation, default
  values, search_path). When in doubt, mark as non-shippable.
- **[INV-3]** EPQ (EvalPlanQual) for foreign tables requires
  `RefetchForeignRow` — implemented but adds round-trip cost.
  Don't claim "EPQ works" for new pushdown shapes without
  exercising it.
- **[INV-4]** Async-append's polling loop must yield on
  `WL_LATCH_SET` + `WL_EXIT_ON_PM_DEATH`. Same rule as any
  long wait in a backend.
- The deparser duplicates parts of `ruleutils.c`. When `ruleutils.c`
  learns to deparse a new shape, the postgres_fdw deparser usually
  needs the same change.

## 7. Owners (as of 2026-06-12)

- **Primary maintainer:** Etsuro Fujita (per `knowledge/personas/`
  and recent `git log`).
- Major contributors over time: Tom Lane (early architecture),
  Robert Haas, Ashutosh Bapat, Thomas Munro (async).
- Persona drivers: `etsuro-fujita.md` — FDW pushdown correctness;
  `tom-lane.md` — back-compat reflex on PgFdwRelationInfo struct
  layout.

## 8. Local reviewer reflexes

- Any deparse change: confirm `ruleutils.c` parity for the same
  node type.
- Any new pushdown shape: walk the `is_foreign_expr` /
  `foreign_expr_walker` shippability check; default to "no" if
  unsure.
- Any libpq usage: `pgfdw_get_result` is the canonical
  cancellable-on-interrupt wrapper. Direct `PQexec` calls in
  postgres_fdw are a bug.
- Any new connection lifecycle event: the xact callback
  registration in `connection.c` must understand it.


## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**6 files.**

| File |
|---|
| [`contrib/postgres_fdw/connection.c`](../files/contrib/postgres_fdw/connection.c.md) |
| [`contrib/postgres_fdw/deparse.c`](../files/contrib/postgres_fdw/deparse.c.md) |
| [`contrib/postgres_fdw/option.c`](../files/contrib/postgres_fdw/option.c.md) |
| [`contrib/postgres_fdw/postgres_fdw.c`](../files/contrib/postgres_fdw/postgres_fdw.c.md) |
| [`contrib/postgres_fdw/postgres_fdw.h`](../files/contrib/postgres_fdw/postgres_fdw.h.md) |
| [`contrib/postgres_fdw/shippable.c`](../files/contrib/postgres_fdw/shippable.c.md) |

<!-- /files-owned:auto -->

## Cross-references

- `.claude/skills/access-method-apis/SKILL.md` — sibling tableam side (heap is in-tree; FDW is the pluggable counterpart).
- `.claude/skills/executor-and-planner/SKILL.md` — `Path` / `RelOptInfo` lifecycle, `add_path`, `createplan.c` interaction with the `FdwRoutine` callbacks.
- `.claude/skills/parser-and-nodes/SKILL.md` — `Query` / `RangeTblEntry` shape that the deparser consumes.
- `.claude/skills/error-handling/SKILL.md` — libpq errors → `ereport(ERROR, ...)` translation.
- `.claude/skills/bgworker-and-extensions/SKILL.md` — extension `_PG_init` registration shape.
- `knowledge/subsystems/foreign.md` — in-core FDW dispatch + catalog accessors.
- `doc/src/sgml/postgres-fdw.sgml` — user-facing reference.
