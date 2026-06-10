---
path: src/include/executor/nodeWorktablescan.h
anchor_sha: 4b0bf0788b0
loc: 22
depth: read
---

# nodeWorktablescan.h

- **Source path:** `source/src/include/executor/nodeWorktablescan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 22

## Purpose

Prototype header for the `WorkTableScan` executor node
(`nodeWorktablescan.c`) — the reader of the **working table** in a
`WITH RECURSIVE` query. On each iteration the controlling
[[nodeRecursiveunion.h]] swaps the working table, and this node scans the
current generation's tuples. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitWorkTableScan(WorkTableScan *, EState *, int eflags)` | init | returns `WorkTableScanState *` |
| `ExecReScanWorkTableScan(WorkTableScanState *)` | rescan | |

## Invariants & gotchas

- **No `ExecEndWorkTableScan`** — explicit no-cleanup case at
  `execProcnode.c:734-738`; the working tuplestore is owned by the parent
  `RecursiveUnion`, not by this scan. [verified-by-code]
- The node finds its working table by following a back-link to the
  enclosing `RecursiveUnionState`, so it must be planned strictly inside
  the recursive term. [inferred]

## Cross-refs

- [[nodeRecursiveunion.h]] — owns the working/intermediate tuplestores.
- [[nodeValuesscan.h]], [[nodeNamedtuplestorescan.h]] — fellow no-ExecEnd nodes.

## Tags

- [verified-by-code] prototype surface + no-ExecEnd dispatch.
