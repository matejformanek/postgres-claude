---
path: src/include/executor/nodeMemoize.h
anchor_sha: 4b0bf0788b0
loc: 32
depth: read
---

# nodeMemoize.h

- **Source path:** `source/src/include/executor/nodeMemoize.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 32

## Purpose

Prototype header for the `Memoize` executor node (`nodeMemoize.c`, added
in PG14). Sits on the inner side of a parameterised nestloop and caches
each parameter combination's result rows in a hash table with LRU
eviction, so repeated outer keys skip re-executing the inner subtree.
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitMemoize(Memoize *, EState *, int eflags)` | init | returns `MemoizeState *` |
| `ExecEndMemoize` / `ExecReScanMemoize` | teardown / rescan | |
| `ExecEstimateCacheEntryOverheadBytes(double ntuples)` | helper | **public** — used by the planner's `cost_memoize_rescan` to size the cache |
| `ExecMemoizeEstimate / InitializeDSM / InitializeWorker` | instrumentation | shared cache-hit stats |
| `ExecMemoizeRetrieveInstrumentation` | instrumentation | pull worker hit/miss/evict counters |

## Internal landmarks

- `ExecEstimateCacheEntryOverheadBytes` is the one prototype here that the
  **planner** calls (not just the executor) — a costing helper exposed
  across the planner/executor seam. [verified-by-code]

## Invariants & gotchas

- Eviction means a cached entry can disappear, so Memoize must transparently
  re-run the inner subtree on a miss — correctness never depends on a hit.
  [from-comment]

## Cross-refs

- [[nodeNestloop.h]] — the parameterised join Memoize accelerates.
- [[nodeMaterial.h]] — blanket buffering vs. per-key caching.

## Tags

- [verified-by-code] prototype surface incl. the public planner helper.
