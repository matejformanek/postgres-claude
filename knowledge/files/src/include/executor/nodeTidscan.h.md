---
path: src/include/executor/nodeTidscan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeTidscan.h

- **Source path:** `source/src/include/executor/nodeTidscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `TidScan` executor node (`nodeTidscan.c`), which
fetches tuples by an explicit set of TIDs — e.g. `WHERE ctid = '(0,1)'`
or `ctid IN (...)`, and `WHERE CURRENT OF cursor`. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitTidScan(TidScan *, EState *, int eflags)` | init | returns `TidScanState *` |
| `ExecEndTidScan(TidScanState *)` | teardown | |
| `ExecReScanTidScan(TidScanState *)` | rescan | re-evals the TID expression list |

## Invariants & gotchas

- No parallel support — the TID list is small and evaluated in the leader.
  Contrast [[nodeTidrangescan.h]], which *is* parallel-aware because a
  range can span many blocks. [inferred]

## Cross-refs

- [[nodeTidrangescan.h]] — the range variant (`ctid > / <`).

## Tags

- [verified-by-code] prototype surface.
