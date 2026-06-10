---
path: src/include/executor/nodeMergeAppend.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeMergeAppend.h

- **Source path:** `source/src/include/executor/nodeMergeAppend.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `MergeAppend` executor node
(`nodeMergeAppend.c`), which merges several already-sorted child subplans
into one sorted output stream via a binary heap of child tuples. The
order-preserving counterpart to plain `Append`; central to ordered scans
over a partitioned table. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitMergeAppend(MergeAppend *, EState *, int eflags)` | init | returns `MergeAppendState *` |
| `ExecEndMergeAppend(MergeAppendState *)` | teardown | |
| `ExecReScanMergeAppend(MergeAppendState *)` | rescan | |

## Invariants & gotchas

- Each child must deliver rows already sorted on the merge keys — the heap
  only chooses which child advances next, it does not sort. [from-comment]
- Unlike [[nodeAppend.h]], no async/parallel-Append support: a binary-heap
  merge needs every child's current head tuple synchronously. [inferred]

## Cross-refs

- [[nodeAppend.h]] — the unordered concatenation sibling.

## Tags

- [verified-by-code] prototype surface.
