---
path: src/include/executor/nodeGatherMerge.h
anchor_sha: 4b0bf0788b0
loc: 26
depth: read
---

# nodeGatherMerge.h

- **Source path:** `source/src/include/executor/nodeGatherMerge.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 26

## Purpose

Prototype header for the `GatherMerge` executor node
(`nodeGatherMerge.c`) — the **order-preserving parallel leader**. Like
[[nodeGather.h]] it collects tuples from parallel workers, but it merges
their already-sorted streams via a binary heap so the combined output
stays sorted. Used when a parallel plan must preserve an `ORDER BY`.
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitGatherMerge(GatherMerge *, EState *, int eflags)` | init | returns `GatherMergeState *` |
| `ExecEndGatherMerge(GatherMergeState *)` | teardown | |
| `ExecReScanGatherMerge(GatherMergeState *)` | rescan | re-launches workers |
| `ExecShutdownGatherMerge(GatherMergeState *)` | shutdown | early worker/DSM release |

## Invariants & gotchas

- Each worker must produce rows sorted on the merge key — GatherMerge only
  chooses the next worker to advance, mirroring [[nodeMergeAppend.h]] but
  across DSM tuple queues rather than child subplans. [inferred]

## Cross-refs

- [[nodeGather.h]] — unordered leader.
- [[nodeMergeAppend.h]] — the serial order-preserving merge.

## Tags

- [verified-by-code] prototype surface.
