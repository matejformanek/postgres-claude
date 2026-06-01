# nodeMemoize.c

- **Source:** `source/src/backend/executor/nodeMemoize.c` (≈1100 lines, 36 KB)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

LRU-cached parameterized inner scan. Sits above a parameterized child
(e.g. inner side of a NestLoop with index lookup); whenever the parent
asks for results with a parameter vector the cache has seen before, the
child is skipped and rows replay from cache. PG 14+. [from-comment] `:6-18`

## When the planner uses it

Above a parameterized inner side of a NestLoop, when the planner estimates
that the outer side will repeatedly probe the inner with the same
parameter values (e.g. small outer with high duplicate count, or large
NestLoop with skewed key distribution).

## Cache design

- Hash table keyed by the parameter vector (uses a compiled equality
  ExprState `ExecBuildParamSetEqual` from execExpr.c).
- Each entry stores a list of MinimalTuples (the entire result set for
  that parameter combo) and a "complete" flag.
- **LRU eviction**: doubly-linked list head/tail. New / accessed entries
  pushed to tail; when over `hash_mem`, evict head. No spill to disk.
  [from-comment] `:14-18`

## Incomplete entries

If the parent stops pulling early (semi-join finds its match), the cache
entry is marked **incomplete**. Next probe with the same key cannot use
it as-is; instead either:

- The planner marked the join as a **unique** join → we know one row was
  enough; mark the entry complete after the first stored row.
- Otherwise, the incomplete entry is discarded and the child rescanned.

[from-comment] `:22-32`

## Cache-table layout

Custom hash table (memohash) keyed on Params; stores entries inline in
chunks (similar to Hash's chunk allocator) so MinimalTuples for the same
entry are contiguous.

## EXPLAIN ANALYZE

Memoize reports cache hits / misses / evictions / overflows. The "Memory
Usage" line shows peak cache size; "Cache Misses" minus eligible probes
diagnoses bad planning choices.

## Tags

- [verified-by-code] LRU mechanism, eq-ExprState integration with execExpr.c.
- [from-comment] file header explanation of semi-join early-exit.
