---
path: src/include/executor/nodeTidrangescan.h
anchor_sha: 4b0bf0788b0
loc: 40
depth: read
---

# nodeTidrangescan.h

- **Source path:** `source/src/include/executor/nodeTidrangescan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 40

## Purpose

Prototype header for the `TidRangeScan` executor node
(`nodeTidrangescan.c`), which scans a contiguous CTID range — e.g.
`WHERE ctid >= '(10,0)' AND ctid < '(20,0)'`. Unlike the point
[[nodeTidscan.h]], a range can cover many blocks, so this node carries the
full parallel-aware surface. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitTidRangeScan(TidRangeScan *, EState *, int eflags)` | init | returns `TidRangeScanState *` |
| `ExecEndTidRangeScan` / `ExecReScanTidRangeScan` | teardown / rescan | |
| `ExecTidRangeScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | shares the block range across workers |
| `ExecTidRangeScanInstrument{Estimate,InitDSM,InitWorker}` + `RetrieveInstrumentation` | parallel | instrumentation channel |

## Invariants & gotchas

- Same two-quartet parallel shape as [[nodeSeqscan.h]] — it sets the
  table-AM scan's start/end block from the evaluated range bounds and lets
  workers divide it. [verified-by-code / inferred]

## Cross-refs

- [[nodeTidscan.h]], [[nodeSeqscan.h]].

## Tags

- [verified-by-code] prototype surface.
