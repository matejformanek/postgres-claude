# Extension-driven parallel C code via ParallelContext

## Two-layer choice (and why ParallelContext is correct here)

| Goal | Use |
|---|---|
| Build a parallel-aware executor node | `execParallel.c` overrides |
| Run arbitrary parallel C code from an extension | **`ParallelContext` API** (this case) |
| Just expose a function to a parallel plan | mark it `PARALLEL SAFE` |

The `ParallelContext` API lives in `source/src/include/access/parallel.h`.
Parallel `CREATE INDEX` is a real in-tree consumer.

## Lifecycle of calls

[verified-by-code `source/src/include/access/parallel.h:64-72`;
`source/src/backend/access/transam/parallel.c`]

```c
EnterParallelMode();

pcxt = CreateParallelContext("myext",            /* library  */
                             "myext_par_main",   /* function */
                             nworkers);

/* Estimate DSM size — one chunk_estimate per piece of shared state,
 * plus a matching keys_estimate. */
shm_toc_estimate_chunk(&pcxt->estimator, sizeof(MyState));
shm_toc_estimate_keys (&pcxt->estimator, 1);

InitializeParallelDSM(pcxt);          /* allocates DSM, sets up TOC,
                                         serialises snapshot/GUCs/xact */

/* Publish shared state. */
MyState *st = shm_toc_allocate(pcxt->toc, sizeof(MyState));
init_my_state(st);
shm_toc_insert(pcxt->toc, MY_KEY_STATE, st);

LaunchParallelWorkers(pcxt);
/* pcxt->nworkers_launched is the ACTUAL count — may be < requested
 * if max_parallel_workers is saturated. Always check this. */

/* Optionally do leader-side work in parallel with workers. */

WaitForParallelWorkersToFinish(pcxt); /* errors re-raised here */
DestroyParallelContext(pcxt);

ExitParallelMode();
```

## Worker entry point

The function name passed to `CreateParallelContext` must resolve via
`load_external_function(library_name, function_name, ...)` in the
worker. So it must be `PGDLLEXPORT` and the signature is fixed:

```c
PGDLLEXPORT void myext_par_main(dsm_segment *seg, shm_toc *toc);
```

[verified-by-code `source/src/include/access/parallel.h:25`]

Inside the worker:

- `ParallelWorkerNumber` is the worker index (≥ 0); `IsParallelWorker()`
  is true.
- Look up your shared state by key: `shm_toc_lookup(toc, MY_KEY_STATE, false)`.
- Snapshot, GUCs, transaction state, combo CIDs, user/db OIDs are
  already restored by `ParallelWorkerMain` *before* your function runs.
- Errors: just `ereport(ERROR, ...)` — the error message is sent back
  through the per-worker error queue and re-raised in the leader by
  `WaitForParallelWorkersToFinish`.

## Reserved TOC key range

Don't collide with core. PG reserves the high range
**`0xFFFFFFFFFFFF0001 .. 0xFFFFFFFFFFFF000F`** for fixed parallel
state (`PARALLEL_KEY_FIXED`, `PARALLEL_KEY_GUC`, `PARALLEL_KEY_SNAPSHOT`,
`PARALLEL_KEY_TRANSACTION_STATE`, etc.). Extension code should use
small unsigned ints (`0x0001`, `0x0002`, ...) — they are disjoint from
the reserved range.

[verified-by-code `source/src/backend/access/transam/parallel.c:67-81`]

## What workers cannot do

A parallel worker must not:

- **Modify the database** — no INSERT/UPDATE/DELETE, no DDL. Workers
  share the leader's snapshot/XID; sibling writes under the same XID
  break MVCC.
- **Use temp tables or sequences** (`nextval` allocates an XID-ish
  resource).
- **Acquire locks not already held by the leader**, other than buffer
  locks.
- **Modify persistent backend state** — no prepared statements, LISTEN,
  etc.
- **Call any `PARALLEL UNSAFE` function.**

This is enforced upstream of execution by the planner via
`pg_proc.proparallel` markings.

## Yes — workers see leader's GUCs at launch time

`InitializeParallelDSM` serialises the leader's full GUC state into
`PARALLEL_KEY_GUC`; `ParallelWorkerMain` restores it before your
function runs. So workers see *exactly* the leader's GUC values at
launch time. A later `SET` in the leader (or any other backend) does
**not** propagate to workers already running.

## Estimate / allocate symmetry — common gotcha

Every `shm_toc_allocate` you'll do after `InitializeParallelDSM` must
be matched by a *prior* `shm_toc_estimate_chunk` + bump of
`shm_toc_estimate_keys`. The TOC is fixed-size after init; forgetting
an estimate either trips an assertion (debug) or silently corrupts
memory (release).

## Checklist (SKILL.md §3.6)

- [x] `EnterParallelMode` / `ExitParallelMode` bracket.
- [x] Estimate-then-allocate symmetry for every TOC chunk.
- [x] TOC keys are small ints, not in `0xFFFFFFFFFFFF000x` range.
- [x] Worker function is `PGDLLEXPORT` with the
      `(dsm_segment*, shm_toc*)` signature.
- [x] Check `pcxt->nworkers_launched` — may be less than requested.
- [x] Worker only reads (no DB writes, no temp, no sequences, no
      non-buffer locks).
