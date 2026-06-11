# Issues — `src/include/partitioning/`

Per-subdirectory issue register for partition bounds, pruning, and
descriptor headers.

**Parent docs:** `knowledge/files/src/include/partitioning/*.h.md`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/partitioning/partbounds.h:87-89 | undocumented-invariant | likely | `interleaved_parts` is conservative ("proof of NOT interleaved"); a future patch reading it as proof OF interleaved would introduce correctness bugs | open | files/.../partbounds.h.md |
| 2026-06-11 | src/include/partitioning/partbounds.h:107-108 | doc-drift | nit | `partition_bounds_create(...,**mapping)` — caller-allocation contract for mapping out-param not in header | open | files/.../partbounds.h.md |
| 2026-06-11 | src/include/partitioning/partbounds.h:58-63 | question | nit | HASH `nindexes <= INT_MAX` upper bound not stated; pathological modulus stack could overflow | open | files/.../partbounds.h.md |
| 2026-06-11 | src/include/partitioning/partbounds.h:127-129 | question | nit | `check_default_partition_contents` scan cost on ATTACH not flagged for huge DEFAULT partitions | open | files/.../partbounds.h.md |
| 2026-06-11 | src/include/partitioning/partprune.h:51 | undocumented-invariant | nit | `PartitionPruneContext.strategy` stored as `char` while underlying enum is wider | open | files/.../partprune.h.md |
| 2026-06-11 | src/include/partitioning/partprune.h:64-71 | undocumented-invariant | likely | `PruneCxtStateIdx` layout is load-bearing; many call sites assume `partnatts*step+key` math | open | files/.../partprune.h.md |
| 2026-06-11 | src/include/partitioning/partprune.h:45-47 | doc-drift | nit | `exprstates` allocation tied to `planstate != NULL` but not struct-enforced | open | files/.../partprune.h.md |
| 2026-06-11 | src/include/partitioning/partdesc.h:46-52 | question | maybe | `last_found_*` cache mutates on lookup; concurrent same-backend lookups (nested PL) race | open | files/.../partdesc.h.md |
| 2026-06-11 | src/include/partitioning/partdesc.h:23-27 | question | nit | omit_detached path rebuilds afresh per snapshot; no upper bound on rebuild frequency in DETACH-heavy workloads | open | files/.../partdesc.h.md |
| 2026-06-11 | src/include/partitioning/partdesc.h:69-71 | undocumented-invariant | likely | `PartitionDirectory` pinning contract not advertised; callers tend to use `RelationGetPartitionDesc` directly | open | files/.../partdesc.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- `partdefs.h` is intentionally minimal (forward typedefs only) —
  no issues filed.
- The `interleaved_parts` "conservative-only" invariant is the
  most reviewer-trap-prone bit; a planner patch that turns it
  around could regress LIST-with-DEFAULT pruning.
- `PartitionPruneContext` is structurally tied across plan-time
  (NULL planstate) and exec-time (non-NULL) — patches that change
  the lifetime would need to audit both paths.
