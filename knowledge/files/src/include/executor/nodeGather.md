# `executor/nodeGather.h` — Gather parallel-leader entry points

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeGather.h`)

## Role
Declares the leader-side executor entry points for `Gather` — the plan node that launches parallel workers, drains their tuple queues via `tqueue.c`, and emits results in arbitrary order (unsorted). Parent of every parallel-query plan tree.

## Public API
- `ExecInitGather(Gather *, EState *, int eflags)` — nodeGather.h:19
- `ExecEndGather(GatherState *)` — nodeGather.h:20
- `ExecShutdownGather(GatherState *)` — nodeGather.h:21 (called at end-of-Gather *and* rescan to tear workers down cleanly)
- `ExecReScanGather(GatherState *)` — nodeGather.h:22

## Phase D
Parallel-execution security envelope (A15 echo). Workers inherit the leader's user, SECDEFINER context, and active GUCs via `ParallelContext` serialization (`access/parallel.h`). Any `parallel_safe = false` function or RLS leak that bypasses the safety classification produces a privilege-escalation primitive in the worker. The `ExecShutdownGather` call is the cleanup join point — failing to call it on early Limit short-circuit leaves workers blocked on the shm_mq.

## Cross-refs
- Plan node: `Gather` in `nodes/plannodes.h`
- State node: `GatherState` in `nodes/execnodes.h`
- Sibling (ordered variant): `executor/nodeGatherMerge.h`
- Parallel framework: `access/parallel.h`, `executor/execParallel.h`
- Tuple queues: `executor/tqueue.h`
- `.c` impl: `source/src/backend/executor/nodeGather.c`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
