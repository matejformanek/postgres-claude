---
path: src/include/executor/nodeCtescan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeCtescan.h

- **Source path:** `source/src/include/executor/nodeCtescan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `CteScan` executor node (`nodeCtescan.c`), which
reads from a non-recursive `WITH` CTE that was materialised by a
`CteScan`'s underlying `RecursiveUnion`/subplan. Multiple references to
the same CTE share one tuplestore; each `CteScan` is a reader cursor over
it. [verified-by-code / inferred]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitCteScan(CteScan *, EState *, int eflags)` | init | returns `CteScanState *` |
| `ExecEndCteScan(CteScanState *)` | teardown | |
| `ExecReScanCteScan(CteScanState *)` | rescan | rewinds its read pointer in the shared tuplestore |

## Invariants & gotchas

- The CTE's tuplestore is owned by the leader `CteScan`; sibling readers
  hold additional read pointers. Rescan rewinds the pointer, not the
  store. [inferred from shared-CTE design]

## Cross-refs

- [[nodeWorktablescan.h]] — the recursive-CTE working-table reader.
- [[nodeRecursiveunion.h]] — drives `WITH RECURSIVE`.

## Tags

- [verified-by-code] prototype surface; [inferred] shared-tuplestore note.
