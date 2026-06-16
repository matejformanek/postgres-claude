---
name: parallel-query
description: Add parallel-aware C code in a PostgreSQL backend patch or extension — covers ParallelContext lifecycle (EnterParallelMode / CreateParallelContext / InitializeParallelDSM / LaunchParallelWorkers / WaitForParallelWorkersToFinish / DestroyParallelContext / ExitParallelMode), shm_toc DSM allocation + key lookup, ExecXXXInitializeDSM / ExecXXXInitializeWorker / ExecXXXReInitializeDSM hooks on plan nodes, and parallel-safety markings (pg_proc.proparallel s/r/u; PARALLEL SAFE / RESTRICTED / UNSAFE). Use whenever a PG patch or extension adds parallel-aware code, picks PARALLEL SAFE/RESTRICTED/UNSAFE for a SQL-callable function, extends execParallel.c, plumbs a worker shmem state via shm_toc, or debugs a parallel worker DSM/TOC issue. Skip for DBA tuning of max_parallel_workers GUC, OpenMP / CUDA / pthread / Tokio / Go-goroutine parallelism, JavaScript Promise.all and async-iter parallel fetches, generic worker-pool questions, and ML data-parallel training.
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

**Index-expression context:** `CREATE INDEX` on btree can run in parallel
(see `max_parallel_maintenance_workers`); a `SAFE`-marked expression
function allows the parallel-build path. DML evaluation of the same
expression runs leader-only regardless of marking, because DML itself is
parallel-unsafe.

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

Reserved TOC magic-number ranges (don't collide):

- `0xFFFFFFFFFFFF0001` .. `0xFFFFFFFFFFFF000F` — used by
  `access/transam/parallel.c` for fixed state, error queues, GUC state,
  snapshots, combo CIDs, etc. [verified-by-code
  `source/src/backend/access/transam/parallel.c:67-81`]
- `0xE000000000000001` and up — used by `executor/execParallel.c` for
  `PARALLEL_KEY_EXECUTOR_FIXED`, `PARALLEL_KEY_PLANNEDSTMT`,
  instrumentation, etc. (see §8). [verified-by-code
  `source/src/backend/executor/execParallel.c:60-69`]

Use small integers (`0x0001`, `0x0002`, ...) for your own keys to stay
clear of both ranges.

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

## 5b. Leader ↔ worker rendezvous — use DSM primitives, NOT the lock manager

Parallel workers join the leader's **lock group** during startup, via
`BecomeLockGroupMember(leader_pgproc, leader_pid)` called from
`ParallelWorkerMain`. [verified-by-code
`source/src/backend/access/transam/parallel.c:1392-1403`] The lock
manager's `LockCheckConflicts` then treats locks held by other group
members as non-conflicting — that's how the leader's already-held
table/index/catalog locks "inherit" to workers without deadlocking
against the leader. [verified-by-code
`source/src/backend/storage/lmgr/lock.c:1610-1614`]

**Consequence — the trap:** heavyweight locks (including
`LOCKTAG_USERLOCK` advisory locks) are **useless for leader↔worker
mutual exclusion**. A worker calling `LockAcquire` on a tag the leader
already holds is granted immediately. Don't try to "wait on the leader"
via userlocks; the wait won't happen. The one carve-out is
`LOCKTAG_RELATION_EXTEND`, which conflicts even within a group —
[verified-by-code `source/src/backend/storage/lmgr/lock.c:1600-1608`] —
but you can't use that tag from extension code anyway.

**Use these DSM-friendly primitives instead:**

| Need | Primitive | Header |
|---|---|---|
| Wait / signal | `ConditionVariable` + `ConditionVariableSleep` / `ConditionVariableBroadcast` | `storage/condition_variable.h` |
| Streaming bytes | `shm_mq` (already used by parallel infra for per-worker error queue, see `PARALLEL_KEY_ERROR_QUEUE`) | `storage/shm_mq.h` |
| Short critical section | `LWLock` allocated on DSM memory via `LWLockNewTrancheId` + `LWLockInitialize` | `storage/lwlock.h` |
| N-way phase sync | `Barrier` (used by parallel hash join) | `storage/barrier.h` |
| Simple flags | `pg_atomic_uint32` + memory barriers | `port/atomics.h` |

Allocate the primitive's storage inside your shm_toc chunk during
`InitializeDSM`, then look it up with `shm_toc_lookup` in
`InitializeWorker`. The standard CV wait loop is:

```c
ConditionVariablePrepareToSleep(&shared->cv);
while (!shared->ready)
    ConditionVariableSleep(&shared->cv, WAIT_EVENT_EXTENSION);
ConditionVariableCancelSleep();
```

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

`parallel_leader_participation` (default on) controls whether the
leader also runs the parallel subplan after launching workers. If off,
the leader purely coordinates — relevant when sizing `pcxt->nworkers`
and reading `nworkers_to_launch` vs `nworkers_launched`.
[verified-by-code
`source/src/backend/utils/misc/guc_parameters.dat:2312-2317`]

## 7. Custom GUCs visible to workers

Plain GUCs are inherited by workers via `RestoreGUCState` (called from
`ParallelWorkerMain`). For a custom GUC, the flag `GUC_ALLOW_IN_PARALLEL`
(see `gucs-config` §7) marks that it's safe to `SET` inside a parallel
block; without it, attempts to change the GUC inside a parallel
operation error out.

## 8. Plumbing into `execParallel.c` (executor-node view)

For a custom executor node that wants to participate in parallel
execution, set `path->parallel_aware = true` (the resulting `Plan`
inherits it) so the executor's per-node dispatch fires, then implement
these five hooks:

- `ExecXXXEstimate(XxxState *node, ParallelContext *pcxt)` — add to the
  DSM size estimate (call `shm_toc_estimate_chunk` + `_keys`).
- `ExecXXXInitializeDSM(XxxState *node, ParallelContext *pcxt)` —
  allocate and initialize per-node shared state; `shm_toc_insert` it.
- `ExecXXXReInitializeDSM(XxxState *node, ParallelContext *pcxt)` —
  reset per-iteration state (rescan); the chunk stays in the TOC, just
  reset its contents.
- `ExecXXXInitializeWorker(XxxState *node, ParallelWorkerContext *pwcxt)`
  — find and attach to the shared state in a worker. **Note the second
  parameter is `ParallelWorkerContext *`, not `ParallelContext *`.**
- `ExecXXXShutdown(XxxState *node)` — collect per-worker stats before
  workers exit.

**You also have to teach `execParallel.c` about your node.** Three
`switch (nodeTag(planstate))` blocks dispatch into the per-node hooks —
one each inside `ExecParallelEstimate`, `ExecParallelInitializeDSM`,
and `ExecParallelReInitializeDSM`. Add a `case T_FooState:` branch to
each (gated on `planstate->plan->parallel_aware`). See the
`T_SeqScanState` branches at execParallel.c:256-263 for the reference
shape. [verified-by-code
`source/src/backend/executor/execParallel.c:246-345,480-593`]

**Executor-owned high-magic key range** (don't collide):
`0xE000000000000001` and up are used by `execParallel.c` for
`PARALLEL_KEY_EXECUTOR_FIXED`, `PARALLEL_KEY_PLANNEDSTMT`,
`PARALLEL_KEY_PARAMLISTINFO`, instrumentation, DSA, and friends.
[verified-by-code
`source/src/backend/executor/execParallel.c:60-69`] Per-node code
typically uses the node's `plan_node_id` as its TOC key (an int that
won't collide with either high-magic range); see
`ExecSeqScanInitializeDSM` at
`source/src/backend/executor/nodeSeqscan.c:391-412` for the canonical
shape (it calls `shm_toc_insert(pcxt->toc,
node->ss.ps.plan->plan_node_id, pscan)`). Deep architecture lives in
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
- `.claude/skills/locking/SKILL.md` — what locks workers can/can't acquire; lock-group conflict bypass (`LockCheckConflicts` group-member rule) and the `LOCKTAG_RELATION_EXTEND` carve-out; predicate-lock implications.
- `.claude/skills/memory-contexts/SKILL.md` — DSM is not a `MemoryContext`; allocations are explicit shm_toc, not palloc.
- `knowledge/idioms/bgworker-and-parallel.md` — conceptual model.
- `knowledge/docs-distilled/parallel-query.md` — SGML-distilled reference.
- `knowledge/files/src/backend/access/transam/parallel.c.md` — per-file doc.
- `knowledge/files/src/include/access/parallel.h.md` — per-file doc.
