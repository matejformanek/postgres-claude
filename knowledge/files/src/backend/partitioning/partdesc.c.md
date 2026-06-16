# `src/backend/partitioning/partdesc.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~508
- **Source:** `source/src/backend/partitioning/partdesc.c`

Builds and caches `PartitionDesc` — the per-relation, sorted,
canonicalised list of child OIDs + bounds — and the
`PartitionDirectory` per-query lookup table that pins identical
descriptors across repeated lookups. Carefully written to be safe
against concurrent `ATTACH PARTITION` / `DETACH CONCURRENTLY`.
[verified-by-code]

## API / entry points

- `RelationGetPartitionDesc(rel, omit_detached)` (line 71) — the
  hot path. Returns a cached `rd_partdesc` if available and either
  no detached partitions exist, the caller is happy to see them,
  or there is no active snapshot. Otherwise tries the
  detached-omitted cache (`rd_partdesc_nodetached`), validating
  via `XidInMVCCSnapshot` on the stored `xmin`. Falls back to
  `RelationBuildPartitionDesc`. [verified-by-code]
- `RelationBuildPartitionDesc(rel, omit_detached)` (line 133,
  static) — read children from `pg_inherits` with
  `find_inheritance_children_extended`, then for each child look up
  `relpartbound` via syscache, falling back to a direct
  `pg_class` scan if the syscache doesn't have it yet, then build
  the `PartitionBoundInfo`. Has a `retry:` label that loops once
  on inconsistent DETACH CONCURRENTLY state.
  [verified-by-code]
- `CreatePartitionDirectory(mcxt, omit_detached)` (line 423) — set
  up the per-portal hash table. [verified-by-code]
- `PartitionDirectoryLookup(pdir, rel)` (line 456) — first lookup
  of a relation in this directory increments the relcache refcount
  and snapshots the partdesc; later lookups return the same one
  even if concurrent DDL would otherwise produce a different
  partdesc. [verified-by-code]
- `DestroyPartitionDirectory(pdir)` (line 484) — drops the held
  refcounts. [verified-by-code]
- `get_default_oid_from_partdesc(partdesc)` (line 501) — convenience
  for the default-partition slot. [verified-by-code]

## Notable invariants / details

- **Two parallel caches:** `rel->rd_partdesc` includes detached
  partitions, `rel->rd_partdesc_nodetached` omits them. The
  no-detached one carries `rd_partdesc_nodetached_xmin` so future
  lookups can revalidate against the caller's snapshot. [from-comment
  L58]
- **DETACH CONCURRENTLY race window:** lines 202-275 carefully
  comment the two failure modes — concurrent ATTACH adding a
  partition whose syscache row hasn't appeared yet, and concurrent
  DETACH having cleared `relpartbound` after we found the OID via
  pg_inherits. Solution is the direct pg_class scan + a one-shot
  retry. The comment justifies why only one retry suffices
  ("only one DETACH CONCURRENTLY session could affect us at a
  time, since each of them would have to wait for the snapshot
  under which this is running"). [from-comment, INV: only one
  retry is sufficient]
- **Memory context dance** (line 318-376): the new partdesc is
  built under `CurTransactionContext` (so an ereport mid-build
  leaks only transient memory), THEN reparented to
  `CacheMemoryContext` once fully valid. Old partdesc context is
  retained as a child of the new one — any code still holding a
  pointer remains valid until the relcache entry's refcount goes
  to zero. [from-comment]
- The default partition's OID is cross-checked against
  `pg_partitioned_table.partdefid` (line 289) — a corrupt catalog
  trips `elog(ERROR, "expected partdefid %u, but got %u")`.
  [verified-by-code]

## Potential issues

- Line 153 — single `retried` flag governs the entire retry path;
  if a hypothetical future change introduced two distinct retry
  reasons, they would share a budget of one. The comment notes
  this is "to avoid possible infinite loops in case of catalog
  corruption", so it is by design — but the design depends on
  external invariants (DETACH CONCURRENTLY snapshot semantics)
  that aren't asserted here. [ISSUE-undocumented-invariant: one
  retry suffices because DETACH CONCURRENTLY blocks behind
  snapshot (maybe)]
- Line 376 — `MemoryContextSetParent(new_pdcxt, CacheMemoryContext)`
  happens before storing into relcache. If the subsequent
  `rd_pdcxt`/`rd_pddcxt` reparenting throws, the new context
  is now in cache but unowned. In practice these are simple
  pointer writes; would still be cleaner with a critical section.
  [ISSUE-correctness: tiny window between reparent and relcache
  store (nit)]
- The "kluge" comment at line 381 ("preserve while not leaking it
  by reattaching it as a child context of the new one") is a known
  oddity — long-standing, deliberate, but acknowledged as a kluge.
  [ISSUE-stale-todo: documented kluge for old-partdesc retention
  (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `partitioning`](../../../../issues/partitioning.md)
<!-- issues:auto:end -->
