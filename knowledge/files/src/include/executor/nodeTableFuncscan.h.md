---
path: src/include/executor/nodeTableFuncscan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeTableFuncscan.h

- **Source path:** `source/src/include/executor/nodeTableFuncscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `TableFuncScan` executor node
(`nodeTableFuncscan.c`), which evaluates a `TableFunc` expression —
`XMLTABLE(...)` and SQL/JSON `JSON_TABLE(...)` — driving a
`TableFuncRoutine` to shred a document into rows. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitTableFuncScan(TableFuncScan *, EState *, int eflags)` | init | returns `TableFuncScanState *` |
| `ExecEndTableFuncScan(TableFuncScanState *)` | teardown | |
| `ExecReScanTableFuncScan(TableFuncScanState *)` | rescan | re-evaluates the document expression |

## Invariants & gotchas

- The actual XML/JSON parsing lives behind the `TableFuncRoutine` vtable
  (`tablefuncapi`), not in the node itself — the node is the generic
  per-row driver. [inferred]

## Cross-refs

- [[nodeFunctionscan.h]] — the SRF-in-FROM sibling.

## Tags

- [verified-by-code] prototype surface.
