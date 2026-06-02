# Parallel C code from an extension via `ParallelContext`

## Lifecycle

```c
EnterParallelMode();

pcxt = CreateParallelContext("myext", "my_parallel_main", nworkers);

/* Estimate every DSM chunk + key BEFORE InitializeParallelDSM. */
shm_toc_estimate_chunk(&pcxt->estimator, my_state_size);
shm_toc_estimate_keys (&pcxt->estimator, 1);

InitializeParallelDSM(pcxt);          /* allocates DSM, sets up TOC */

/* Now populate. */
my_state = shm_toc_allocate(pcxt->toc, my_state_size);
init_my_state(my_state);
shm_toc_insert(pcxt->toc, MY_KEY_STATE, my_state);

LaunchParallelWorkers(pcxt);
/* pcxt->nworkers_launched may be < requested under load — check it! */

/* Optionally do leader work in parallel. */

WaitForParallelWorkersToFinish(pcxt);
DestroyParallelContext(pcxt);

ExitParallelMode();
```

[verified-by-code `source/src/include/access/parallel.h:64-72`]

## Gotcha: estimate-then-allocate symmetry

Every `shm_toc_allocate` call you make after `InitializeParallelDSM`
must be matched by a prior `shm_toc_estimate_chunk` + bump of
`shm_toc_estimate_keys`. Mismatch trips an assert in debug builds and
silently overruns the DSM segment in release.

## Reserved TOC key range

parallel.c uses keys `0xFFFFFFFFFFFF0001 .. 0xFFFFFFFFFFFF000F`
(FIXED, ERROR_QUEUE, LIBRARY, GUC, COMBO_CID, snapshots, xact state,
ENTRYPOINT, SESSION_DSM, PENDING_SYNCS, REINDEX_STATE,
RELMAPPER_STATE, UNCOMMITTEDENUMS, CLIENTCONNINFO). Use small ints
like `0x0001`, `0x0002` for your own keys — they're disjoint.
[verified-by-code `source/src/backend/access/transam/parallel.c:67-81`]

## Worker entry point

Must be a `PGDLLEXPORT` symbol resolvable in the library you passed
to `CreateParallelContext`, with this signature:

```c
PGDLLEXPORT void my_parallel_main(dsm_segment *seg, shm_toc *toc);
```

[verified-by-code `source/src/include/access/parallel.h:25`]

Inside, look up shared state with `shm_toc_lookup(toc, MY_KEY_STATE, false)`.
`ParallelWorkerNumber` is your 0-based index; `IsParallelWorker()` is true.

## What workers MUST NOT do

- Acquire locks not already held by the leader (other than buffer locks).
- Modify the database (no INSERT/UPDATE/DELETE, no DDL).
- Use temp tables or sequences.
- Change persistent backend state (prepared statements, NOTIFY/LISTEN).
- Call any `PARALLEL UNSAFE` function.

This is why the catalog markings matter — the planner uses
`pg_proc.proparallel` to decide which functions a parallel path can
contain. `s` (safe), `r` (restricted = leader only), `u` (unsafe =
no parallel plan at all). [verified-by-code
`source/src/include/catalog/pg_proc.h:79`]

## Does the worker see the leader's GUC values?

**Yes, at launch time.** `ParallelWorkerMain` deserializes the
leader's GUC snapshot from the DSM (via `PARALLEL_KEY_GUC`) and
restores it *before* your `my_parallel_main` runs — so workers start
with the exact GUC values the leader had at `LaunchParallelWorkers`.

What this **does not** do: propagate later changes. If the user
`SET`s a `PGC_USERSET` GUC in the leader after workers are running,
in-flight workers do not observe it.

(Same machinery restores transaction snapshot, combo CIDs, etc.)

## Checklist hits (§3.6)

- [x] `EnterParallelMode` paired with `ExitParallelMode`.
- [x] Estimate calls precede `InitializeParallelDSM` 1:1 with allocates.
- [x] TOC keys are small ints, no collision with `PARALLEL_KEY_*`.
- [x] Worker fn is `PGDLLEXPORT` and discoverable.
- [x] Workers read state via `shm_toc_lookup`, not globals.
- [x] `pcxt->nworkers_launched` checked before assuming requested count.
