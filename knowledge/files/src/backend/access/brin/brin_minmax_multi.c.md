# brin_minmax_multi.c

- **Source path:** `source/src/backend/access/brin/brin_minmax_multi.c` (3135 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

**Multi-minmax** opclass: summary is a *set of disjoint intervals* instead of a single `(min,max)`. Handles outliers gracefully: instead of one page-range becoming `[1000, 1000000]` after a single outlier, it becomes `[1000, 2000] ∪ [1000000, 1000000]`, retaining selectivity for keys in the gap. [from-comment, brin_minmax_multi.c:9-32]

## Key concepts

- **Values per range** (default 32, settable via `values_per_range` reloption) is the hard cap; intervals are *collapsed* (merged) when the cap is hit. [from-comment, lines 31-40]
- **Distance functions** (procnum 11) compute per-type "distance" between two values; the merge-step combines the two closest intervals. Functions exist for int2/4/8, float4/8, numeric, timestamp(tz), date, interval, oid, uuid, time(tz), pg_lsn, macaddr(8), and inet/cidr. [verified-by-code, ~lines 95-130 distance proto declarations]
- **Serialized form**: a variable-length `SerializedRanges` blob carried inside the BRIN tuple. Bookkeeping fields include `nranges`, `nvalues`, packed value array (sorted), with a typoid header so deserialization knows the type. [verified-by-code, struct definitions around lines 150-220]
- **Union step** merges the two interval sets, then collapses back down via repeated nearest-pair merge using the distance proc.

## Required + extra procs

| Procnum | Function/role |
|---|---|
| 1 opcInfo | one stored column of BYTEA (serialized) |
| 2 addValue | insert into in-memory minmax-multi structure; collapse if over cap |
| 3 consistent | strategy-aware: for `=` test against all intervals; for ordering ops compare to extreme |
| 4 union | combine two serialized sets + collapse |
| 11 distance | required type-specific helper, dispatched per-element |

## Notes

- File is 3 135 lines: large because every supported type needs an `_distance` function.
- The "collapse" step's choice of nearest-pair to merge is greedy O(n²) over `values_per_range`; fine because n ≤ 32.

Tags: [from-comment, brin_minmax_multi.c:9-40], [verified-by-code for struct shape].

## Open questions

- The serialization format's exact bytes vs. cross-version stability not traced.
- Whether the collapse is deterministic enough that two backends building the same range produce the same serialized output (matters for parallel build merge). [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
