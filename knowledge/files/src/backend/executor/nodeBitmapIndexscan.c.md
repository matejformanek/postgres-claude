# nodeBitmapIndexscan.c

- **Source:** `source/src/backend/executor/nodeBitmapIndexscan.c` (≈340 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

The leaf node of a bitmap-scan plan. Uses the index AM's `amgetbitmap`
callback to drain all matching TIDs into a `TIDBitmap` in one shot, rather
than tuple-at-a-time. Returned to parent via MultiExecProcNode (not the
regular ExecProcNode tuple interface). [from-comment INTERFACE]

## MultiExec

`MultiExecBitmapIndexScan`:
- Allocates a `TIDBitmap` (or attaches to a shared one for parallel).
- Calls `index_getbitmap(scanDesc, tbm)`.
- Records `nreturned` for instrumentation.
- Returns the TIDBitmap pointer (cast through `Node *` for MultiExec API).

## ScanKey setup

Same `ExecIndexBuildScanKeys` as nodeIndexscan, with runtime-key support.

## Parallel

PG 16+ supports parallel bitmap heap scan with a *shared* TIDBitmap built
once by one worker (or the leader) during `MultiExecBitmapIndexScan`, then
all workers iterate it via `tbm_begin_shared_iterate`. Init/DSM hooks
allocate the shared dsa-backed TBM.

## Tags

- [verified-by-code] MultiExec interface contract.
- [from-comment] INTERFACE list at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/bitmap-and-or-heap-executor.md](../../../../idioms/bitmap-and-or-heap-executor.md)

