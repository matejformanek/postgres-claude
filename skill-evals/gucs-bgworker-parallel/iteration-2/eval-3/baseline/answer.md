# Extension-driven parallel C code via `ParallelContext`

## Lifecycle

```c
EnterParallelMode();

pcxt = CreateParallelContext("myext", "my_parallel_main", nworkers);

shm_toc_estimate_chunk(&pcxt->estimator, my_state_size);
shm_toc_estimate_keys (&pcxt->estimator, 1);

InitializeParallelDSM(pcxt);

my_state = shm_toc_allocate(pcxt->toc, my_state_size);
init_my_state(my_state);
shm_toc_insert(pcxt->toc, MY_KEY_STATE, my_state);

LaunchParallelWorkers(pcxt);
/* leader can also do work here */
WaitForParallelWorkersToFinish(pcxt);

DestroyParallelContext(pcxt);
ExitParallelMode();
```

## Sharing state via DSM

You allocate via the TOC: estimate first, `InitializeParallelDSM`,
then `shm_toc_allocate` + `shm_toc_insert` with a key of your choice.
The worker calls `shm_toc_lookup` with the same key to find its
state.

## TOC keys

There are some reserved magic numbers used internally by the parallel
infrastructure (very large `uint64` values like `0xFFFFFFFFFFFF...`).
Use distinct values for your own keys to avoid colliding with those.

## Worker function

Signature is something like `void f(dsm_segment *seg, shm_toc *toc)`.
It looks up state via the TOC and runs whatever work it needs.

## What workers cannot do

- No writes to the database (no DML, no DDL).
- No temp tables, no sequence operations.
- No acquiring of arbitrary heavyweight locks.
- No calls to PARALLEL UNSAFE functions.

## Do workers see the leader's GUCs?

Yes — `ParallelWorkerMain` propagates the leader's transaction state,
snapshot, and GUC values to each worker before user code runs.
