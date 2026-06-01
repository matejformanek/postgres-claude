# nodeBitmapOr.c

- **Source:** `source/src/backend/executor/nodeBitmapOr.c` (≈170 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Unions TIDBitmaps from N children via `tbm_union`. Used for OR'd index
conditions. [from-comment]

## MultiExec

Symmetric with BitmapAnd: MultiExec each child, union into a running TBM.
Children are typically BitmapIndexScans on the same heap relation but on
different indexes / different qual conditions. A single child whose result
is empty contributes nothing; a single non-empty child shortcuts to the
trivial heap scan via BitmapHeapScan above.

## Tags

- [verified-by-code] tbm_union loop.
- [from-comment] interface comment.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
