# parallel.h

- **Source path:** `source/src/include/access/parallel.h`
- **Lines:** 83
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `parallel.c`, `README.parallel`.

## Purpose

Public interface for the parallel-worker infrastructure. Defines
`ParallelContext`, `ParallelWorkerContext`, and the
`CreateParallelContext` → `InitializeParallelDSM` →
`LaunchParallelWorkers` → `WaitForParallelWorkersToFinish` →
`DestroyParallelContext` lifecycle. [from-comment] `parallel.h:3-4`.

## Top-of-file comment (verbatim)

```
parallel.h
   Infrastructure for launching parallel workers
```
[verified-by-code] `parallel.h:3-4`.

## Key types

### `ParallelWorkerInfo` (`parallel.h:27-31`) [verified-by-code]

`{ BackgroundWorkerHandle *bgwhandle; shm_mq_handle *error_mqh; }`.

### `ParallelContext` (`parallel.h:33-50`) [verified-by-code]

The leader-side handle: `dlist_node node`, `SubTransactionId subid`,
worker counts (`nworkers`, `nworkers_to_launch`, `nworkers_launched`),
`library_name`/`function_name`, `error_context_stack`,
`shm_toc_estimator estimator`, `dsm_segment *seg`,
`private_memory`, `shm_toc *toc`, `ParallelWorkerInfo *worker`,
`nknown_attached_workers`, `known_attached_workers[]`.

### `ParallelWorkerContext` (`parallel.h:52-56`) [verified-by-code]

The worker-side handle: `{ dsm_segment *seg; shm_toc *toc; }`.

### `parallel_worker_main_type` (`parallel.h:25`) [verified-by-code]

`void (*)(dsm_segment *seg, shm_toc *toc)` — the worker entrypoint
signature looked up by name via `LookupParallelWorkerFunction`.

## Public surface

- Globals: `ParallelMessagePending` (signal flag),
  `ParallelWorkerNumber`, `InitializingParallelWorker`. Macro
  `IsParallelWorker() = (ParallelWorkerNumber >= 0)`.
  [verified-by-code] `parallel.h:58-62`.
- Lifecycle: `CreateParallelContext`, `InitializeParallelDSM`,
  `ReinitializeParallelDSM`, `ReinitializeParallelWorkers`,
  `LaunchParallelWorkers`, `WaitForParallelWorkersToAttach`,
  `WaitForParallelWorkersToFinish`, `DestroyParallelContext`,
  `ParallelContextActive`. [verified-by-code] `parallel.h:64-73`.
- Messages: `HandleParallelMessageInterrupt`,
  `ProcessParallelMessages`. [verified-by-code] `parallel.h:75-76`.
- xact hooks: `AtEOXact_Parallel`, `AtEOSubXact_Parallel`.
  [verified-by-code] `parallel.h:77-78`.
- Worker → leader handoff: `ParallelWorkerReportLastRecEnd(lsn)`.
  [verified-by-code] `parallel.h:79`.
- Worker entrypoint: `ParallelWorkerMain(Datum main_arg)`.
  [verified-by-code] `parallel.h:81`.

## Key invariants

1. **Workers identified by non-negative number.**
   `ParallelWorkerNumber = -1` in leader; `>= 0` in workers.
   [verified-by-code] `parallel.h:62`.

## Cross-references

- `parallel.c` is the implementation.
- `README.parallel` is the canonical narrative.

## Confidence tag tally

- `[verified-by-code]`: 13
- `[from-comment]`: 1
