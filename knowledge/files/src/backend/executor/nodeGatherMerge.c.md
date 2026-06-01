# nodeGatherMerge.c

- **Source:** `source/src/backend/executor/nodeGatherMerge.c` (≈700 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Like Gather but **preserves order**: each worker's partial subplan is
expected to emit rows in a given sort order (typically because the partial
subplan ends in a Sort or an Index Scan in key order), and the leader
k-way-merges using a `binaryheap`. [from-comment] `:4`

## Key data

- `tuples_left` arrays per worker (`GMReaderTupleBuffer`): prefetched
  rows (up to MAX_TUPLE_STORE=10) so reading is cache-friendly. `:30-43`
- `done` flag per worker.
- `gm_heap`: binaryheap of indexes into the per-worker buffer, keyed by
  the current head tuple's sort key.

## ExecGatherMerge

1. Init: pull at least one row from every reader (block if necessary so
   the heap starts with every active worker represented).
2. Each call: pop the heap, return that row, prefetch the next row from
   the same worker (or mark `done` and remove from heap).

## Leader-as-worker

Leader may participate (default), in which case it acts as one of the
"workers" and feeds its own local subplan into the heap.

## ReScan

GatherMerge generally rescans by tearing down and re-launching workers
(`ExecParallelReinitialize`).

## Tags

- [verified-by-code] heap + per-reader buffer arrays.
- [from-comment] purpose + MAX_TUPLE_STORE constant.
