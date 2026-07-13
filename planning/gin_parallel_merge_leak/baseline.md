# Phase 0 baseline — gin_parallel_merge_leak

**Target:** `1681a70df3d68b6f9dc82645f97f8d4668edc42f` — "Fix
memory leak in `_gin_parallel_merge`" (Vinod Sridharan author,
Tomas Vondra reviewer + committer, 2025-05-02).

**Parent pin:** `e83a8ae4472`.
**Worktree:** `postgresql-dev-feature-gin-parallel-merge-leak`.

## Bug shape (from commit summary — the only body text we've read)

Parallel GIN index build's leader phase runs `_gin_parallel_merge`
which calls `ginEntryInsert()` for each key extracted from the
parallel workers' sorted output.  `ginEntryInsert` may allocate
transient memory (new leaf tuple, split-page metadata, etc.).
Under the parent pin these allocations land in `PortalContext`
(the surrounding `CREATE INDEX` portal's context) and are freed
only when the entire index build ends.

For a normal GIN opclass the per-insert allocation is small
(bytes-to-KBs) — leak amount = O(index tuples).  For **custom
opclasses with large keys** (jsonb path queries, text arrays with
long strings, etc.) the leak scales with key size × index tuples,
causing OOM on real workloads.

## Signal shape — RSS climb during CREATE INDEX

Not per-query — per-CREATE-INDEX.  Signal amplification:

1. A table with a wide `text[]` column (or similar) containing
   many distinct keys.
2. GIN index on that column.
3. Force parallel index build (`SET
   max_parallel_maintenance_workers = 4`).
4. Watch RSS climb during CREATE INDEX.  Under the parent pin,
   RSS grows unboundedly with the index size × key width.

## Reproducer draft

```sql
-- Ensure parallel index build is available
SET max_parallel_maintenance_workers = 4;
SET maintenance_work_mem = '64MB';

-- 1M rows with wide text keys
DROP TABLE IF EXISTS t;
CREATE TABLE t (id int, keys text[]);
INSERT INTO t
  SELECT g, array[
      repeat(md5(g::text), 32),        -- ~1KB key
      repeat(md5((g+1)::text), 32),
      repeat(md5((g+2)::text), 32)
   ]
  FROM generate_series(1, 1000000) g;

-- Build the GIN index while poll backend RSS
CREATE INDEX t_keys_gin ON t USING gin (keys);
```

Signal: on parent pin the leader backend's RSS climbs steadily
during the merge phase.  Post-fix RSS stays flat.

Signal magnitude expectation: with 1 M × ~3 KB keys ≈ 3 GB
worth of key data, leak may be visible at 100 MB+ during a
30-60 s build phase.  Exact magnitude depends on how much
`ginEntryInsert` allocates per leaf-tuple write.

## Phase 0.5 — target-suite health check (F37)

Target-suite for GIN: no dedicated regress file for parallel
GIN specifically; `src/test/regress/sql/gin.sql` covers GIN
basics.  Isolation suite exercises parallel workers.  Neither
suite has a build-phase memory-canary style test.

R13 gate for this run: core `regress` + `isolation` (executor +
parallel tier) plus the manual RSS-during-CREATE-INDEX canary
from above.

## Phase 0 exit condition — MET

- Bug etiology derived from parent-pin source alone.
- Reproducer sequence documented.
- Signal magnitude expectation: 100 MB+ during multi-minute
  parallel GIN build with wide keys.
- Target-suite: no target-specific suite; R13 = regress +
  isolation + RSS canary.
