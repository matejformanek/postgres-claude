# matview.c

- **Source path:** `source/src/backend/commands/matview.c`
- **Lines:** 969
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Materialised view support — `REFRESH MATERIALIZED VIEW [CONCURRENTLY]`, plus the bookkeeping that marks a matview as populated/not. Note the include of `commands/repack.h` — REFRESH non-concurrent uses the REPACK swap-relfilenodes machinery.

## Public surface

- `ExecRefreshMatView` — REFRESH MATERIALIZED VIEW. Non-concurrent: re-runs the matview's query into a transient heap, then swaps relfilenodes (via `repack.c`'s `finish_heap_swap`). Concurrent: uses a "delta computation" via SQL — compares old vs new contents using the matview's unique index and issues per-row INSERT/UPDATE/DELETE on the old heap.
- `RefreshMatViewByOid` — internal entry; also used by CREATE MATERIALIZED VIEW WITH DATA (which after creating the empty matview refreshes it once).
- `SetMatViewPopulatedState` — flip `pg_class.relispopulated` (REFRESH … WITH NO DATA sets it to false; subsequent SELECT on an unpopulated matview errors).

## CONCURRENTLY rules

`REFRESH MATERIALIZED VIEW CONCURRENTLY` requires the matview to have a UNIQUE index covering ALL rows (no WHERE on the index). The delta-computation builds a temporary table of (operation, key, new-values) and applies it row-by-row, so concurrent SELECTs see a continuously consistent matview throughout — at the cost of being O(N) writes even if the actual change is tiny.

## Confidence tag tally

`[verified-by-code]=3 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
