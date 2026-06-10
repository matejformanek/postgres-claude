---
path: src/include/executor/nodeBitmapIndexscan.h
anchor_sha: 4b0bf0788b0
loc: 30
depth: read
---

# nodeBitmapIndexscan.h

- **Source path:** `source/src/include/executor/nodeBitmapIndexscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 30

## Purpose

Prototype header for the `BitmapIndexScan` executor node
(`nodeBitmapIndexscan.c`). This is the **leaf bitmap producer**: it scans
one index via the AM's `amgetbitmap` callback and returns a `TIDBitmap`
(`Node *`) through `MultiExec`, never tuples. Its output feeds a
`BitmapHeapScan`, a `BitmapAnd`, or a `BitmapOr`. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitBitmapIndexScan(BitmapIndexScan *, EState *, int eflags)` | init | returns `BitmapIndexScanState *` |
| `MultiExecBitmapIndexScan(BitmapIndexScanState *)` | multi-exec | returns `Node *` (`TIDBitmap`) |
| `ExecEndBitmapIndexScan(BitmapIndexScanState *)` | teardown | |
| `ExecReScanBitmapIndexScan(BitmapIndexScanState *)` | rescan | re-evals runtime keys |
| `ExecBitmapIndexScanEstimate / InitializeDSM / InitializeWorker` | parallel | shared-instrumentation DSM plumbing |
| `ExecBitmapIndexScanRetrieveInstrumentation(BitmapIndexScanState *)` | parallel | pull worker instrumentation |

## Internal landmarks

- Uses `ExecIndexBuildScanKeys` / `ExecIndexEvalRuntimeKeys` (declared in
  [[nodeIndexscan.h]]) — the same scan-key machinery shared by plain
  index scans and index-only scans. [verified-by-code]

## Invariants & gotchas

- `MultiExecProcNode` dispatch (non-tuple node), like the bitmap
  combinators.
- The parallel quartet here is for **instrumentation propagation** from
  parallel workers (a BitmapIndexScan can sit under a parallel
  BitmapHeapScan); it does not itself partition the index scan. [inferred]

## Cross-refs

- [[nodeIndexscan.h]] — shares the ScanKey-build helpers.
- [[nodeBitmapHeapscan.h]], [[nodeBitmapAnd.h]], [[nodeBitmapOr.h]].

## Tags

- [verified-by-code] prototype surface; [inferred] parallel-role note.
