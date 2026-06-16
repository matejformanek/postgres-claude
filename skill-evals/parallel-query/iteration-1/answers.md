# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Make `nodeFoo` parallel-aware: files, hooks, key, call order

### with_skill answer

`nodeFoo` is a custom executor node. To participate in parallel execution it
plumbs into `src/backend/executor/execParallel.c`, which walks the plan tree
on the leader (estimate + init DSM phases) and on each worker (attach
phase).

**Files to touch:**

- `src/backend/executor/nodeFoo.c` — implement the five hook functions.
- `src/backend/executor/execParallel.c` — extend the `switch (nodeTag(...))`
  in `ExecParallelEstimate`, `ExecParallelInitializeDSM`,
  `ExecParallelReInitializeDSM` so the walker dispatches into your node when
  `planstate->plan->parallel_aware` is true. (See the `T_SeqScanState` etc.
  branches at execParallel.c:254-340.)
- `src/include/executor/nodeFoo.h` — prototype the five new functions.
- `src/backend/optimizer/path/allpaths.c` (or your add-path site) — set
  `parallel_aware = true` on the path/plan node when you want this branch
  taken.

**The five hooks (signatures match SeqScan):**

```c
void ExecFooEstimate(FooState *node, ParallelContext *pcxt);
void ExecFooInitializeDSM(FooState *node, ParallelContext *pcxt);
void ExecFooReInitializeDSM(FooState *node, ParallelContext *pcxt);
void ExecFooInitializeWorker(FooState *node, ParallelWorkerContext *pwcxt);
void ExecFooShutdown(FooState *node);  /* optional, before workers die */
```

**Call order — leader (in `ExecInitParallelPlan`, execParallel.c:659+):**

1. `ExecParallelEstimate` walks the plan tree → calls
   `ExecFooEstimate(node, pcxt)`. Inside, you call
   `shm_toc_estimate_chunk(&pcxt->estimator, sizeof(FooParallelState))` and
   `shm_toc_estimate_keys(&pcxt->estimator, 1)` for each chunk you'll
   allocate.
2. `InitializeParallelDSM(pcxt)` runs once — sizes + allocates the DSM, sets
   up the TOC.
3. `ExecParallelInitializeDSM` walks the tree → calls
   `ExecFooInitializeDSM(node, pcxt)`. Inside, you
   `shm_toc_allocate(pcxt->toc, sizeof(FooParallelState))`, initialise the
   struct, and `shm_toc_insert(pcxt->toc, MY_KEY, ptr)`.
4. `LaunchParallelWorkers(pcxt)`. Check `pcxt->nworkers_launched` —
   postmaster may give you fewer than asked, possibly 0.

**Call order — worker (in `ParallelQueryMain`):**

5. Worker attaches to DSM, runs `ExecParallelInitializeWorker` → calls
   `ExecFooInitializeWorker(node, pwcxt)`. Inside, you do
   `node->pstate = shm_toc_lookup(pwcxt->toc, MY_KEY, false)` and stash the
   pointer on `FooState`. (Note the parameter type is
   `ParallelWorkerContext`, not `ParallelContext`.)

**On rescan (e.g. nested loop driving outer side):**

6. Leader calls `ExecParallelReInitializeDSM` → `ExecFooReInitializeDSM`.
   Reset per-iteration state in the shared chunk in place; do NOT
   re-allocate (the chunk is already in the TOC).

**Picking a TOC key:**

The executor's per-plan-node key convention is a `uint64` derived from
`planstate->plan->plan_node_id` (left-shift into the high bits) so each node
gets its own keyspace. The reserved high-magic range
`0xFFFFFFFFFFFF0001 .. 0xFFFFFFFFFFFF000F` is used by
`access/transam/parallel.c` internals; the executor uses the
`0xE000000000000001`+ range (`PARALLEL_KEY_EXECUTOR_FIXED`,
`PARALLEL_KEY_PLANNEDSTMT`). Per-node code typically packs the
`plan_node_id` into the low bits and ORs a node-private constant in the
upper bits, so two parallel-aware nodes can't collide. (See
`nodeBitmapHeapscan.c` / `nodeSeqscan.c` for examples.)

**Worker startup state restoration**

By the time `ExecFooInitializeWorker` runs, the worker has already had
transaction state, the active and transaction snapshots, GUC values, the
combo CID hash, the relmapper, and pending syncs restored by
`ParallelWorkerMain` — these come from the high-magic `PARALLEL_KEY_*` chunks
that the parallel infrastructure (not the executor) put in the TOC. The
node hook just looks up your own chunk.

`[verified-by-code source/src/include/access/parallel.h:25-50,62-72]`
`[verified-by-code source/src/backend/executor/execParallel.c:60-61,246-345,480-593,659-925]`
`[verified-by-code source/src/backend/access/transam/parallel.c:60-81,591-626]`

### baseline answer

You'd write a parallel-aware version of `nodeFoo` by adding hook functions
that match what other scan nodes do — there's something like
`ExecFooEstimate`, `ExecFooInitializeDSM`, and an Initialize-worker function.
The executor's parallel machinery (somewhere in execParallel.c) walks the
plan tree and calls these on each node that is marked `parallel_aware`.

Order is roughly: leader walks the tree to size the DSM, then allocates it,
then walks the tree again to populate shared state, then launches workers;
each worker attaches to the DSM and walks the tree to fetch its starting
state. There's also a reinit step for rescans.

Keys into the shm_toc — I'd pick large `uint64` constants and hope they
don't collide with whatever the infrastructure uses. The worker fetches its
state by calling `shm_toc_lookup` with the same key. Transaction / snapshot
state is handled for me by the parallel infrastructure before my worker
function runs.

I'm not sure of the exact function signatures or where the executor switch
on nodeTag lives, and I don't remember the specific reserved key range —
I'd grep for `ExecSeqScanInitializeDSM` to find the reference shape.

---

## Eval 2 — Parallel-safety for a bcrypt-row-hashing C function

### with_skill answer

For the base case (pure compute on argument data, no DB access, no session
state): **PARALLEL SAFE**. It's a deterministic function of its inputs and
nothing it does touches anything a worker can't replicate. Mark it `s` in
`pg_proc.dat` (or `PARALLEL SAFE` in the `CREATE FUNCTION` SQL).

That matters because index expressions are evaluated during INSERT / UPDATE
(no parallelism — DML is parallel-unsafe by definition) and during
`CREATE INDEX` (where parallel-aware index builds for btree exist and want
to push expression evaluation into workers). Marking SAFE keeps `CREATE
INDEX` parallelism legal; marking it UNSAFE would force the leader-only path.

**Variant (a) — reads from a temp table:** `PARALLEL UNSAFE`. Workers
cannot access temp tables — they live in the leader's session-private
temp namespace, and workers don't share that. Even read-only access is
unsafe. This is one of the canonical UNSAFE-triggers.

**Variant (b) — `SET LOCAL work_mem = '1GB'`:** `PARALLEL RESTRICTED`,
**not** SAFE. The function mutates GUC state. Plain GUCs are inherited by
workers at launch via `RestoreGUCState`, but changing one inside a parallel
region requires the GUC to carry `GUC_ALLOW_IN_PARALLEL` (and `work_mem`
doesn't). With RESTRICTED, the planner may still parallelise the plan but
forces this function to run only in the leader's portion — the leader can
mutate its own GUC stack safely. If you mark it SAFE, a worker trying to
`SET LOCAL` will error out at runtime; if you mark it UNSAFE, the whole
plan loses parallelism even when the function happens not to be in the
parallel subtree.

**Variant (c) — wrapper calls a pl/pgsql function that is itself UNSAFE:**
the wrapper must be marked **PARALLEL UNSAFE**. The proparallel marking is
not transitive at runtime — the planner uses your declared marking as the
truth. If you lie (mark SAFE while calling UNSAFE), the planner will
parallelise plans that then break inside the worker (e.g. trying to write
the DB, or the pl/pgsql callee doing something only a leader can do). The
rule is: your function's marking must be the **most restrictive** of itself
and anything it transitively calls.

(Aside: for index expressions specifically, the leader's planner forbids
RESTRICTED and UNSAFE expressions from parallel `CREATE INDEX` paths
entirely — RESTRICTED is no better than UNSAFE in that one context. But
for general query planning RESTRICTED is strictly less constraining than
UNSAFE.)

`[verified-by-code source/src/include/catalog/pg_proc.h:79]` (proparallel
column) `[verified-by-code source/src/backend/access/transam/parallel.c:70]`
(`PARALLEL_KEY_GUC` — GUC state restored to workers at launch)

### baseline answer

Base case: PARALLEL SAFE — it's a deterministic compute over arguments,
nothing weird. Use `s` in `pg_proc.dat`.

(a) Temp table read — PARALLEL UNSAFE; workers can't see temp tables (the
temp schema is per-backend, and worker backends don't share the leader's
local-buffer state for the temp relation).

(b) `SET LOCAL work_mem` — I'd lean PARALLEL RESTRICTED here, because the
function changes session state. Some GUCs are okay to set in parallel
contexts and some aren't; I'd play it safe with RESTRICTED so it's
guaranteed to run in the leader. Whether SAFE would actually error or
silently misbehave I'm not 100% sure of.

(c) Wrapper calling an UNSAFE pl/pgsql — the wrapper must be UNSAFE; the
proparallel marking has to be the most restrictive of the function and
everything it calls. If you mark it SAFE, you'll get a runtime error inside
a worker. The planner trusts your declaration.

---

## Eval 3 — Why advisory userlock rendezvous is broken; the right pattern

### with_skill answer

**Why it's broken — the lock-group bypass:**

When a parallel worker starts up, `ParallelWorkerMain` calls
`BecomeLockGroupMember(leader_pgproc, ...)`, joining the leader's lock
group. The lock manager's `LockCheckConflicts` then treats locks held by
any member of the group as **non-conflicting** with the requesting group
member — comment at `lock.c:1611-1614`: "Locks held in conflicting modes by
members of our own lock group are not real conflicts; we can subtract those
out and see if we still have a conflict."

So if the leader took `LOCKTAG_USERLOCK` X in EXCLUSIVE mode, a worker
calling `LockAcquire` on the same tag in EXCLUSIVE mode will *not* block —
it'll be granted immediately because the group-leader's hold is subtracted
out. The author's mental model ("workers wait on the leader's lock") is
exactly backwards: the lock manager goes out of its way to make sure
workers and leader **don't** block on each other (otherwise a leader
holding a relation lock would deadlock its own workers the moment they
tried to touch the same table).

The one carve-out is `LOCKTAG_RELATION_EXTEND`, which conflicts even
within a lock group (`lock.c:1601-1608`) — but that's a special case and
doesn't apply to userlocks.

Net: userlocks between leader and workers are essentially no-ops for
mutual exclusion. The "synchronisation" the author thinks is happening
isn't.

**The right pattern:**

Leader/worker rendezvous in parallel-aware code uses DSM-backed primitives,
not the heavyweight lock manager:

1. **`ConditionVariable`** for wait/signal in shared memory. The leader
   `ConditionVariableInit`s a CV in its DSM chunk during
   `ExecFooInitializeDSM`; workers find it via `shm_toc_lookup` and call
   `ConditionVariableSleep(cv, WAIT_EVENT_FOO)`; the signaller calls
   `ConditionVariableBroadcast` or `ConditionVariableSignal`. Spurious
   wakeups are possible, so the standard loop is
   `while (!ready) ConditionVariableSleep(...); ConditionVariableCancelSleep();`.
2. **`shm_mq`** for point-to-point byte streams (the parallel infrastructure
   already uses `shm_mq` for per-worker error queues — see
   `PARALLEL_ERROR_QUEUE_SIZE` and `PARALLEL_KEY_ERROR_QUEUE` in
   `parallel.c:57-68`).
3. **Atomic flags + barriers** in the shared struct for simple state
   exchange (e.g. `pg_atomic_uint32` plus `pg_memory_barrier`).
4. **Lightweight locks** (`LWLock`) for short critical sections within the
   shared chunk. Allocate via `LWLockNewTrancheId` + `LWLockInitialize` on
   memory carved out of the DSM. (Lock-group exception does NOT apply to
   LWLocks — they're a separate subsystem.)
5. **`Barrier`** (`src/backend/storage/ipc/barrier.c`) for phase-style
   synchronisation when N workers must all reach a checkpoint before
   anyone advances (parallel hash join uses this).

The lock-group conflict bypass exists precisely to let the *leader's*
heavyweight locks (taken at plan time on tables, indexes, catalogs)
inherit-by-membership to the workers without forcing workers to
re-acquire and contend. Trying to repurpose that machinery for
intra-group signalling fights the design.

`[verified-by-code source/src/backend/storage/lmgr/lock.c:1591-1614]`
`[verified-by-code source/src/backend/access/transam/parallel.c:57-68,1395-1410]`
`[verified-by-code source/src/include/storage/condition_variable.h:32-60]`

### baseline answer

Heavyweight LOCKTAG_USERLOCK between a leader and its parallel workers
won't synchronise the way the author thinks. PostgreSQL has a concept of
lock groups — a parallel worker joins the leader's group at startup, and
the lock manager treats lock holds within a group as compatible (otherwise
the leader's already-held table locks would deadlock against its own
workers). So a worker calling `LockAcquire` on a lock the leader already
holds gets granted immediately, no waiting.

The right way to coordinate leader/worker is via DSM-backed primitives:
condition variables for wait/signal, shared-memory atomics for simple
flags, or message queues (`shm_mq`) for streaming data. The parallel
infrastructure already uses `shm_mq` internally for the per-worker error
queue so the leader sees worker errors. Lightweight locks on memory
allocated in your DSM segment work for short critical sections. There's
also a Barrier abstraction for "all N workers reach this point before
any advance" — used by parallel hash join I think.

I don't remember the exact function name for joining the lock group
(`BecomeLockGroupMember`?) or the file:line where the conflict bypass is
implemented. The relation-extension lock has some special carve-out where
even group members conflict, but I'd have to look that up.
