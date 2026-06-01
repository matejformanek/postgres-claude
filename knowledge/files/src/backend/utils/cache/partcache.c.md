# partcache.c

- **Source path:** `source/src/backend/utils/cache/partcache.c`
- **Lines:** 432
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `partcache.h`, `catalog/partition.h`, `partitioning/partbounds.c`, `relcache.c` (which owns `rd_partkey`, `rd_partdesc`, `rd_partcheck`).

## Purpose

Helpers for partition-related info attached to a relcache entry: partition key (`rd_partkey`), partition descriptor (`rd_partdesc` — managed by `partition.c`), and partition constraint qual (`rd_partcheck`). Lazy: each is built only on first call after a relcache (re)build. [from-comment, partcache.c:3-6]

## Top-of-file comment

> "Support routines for manipulating partition information cached in relcache" [partcache.c:3-5]

## Public surface

- `RelationGetPartitionKey` (51) — return cached `PartitionKey`, building on demand.
- `RelationGetPartitionQual` (277) — return cached partition qual list (for the relation as a partition).
- `get_partition_qual_relid` (299) — SQL-callable convenience returning the qual as an `Expr *` given an oid.
- Static workers: `RelationBuildPartitionKey` (78), `generate_partition_qual` (337).

## Key types / structs

- `PartitionKey` — defined in `partcache.h`; partition strategy, partattrs, partexprs, partcollation, partopclass, partsupfunc.
- The cache fields live on `RelationData`: `rd_partkey`, `rd_partkeycxt`, `rd_partcheck`, `rd_partcheckvalid`, `rd_partcheckcxt`.

## Key invariants and locking

- **Partition keys never change.** "Note: partition keys are not allowed to change after the partitioned rel is created. RelationClearRelation knows this and preserves rd_partkey across relcache rebuilds, as long as the relation is open. Therefore, even though we hand back a direct pointer into the relcache entry, it's safe for callers to continue to use that pointer as long as they hold the relation open." [from-comment, partcache.c:42-48]
- **Two-step memory-context promotion.** `RelationBuildPartitionKey` creates `partkeycxt` as a child of `CurTransactionContext` first, then re-parents to `CacheMemoryContext` only when the whole build succeeded — avoids leaking on ereport. Same pattern as relcache's index-info init. [from-comment, partcache.c:67-75; verified-by-code]
- **Partition qual cached on the partition rel** (not on parent). `generate_partition_qual` walks UP the partition tree, AND-ing every level's `relpartbound`. Guarded by `check_stack_depth()` to defend against pathological depth. Result is copied into `rd_partcheckcxt` (created lazily); a copy is returned. [verified-by-code, partcache.c:337-432]
- **Parent lock during qual build.** "Grab at least an AccessShareLock on the parent table. Must do this even if the partition has been partially detached, because transactions concurrent with the detach might still be trying to use a partition descriptor that includes it." [from-comment, partcache.c:355-360]
- `rd_partdesc` is NOT built here — it's built in `catalog/partition.c` (`RelationGetPartitionDesc`). This file only owns the key and the qual.

## Functions of note

1. **`RelationGetPartitionKey`** (51) — null-fast path for non-partitioned rels; else lazy build into `rd_partkeycxt`.
2. **`RelationBuildPartitionKey`** (78) — fetches `PARTRELID` syscache row; populates `PartitionKey` fields; resolves opclass support procs via lsyscache; reparents context at the end.
3. **`generate_partition_qual`** (337) — fetches `pg_class.relpartbound`, calls `get_qual_from_partbound`, recursively AND-s with parent qual via another `generate_partition_qual` call (after taking a lock on the parent). Memoized in `rd_partcheck` with `rd_partcheckvalid` flag.

## Cross-references

- **Called by**: optimizer (`get_relation_info` for partition pruning), executor (`ExecInitPartitionInfo`), tuple-routing in `execPartition.c`, DDL paths in `commands/tablecmds.c`, `RelationGetPartitionDesc` in catalog/partition.c.
- **Calls into**: syscache (`PARTRELID`, `RELOID`), lsyscache (opclass support procs), `partbounds.c` (`get_qual_from_partbound`), relcache (relation_open for parent).

## Open questions

- The exact moment `rd_partkey` is invalidated — since "partition keys never change", presumably only on full relcache drop. Confirm via `RelationDestroyRelation`/`RelationClearRelation`. [unverified]
- `rd_partcheckvalid` reset semantics on detach/attach partition operations. [unverified]

## Confidence tag tally

verified-by-code: 3 — from-comment: 4 — from-readme: 0 — inferred: 0 — unverified: 2
