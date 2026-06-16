# execParallel.c

- **Source:** `source/src/backend/executor/execParallel.c` (1616 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (leader-side parallel setup; worker entry point)

## Purpose

Leader-side glue between the executor and the generic ParallelContext
machinery (see `access/transam/README.parallel`). Serializes plan + state
into the DSM segment, launches workers, collects WAL/Buffer usage and
instrumentation back from them. [from-comment] `:8-17`

## Per-query objects

- `ParallelExecutorInfo` (decl in `execParallel.h`) — the leader's view:
  ParallelContext pointer, `TupleQueueReader[]` (one per worker), shared
  BufferUsage/WalUsage arrays, per-node DSA areas for parallel-aware nodes,
  a "param exec" area for shareable PARAM_EXEC slots.

## Lifecycle

### `ExecInitParallelPlan(planstate, estate, sendParams, nworkers, tuples_needed)` `:653`

The big one. Steps:

1. Walk the plan tree counting how much DSM each parallel-aware node needs
   via `EstimateParallelExecutorInfoSpace` and per-node `ExecXxxEstimate`
   callbacks (Hash, BitmapHeapScan, Sort if incremental_sort/full sort,
   HashAgg, Append, …).
2. Create a ParallelContext, calling `InitializeParallelDSM`.
3. Serialize the plan tree via `nodeToString` into a shm_toc key, plus
   ParamListInfo, queryString, query environment, snapshot, etc.
4. Per-node `ExecXxxInitializeDSM` — gives parallel-aware nodes a chance
   to lay out their shared state in the DSM (e.g. Hash sets up
   `ParallelHashJoinState`).
5. Create N `shm_mq` queues, one per worker; the leader wraps each in a
   TupleQueueReader.
6. **Do not launch workers yet** — that happens via
   `ExecParallelCreateReaders` (called from Gather/GatherMerge when it
   actually wants the first row).

### `ExecParallelCreateReaders(pei)` `:944`

Calls `LaunchParallelWorkers`; each worker forks and enters
`ParallelQueryMain` `:1514`. Workers may fail to launch (fork failure, no
slots); leader still proceeds with whatever workers came up plus its own
in-process execution.

### `ExecParallelReinitialize(planstate, pei, sendParams)` `:970`

For looping execution (parameterized plans inside a NestLoop, BitmapHeapScan
inside Gather). Reinits per-node DSM state, drains old tuple queues,
re-launches workers.

### `ExecParallelFinish(pei)` `:1221`

Waits for all workers to exit, accumulates each worker's `BufferUsage` /
`WalUsage` into the leader's pgBufferUsage / pgWalUsage globals,
collects Instrumentation arrays.

### `ExecParallelCleanup(pei)` `:1274`

Destroys the ParallelContext + DSM segment after everything is done.

## Worker side: `ParallelQueryMain` `:1514`

Worker entry. Looks up the serialized plan + params from the DSM, reconstructs
a QueryDesc, restores active snapshots and the param list, then calls
`ExecutorStart`/`ExecutorRun`/`ExecutorFinish`/`ExecutorEnd` with a
`DestReceiver` that writes to the worker's shm_mq. Per-node
`ExecXxxInitializeWorker` is called so nodes can attach to their leader-side
DSM area.

## Surprising/important details

- **Plans are serialized as text**: `nodeToString` produces the on-the-wire
  form; workers `stringToNode` it back. This means everything in a plan node
  must be string-roundtrippable (= no opaque pointers without read/out support).
- **Instrumentation is collected per-worker** then merged; this is what
  EXPLAIN ANALYZE's "Workers Launched: N" / per-worker stats come from.
- **Workers run a separate executor invocation each.** Shared state between
  them lives in DSM (Hash table, Bitmap, sort tape pool, HashAgg shared
  hash). The "merge" happens either in the parallel-aware node (Hash) or
  the leader (Gather/GatherMerge).

## Tags

- [verified-by-code] entry-point line numbers; lifecycle ordering.
- [from-comment] file header; README.parallel referenced for protocol.
- [inferred] the "do not launch until Gather pulls first row" detail
  (consistent with code, but worth a re-read of nodeGather to confirm timing).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->
