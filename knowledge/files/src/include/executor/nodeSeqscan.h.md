---
path: src/include/executor/nodeSeqscan.h
anchor_sha: 4b0bf0788b0
loc: 40
depth: read
---

# nodeSeqscan.h

- **Source path:** `source/src/include/executor/nodeSeqscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 40

## Purpose

Prototype header for the `SeqScan` executor node (`nodeSeqscan.c`) — the
canonical table-AM sequential scan and the reference template for every
other scan node (the `executor-and-planner` skill cites it throughout).
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitSeqScan(SeqScan *, EState *, int eflags)` | init | returns `SeqScanState *`; picks one of four specialised `ExecProcNode` variants by qual/projection presence |
| `ExecEndSeqScan(SeqScanState *)` | teardown | closes the table-AM scan |
| `ExecReScanSeqScan(SeqScanState *)` | rescan | |
| `ExecSeqScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | shares a `ParallelTableScanDesc` so workers split the heap |
| `ExecSeqScanInstrument{Estimate,InitDSM,InitWorker}` + `RetrieveInstrumentation` | parallel | per-worker instrumentation channel |

## Invariants & gotchas

- The **two parallel quartets** are the model the corpus refers to:
  Estimate/InitializeDSM/InitializeWorker = real parallel-scan
  partitioning; the Instrument* set = pulling EXPLAIN ANALYZE counters
  back from workers. Most parallel-aware scan headers mirror this exact
  shape. [verified-by-code]
- No mark/restore: a SeqScan never sits under a mergejoin inner directly
  (a Material/Sort would be interposed). [inferred]

## Cross-refs

- [[nodeSamplescan.h]], [[nodeBitmapHeapscan.h]], [[nodeTidrangescan.h]] —
  fellow parallel-aware heap scanners.

## Tags

- [verified-by-code] prototype surface.
