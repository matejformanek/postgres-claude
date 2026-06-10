---
path: src/include/executor/nodeLimit.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeLimit.h

- **Source path:** `source/src/include/executor/nodeLimit.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `Limit` executor node (`nodeLimit.c`), which
implements `LIMIT` / `OFFSET` and `FETCH FIRST ... WITH TIES`. It skips
the OFFSET rows, passes through the next LIMIT rows, then signals
exhaustion to its child (triggering shutdown of any parallel Gather below).
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitLimit(Limit *, EState *, int eflags)` | init | returns `LimitState *` |
| `ExecEndLimit(LimitState *)` | teardown | |
| `ExecReScanLimit(LimitState *)` | rescan | re-evaluates LIMIT/OFFSET params |

## Invariants & gotchas

- When the limit is reached the node calls `ExecShutdownNode` on its child
  so parallel workers/FDW cursors are released early — the consumer of the
  `ExecShutdown*` hooks on [[nodeGather.h]] / [[nodeForeignscan.h]].
  [from-comment / inferred]
- `WITH TIES` keeps emitting rows that tie with the last in-limit row on
  the ORDER BY key, so the cutoff is value-based, not a fixed count.
  [verified-by-code]

## Cross-refs

- [[nodeGather.h]], [[nodeForeignscan.h]] — recipients of early shutdown.

## Tags

- [verified-by-code] prototype surface.
