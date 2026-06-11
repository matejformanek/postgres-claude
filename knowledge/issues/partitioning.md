# Issues — `partitioning`

Per-subsystem issue register for `src/backend/partitioning/`. See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem docs:**
- (none yet — `knowledge/subsystems/partitioning.md` not authored)
- `knowledge/files/src/backend/partitioning/partbounds.c.md`
- `knowledge/files/src/backend/partitioning/partdesc.c.md`
- `knowledge/files/src/backend/partitioning/partprune.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | partitioning/partprune.c:3713 | undocumented-invariant | maybe | `match_boolean_partition_clause` checks only built-in bool opfamily; assumes "partitioning AMs are built-in", will silently miss user-defined opfamilies if that ever changes | open | knowledge/files/src/backend/partitioning/partprune.c.md §Potential issues |
| 2026-06-11 | partitioning/partprune.c:3797 | undocumented-invariant | likely | Per-tuple memory-context reset contract for partkey_datum_from_expr lives in comment only and crosses into execPartition.c; not asserted | open | knowledge/files/src/backend/partitioning/partprune.c.md §Potential issues |
| 2026-06-11 | partitioning/partprune.c | question | maybe | 3830-line file with no module-level invariant doc; best architectural comment is on a static helper (`gen_partprune_steps_internal` L952) | open | knowledge/files/src/backend/partitioning/partprune.c.md §Potential issues |
| 2026-06-11 | partitioning/partprune.c:3429 | style | nit | Cast `(PartitionPruneStepOp *) lfirst(lc)` performed before the `IsA` tag check in `get_partkey_exec_paramids`; safe by node-layout convention | open | knowledge/files/src/backend/partitioning/partprune.c.md §Potential issues |
| 2026-06-11 | partitioning/partbounds.c | doc-drift | maybe | 6025-line file with no top-of-file architectural overview; mixes catalog canonicalisation, qsort comparators, partition-wise-join merging, MERGE/SPLIT validation, predicate generation | open | knowledge/files/src/backend/partitioning/partbounds.c.md §Potential issues |
| 2026-06-11 | partitioning/partbounds.c:3407 | stale-todo | nit | `get_hash_partition_greatest_modulus` is documented as "no longer used in the core code, but we keep it around in case external modules are using it" | open | knowledge/files/src/backend/partitioning/partbounds.c.md §Potential issues |
| 2026-06-11 | partitioning/partbounds.c:5057-5500 | undocumented-invariant | likely | MERGE/SPLIT helpers (PG17+) depend on canonical-bounds-ordering invariant being eager; if relaxed to lazy, they silently produce wrong answers | open | knowledge/files/src/backend/partitioning/partbounds.c.md §Potential issues |
| 2026-06-11 | partitioning/partbounds.c:1192-2470 | question | maybe | Partition-wise-join + FULL OUTER JOIN + (default + null partitions on both sides) lacks property-test coverage; helpers exist but interaction matrix is large | open | knowledge/files/src/backend/partitioning/partbounds.c.md §Potential issues |
| 2026-06-11 | partitioning/partdesc.c:153 | undocumented-invariant | maybe | Single `retried` flag governs the entire retry path; one-retry budget depends on DETACH CONCURRENTLY blocking behind the active snapshot | open | knowledge/files/src/backend/partitioning/partdesc.c.md §Potential issues |
| 2026-06-11 | partitioning/partdesc.c:376 | correctness | nit | Tiny window between `MemoryContextSetParent(new_pdcxt, CacheMemoryContext)` and storing into relcache; would be cleaner in a critical section | open | knowledge/files/src/backend/partitioning/partdesc.c.md §Potential issues |
| 2026-06-11 | partitioning/partdesc.c:381 | stale-todo | nit | Known kluge ("preserve while not leaking it by reattaching it as a child context of the new one") — long-standing, deliberate, acknowledged | open | knowledge/files/src/backend/partitioning/partdesc.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **partprune.c is the highest-complexity file in this subsystem**
  (3830 lines). Has three pruning targets (PLANNER / INITIAL /
  EXEC), three partition strategies (HASH / LIST / RANGE),
  multi-column-prefix matching, run-time param plumbing, and
  cross-file invariants with execPartition.c. New behaviour
  additions should come with a dedicated test pass in
  `partition_prune.sql`.
- **partbounds.c is the biggest** (6025 lines) but the complexity
  is more divisible — most callers touch only one or two of the
  five major sections. The partition-wise-join merging code
  (~1300 lines, lines 1100-2470) is functionally the densest.
- **partdesc.c is small but cache-critical.** The dual partdesc
  (`rd_partdesc` + `rd_partdesc_nodetached`) with `xmin`
  revalidation against MVCC snapshot is the cleverest piece of
  the file and the one most likely to harbour future bugs around
  DETACH CONCURRENTLY semantics.
- All three files share an unwritten invariant: **bounds are
  canonical and immutable once built**, with `partition_bounds_copy`
  the only way to get a long-lived copy. A subsystem doc making
  this explicit would prevent a class of future-maintainer
  mistakes.
