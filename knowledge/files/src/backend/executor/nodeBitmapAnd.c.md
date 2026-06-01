# nodeBitmapAnd.c

- **Source:** `source/src/backend/executor/nodeBitmapAnd.c` (≈170 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Intersects TIDBitmaps from N child subplans (each typically a
BitmapIndexScan or another BitmapAnd/Or). Produces one combined TIDBitmap
via `tbm_intersect`. Used to combine multiple index conditions in a single
heap scan. [from-comment]

## MultiExec

`MultiExecBitmapAnd`:
- MultiExec each child to get a TIDBitmap.
- Use the first as the result, `tbm_intersect` each subsequent into it.
- Note: the planner orders children by descending estimated rowcount so
  small bitmaps last → minimal intersection work.

## Tags

- [verified-by-code] tbm_intersect loop.
- [from-comment] interface comment.
