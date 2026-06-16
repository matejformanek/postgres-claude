# Iteration 1 — Summary

**Skill**: `psql`
**Date**: 2026-06-16
**Method**: single-context, no subagents

## Prompts evaluated

1. Watch a backend's memory-context tree grow + snapshot ANOTHER
   backend's contexts into the server log.
2. Capture a backend PID for lldb without the query racing to finish.
3. Force a hash join, EXPLAIN (ANALYZE, BUFFERS, WAL), revert without
   restart.

## Scores

| Cohort | Passed / Total | Pass rate |
|---|---|---|
| with_skill | 28 / 29 | 0.966 |
| baseline   | 10 / 29 | 0.345 |

Skill delta: **+0.621** (18 additional assertions out of 29).

## What the skill clearly helped with

- The dev-cluster connection idiom (`psql -h /tmp -d postgres`) — every
  baseline answer either guessed `-d postgres` or asked the user.
- The `$USER` superuser gotcha (no literal `postgres` role).
- The `PGAPPNAME=hold` + `pg_sleep` + `application_name='hold'` lookup
  recipe for race-safe lldb attach.
- `/pg-attach` as the project's lldb wrapper (with `errstart` /
  `MemoryContextStats` breakpoints pre-set).
- Full `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)` form.
- Session-vs-system GUC change machinery (`SET` / `RESET` vs
  `ALTER SYSTEM SET` + `pg_reload_conf`).
- The `dev/data-debug/server.log` path for `pg_log_backend_memory_contexts`
  output (or `/pg-tail-log`).

## Where baseline kept up

- Knowledge of `pg_log_backend_memory_contexts(pid)` and where it sends
  output.
- `SET enable_nestloop = off` as a hash-join-forcing knob.
- `pg_sleep` for holding a session open.

## Bug found in SKILL.md

The query at lines 98-100 references column `parent` which does NOT
exist in `pg_backend_memory_contexts`. Verified schema (from
`source/src/include/catalog/pg_proc.dat:8709-8715`): `name, ident, type,
level, path, total_bytes, total_nblocks, free_bytes, free_chunks,
used_bytes`. Replace `parent` with `path` (or `type`).

## One with_skill miss

The skill doesn't surface the per-connection-fork model inline — only
via cross-ref to `knowledge/architecture/process-model.md`. One sentence
under §"Capturing a backend PID" closes this.

## Recommended edits (see proposed-edits.md)

1. **HIGH**: fix the `parent` column bug (lines 98-100) — current query errors.
2. HIGH: name the managed-PG vs dev-cluster trap inline in §Common gotchas.
3. MED: inline the 5-line held-PID handoff recipe (don't only cross-ref).
4. MED: name MessageContext's role in the leak-workflow explicitly.
5. MED: per-connection-fork note in §"Capturing a backend PID".
6. LOW: clarify `enable_*` is "discourage not disable".

## Decision

Skill is strong but ships with a copy-paste error in the
memory-contexts query. Edits #1, #2, #3, #5 should all land before
iteration 2.
