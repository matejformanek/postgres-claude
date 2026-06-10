---
path: src/include/executor/nodeIndexonlyscan.h
anchor_sha: 4b0bf0788b0
loc: 43
depth: read
---

# nodeIndexonlyscan.h

- **Source path:** `source/src/include/executor/nodeIndexonlyscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 43

## Purpose

Prototype header for the `IndexOnlyScan` executor node
(`nodeIndexonlyscan.c`). Returns columns straight from the index, using
the visibility map to avoid heap fetches for all-visible pages. Supports
mark/restore (so it can be a mergejoin inner) and the full parallel
surface. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitIndexOnlyScan(IndexOnlyScan *, EState *, int eflags)` | init | returns `IndexOnlyScanState *` |
| `ExecEndIndexOnlyScan` / `ExecReScanIndexOnlyScan` | teardown / rescan | |
| `ExecIndexOnlyMarkPos` / `ExecIndexOnlyRestrPos` | mark/restore | for mergejoin inner |
| `ExecIndexOnlyScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | shared parallel index scan |
| `ExecIndexOnlyScanInstrument{Estimate,InitDSM,InitWorker}` + `RetrieveInstrumentation` | parallel | instrumentation channel |

## Invariants & gotchas

- Shares `ExecIndexBuildScanKeys` / `ExecIndexEvalRuntimeKeys` with plain
  and bitmap index scans (declared in [[nodeIndexscan.h]]). [verified-by-code]
- Heap visibility recheck: when the VM bit is not set, the node must fetch
  the heap tuple to test visibility, so "index-only" is best-effort.
  [from-comment, access/nbtree]

## Cross-refs

- [[nodeIndexscan.h]] — shares scan-key helpers, also mark/restore-capable.
- [[nodeBitmapIndexscan.h]].

## Tags

- [verified-by-code] prototype surface.
