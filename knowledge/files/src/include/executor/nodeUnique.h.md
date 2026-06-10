---
path: src/include/executor/nodeUnique.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeUnique.h

- **Source path:** `source/src/include/executor/nodeUnique.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `Unique` executor node (`nodeUnique.c`), which
removes adjacent duplicate rows from **sorted** input — the sort-based
implementation of `SELECT DISTINCT` and `DISTINCT ON`. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitUnique(Unique *, EState *, int eflags)` | init | returns `UniqueState *` |
| `ExecEndUnique(UniqueState *)` | teardown | |
| `ExecReScanUnique(UniqueState *)` | rescan | |

## Invariants & gotchas

- Like [[nodeGroup.h]], compares only adjacent rows, so it relies on a Sort
  (or ordered index) below. The hashed `DISTINCT` path is handled by a
  hashed `Agg` instead. [inferred]

## Cross-refs

- [[nodeGroup.h]] — same adjacent-comparison technique.
- [[nodeSetOp.h]] — set operations, also dedup-oriented.

## Tags

- [verified-by-code] prototype surface.
