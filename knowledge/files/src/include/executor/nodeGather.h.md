---
path: src/include/executor/nodeGather.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# nodeGather.h

- **Source path:** `source/src/include/executor/nodeGather.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 24

## Purpose

Prototype header for the `Gather` executor node (`nodeGather.c`) — the
**parallel leader** node. It launches the parallel workers (via the
parallel-context/DSM machinery), reads tuples from the workers' shared
tuple queues in arbitrary order, and (optionally) also runs the plan
itself in the leader. The boundary between the parallel and serial parts
of a plan. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitGather(Gather *, EState *, int eflags)` | init | returns `GatherState *` |
| `ExecEndGather(GatherState *)` | teardown | |
| `ExecShutdownGather(GatherState *)` | shutdown | tears down workers/DSM early (e.g. under a Limit) |
| `ExecReScanGather(GatherState *)` | rescan | re-launches workers |

## Invariants & gotchas

- `ExecShutdownGather` exists so a Limit above can stop and release workers
  before the full `ExecEndNode`; forgetting to propagate shutdown leaves
  workers spinning. [from-comment / inferred]
- Output is **unordered** — if the plan needs ordering use
  [[nodeGatherMerge.h]] instead. [verified-by-code]

## Cross-refs

- [[nodeGatherMerge.h]] — order-preserving leader.
- [[execParallel.md]] — the DSM/worker setup this node drives.

## Tags

- [verified-by-code] prototype surface.
