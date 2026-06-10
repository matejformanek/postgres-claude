---
path: src/include/executor/nodeNamedtuplestorescan.h
anchor_sha: 4b0bf0788b0
loc: 22
depth: read
---

# nodeNamedtuplestorescan.h

- **Source path:** `source/src/include/executor/nodeNamedtuplestorescan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 22

## Purpose

Prototype header for the `NamedTuplestoreScan` executor node
(`nodeNamedtuplestorescan.c`), which scans a tuplestore registered by name
in the `EState` — most notably the **transition tables** (`OLD TABLE` /
`NEW TABLE`) made available to `AFTER` statement triggers. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitNamedTuplestoreScan(NamedTuplestoreScan *, EState *, int eflags)` | init | returns `NamedTuplestoreScanState *` |
| `ExecReScanNamedTuplestoreScan(NamedTuplestoreScanState *)` | rescan | |

## Invariants & gotchas

- **No `ExecEndNamedTuplestoreScan`** — explicit no-cleanup case at
  `execProcnode.c:734-738`; the named tuplestore is owned by whoever
  registered it (the trigger machinery), not by this scan, so the node only
  holds a read pointer. [verified-by-code]
- The tuplestore is looked up by name through the `EState`'s registered
  ENR (ephemeral named relation) list. [inferred]

## Cross-refs

- [[nodeValuesscan.h]], [[nodeWorktablescan.h]] — fellow no-ExecEnd nodes.

## Tags

- [verified-by-code] prototype surface + no-ExecEnd dispatch.
