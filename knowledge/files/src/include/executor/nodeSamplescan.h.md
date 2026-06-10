---
path: src/include/executor/nodeSamplescan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeSamplescan.h

- **Source path:** `source/src/include/executor/nodeSamplescan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `SampleScan` executor node (`nodeSamplescan.c`),
which implements `TABLESAMPLE` (SYSTEM / BERNOULLI / custom tablesample
methods). It drives a tablesample handler (`TsmRoutine`) to decide which
blocks/tuples to return. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitSampleScan(SampleScan *, EState *, int eflags)` | init | returns `SampleScanState *` |
| `ExecEndSampleScan(SampleScanState *)` | teardown | |
| `ExecReScanSampleScan(SampleScanState *)` | rescan | re-seeds the sampling method |

## Invariants & gotchas

- No parallel support in the header: the sampling cursor is per-backend;
  parallelism for sampled scans is not offered at this node. [inferred
  from absence of DSM prototypes]

## Cross-refs

- [[nodeSeqscan.h]] — the non-sampled heap scan template.

## Tags

- [verified-by-code] prototype surface.
