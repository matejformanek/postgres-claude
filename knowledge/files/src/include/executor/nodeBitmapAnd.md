# `executor/nodeBitmapAnd.h` — BitmapAnd combiner declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeBitmapAnd.h`)

## Role
Declares the executor entry points for the `BitmapAnd` plan node, which intersects (`AND`s) two or more child bitmaps produced by `BitmapIndexScan` (or nested `BitmapAnd/BitmapOr`) into a combined bitmap consumed by `BitmapHeapScan`. Pure combiner; emits a bitmap, not tuples.

## Public API
- `ExecInitBitmapAnd(BitmapAnd *, EState *, int eflags)` — nodeBitmapAnd.h:19
- `MultiExecBitmapAnd(BitmapAndState *)` — nodeBitmapAnd.h:20 (returns a `Node *` bitmap rather than a `TupleTableSlot`; called via `MultiExecProcNode`)
- `ExecEndBitmapAnd(BitmapAndState *)` — nodeBitmapAnd.h:21
- `ExecReScanBitmapAnd(BitmapAndState *)` — nodeBitmapAnd.h:22

## Cross-refs
- Plan node: `BitmapAnd` in `nodes/plannodes.h`
- State node: `BitmapAndState` in `nodes/execnodes.h` (forward-decl via include)
- Sibling combiner: `executor/nodeBitmapOr.h`
- Consumer: `executor/nodeBitmapHeapscan.h`
- Producers: `executor/nodeBitmapIndexscan.h`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
