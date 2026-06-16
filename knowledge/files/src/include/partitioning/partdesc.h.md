# `src/include/partitioning/partdesc.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~75
- **Source:** `source/src/include/partitioning/partdesc.h`

`PartitionDesc` — runtime descriptor of a partitioned table's
partitions. Cached on `Relation` (relcache) for the common case
"all-partitions descriptor"; rebuilt afresh for "omit detached"
because the visibility of detached partitions is snapshot-dependent
and not cache-friendly. [from-comment]

## API / declarations

### PartitionDescData

```
{
  int                nparts;
  bool               detached_exist;   /* are any detached? */
  Oid               *oids;             /* nparts, in bound order */
  bool              *is_leaf;          /* per OID */
  PartitionBoundInfo boundinfo;

  /* Lookup-caching for get_partition_for_tuple */
  int last_found_datum_index;   /* -1 if none */
  int last_found_part_index;
  int last_found_count;         /* LIST: run length of equality;
                                   RANGE: run length of falls-in-range */
}
```

### Entry points

- `RelationGetPartitionDesc(rel, omit_detached)` — main accessor.
  When `omit_detached = true` we may either reuse the cached
  all-partitions descriptor (if `detached_exist == false`) or build
  a fresh one filtered by snapshot. [from-comment]
- `CreatePartitionDirectory(mcxt, omit_detached)` /
  `PartitionDirectoryLookup(pdir, rel)` /
  `DestroyPartitionDirectory(pdir)` — pin-management helper used
  during a planner/executor pass to keep PartitionDescs alive across
  potential invalidations.
- `get_default_oid_from_partdesc(partdesc)` — returns the DEFAULT
  partition OID (or InvalidOid).

## Notable invariants / details

- "The reason for this is that the set of detached partitions that
  are visible to each caller depends on the snapshot it has, so it's
  pretty much impossible to evict a descriptor from cache at the
  right time." — explains why omit_detached path bypasses the cache
  when `detached_exist`. [from-comment]
- `last_found_*` is per-PartitionDesc cache for sequential-tuple-
  routing locality (e.g. COPY with sorted input). Not thread-safe;
  fine because PartitionDesc is per-backend. [from-comment]
- `is_leaf[]` lets the executor tell sub-partitioned tables apart
  from leaf partitions without re-resolving `pg_class.relkind` each
  time.

## Potential issues

- `last_found_*` mutation happens on lookup — a concurrent
  same-relation lookup from two execution contexts in the same
  backend (e.g. nested PL functions) would race-update the cache.
  [ISSUE-question: is concurrent same-backend access safe? (maybe)]
- The "fresh build per snapshot" path for omit_detached has no
  upper bound on rebuild frequency — pathological repeated calls
  during a DETACH-heavy workload could be costly.
  [ISSUE-question: rebuild cost when detached_exist (nit)]
- `PartitionDirectory` is the only documented way to pin a
  PartitionDesc across an invalidation; new callers tend to use
  `RelationGetPartitionDesc` directly and miss the pinning
  contract. [ISSUE-undocumented-invariant: PartitionDirectory pin
  contract (likely)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-partitioning`](../../../../issues/include-partitioning.md)
<!-- issues:auto:end -->
