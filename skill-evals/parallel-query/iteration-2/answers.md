# Iteration 2 — answers (with_skill vs baseline)

(Same three prompts as iteration 1. Baseline answers unchanged. with_skill
answers updated to reflect the new §5b + expanded §8 in SKILL.md.)

## Eval 1 — Make `nodeFoo` parallel-aware

### with_skill answer

`nodeFoo` is a custom executor node. To participate in parallel execution
it plumbs into `src/backend/executor/execParallel.c`.

**Files to touch:**

- `src/backend/executor/nodeFoo.c` — implement the five hook functions.
- `src/backend/executor/execParallel.c` — add a `case T_FooState:` branch
  (gated on `planstate->plan->parallel_aware`) to the three
  `switch (nodeTag(planstate))` blocks inside `ExecParallelEstimate`,
  `ExecParallelInitializeDSM`, and `ExecParallelReInitializeDSM`.
- `src/include/executor/nodeFoo.h` — prototype the five hooks.
- Path-creation site in the optimizer (e.g. `allpaths.c`) — set
  `path->parallel_aware = true`, which the resulting `Plan` inherits and
  the executor's per-node dispatch reads.

**The five hooks (signatures per skill §8):**

```c
void ExecFooEstimate         (FooState *node, ParallelContext       *pcxt);
void ExecFooInitializeDSM    (FooState *node, ParallelContext       *pcxt);
void ExecFooReInitializeDSM  (FooState *node, ParallelContext       *pcxt);
void ExecFooInitializeWorker (FooState *node, ParallelWorkerContext *pwcxt);
void ExecFooShutdown         (FooState *node);
```

Note the worker hook takes `ParallelWorkerContext *`, not
`ParallelContext *` — easy to miss and the compiler will yell at you.

**Call order — leader (in `ExecInitParallelPlan`):**

1. `ExecParallelEstimate` walks the plan tree → calls
   `ExecFooEstimate(node, pcxt)`. Inside, call
   `shm_toc_estimate_chunk(&pcxt->estimator, sizeof(FooParallelState))`
   AND `shm_toc_estimate_keys(&pcxt->estimator, 1)` for each chunk
   you'll allocate. Both calls are required (skill §3 + checklist).
2. `InitializeParallelDSM(pcxt)` sizes and allocates the DSM.
3. `ExecParallelInitializeDSM` walks the tree → calls
   `ExecFooInitializeDSM(node, pcxt)`. Inside, do
   `shm_toc_allocate(pcxt->toc, sizeof(FooParallelState))`, init the
   struct, then `shm_toc_insert(pcxt->toc, plan_node_id, ptr)` (using
   `node->ss.ps.plan->plan_node_id` as the key — see
   `ExecSeqScanInitializeDSM` at nodeSeqscan.c:391-412).
4. `LaunchParallelWorkers(pcxt)`. Check `pcxt->nworkers_launched` —
   postmaster may give fewer than asked, possibly 0; plan a leader-only
   code path.

**Call order — worker (in `ParallelQueryMain`):**

5. Worker attaches to DSM. `ExecParallelInitializeWorker` walks the tree
   and calls `ExecFooInitializeWorker(node, pwcxt)`. Inside,
   `node->pstate = shm_toc_lookup(pwcxt->toc, plan_node_id, false)` and
   stash on `FooState`.

**On rescan:**

6. Leader calls `ExecParallelReInitializeDSM` → `ExecFooReInitializeDSM`.
   Reset state in place in the shared chunk; don't re-allocate (chunk
   stays in the TOC).

**Picking a TOC key:**

Two reserved high-magic ranges to avoid (skill §3):
- `0xFFFFFFFFFFFF0001..000F` — `parallel.c` infrastructure
  (`PARALLEL_KEY_FIXED`, `PARALLEL_KEY_GUC`, snapshots, etc.).
- `0xE000000000000001+` — `execParallel.c`-owned
  (`PARALLEL_KEY_EXECUTOR_FIXED`, `PARALLEL_KEY_PLANNEDSTMT`,
  instrumentation, DSA).

Per-node code uses `plan_node_id` (a small int) as the key — guaranteed
unique per node and clear of both ranges.

**Worker startup state restoration**

By the time `ExecFooInitializeWorker` runs, the worker has already had
transaction state, the active and transaction snapshots, GUC values,
combo CID hash, relmapper, and pending syncs restored by
`ParallelWorkerMain` from the high-magic `PARALLEL_KEY_*` chunks. The
node hook just looks up your own chunk.

`[verified-by-skill §3,§8]` `[verified-by-code source/src/backend/executor/execParallel.c:60-69,246-345,480-593]`
`[verified-by-code source/src/backend/executor/nodeSeqscan.c:391-412,437+]`

### baseline answer

(Unchanged from iter-1. See iteration-1/answers.md.)

You'd write a parallel-aware version of `nodeFoo` by adding hook
functions that match what other scan nodes do — there's something like
`ExecFooEstimate`, `ExecFooInitializeDSM`, and an Initialize-worker
function. The executor's parallel machinery (somewhere in execParallel.c)
walks the plan tree and calls these on each node that is marked
`parallel_aware`. Order is roughly: leader walks the tree to size the
DSM, then allocates it, then walks the tree again to populate shared
state, then launches workers; each worker attaches to the DSM and walks
the tree to fetch its starting state. There's also a reinit step for
rescans. Keys into the shm_toc — I'd pick large `uint64` constants and
hope they don't collide with whatever the infrastructure uses. Worker
fetches state by calling `shm_toc_lookup` with the same key. Transaction
/ snapshot state is handled for me by the parallel infrastructure
before my worker function runs. I'm not sure of the exact function
signatures or where the executor switch on nodeTag lives, and I don't
remember the specific reserved key range.

---

## Eval 2 — Parallel-safety for a bcrypt-row-hashing C function

### with_skill answer

Base case: **PARALLEL SAFE** (`s` in `pg_proc.dat`). Pure compute of
arguments, no DB access, no session state. Skill §2 lists exactly the
triggers that would push it elsewhere — none of them apply to a hash of
the input bytes.

**Why it matters here specifically:** index expressions get evaluated in
two contexts — DML (always leader-only because writes are themselves
parallel-unsafe) and `CREATE INDEX`. Btree has a parallel-aware build
that benefits from a SAFE-marked expression (skill §2 "Index-expression
context"). Marking SAFE keeps the parallel-build path legal; marking it
UNSAFE forces leader-only.

**Variant (a) reads from a temp table → PARALLEL UNSAFE.** Skill §2 +
§5 are explicit: temp tables are one of the canonical UNSAFE triggers
because workers don't share the leader's per-backend temp namespace.

**Variant (b) `SET LOCAL work_mem = '1GB'` → PARALLEL RESTRICTED**
(skill §7). The function mutates GUC state. Plain GUCs are *inherited*
by workers at launch via `RestoreGUCState` (one-shot at parallel-worker
startup), but **changing** a GUC inside a parallel block requires
`GUC_ALLOW_IN_PARALLEL` on the GUC, which `work_mem` does not carry.
With RESTRICTED, the planner may still parallelise the plan but forces
this function to run in the leader's portion only — the leader can
mutate its own GUC stack safely. If you mark it SAFE, a worker
attempting `SET LOCAL` will error out at runtime. If you mark it
UNSAFE, the entire plan loses parallelism even when the function isn't
in the parallel subtree (per skill §2 table). RESTRICTED is the right
middle ground.

**Variant (c) wrapper calls an UNSAFE pl/pgsql function → PARALLEL
UNSAFE on the wrapper.** Skill §2's last paragraph + §5 final sentence:
the planner trusts your declared `proparallel`. Marking the wrapper SAFE
while it calls UNSAFE leads to runtime breakage inside the worker. The
rule: marking must be the most restrictive of self and all callees.
(`proparallel` is not transitive at runtime — the planner doesn't walk
callees, it trusts your label.)

`[verified-by-skill §2,§5,§7]`

### baseline answer

(Unchanged from iter-1.)

Base: PARALLEL SAFE. (a) UNSAFE for temp table. (b) RESTRICTED because
it changes session state; whether SAFE would error or silently misbehave
I'm not 100% sure. (c) UNSAFE on the wrapper because most-restrictive
must propagate; the planner trusts your declaration.

---

## Eval 3 — Why advisory userlocks fail; the right rendezvous

### with_skill answer

**Why it's broken — the lock-group bypass (skill §5b):**

Parallel workers join the leader's lock group via
`BecomeLockGroupMember(leader_pgproc, leader_pid)` in
`ParallelWorkerMain` (parallel.c:1392-1403). The lock manager's
`LockCheckConflicts` then treats locks held by other group members as
*non-conflicting* — see lock.c:1610-1614: "Locks held in conflicting
modes by members of our own lock group are not real conflicts; we can
subtract those out."

So if the leader took `LOCKTAG_USERLOCK` X in EXCLUSIVE mode, a worker
calling `LockAcquire` on the same tag in EXCLUSIVE mode is granted
immediately — the group-leader's hold is subtracted out. The author's
mental model is exactly backwards: the lock manager goes out of its way
to make workers and leader **not** block on each other, because the
leader holds table/index/catalog locks during plan execution and
deadlocking against its own workers would be catastrophic.

The one carve-out is `LOCKTAG_RELATION_EXTEND`, which conflicts even
within a group (lock.c:1600-1608). It exists so that two backends in
the same lock group can't both try to extend a relation file
simultaneously. It doesn't apply to userlocks and isn't usable from
extension code anyway.

Net: userlocks between leader and workers are no-ops for mutual
exclusion. The "synchronisation" the author imagines isn't happening.

**The right pattern — DSM primitives (skill §5b table):**

| Need | Primitive |
|---|---|
| Wait/signal | `ConditionVariable` + `ConditionVariableSleep` / `Broadcast` |
| Streaming | `shm_mq` (parallel infra already uses one per worker for error queues — see `PARALLEL_KEY_ERROR_QUEUE`) |
| Short crit-section | `LWLock` allocated on DSM via `LWLockNewTrancheId` + `LWLockInitialize` |
| N-way phase sync | `Barrier` (parallel hash join is the canonical user) |
| Simple flags | `pg_atomic_uint32` + memory barriers |

Implementation pattern: allocate the primitive's storage inside the
shm_toc chunk during `InitializeDSM`, look it up via `shm_toc_lookup`
inside `InitializeWorker`. The standard CV wait loop (skill §5b):

```c
ConditionVariablePrepareToSleep(&shared->cv);
while (!shared->ready)
    ConditionVariableSleep(&shared->cv, WAIT_EVENT_EXTENSION);
ConditionVariableCancelSleep();
```

The LWLock vs lock-manager distinction matters: LWLocks are a separate
subsystem and the lock-group bypass does NOT apply to them. An LWLock
in DSM is the right tool for "leader and workers must take turns
mutating shared state".

`[verified-by-skill §5b]` `[verified-by-code source/src/backend/storage/lmgr/lock.c:1600-1614]`
`[verified-by-code source/src/backend/access/transam/parallel.c:1392-1403]`

### baseline answer

(Unchanged from iter-1.)

PostgreSQL has a concept of lock groups — a parallel worker joins the
leader's group at startup, and the lock manager treats lock holds
within a group as compatible. So a worker calling `LockAcquire` on a
lock the leader already holds gets granted immediately, no waiting.
The right way to coordinate is via DSM-backed primitives: condition
variables, shared-memory atomics, or `shm_mq`. There's also a Barrier
abstraction for "all N workers reach this point before any advance" —
used by parallel hash join. The relation-extension lock has some
special carve-out where even group members conflict, but I'd have to
look that up. Don't recall the exact function name for joining the
lock group (`BecomeLockGroupMember`?) or the file:line where the
conflict bypass is implemented.
