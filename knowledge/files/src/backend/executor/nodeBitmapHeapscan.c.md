# nodeBitmapHeapscan.c

- **Source:** `source/src/backend/executor/nodeBitmapHeapscan.c` (≈460 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Bitmap-driven heap scan: receives a `TIDBitmap` from a child BitmapIndex /
BitmapAnd / BitmapOr (via `MultiExecProcNode`), then walks heap pages in
physical order pulling out the marked rows. Combines random-access index
selectivity with sequential I/O patterns. [from-comment INTERFACE]

## Flow

1. `ExecInitBitmapHeapScan` opens the heap, initializes a
   `TBMIterateResult`-style iterator.
2. First fetch: `MultiExecProcNode(child)` returns the populated TIDBitmap.
   Open a `tbm_begin_iterate` (or `tbm_begin_shared_iterate` for parallel).
3. For each page entry: if the page is `recheck=true` (or lossy because
   the bitmap overflowed), re-evaluate the original index quals against
   each heap row via `bitmap_recheck`; otherwise just check the per-tuple
   offset bitmap.
4. Returns rows via ExecScan with the standard recheck callback.

## Lossy pages

A TIDBitmap that exceeds `work_mem` collapses fine-grained tuple bits into
**page-level** marks; on a lossy page we must fetch every tuple on the
page and recheck. EXPLAIN reports "Heap Blocks: exact=N lossy=M".

## Parallel

`pstate` (shared TBM iterator) plus a Barrier coordinate workers; the
TIDBitmap itself is built once during BitmapIndexScan's MultiExec (shared
across workers via DSA — see PG 12+ parallel-aware BitmapIndexScan).

## Tags

- [verified-by-code] iterator model + lossy path.
- [from-comment] INTERFACE list.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
