# Phase 0 baseline — nodesubplan_leak

**Target:** upstream commit `abdeacdb0920d94dec7500d09f6f29fbb2f6310d`
"Fix memory leakage in nodeSubplan.c." (Haiyang Li, reviewed by Tom
Lane, 2025-09-10, Bug #19040, backpatched-through PG13).

**Parent pin (harness base):** `9016fa7e3bc` (meson numeric.c
change).  Contains the leak-introducing commit `bf6c614a2f2`
("Do execGrouping.c via expression eval machinery, take two.") as
ancestor — verified.

**Worktree:** `postgresql-dev-feature-nodesubplan-leak` on branch
`feature_nodesubplan_leak`.

**Build:** cassert + debug, meson build-debug, installed to
`install-debug/`.

## Reproducer

```sql
-- Table with TOAST'd unique 6.4 KB text keys
CREATE TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe
  SELECT g, repeat(md5(g::text), 200)
  FROM generate_series(1, 500) g;

-- Outer table with 2M rows and repeated keys (matches ~500 buckets)
CREATE TABLE t_outer (id int, key text);
INSERT INTO t_outer
  SELECT g, repeat(md5((g % 500)::text), 200)
  FROM generate_series(1, 2000000) g;
ANALYZE;

-- Force serial execution + hashed SubPlan shape
SET max_parallel_workers_per_gather = 0;

-- The reproducer
--   The '(id < 0) OR ...' pattern blocks planner pull-up and produces
--   a 'hashed SubPlan 1' probed per outer row.
SELECT count(*) FROM t_outer o
WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
```

Verified plan shape (on parent pin `9016fa7e3bc`):

```
 Aggregate
   ->  Seq Scan on t_outer o
         Filter: ((id < 0) OR (ANY (key = (hashed SubPlan 1).col1)))
         SubPlan 1
           ->  Seq Scan on t_probe
```

## Leak signal on parent pin

Query is **query-lifespan** — memory grows during the query and is
released at query end (surrounding `ExecutorState` context deletion).
Not visible across queries under `pg_backend_memory_contexts`
snapshots; only visible while the query runs.

Backend RSS over the ~5-second query, sampled via `ps -o rss=` while
the backend is `active`:

| t          | RSS   |
|-----------:|------:|
| ~1.5 s     |  32 MB |
| ~3.5 s     |  48 MB |
| ~6.5 s     |  70 MB |

That is **~15 MB/s of RSS growth during the query**, corresponding
to ~40 bytes per hash probe (2M rows / 5 s ≈ 400 k probes/s).

The named contexts `Subplan HashTable Context` (65 KB) and
`Subplan HashTable Temp Context` (4 KB) stay **flat** in size across
`pg_log_backend_memory_contexts()` dumps — the growing allocation
lives in the `CurrentMemoryContext` at hash-lookup time and is not
attributable to any single stable-named context in the dump.  That
matches the commit-message analysis: the leak is per-probe temporary
allocations made by hash functions (de-toast copies etc.) that
should have been released via a `MemoryContextReset` on a tempcxt
the callers are responsible for holding.

Post-query RSS drops back toward pre-query levels once the executor
state context is torn down.

## What's expected on the fix

Upstream `abdeacdb092` moves the `MemoryContextReset` calls into
`ExecHashSubPlan` and `buildSubPlanHash`, plus documents the new
"caller resets tempcxt" API contract in `execGrouping.c`.  Expected
outcome:

- RSS stays flat at ~32 MB throughout the query.
- Wall time comparable (the fix does not change algorithmic
  complexity — the reproducer is still O(outer × inner) hash ops).

## Phase 0 exit condition — MET

- Reproducer exists.
- Reproducer verified to show unbounded per-query RSS growth on the
  parent pin.
- Signal magnitude (~38 MB over 5 s / ~40 B per probe) is large
  enough to compare pre-fix vs post-fix trivially with `ps -o rss`.
- Both `Subplan HashTable Context` and `Subplan HashTable Temp
  Context` show up in `pg_backend_memory_contexts` output, giving a
  named handle for later mid-query state inspection.

## Notes on reproducer construction

The reproducer needed three non-obvious tricks to reach the "hashed
SubPlan" shape:

1. **`OR (id < 0)`** — the LHS keeps the planner from pulling the
   IN-subquery up into a `Hash Semi Join`; the always-false LHS
   ensures the RHS is always evaluated.
2. **`SET max_parallel_workers_per_gather = 0`** — otherwise the
   plan is a parallel `Gather + Partial Aggregate` and per-worker
   RSS is invisible to the leader's `ps`.
3. **`STORAGE EXTERNAL` + wide `repeat(...)` payloads** — inline
   varlena hashes don't visibly leak (short strings hit
   fast-paths that don't allocate); forcing TOAST amplifies
   per-probe allocation by ~6 KB, though observed per-probe leak is
   only ~40 B so this may not be strictly required — the leak
   applies to ALL hash-function tempcxt usage, not just de-toasting.

## F-finding candidate

**F31** — reproducer construction from a leak-fix commit message
alone can require multiple iterations to find the shape the planner
actually picks.  For the trilogy, "the commit message names A shape,
but you must EXPLAIN it to confirm the planner picks the shape you
expect" needs to be an explicit Phase 0 step in
`knowledge/scenarios/fix-memory-leak.md`.  Adds ~15-30 min but
avoids the surprise-branch pattern seen in this run (three failed
EXPLAINs before landing the hashed-SubPlan shape).
