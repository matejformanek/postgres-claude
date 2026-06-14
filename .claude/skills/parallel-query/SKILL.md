---
name: parallel-query
description: Parallel-query infrastructure in PostgreSQL backend / extensions — ParallelContext lifecycle (EnterParallelMode / CreateParallelContext / InitializeParallelDSM / LaunchParallelWorkers / WaitForParallelWorkersToFinish / DestroyParallelContext / ExitParallelMode), shm_toc estimate + allocate + insert + lookup, dsm_segment + TOC key namespace, ParallelWorkerNumber / IsParallelWorker, parallel-safety markings (pg_proc.proparallel s/r/u, PARALLEL SAFE / RESTRICTED / UNSAFE), execParallel.c hooks (ExecXXXInitializeDSM / ExecXXXInitializeWorker / ExecXXXReInitializeDSM), GUC_ALLOW_IN_PARALLEL. Use whenever a patch or extension adds parallel-aware code, marks a function's parallel safety, or extends execParallel.c. Skip generic threading questions and unrelated worker-pool questions.
when_to_load: Add parallel-aware C code in a patch or extension; mark a function's parallel safety in `pg_proc.dat`; extend a plan node with parallel execution; debug a parallel-worker shmem/TOC issue.
companion_skills:
  - bgworker-and-extensions
  - gucs-config
  - executor-and-planner
  - locking
  - memory-contexts
---

# parallel-query — parallel-query infrastructure

This is the procedural cookbook for parallel-query infrastructure in
the backend and in extensions. For the conceptual model see
`knowledge/idioms/bgworker-and-parallel.md` and
`knowledge/docs-distilled/parallel-query.md`.

This skill is one of three siblings that share the `_PG_init` /
postmaster-lifecycle boundary:
- `gucs-config` — custom GUC variables.
- `bgworker-and-extensions` — RegisterBackgroundWorker, shared-library hooks.
- **parallel-query** (this skill) — ParallelContext + parallel-safe markings.

## 1. Two layers — pick the right one

| Goal | Use |
|---|---|
| Build a parallel-aware **executor node** | Plumb into `execParallel.c` (override `ExecXXXInitializeDSM` / `ExecXXXInitializeWorker`). See `executor-and-planner`. |
| Run arbitrary parallel C code from an extension | Use the `ParallelContext` API directly (`access/parallel.h`) — §3 below. |
| Just expose a function to a query that may run in parallel | Mark it `PARALLEL SAFE` in `pg_proc.dat` and that's it. §2 below. |

## 2. Function parallel-safety markings

Catalog column `pg_proc.proparallel`. [verified-by-code
`source/src/include/catalog/pg_proc.h:79`]

| Value | SQL keyword | Meaning |
|---|---|---|
| `s` (default) | `PARALLEL SAFE` | Function may run in a worker. |
| `r` | `PARALLEL RESTRICTED` | Function may run in the leader only when plan is parallel. |
| `u` | `PARALLEL UNSAFE` | Plan must not be parallelised at all. |

Use **UNSAFE** if the function: writes to the DB, uses SQL that reads
sequences, touches session state (temp tables, prepared statements,
client connection), holds non-table relation locks across calls, calls
PL functions that aren't themselves safe.

Use **RESTRICTED** if the function: reads non-temp tables but needs the
leader's snapshot guarantees, or has costly setup that workers can't
replicate.

For SQL-callable C functions: set `proparallel` in your `pg_proc.dat`
entry; for `CREATE FUNCTION` in an extension SQL: always state it
explicitly (`PARALLEL SAFE` / `RESTRICTED` / `UNSAFE`) rather than
relying on the default.

## 3. ParallelContext lifecycle (extension-author view)

[verified-by-code `source/src/include/access/parallel.h:64-72`]

```c
EnterParallelMode();

/* Library and function must be PGDLLEXPORT and resolvable in workers. */
pcxt = CreateParallelContext("my_ext", "my_parallel_main", nworkers);

/* Estimate DSM size — call shm_toc_estimate_chunk / _keys for every
 * piece of shared state you'll insert later. */
shm_toc_estimate_chunk(&pcxt->estimator, my_state_size);
shm_toc_estimate_keys (&pcxt->estimator, 1);

InitializeParallelDSM(pcxt);    /* allocates the DSM, sets up TOC */

/* Populate shared state. Pick a key value > the PARALLEL_KEY_* range
 * reserved by parallel.c (use small unsigned ints — they're disjoint
 * from the 0xFFFFFFFFFFFF000x range). */
my_state = shm_toc_allocate(pcxt->toc, my_state_size);
init_my_state(my_state);
shm_toc_insert(pcxt->toc, MY_KEY_STATE, my_state);

LaunchParallelWorkers(pcxt);
/* pcxt->nworkers_launched is the actual count; may be < requested. */

/* Optionally do leader work in parallel with workers. */

WaitForParallelWorkersToFinish(pcxt);
DestroyParallelContext(pcxt);

ExitParallelMode();
```

Reserved TOC magic-number range used internally (don't collide):
`0xFFFFFFFFFFFF0001` .. `0xFFFFFFFFFFFF000F`. Use small integers like
`0x0001`, `0x0002`, ... for your own keys.
[verified-by-code `source/src/backend/access/transam/parallel.c:67-81`]

## 4. Worker entry point

The function name passed to `CreateParallelContext` must be a
`PGDLLEXPORT` symbol with signature:

```c
void my_parallel_main(dsm_segment *seg, shm_toc *toc);
```

[verified-by-code `source/src/include/access/parallel.h:25`]

Inside the worker:
- `ParallelWorkerNumber` is set to the worker index (`>= 0`).
  `IsParallelWorker()` is true. [verified-by-code
  `source/src/include/access/parallel.h:59-62`]
- Look up your shared state with `shm_toc_lookup(toc, MY_KEY_STATE, false)`.
- Transaction, snapshot, GUC state, combo CIDs, etc. are restored by
  `ParallelWorkerMain` *before* your function runs — you start with
  the leader's view of the world.
- Errors are propagated back to the leader via the per-worker error
  message queue; just `ereport(ERROR, ...)` as usual.

## 5. What workers can't do

A parallel worker must not:
- Acquire locks not already held by the leader (other than buffer locks).
- Modify the database (no INSERT/UPDATE/DELETE, no DDL).
- Use temp tables or sequences.
- Change persistent backend state (prepared statements, listening on
  notify channels, etc.).
- Call any `PARALLEL UNSAFE` function.

This is why function marking matters: the planner uses `proparallel`
to decide whether a path is allowed to contain parallelism at all
(`UNSAFE`), or allowed only in the leader's part of the plan
(`RESTRICTED`).

## 6. parallel_workers / max_parallel_workers GUC interplay

- `max_parallel_workers_per_gather` — per-Gather upper bound.
- `max_parallel_workers` — across-cluster upper bound (shared with
  `BGWORKER_CLASS_PARALLEL` slots; `bgworker-and-extensions` workers
  don't share this pool).
- `max_worker_processes` — total bgworker slots in postmaster (parallel
  + regular).

Always check `pcxt->nworkers_launched` after `LaunchParallelWorkers` —
the postmaster may launch fewer than requested under load. Plan code
paths for the leader-only case (`nworkers_launched == 0`).

## 7. Custom GUCs visible to workers

Plain GUCs are inherited by workers via `RestoreGUCState` (called from
`ParallelWorkerMain`). For a custom GUC, the flag `GUC_ALLOW_IN_PARALLEL`
(see `gucs-config` §7) marks that it's safe to `SET` inside a parallel
block; without it, attempts to change the GUC inside a parallel
operation error out.

## 8. Plumbing into `execParallel.c` (executor-node view)

For a custom executor node that wants to participate in parallel
execution, override these methods in your `Plan` /`PlanState`:

- `ExecXXXEstimate` — add to the DSM size estimate.
- `ExecXXXInitializeDSM` — allocate and initialize per-node shared state.
- `ExecXXXReInitializeDSM` — reset per-iteration state (rescan).
- `ExecXXXInitializeWorker` — find and attach to the shared state in a
  worker.
- `ExecXXXShutdown` — collect per-worker stats before workers exit.

The convention is one entry per `nodeXxx.c`; see `nodeSeqscan.c` /
`nodeIndexscan.c` for reference shapes. Deep architecture lives in
`executor-and-planner`.

## 9. Checklist

- [ ] `EnterParallelMode()` before `CreateParallelContext`, matching
      `ExitParallelMode()` after `DestroyParallelContext`.
- [ ] Every chunk in the DSM has matching `shm_toc_estimate_chunk` +
      `shm_toc_estimate_keys` calls *before* `InitializeParallelDSM`.
- [ ] TOC keys do not collide with `PARALLEL_KEY_*` (use small ints).
- [ ] Worker function is `PGDLLEXPORT` and findable by
      `load_external_function(library_name, function_name, ...)`.
- [ ] Worker reads shared state with `shm_toc_lookup`, not from globals.
- [ ] Worker never writes the DB, doesn't touch temp tables, doesn't
      acquire non-buffer locks unilaterally.
- [ ] Functions exposed via SQL have explicit `PARALLEL { SAFE |
      RESTRICTED | UNSAFE }` in `CREATE FUNCTION` — don't rely on the
      default `s`.
- [ ] `pcxt->nworkers_launched` is checked — postmaster may launch fewer
      workers than requested under load.
- [ ] Custom GUCs the parallel block sets at runtime carry
      `GUC_ALLOW_IN_PARALLEL` (see `gucs-config`).

## 10. Useful greps

- All `ParallelContext` callers:
  `grep -RIn 'CreateParallelContext' source/src source/contrib`
- Parallel-safety markings in catalog data:
  `grep -RIn 'proparallel' source/src/include/catalog`
- Per-node parallel hooks:
  `grep -RIn 'ExecParallelInitialize\|InitializeWorker' source/src/backend/executor`

## Open questions / [unverified]

- `[unverified]` Maximum number of TOC keys per DSM segment (likely
  bounded only by available DSM size).
- `[unverified]` Exact behaviour when a worker dies mid-execution
  without ereport — leader sees the worker count drop but may not
  always know why.

## Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` — non-parallel bgworker side; `BGWORKER_CLASS_PARALLEL` is for internal use only.
- `.claude/skills/gucs-config/SKILL.md` — `GUC_ALLOW_IN_PARALLEL` flag; GUC state inheritance by workers.
- `.claude/skills/executor-and-planner/SKILL.md` — per-node parallel hooks (`ExecXXXInitializeDSM` etc.); Gather/GatherMerge node shape.
- `.claude/skills/locking/SKILL.md` — what locks workers can/can't acquire; predicate-lock implications.
- `.claude/skills/memory-contexts/SKILL.md` — DSM is not a `MemoryContext`; allocations are explicit shm_toc, not palloc.
- `knowledge/idioms/bgworker-and-parallel.md` — conceptual model.
- `knowledge/docs-distilled/parallel-query.md` — SGML-distilled reference.
- `knowledge/files/src/backend/access/transam/parallel.c.md` — per-file doc.
- `knowledge/files/src/include/access/parallel.h.md` — per-file doc.
