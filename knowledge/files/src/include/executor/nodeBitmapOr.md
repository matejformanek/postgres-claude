# `executor/nodeBitmapOr.h` — BitmapOr combiner declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeBitmapOr.h`)

## Role
Declares executor entry points for the `BitmapOr` plan node, which unions (`OR`s) child bitmaps into a single bitmap. Counterpart to `BitmapAnd`; same `MultiExec` shape returning `Node *` rather than tuples.

## Public API
- `ExecInitBitmapOr(BitmapOr *, EState *, int eflags)` — nodeBitmapOr.h:19
- `MultiExecBitmapOr(BitmapOrState *)` — nodeBitmapOr.h:20
- `ExecEndBitmapOr(BitmapOrState *)` — nodeBitmapOr.h:21
- `ExecReScanBitmapOr(BitmapOrState *)` — nodeBitmapOr.h:22

## Cross-refs
- Plan node: `BitmapOr` in `nodes/plannodes.h`
- State node: `BitmapOrState` in `nodes/execnodes.h`
- Sibling combiner: `executor/nodeBitmapAnd.h`
- Consumer: `executor/nodeBitmapHeapscan.h`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
