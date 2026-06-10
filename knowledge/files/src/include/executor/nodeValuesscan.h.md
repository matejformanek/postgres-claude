---
path: src/include/executor/nodeValuesscan.h
anchor_sha: 4b0bf0788b0
loc: 22
depth: read
---

# nodeValuesscan.h

- **Source path:** `source/src/include/executor/nodeValuesscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 22

## Purpose

Prototype header for the `ValuesScan` executor node (`nodeValuesscan.c`),
which evaluates a `VALUES (...), (...)` list — as a stand-alone
`VALUES` statement or the rows of an `INSERT ... VALUES`. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitValuesScan(ValuesScan *, EState *, int eflags)` | init | returns `ValuesScanState *` |
| `ExecReScanValuesScan(ValuesScanState *)` | rescan | |

## Invariants & gotchas

- **No `ExecEndValuesScan`.** The dispatcher handles teardown in the
  explicit "No clean up actions for these nodes" case at
  `execProcnode.c:734-738` — ValuesScan holds no buffer pins, open
  relations, or owned tuplestores beyond what per-query context teardown
  reclaims. The same applies to [[nodeWorktablescan.h]] and
  [[nodeNamedtuplestorescan.h]]. A future agent adding a similar
  expression-only node should follow this pattern, not invent an empty
  `ExecEnd`. [verified-by-code, execProcnode.c:734]

## Cross-refs

- [[nodeWorktablescan.h]], [[nodeNamedtuplestorescan.h]] — the other two
  no-ExecEnd nodes.

## Tags

- [verified-by-code] prototype surface + no-ExecEnd dispatch.
