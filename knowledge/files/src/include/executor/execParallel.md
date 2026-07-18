# `src/include/executor/execParallel.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Parallel-executor support — sets up the DSM segment, tuple queues,
and per-worker state needed to ship a plan subtree (`Gather` /
`Gather Merge` body) to worker backends.

## Public API

### `ParallelExecutorInfo` [verified-by-code: lines 24-38]

Per-parallel-query handle stored in the leader's `EState`:

- `planstate` — the subtree being parallelized.
- `pcxt` — `ParallelContext` (from `access/parallel.h`).
- `buffer_usage`, `wal_usage` — DSM-resident arrays for workers to
  write usage stats; merged into leader counters at end.
- `instrumentation` — shared executor instrumentation (EXPLAIN
  ANALYZE).
- `jit_instrumentation` — per-worker JIT stats.
- `area` — DSA area for shared data.
- `param_exec` — serialized PARAM_EXEC parameter list (dsa_pointer).
- `finished` — set true by `ExecParallelFinish`.
- `tqueue[nworkers]`, `reader[nworkers]` — output channels.

### Lifecycle [lines 40-47]

- `ExecInitParallelPlan(planstate, EState, sendParams, nworkers,
  tuples_needed)` — build pcxt, allocate DSM, serialize plan tree,
  prepare tuple queues.
- `ExecParallelCreateReaders(pei)` — after workers launched, build
  reader objects.
- `ExecParallelFinish(pei)` — drain queues, merge stats.
- `ExecParallelCleanup(pei)` — release DSM/DSA.
- `ExecParallelReinitialize(planstate, pei, sendParams)` — for
  rescans (e.g. nested-loop with parallel inner side).

### Worker entry point [line 49]

`ParallelQueryMain(dsm_segment *seg, shm_toc *toc)` — the
`pg_main` for parallel-query workers; registered by the bgworker
infrastructure.

## Invariants

- **INV-LEADER-COPY** [inferred from how `ExecInitParallelPlan`
  serializes] Plan tree, range table, dest receiver type, GUCs in
  effect, snapshot, transaction state, `MyClientPort` is NOT sent
  — workers cannot send results to a client.
- **INV-NWORKERS-FIXED** [inferred] `nworkers` is set at init; you
  cannot add workers mid-query. Workers that fail to launch reduce
  effective parallelism but don't fail the query.
- **INV-SENDPARAMS** [verified-by-code: line 41] `sendParams`
  bitmap of PARAM_EXEC IDs to ship; serialized into the DSM at
  init / reinit.

## Trust boundary (Phase D)

**Heavy Phase D surface — workers inherit leader state.**

A parallel worker starts with a *copy* of the leader's:
- **Active snapshot** — workers see the leader's MVCC view (good).
- **User identity** (`CurrentUserId`, `SessionUserId`,
  `OuterUserId`) — workers run AS the leader's effective user.
- **`SecurityRestrictionContext`** — propagated so SECURITY DEFINER
  context survives.
- **`search_path`** — copied.
- **GUC values** — set by `RestoreGUCState`; only `PGC_USERSET`-
  level changes from the leader's session propagate (this is what
  the parallel-leader-only GUCs mechanism enforces).
- **PARAM_EXEC values** for `sendParams`.

The trust posture:

- A worker is essentially a *fork* of the leader's permission
  state. Parallel-safe/restricted function labelling is what
  prevents a worker from issuing side-effecting calls.
- **Snapshot crossover**: if the leader's snapshot ages out (long
  parallel query) the worker still uses the leader's snapshot — no
  cross-snapshot leak. Good.
- **DSM lifecycle**: a worker that segfaults and the DSM stays
  mapped — but the parallel-context's `on_dsm_detach` callbacks
  release locks/buffers held by the dying worker.
- **Tuple-queue output** (`tqueue.h`): if a worker writes garbage
  to a tuple queue, leader's `TupleQueueReaderNext` will error —
  data corruption stays inside that query.

## Cross-refs

- `access/parallel.h` — `ParallelContext`, `RestoreGUCState`,
  parallel-worker lifecycle.
- `executor/tqueue.h` — tuple flow.
- `nodes/execnodes.h` — `PlanState` / `EState`.
- `executor/nodeGather.h` — leader-side consumer.
- A11 (parallel + FDW interaction).

## Issues

- [ISSUE-PHASE-D: worker inherits leader's user identity / search
  path / SecurityRestrictionContext / snapshot — any mis-labeled
  parallel-unsafe function called from a worker breaks the implicit
  security envelope (high, well-known PG security model)] —
  not commented in header; lives in `parallel.c`.
- [ISSUE-DOC: header gives no entry point to "what is sent to a
  worker" — that lives in `ExecParallelInitializeDSM` in
  `execParallel.c` (medium)] — entire file.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
