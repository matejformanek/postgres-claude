---
path: src/include/executor/nodeGroup.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeGroup.h

- **Source path:** `source/src/include/executor/nodeGroup.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `Group` executor node (`nodeGroup.c`), which
groups **already-sorted** input by the grouping columns, emitting one row
per distinct group. It does *not* compute aggregates — that's `Agg`; Group
is the bare `GROUP BY` collapse used when no aggregate functions are
present. [verified-by-code / inferred]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitGroup(Group *, EState *, int eflags)` | init | returns `GroupState *` |
| `ExecEndGroup(GroupState *)` | teardown | |
| `ExecReScanGroup(GroupState *)` | rescan | |

## Invariants & gotchas

- Requires sorted input (a Sort or index path below) — it only compares
  adjacent rows, like [[nodeUnique.h]]. The hashed alternative is `Agg`
  with `AGG_HASHED`, not this node. [inferred]

## Cross-refs

- [[nodeUnique.h]] — the same adjacent-comparison idiom for `DISTINCT`.
- [[nodeAgg.h]] — aggregates + hashed grouping.

## Tags

- [verified-by-code] prototype surface.
