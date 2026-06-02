# Parallel C code via ParallelContext — baseline

The ParallelContext API in `access/parallel.h` lets you run parallel C
code outside the executor. The basic lifecycle is:

1. `EnterParallelMode()` — flips a backend flag that prevents the
   leader from assigning new XIDs while workers run.
2. `CreateParallelContext(library, function, nworkers)` — creates the
   context object. The library/function pair identifies the worker
   entry point.
3. Estimate the DSM size with `shm_toc_estimate_chunk` for each piece
   of shared state and `shm_toc_estimate_keys` for the count.
4. `InitializeParallelDSM(pcxt)` — actually allocates the DSM and sets
   up the TOC.
5. Allocate shared state with `shm_toc_allocate` and publish it with
   `shm_toc_insert(toc, key, ptr)`.
6. `LaunchParallelWorkers(pcxt)` — actually spawns the workers.
7. Optionally do leader work in parallel.
8. `WaitForParallelWorkersToFinish(pcxt)`.
9. `DestroyParallelContext(pcxt)`.
10. `ExitParallelMode()`.

The worker function has signature `void worker_main(dsm_segment *seg,
shm_toc *toc)` and must be exported with `PGDLLEXPORT` so
`load_external_function` can find it.

Inside the worker you call `shm_toc_lookup(toc, key, false)` to get
your shared state. There are reserved TOC keys used by the parallel
infrastructure itself — I think they're at the top of the uint64 range
to avoid collisions, so extensions should use small keys like 1, 2, 3.

What workers cannot do:
- They can't write to the database (no INSERT/UPDATE/DELETE, no DDL).
  This is because they share the leader's snapshot.
- They can't use temp tables.
- They can't use sequences.
- They can't take new heavyweight locks freely.
- They can't call PARALLEL UNSAFE functions.

For GUCs: yes, workers see the leader's GUC values. The parallel
infrastructure serializes the leader's state (snapshot, GUCs, xact
state, etc.) into the DSM during `InitializeParallelDSM`, and the
worker restores it before running your code. A SET in the leader
afterwards won't propagate to running workers.

You should also check `pcxt->nworkers_launched` after
`LaunchParallelWorkers` — under load the postmaster may launch fewer
than you asked for.
