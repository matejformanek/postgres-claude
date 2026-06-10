---
path: src/include/executor/nodeNestloop.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeNestloop.h

- **Source path:** `source/src/include/executor/nodeNestloop.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `NestLoop` executor node (`nodeNestloop.c`) — the
nested-loop join and the corpus's reference *join* template (the
`executor-and-planner` skill cites `ExecNestLoop`/`ExecReScanSeqScan`
patterns). For each outer tuple it rescans the inner subtree, optionally
passing down join parameters (`nestParams`) for parameterised inner
index scans. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitNestLoop(NestLoop *, EState *, int eflags)` | init | returns `NestLoopState *` |
| `ExecEndNestLoop(NestLoopState *)` | teardown | |
| `ExecReScanNestLoop(NestLoopState *)` | rescan | |

## Invariants & gotchas

- Resets the per-tuple ExprContext between outer rows
  (`nodeNestloop.c:92`, per the skill). The inner subtree's rescan is what
  makes parameterised nestloop (the index-driven join) work. [verified-by-code]
- No mark/restore and no parallel surface at the join node itself —
  parallelism comes from a parallel-aware scan below, gathered above.

## Cross-refs

- [[nodeMergejoin.h]], [[nodeHashjoin.h]] — the other two join strategies.

## Tags

- [verified-by-code] prototype surface.
