---
path: src/include/executor/nodeBitmapOr.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# nodeBitmapOr.h

- **Source path:** `source/src/include/executor/nodeBitmapOr.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 24

## Purpose

Prototype header for the `BitmapOr` executor node (`nodeBitmapOr.c`). The
OR counterpart to [[nodeBitmapAnd.h]]: it OR-combines the `TIDBitmap`s
produced by its children into a single bitmap returned via `MultiExec`.
Used to execute index-OR conditions (`WHERE a = 1 OR b = 2` with indexes
on both columns) under a `BitmapHeapScan`. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitBitmapOr(BitmapOr *, EState *, int eflags)` | init | returns `BitmapOrState *` |
| `MultiExecBitmapOr(BitmapOrState *)` | multi-exec | returns `Node *` (`TIDBitmap`) |
| `ExecEndBitmapOr(BitmapOrState *)` | teardown | |
| `ExecReScanBitmapOr(BitmapOrState *)` | rescan | |

## Invariants & gotchas

- Same `MultiExecProcNode` dispatch rule as `BitmapAnd` — non-tuple node.
- A child of `BitmapOr` may itself be a `BitmapIndexScan` or a nested
  `BitmapAnd`, letting the planner build arbitrary AND/OR bitmap trees.
  [inferred from node nesting]

## Cross-refs

- [[nodeBitmapAnd.h]], [[nodeBitmapIndexscan.h]], [[nodeBitmapHeapscan.h]].

## Tags

- [verified-by-code] prototype surface.
