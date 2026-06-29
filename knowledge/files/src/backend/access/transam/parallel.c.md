# parallel.c

- **Source path:** `source/src/backend/access/transam/parallel.c`
- **Lines:** 1673
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/parallel.h`,
  `source/src/backend/access/transam/README.parallel`, `xact.c`
  (`EnterParallelMode`, `SerializeTransactionState`),
  `storage/ipc/shm_mq.c`, `storage/ipc/dsm.c`.

## Purpose

Infrastructure for launching parallel workers. Builds a
`ParallelContext` over dynamic shared memory: serialize leader state
(GUCs, transaction state, snapshots, sinval, combocid, relmap, …),
launch bgworkers, route their errors via shm_mq, wait for them to
finish, and tear the segment down. [from-comment]
`source/src/backend/access/transam/README.parallel:1-25`.

## Top-of-file comment (verbatim)

```
parallel.c
   Infrastructure for launching parallel workers
```
[verified-by-code] `parallel.c:3-4`. The substantive narrative is in
the sibling `README.parallel` (218 lines).

## Public surface

- `CreateParallelContext(library_name, function_name, nworkers)` —
  `parallel.c:175` [verified-by-code]
- `InitializeParallelDSM(pcxt)` — `parallel.c:213` [verified-by-code]
- `ReinitializeParallelDSM(pcxt)` — `parallel.c:511` [verified-by-code]
- `ReinitializeParallelWorkers(pcxt, n)` — `parallel.c:568`
  [verified-by-code]
- `LaunchParallelWorkers(pcxt)` — `parallel.c:583` [verified-by-code]
- `WaitForParallelWorkersToAttach(pcxt)` — `parallel.c:702`
  [verified-by-code]
- `WaitForParallelWorkersToFinish(pcxt)` — `parallel.c:805`
  [verified-by-code]
- `WaitForParallelWorkersToExit(pcxt)` — `parallel.c:919`
  [verified-by-code]
- `DestroyParallelContext(pcxt)` — `parallel.c:959` [verified-by-code]
- `ParallelContextActive(void)` — `parallel.c:1033` [verified-by-code]
- Worker entrypoint glue: `ParallelWorkerMain` — `parallel.c:1301`
  [verified-by-code]
- `ParallelWorkerReportLastRecEnd(last_xlog_end)` — `parallel.c:1594`
  [verified-by-code]
- Message handling: `HandleParallelMessageInterrupt`,
  `ProcessParallelMessages`, `ProcessParallelMessage` —
  `parallel.c:1046-1262` [verified-by-code]
- xact hooks: `AtEOSubXact_Parallel`, `AtEOXact_Parallel` —
  `parallel.c:1263, 1284` [verified-by-code]

## Key types

- `ParallelContext` — declared in `parallel.h`. Holds leader+worker
  bookkeeping, DSM segment, shm_toc, shm_mq array, worker registration
  array, entrypoint name.
- `FixedParallelState` — fixed-size record in DSM with leader's
  PGPROC, database, user, parallel-master-pid, last-xlog-end, etc.
  (Defined in this file.) [verified-by-code]

## Key invariants and locking

1. **Worker state must match leader at launch.** Leader serializes
   xact state, GUCs, snapshot, combocid, sinval queue, relmap,
   reindex state, etc.; worker deserializes before invoking the
   entrypoint. [from-README] (README.parallel).

2. **Parallel mode is recursive and reference-counted.**
   `EnterParallelMode` / `ExitParallelMode` (in `xact.c`) maintain
   `parallelModeLevel`; while > 0, many ops are restricted.

3. **Workers cannot write WAL on behalf of the leader's commit.**
   `xact.c:CommitTransaction` for `TBLOCK_PARALLEL_INPROGRESS` skips
   `RecordTransactionCommit` and instead calls
   `ParallelWorkerReportLastRecEnd` to give the leader the WAL
   high-water mark. [verified-by-code] `xact.c:2409-2422`,
   `parallel.c:1594`.

4. **`pg_atomic_*` is used for `last_xlog_end` aggregation.**
   The DSM-resident counter is updated atomically; leader reads it on
   wait-for-finish. [verified-by-code] (around `parallel.c:1594-1620`).

5. **Worker errors propagate through shm_mq as `'E'` messages.**
   `ProcessParallelMessage` translates them into local
   `ereport(ERROR, …)`. [verified-by-code] `parallel.c:1146-1262`.

## Functions of note

### `CreateParallelContext` / `InitializeParallelDSM` —
`parallel.c:175, 213` [verified-by-code]

The two-step pattern: allocate the context struct (estimating sizes),
then create the DSM and populate it (TOC entries for transaction
state, snapshot, GUCs, error queue, fixed state, etc.).

### `LaunchParallelWorkers` — `parallel.c:583` [verified-by-code]

Registers `nworkers` bgworkers via `RegisterDynamicBackgroundWorker`,
each running `ParallelWorkerMain` with the DSM handle.

### `ParallelWorkerMain` — `parallel.c:1301` [verified-by-code]

Worker entrypoint. Attaches DSM, sets up libpq error redirect to the
leader's shm_mq, deserializes leader state into worker state, calls
`StartParallelWorkerTransaction` (xact.c), then dispatches to the
named function via `LookupParallelWorkerFunction`.

### `WaitForParallelWorkersToFinish` — `parallel.c:805`
[verified-by-code]

Drains error queues, accumulates `XactLastRecEnd` from each worker's
fixed-state slot into the leader's `XactLastRecEnd`. Errors out the
leader if any worker reported an error.

## Cross-references

- `xact.c`: `EnterParallelMode` / `ExitParallelMode`,
  `SerializeTransactionState`, `StartParallelWorkerTransaction`,
  `EndParallelWorkerTransaction`.
- `postmaster/bgworker.c`: registers dynamic workers.
- `storage/ipc/shm_mq.c`: error queue transport.
- `executor/execParallel.c`: parallel-aware executor users.
- `access/{nbtree,gin,brin}xlog`-adjacent: parallel index builds.
- `utils/snapmgr.c`: snapshot serialization helpers.

## Open questions

- Exact GUC subset serialized vs. left to inherit from postmaster
  defaults not enumerated here. [unverified]
- The interaction between worker fork-time `_PG_init` libraries and
  the leader's `shared_preload_libraries` not fully analyzed.
  [unverified]

## Confidence tag tally

- `[verified-by-code]`: 21
- `[from-comment]`: 1
- `[from-README]`: 1
- `[unverified]`: 2

## Synthesized by
<!-- backlinks:auto -->
- [idioms/bgworker-and-parallel.md](../../../../../idioms/bgworker-and-parallel.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/parallel-context-and-dsm.md](../../../../../idioms/parallel-context-and-dsm.md)
- [idioms/parallel-state-propagation.md](../../../../../idioms/parallel-state-propagation.md)
- [idioms/parallel-worker-coordination.md](../../../../../idioms/parallel-worker-coordination.md)
- [idioms/parallel-worker-launch-wait-and-errors.md](../../../../../idioms/parallel-worker-launch-wait-and-errors.md)
- [idioms/snapshot-export-historic-parallel.md](../../../../../idioms/snapshot-export-historic-parallel.md)

