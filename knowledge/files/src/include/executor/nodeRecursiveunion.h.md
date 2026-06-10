---
path: src/include/executor/nodeRecursiveunion.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeRecursiveunion.h

- **Source path:** `source/src/include/executor/nodeRecursiveunion.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `RecursiveUnion` executor node
(`nodeRecursiveunion.c`), the engine behind `WITH RECURSIVE`. It runs the
non-recursive term once, then repeatedly runs the recursive term over the
**working table** until a generation produces no rows, optionally
deduplicating with a hash table (`UNION` vs `UNION ALL`). [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitRecursiveUnion(RecursiveUnion *, EState *, int eflags)` | init | returns `RecursiveUnionState *` |
| `ExecEndRecursiveUnion(RecursiveUnionState *)` | teardown | frees working/intermediate tuplestores + dedup hash |
| `ExecReScanRecursiveUnion(RecursiveUnionState *)` | rescan | |

## Invariants & gotchas

- Owns the working and intermediate tuplestores that
  [[nodeWorktablescan.h]] reads — the WorkTableScan in the recursive term
  finds them via a back-link to this node's state. [verified-by-code / inferred]
- For `UNION` (not `ALL`) it keeps a hash table of all emitted rows to
  filter duplicates across generations. [from-comment]

## Cross-refs

- [[nodeWorktablescan.h]] — reads the working table this node maintains.
- [[nodeCtescan.h]] — non-recursive CTE reads.

## Tags

- [verified-by-code] prototype surface.
