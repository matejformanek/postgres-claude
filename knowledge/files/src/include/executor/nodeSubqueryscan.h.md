---
path: src/include/executor/nodeSubqueryscan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeSubqueryscan.h

- **Source path:** `source/src/include/executor/nodeSubqueryscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `SubqueryScan` executor node
(`nodeSubqueryscan.c`) — a thin shell wrapping a sub-`Plan` that came from
a `FROM (SELECT ...)` subquery that was *not* pulled up into the parent
query. It simply pulls tuples from its single child subplan. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitSubqueryScan(SubqueryScan *, EState *, int eflags)` | init | returns `SubqueryScanState *` |
| `ExecEndSubqueryScan(SubqueryScanState *)` | teardown | |
| `ExecReScanSubqueryScan(SubqueryScanState *)` | rescan | |

## Invariants & gotchas

- Most subqueries are flattened by `pull_up_subqueries` in the planner; a
  surviving `SubqueryScan` is essentially an optimization barrier the
  planner couldn't remove. [from-comment / inferred]

## Cross-refs

- [[nodeCtescan.h]] — the `WITH` analogue.

## Tags

- [verified-by-code] prototype surface.
