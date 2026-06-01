# nodeGather.c

- **Source:** `source/src/backend/executor/nodeGather.c` (≈430 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Leader-side node that launches parallel workers (via execParallel.c) to run
the subplan in multiple copies, and **interleaves** their output streams in
arbitrary (non-deterministic) order. Used above a parallel-aware partial
plan whose results are *unordered*. [from-comment] `:8-24`

## Operation

`ExecGather`:

1. **First call** — if not already started, `ExecInitParallelPlan` +
   `ExecParallelCreateReaders`. Workers begin executing immediately.
2. **Try workers**: round-robin over `funnel->reader[i]` calling
   `TupleQueueReaderNext(reader, nowait=true)`. If anyone has a row, return
   it. If a reader is detached (worker done), close it; if all readers done,
   set `funnel->nworkers_launched=0`.
3. **No worker had a row immediately** — Gather may **also run the plan
   locally**. The `need_to_scan_locally` flag controls this; if set, ask
   the local copy of the subplan for a row.
4. **Block** if neither workers nor local have a row, on a WaitEventSet
   that watches every active worker's shm_mq fd plus the latch.

## Single-copy mode

`single_copy=true` (planner-set) means run the plan exactly once, in either
a single worker or (if no worker can be launched) the leader, and don't run
the local copy in parallel with the worker. Used when the plan isn't
parallel-aware but still benefits from offloading work to a different
process.

## Leader-side execution disable

GUC `parallel_leader_participation`: if off, the leader never executes its
local copy; it only ferries worker output. This helps short-running plans
where leader-time is dominated by reading tuple queues.

## Shutdown

`ExecShutdownGather` → `ExecParallelFinish` + `ExecParallelCleanup` — wait
for workers to exit, accumulate their BufferUsage/WalUsage/instr.

## Tags

- [verified-by-code] funnel and waitset structure.
- [from-comment] purpose statement + single-copy.
- [inferred] parallel_leader_participation GUC link (consistent with code).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
