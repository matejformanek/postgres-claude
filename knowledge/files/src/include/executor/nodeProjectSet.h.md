---
path: src/include/executor/nodeProjectSet.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeProjectSet.h

- **Source path:** `source/src/include/executor/nodeProjectSet.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `ProjectSet` executor node (`nodeProjectSet.c`),
which evaluates a target list containing **set-returning functions**
(`SELECT generate_series(1,3), x FROM ...`). It produces one output row
per SRF result element, replacing the legacy `tList SRF` mechanism
removed in PG10. [verified-by-code / inferred]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitProjectSet(ProjectSet *, EState *, int eflags)` | init | returns `ProjectSetState *` |
| `ExecEndProjectSet(ProjectSetState *)` | teardown | |
| `ExecReScanProjectSet(ProjectSetState *)` | rescan | |

## Invariants & gotchas

- Multiple SRFs in one target list iterate to the LCM of their lengths,
  with shorter ones cycling NULLs — the standard SQL SRF row-multiplication
  rule the node implements. [from-comment]
- A target list with SRFs is only ever placed in a ProjectSet, never a
  plain [[nodeResult.h]] projection. [inferred]

## Cross-refs

- [[nodeResult.h]] — the non-set projection node.
- [[nodeFunctionscan.h]] — SRFs in `FROM` instead of the target list.

## Tags

- [verified-by-code] prototype surface.
