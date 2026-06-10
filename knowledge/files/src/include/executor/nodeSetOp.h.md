---
path: src/include/executor/nodeSetOp.h
anchor_sha: 4b0bf0788b0
loc: 25
depth: read
---

# nodeSetOp.h

- **Source path:** `source/src/include/executor/nodeSetOp.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 25

## Purpose

Prototype header for the `SetOp` executor node (`nodeSetOp.c`), which
implements `INTERSECT [ALL]` and `EXCEPT [ALL]` (plain `UNION` is handled
by Append+dedup, not here). It tags rows by which input side they came
from and counts matches per group. Supports both a sorted and a hashed
strategy. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitSetOp(SetOp *, EState *, int eflags)` | init | returns `SetOpState *` |
| `ExecEndSetOp(SetOpState *)` | teardown | |
| `ExecReScanSetOp(SetOpState *)` | rescan | |
| `EstimateSetOpHashTableSpace(double nentries, Size tupleWidth)` | helper | **public** — planner costing for the hashed strategy |

## Internal landmarks

- `EstimateSetOpHashTableSpace` is exported for the **planner** to size the
  hashed-setop hash table during costing — the planner/executor-shared
  helper on this node, analogous to `ExecEstimateCacheEntryOverheadBytes`
  on [[nodeMemoize.h]]. [verified-by-code]

## Invariants & gotchas

- The sorted strategy needs both inputs sorted on all columns; the hashed
  strategy builds a hash table from one side. Which one runs is fixed by
  the planner via the `SetOp.strategy` field. [inferred]

## Cross-refs

- [[nodeUnique.h]], [[nodeAppend.h]] — the UNION building blocks.

## Tags

- [verified-by-code] prototype surface incl. the public planner helper.
