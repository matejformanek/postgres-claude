# Phase 1 triage — nodesubplan_leak

## Target selection

**Chosen:** upstream commit `abdeacdb0920d94dec7500d09f6f29fbb2f6310d`
*"Fix memory leakage in nodeSubplan.c."*

- **Author:** Haiyang Li \<mohen.lhy@alibaba-inc.com\>
- **Date:** 2025-09-10
- **Committer / reviewer:** Tom Lane
- **Bug:** [#19040](https://postgr.es/m/19040-c9b6073ef814f48c@postgresql.org)
- **Backpatch-through:** PG13
- **Files touched:** `src/backend/executor/nodeSubplan.c`
  (+27 / −43), `src/backend/executor/execGrouping.c` (+6)
- **Fix size:** 33 insertions / 43 deletions in 2 files

## Why this target (vs. the 2 prior calibration wins)

|                       | jsonpath_leak (`5a2043bf713`) | pgstat_progress_leak (`b20c952ce70`) | **nodesubplan_leak (`abdeacdb092`)** |
|-----------------------|-------------------------------|--------------------------------------|--------------------------------------|
| Subsystem             | utils/adt/jsonpath            | utils/activity/pgstat                | **executor / TupleHashTable**         |
| Bug shape             | Transient-lifetime leak       | Redundant double-init                | **Ownership-boundary API change**     |
| Diff size             | +362 / −233 (1 file)          | −2 (1 file)                          | **+33 / −43 (2 files)**               |
| Reproducer in message | Explicit SQL                  | Amplified from Michael's report      | Bug #19040 reference + narrative     |
| Growth shape          | Quadratic in input size       | Per-parallel-worker cumulative       | **Per hash-probe accumulation**       |

**Novelty for the calibration:**

1. **New subsystem** — executor / hash groupings — the prior two hit
   `utils/adt` and `utils/activity`.  Executor internals stress a
   different corpus surface (nodeXxx.c per-shape state machines +
   `execGrouping.c` cross-cutting API).
2. **Mid-range diff size** — 76 lines vs. the 595-line jsonpath fix
   and the 2-line pgstat fix.  Fills the "small refactor" bucket
   the calibration hadn't probed.
3. **API-contract change, not raw pfree.** The fix moves reset
   ownership between `TupleHashTable*` callers and
   `TupleHashTableMatch` — the brainstorm has to consider *where*
   the reset belongs, not just *whether* to add it.  Design surface.
4. **Different author + reviewer pair.** Haiyang Li (Alibaba) as
   author, Tom Lane as reviewer, not Tom-as-committer.  Marginal
   diversity signal but real.

## Subsystem mapping

| Layer                     | Files                                           | Prior corpus support                        |
|---------------------------|-------------------------------------------------|---------------------------------------------|
| Subplan executor          | `src/backend/executor/nodeSubplan.c`            | `knowledge/subsystems/optimizer.md` §Subplan (light) |
| Tuple-hash-table core     | `src/backend/executor/execGrouping.c`           | `knowledge/idioms/tuple-hash-table.md` (if present) |
| Memory-context idioms     | —                                               | `knowledge/idioms/memory-contexts.md` (rich) |
| Hash-agg / setop callers  | `src/backend/executor/nodeAgg.c`, `nodeSetOp.c` | not in scope this phase                     |

## Blast-radius estimate

- **Direct edits:** `nodeSubplan.c` (2 functions: `ExecHashSubPlan` +
  `buildSubPlanHash`), `execGrouping.c` (1-2 comments / docs).
- **Callers of the modified API** (`TupleHashTable*` routines
  in `execGrouping.h`): `nodeAgg.c`, `nodeSetOp.c`,
  `nodeRecursiveunion.c`.  These are OUT of scope but the plan §7
  must verify they already reset the tempcxt so the new API
  contract isn't violated.
- **On-disk / catalog / WAL:** none — pure executor behavior.
- **Concurrency:** none — per-backend, in-memory.

## Reproducer recipe (validated in Phase 0 baseline.md)

```sql
-- Force STORAGE EXTERNAL for wide keys → per-probe detoast allocations
CREATE TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe SELECT g, repeat(md5(g::text), 200) FROM generate_series(1, 500) g;

CREATE TABLE t_outer (id int, key text);
INSERT INTO t_outer SELECT g, repeat(md5((g % 500)::text), 200) FROM generate_series(1, 2000000) g;
ANALYZE;

-- '(id < 0) OR ...' pattern blocks Hash-Semi-Join pull-up → hashed SubPlan
SET max_parallel_workers_per_gather = 0;
SELECT count(*) FROM t_outer o
WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
```

Signal: backend RSS climbs **32 MB → 48 MB → 70 MB over ~5 s**
(~40 B per hash probe × 400 k probes/s).  Released at query end.

## Ranked runners-up (kept for reference)

Position 2 — `1681a70df3d68` (Tomas Vondra, 2025-05-02, `_gin_parallel_merge`).
GIN parallel index build; +12 lines; opclass-with-large-keys
reproducer.  Passed over because the diff is too close to the 2-line
`pgstat_progress_leak` shape.

Position 3 — `f16f5d608ca6` (Jeff Davis, 2026-03-24, `GetSubscription`).
Logical replication per-object memory context refactor.  Passed over
because commit message has **no concrete reproducer** — synthesising
one would waste Phase 0 budget.

## Phase 2 handoff

- Read `baseline.md` for the reproducer + measurement.
- BLIND CONSTRAINT: do NOT read `abdeacdb092` source, commit
  message body beyond the summary line, or the Bug #19040 thread
  during Phases 2-3.
- Enter `pg-feature-brainstorm` next, with the leak evidence as
  input.
- L5 (storage-representation sub-question) and F30 (grep-pass over
  `TupleHashTable*` callers) MUST fire.

## Phase 1 exit condition — MET

- Target picked with explicit reasoning against 2 alternatives.
- Reproducer recipe carried forward from Phase 0.
- Blast radius estimated + corpus support mapped.
- Blind constraint restated for Phase 2.
