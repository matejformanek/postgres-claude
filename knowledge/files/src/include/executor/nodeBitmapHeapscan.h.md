---
path: src/include/executor/nodeBitmapHeapscan.h
anchor_sha: 4b0bf0788b0
loc: 39
depth: read
---

# nodeBitmapHeapscan.h

- **Source path:** `source/src/include/executor/nodeBitmapHeapscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 39

## Purpose

Prototype header for the `BitmapHeapScan` executor node
(`nodeBitmapHeapscan.c`). This is the **bitmap consumer**: it pulls a
`TIDBitmap` from its single child (`BitmapIndexScan` / `BitmapAnd` /
`BitmapOr`) and fetches the matching heap tuples in physical order,
applying any recheck quals. Unlike its child it is a normal
tuple-returning node (no `MultiExec`). [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitBitmapHeapScan(BitmapHeapScan *, EState *, int eflags)` | init | returns `BitmapHeapScanState *` |
| `ExecEndBitmapHeapScan(BitmapHeapScanState *)` | teardown | |
| `ExecReScanBitmapHeapScan(BitmapHeapScanState *)` | rescan | |
| `ExecBitmapHeapEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | shared bitmap-scan state across workers |
| `ExecBitmapHeapInstrument{Estimate,InitDSM,InitWorker}` + `RetrieveInstrumentation` | parallel | separate instrumentation channel |

## Invariants & gotchas

- **Genuinely parallel-aware**: the Estimate/InitializeDSM/InitializeWorker
  quartet shares the iteration cursor over the TID bitmap so multiple
  workers divide the heap fetch. This is the parallel-scan flavor, *plus*
  a distinct Instrument* quartet — the heaviest parallel surface among the
  bitmap nodes. [verified-by-code]
- Lossy bitmap pages force a recheck of the original index qual against
  each heap tuple; exact pages skip the recheck. [from-README, access/heap]

## Cross-refs

- [[nodeBitmapIndexscan.h]] — the child bitmap producer.
- [[nodeSeqscan.h]] — the other parallel-aware heap scanner (same DSM idiom).

## Tags

- [verified-by-code] prototype surface; [from-README] lossy-page recheck.
