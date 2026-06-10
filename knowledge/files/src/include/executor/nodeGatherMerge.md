# `executor/nodeGatherMerge.h` — ordered Gather entry points

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeGatherMerge.h`)

## Role
Declares entry points for `GatherMerge` — same role as `Gather` but each worker produces tuples in a presorted order, and the leader does a k-way merge over the worker queues to preserve total order. Used when the consumer plan needs sorted input (e.g. `Sort`-free top-N, Merge-Join feeding the worker stream).

## Public API
- `ExecInitGatherMerge(GatherMerge *, EState *, int eflags)` — nodeGatherMerge.h:19
- `ExecEndGatherMerge(GatherMergeState *)` — nodeGatherMerge.h:22
- `ExecReScanGatherMerge(GatherMergeState *)` — nodeGatherMerge.h:23
- `ExecShutdownGatherMerge(GatherMergeState *)` — nodeGatherMerge.h:24

## Phase D
Same envelope as `Gather` (A15 echo) — workers inherit the leader's authorization context via `ParallelContext`. Additionally, the leader's k-way merge holds tuples from each worker queue; back-pressure asymmetry can amplify a slow-worker DoS into a leader memory issue under high-`max_parallel_workers_per_gather`.

## Cross-refs
- Plan node: `GatherMerge` in `nodes/plannodes.h`
- State node: `GatherMergeState` in `nodes/execnodes.h`
- Sibling (unordered): `executor/nodeGather.h`
- Parallel framework: `access/parallel.h`, `executor/execParallel.h`
- `.c` impl: `source/src/backend/executor/nodeGatherMerge.c`
