---
path: src/include/executor/nodeBitmapAnd.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# nodeBitmapAnd.h

- **Source path:** `source/src/include/executor/nodeBitmapAnd.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 24

## Purpose

Prototype header for the `BitmapAnd` executor node (`nodeBitmapAnd.c`).
`BitmapAnd` is one of the three **`MultiExec`-returning** plan nodes: it
does not return tuples, it returns a `TIDBitmap` (`Node *`) built by
AND-combining the bitmaps produced by its child `BitmapIndexScan` /
nested `BitmapAnd` / `BitmapOr` nodes. The result feeds upward into a
`BitmapHeapScan` (or another bitmap combinator). [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitBitmapAnd(BitmapAnd *, EState *, int eflags)` | init | returns `BitmapAndState *` |
| `MultiExecBitmapAnd(BitmapAndState *)` | multi-exec | returns `Node *` (a `TIDBitmap`), **not** a tuple slot |
| `ExecEndBitmapAnd(BitmapAndState *)` | teardown | |
| `ExecReScanBitmapAnd(BitmapAndState *)` | rescan | |

## Invariants & gotchas

- **Dispatch asymmetry**: because this node returns a non-tuple result,
  it must have a `case` in `MultiExecProcNode` (`execProcnode.c`), not in
  the normal `ExecProcNode` tuple path. See the `executor-and-planner`
  skill §A.2 "tag asymmetry". [verified-by-code]
- No parallel or mark/restore support — bitmap combinators run in the
  leader's bitmap-build phase only.

## Cross-refs

- [[nodeBitmapOr.h]] — the OR sibling combinator.
- [[nodeBitmapIndexscan.h]] — the leaf bitmap producer.
- [[nodeBitmapHeapscan.h]] — the consumer that turns the TID bitmap into tuples.

## Tags

- [verified-by-code] prototype surface.
