---
path: src/include/executor/nodeResult.h
anchor_sha: 4b0bf0788b0
loc: 25
depth: read
---

# nodeResult.h

- **Source path:** `source/src/include/executor/nodeResult.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 25

## Purpose

Prototype header for the `Result` executor node (`nodeResult.c`), the
general-purpose projection/gating node. Three roles: (1) a child with a
one-time `resconstantqual` gate (skip everything if a constant qual is
false, e.g. `WHERE false`); (2) compute a target list with no scan
(`SELECT 1`); (3) pass through a single child applying projection.
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitResult(Result *, EState *, int eflags)` | init | returns `ResultState *` |
| `ExecEndResult(ResultState *)` | teardown | |
| `ExecResultMarkPos` / `ExecResultRestrPos` | mark/restore | delegates to the child |
| `ExecReScanResult(ResultState *)` | rescan | re-arms the one-time qual |

## Invariants & gotchas

- Mark/restore is **pass-through**: a Result with a child forwards
  mark/restore to that child, so it can sit transparently under a mergejoin
  inner. [from-comment]
- The `resconstantqual` is evaluated once; once it returns false the node
  is permanently empty for that execution. [verified-by-code]

## Cross-refs

- [[nodeProjectSet.h]] — the set-returning projection sibling.

## Tags

- [verified-by-code] prototype surface.
