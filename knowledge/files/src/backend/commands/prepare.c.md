# prepare.c

- **Source path:** `source/src/backend/commands/prepare.c`
- **Lines:** 762
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Preparable SQL statements via PREPARE, EXECUTE and DEALLOCATE. This module also implements storage of prepared statements that are accessed via the extended FE/BE query protocol." [from-comment, prepare.c:3-7]

## Public surface

- `PrepareQuery` — SQL-level PREPARE. Wraps the query in a `CachedPlanSource` (from utils/cache/plancache.c) and stores it in the per-session prepared-statement hashtable keyed by name.
- `ExecuteQuery` — EXECUTE; looks up the CachedPlanSource, builds a CachedPlan (using `GetCachedPlan` which picks generic-vs-custom based on the heuristic), runs it through the executor.
- `DeallocateQuery`, `DeallocateAll` — DEALLOCATE; the DISCARD ALL path also calls DeallocateAll.
- `StorePreparedStatement` / `FetchPreparedStatement` / `DropPreparedStatement` — the protocol-level entries used by libpq's `PQprepare`/`PQexecPrepared`.
- `ExplainExecuteQuery` — `EXPLAIN EXECUTE name(args)` plumbing.
- `pg_prepared_statement` — SRF returning all prepared statements in the session.

## Generic-vs-custom plan choice

A prepared statement starts with custom plans (replan with the actual parameter values each EXECUTE) for the first **five** executions. Then it computes the average custom-plan cost and the generic-plan cost; if generic ≤ avg(custom) + planning-savings-estimate, it switches to generic permanently. This decision is in `plancache.c:choose_custom_plan`, but you reach it via this file's `ExecuteQuery`.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
