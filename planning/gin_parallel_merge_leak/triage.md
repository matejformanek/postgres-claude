# Phase 1 triage — gin_parallel_merge_leak

## Target selection

**Chosen:** `1681a70df3d68b6f9dc82645f97f8d4668edc42f` — Vinod
Sridharan's fix for `_gin_parallel_merge` PortalContext leak
(Tomas Vondra reviewer + committer, 2025-05-02).

## Why this target (post-5-run trilogy)

Two explicit criteria from the 2026-07-13 five-run retro's
"recommended next runs" section:

1. **A subsystem not yet probed by the calibration.** The 5 prior
   runs hit utils/adt, utils/activity, executor, contrib/postgres_fdw,
   and replication/pgoutput. **GIN parallel index build** is a
   fresh subsystem — access/gin and the parallel-index-build
   subsystem specifically.

2. **A fix whose upstream shape is NOT callback-based.** After 3
   consecutive callback-heavy runs (#3 nodesubplan reset,
   #4 fdw_directmodify callback, #5 pgoutput_uaf callback), the
   calibration risks over-fitting L6+L7 to callback patterns.
   Vinod's fix is documented in the commit message as
   "calling ginEntryInsert() in a temporary memory context,
   reset after each insert" — a **per-loop MemoryContextReset**
   pattern, not a callback. Neither L6 approach E nor L7 should
   fire on this shape.

## Comparison against 5 prior calibration wins

|                       | jsonpath | pgstat | nodesubplan | fdw_directmodify | pgoutput_uaf | **gin_parallel_merge** |
|-----------------------|----------|--------|-------------|------------------|--------------|------------------------|
| Subsystem             | utils/adt | utils/activity | executor | contrib/postgres_fdw | replication/pgoutput | **access/gin (parallel)** |
| Bug shape             | transient-lifetime | redundant init | ownership boundary | PG_TRY-not-enough | UAF on retry | **PortalContext accumulator** |
| Fix approach          | struct + Free | delete init | reset in loop | reset callback | reset callback | **short-lived cxt + reset** |
| Diff size             | +362/-233 | -2 | +33/-43 | +35/-27 | +24/-5 | **+12/-0 (predicted)** |
| Signal shape          | RSS climb | per-worker cumulative | per-hash-probe | libpq malloc | UAF | **RSS during CREATE INDEX** |
| L6 approach-E trigger | n/a       | n/a    | fires        | fires            | fires        | **should NOT fire**    |
| L7 callback-detail    | n/a       | n/a    | n/a          | fires            | fires        | **should NOT fire**    |

Novelty:
1. First access/gin target.
2. First parallel-index-build target.
3. First target where **the fix is a pure `MemoryContext` reset
   loop**, not a callback. Tests whether the trilogy's
   codifications correctly IGNORE inappropriate approach-E /
   L7 triggers.
4. Author diversity: Vinod Sridharan (Alibaba? Meta?) — new
   author to the calibration corpus.

## Reproducer recipe (validated in baseline.md)

```sql
SET max_parallel_maintenance_workers = 4;
SET maintenance_work_mem = '64MB';
CREATE TABLE t (id int, keys text[]);
INSERT INTO t
  SELECT g, array[
      repeat(md5(g::text), 32),
      repeat(md5((g+1)::text), 32),
      repeat(md5((g+2)::text), 32)]
  FROM generate_series(1, 1000000) g;
CREATE INDEX t_keys_gin ON t USING gin (keys);
```

Signal: RSS climbs on parent pin during the leader-side merge
phase; flat on post-fix.

## Blast-radius estimate

- **Direct edits:** `src/backend/access/gin/gininsert.c` —
  `_gin_parallel_merge` function only (parent-pin lines
  1613-1756). 3 `ginEntryInsert` call sites at lines 1688, 1714,
  1738.
- **Callers of the modified API:** none (this function is one of
  the two entry points from `ginbuild`; the other is the serial
  path).
- **Sister leaks:** commit message notes "Other ginEntryInsert()
  callers do this too, except that the context is reset after
  batches of inserts" — implying the serial `ginbuild` path
  already has some form of context reset, just less frequent.
  Out of scope this run.
- **On-disk / catalog / WAL / concurrency:** none — pure build
  memory management.

## Phase 2 handoff

- Read `baseline.md` for the semantic bug etiology.
- BLIND CONSTRAINT: do NOT read `1681a70df3d68` diff or the
  discussion thread.  You may read the parent-pin source freely.
- Look at the OTHER `ginEntryInsert` callers in `gininsert.c`
  (lines 468, 734, 819) — the commit message says they already
  use a memory-context reset pattern, so that's the existing
  idiom.
- L6 approach-E should NOT fire (this fix isn't a control-flow
  restructure).
- L7 sub-block should NOT fire (this fix isn't callback-based).
- L5 storage-representation may fire lightly (the "storage" here
  is the memory context — reset-in-loop vs long-lived).
- F30 grep-pass over ownership of allocations inside
  `ginEntryInsert`.
- F31 reproducer-shape verification — CREATE INDEX with GIN +
  parallel workers must actually take the `_gin_parallel_merge`
  path (rather than the serial path).  Parent pin needs
  `max_parallel_maintenance_workers > 0` AND a table big enough
  to trigger parallel.

## Phase 1 exit condition — MET

- Target picked with explicit criteria from the 5-run retro.
- Reproducer sequence carried from baseline.
- Blast radius mapped.
- Predictions filed: L6/L7 should NOT fire; the fix should be
  ~10-15 lines of context creation + reset-in-loop; total diff
  under 20 lines.
