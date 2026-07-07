# Partition attach + detach — DDL flow + CONCURRENTLY variants

`ALTER TABLE parent ATTACH PARTITION child` and the reverse
`DETACH PARTITION child` are the DDL primitives that
restructure a partition tree. Both can run under
`AccessExclusiveLock` (default, fast, blocking) or
`CONCURRENTLY` (slower, allows reads + DML). The CONCURRENTLY
variants exist specifically for production schema changes
where blocking is unacceptable, at the cost of two transactions
and a wait-for-active-readers phase.

Anchors:
- `source/src/backend/commands/tablecmds.c:20537` —
  ATExecAttachPartition [verified-by-code]
- `source/src/backend/commands/tablecmds.c:21227` —
  ATExecDetachPartition [verified-by-code]
- `source/src/backend/commands/tablecmds.c:21400` —
  DetachPartitionFinalize [verified-by-code]
- `source/src/backend/commands/tablecmds.c:21734` —
  ATExecDetachPartitionFinalize [verified-by-code]
- `knowledge/idioms/partition-tuple-routing.md` — companion
- `knowledge/idioms/partition-runtime-pruning.md` — companion
- `knowledge/idioms/partition-bound-comparison.md` —
  companion (validation)
- `.claude/skills/catalog-conventions/SKILL.md` — companion

## ATTACH PARTITION — the standard flow

[verified-by-code `tablecmds.c:20537`]

```sql
ALTER TABLE parent ATTACH PARTITION child FOR VALUES IN (1,2,3);
```

`ATExecAttachPartition`:
1. Acquire `AccessExclusiveLock` on parent + child.
2. Validate child relation's structure matches parent
   (column count, types, NOT NULL, etc.).
3. Validate the FOR VALUES bound doesn't overlap with existing
   partitions (via `check_new_partition_bound`).
4. Scan the child's existing rows and verify each one
   satisfies the partition constraint (unless the child has
   a CHECK constraint matching the partition bound).
5. Update `pg_class.relispartition = true` and
   `pg_partitioned_table` bound entries.
6. Invalidate the parent's relcache.

Step 4 is the expensive part — a full scan of the child. PG
17+ adds "ATTACH PARTITION ... WITHOUT VALIDATION" to skip
this if the operator promises matching constraints.

## DETACH PARTITION — the standard flow

[verified-by-code `tablecmds.c:21227`]

```sql
ALTER TABLE parent DETACH PARTITION child;
```

`ATExecDetachPartition`:
1. Acquire `AccessExclusiveLock` on parent + child.
2. Remove the partition-bound entry from
   `pg_partitioned_table`.
3. Update `pg_class.relispartition = false` on the child.
4. Drop any inherited-only constraints (e.g., partition
   default).
5. Invalidate caches.

The child becomes a standalone table after detach. Its data
is preserved.

## ATTACH PARTITION CONCURRENTLY

Not currently supported — listed as a TODO in some discussions.
The complication is acquiring a consistent view of the parent
without an `AccessExclusiveLock`.

## DETACH PARTITION CONCURRENTLY — the two-phase flow

[verified-by-code `tablecmds.c:21400` (DetachPartitionFinalize) +
21734 (ATExecDetachPartitionFinalize)]

```sql
-- Phase 1: mark as detached-pending
ALTER TABLE parent DETACH PARTITION child CONCURRENTLY;
-- (may need to be in its own transaction)

-- Phase 2: finalize after waiters drain
ALTER TABLE parent DETACH PARTITION child FINALIZE;
```

The flow:
1. **Phase 1** — under `ShareUpdateExclusiveLock` (compatible
   with reads + DML):
   - Mark the partition as "detached-pending" in
     `pg_inherits`.
   - Wait for in-progress transactions on the parent to
     finish (so they see consistent state).
   - Commit Phase 1.
2. **Waiting phase** — between Phase 1's commit and Phase 2:
   - Existing transactions see the partition as still
     attached (consistent view).
   - New transactions see it as detached.
   - The operator (or auto-completion) waits for old txns
     to drain.
3. **Phase 2** — `DetachPartitionFinalize`:
   - Now safe to remove from `pg_inherits` + update
     `pg_class.relispartition`.
   - Drop any inherited-only constraints.

If Phase 2 isn't run, the partition stays in detached-pending
state — visible via `SELECT * FROM pg_inherits WHERE inhdetachpending`.

## Why CONCURRENTLY requires two phases

The fundamental challenge: existing transactions might be
holding tuples from the parent and seeing the child. Detaching
under their feet would break consistency. The two-phase
approach gives those transactions a window to finish.

Phase 2 uses `WaitForLockers` to drain old snapshots.

## Validation cost

[per ATExecAttachPartition step 4]

```c
ValidatePartitionConstraints(rel, scanrel);
```

Scans the child relation to verify every row satisfies the
partition bound. For a large child, this can take minutes /
hours. Mitigations:
- Pre-add a CHECK constraint matching the bound; PG sees it
  and skips the scan.
- WITHOUT VALIDATION clause (PG 17+).

## Constraint inheritance

When ATTACH:
- CHECK / NOT NULL constraints on parent become inherited on
  child if not already present.
- Constraints duplicated on parent + child are merged (one
  copy on child marked inherited).

When DETACH:
- Inherited constraints stay on child (no longer marked
  inherited).
- The child's autonomy as a standalone table is restored.

## What you can't do

- DETACH the only partition (would leave parent without any).
- DETACH if the partition has a default-partition relationship
  that would orphan rows.
- ATTACH a child that has overlapping rows with existing
  partitions (validation catches this).

## Common review-time concerns

- **ATExecAttachPartition has full-scan validation** —
  expensive for large partitions; pre-check constraint helps.
- **DETACH CONCURRENTLY is two transactions** — operator
  must run both; in-between state is visible.
- **inhdetachpending = true** flags Phase-1-completed
  partitions.
- **No ATTACH CONCURRENTLY** in current PG.
- **DETACH ... FINALIZE** completes a Phase-1-only operation
  (e.g., after crash).
- **Locking gradient**: ATTACH = AccessExclusiveLock,
  DETACH = AccessExclusiveLock, DETACH CONCURRENTLY =
  ShareUpdateExclusiveLock.

## Invariants

- **[INV-1]** Standard ATTACH/DETACH = AccessExclusiveLock.
- **[INV-2]** ATTACH validates partition-constraint on
  existing rows.
- **[INV-3]** DETACH CONCURRENTLY = 2 phases with drain
  window.
- **[INV-4]** Phase-1-only DETACH leaves
  pg_inherits.inhdetachpending = true.
- **[INV-5]** Partition tree state changes are
  cache-invalidated.

## Useful greps

- ATTACH entry:
  `grep -n 'ATExecAttachPartition' source/src/backend/commands/tablecmds.c | head -5`
- DETACH entry + finalize:
  `grep -n 'ATExecDetachPartition\|DetachPartitionFinalize' source/src/backend/commands/tablecmds.c | head -10`
- Partition-bound validation:
  `grep -n 'ValidatePartitionConstraints\|check_new_partition_bound' source/src/backend | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/tablecmds.c`](../files/src/backend/commands/tablecmds.c.md) | 20537 | ATExecAttachPartition |
| [`src/backend/commands/tablecmds.c`](../files/src/backend/commands/tablecmds.c.md) | 21227 | ATExecDetachPartition |
| [`src/backend/commands/tablecmds.c`](../files/src/backend/commands/tablecmds.c.md) | 21400 | DetachPartitionFinalize |
| [`src/backend/commands/tablecmds.c`](../files/src/backend/commands/tablecmds.c.md) | 21734 | ATExecDetachPartitionFinalize |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/partition-tuple-routing.md` —
  routing uses partition bounds.
- `knowledge/idioms/partition-runtime-pruning.md` —
  pruning uses the same bounds.
- `knowledge/idioms/partition-bound-comparison.md` —
  validation / lookup mechanics.
- `knowledge/idioms/cache-invalidation-registration.md` —
  ATTACH/DETACH triggers inval.
- `knowledge/idioms/cached-plan-invalidation.md` — plans
  referencing the partition tree invalidated.
- `knowledge/data-structures/relfilelocator.md` —
  child has its own relfilenumber.
- `knowledge/subsystems/partitioning.md` — partitioning
  overview.
- `.claude/skills/catalog-conventions/SKILL.md` —
  pg_partitioned_table + pg_inherits.
- `source/src/backend/commands/tablecmds.c:20537` —
  ATTACH entry.
