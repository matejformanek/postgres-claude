# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

With_skill: 20/33 = 0.606. Baseline: 14/33 = 0.424. Lift: +0.18 — weak.

The skill scores well on the lifecycle mechanics it explicitly enumerates
(§3 + §4 + §6 + §7 + §8 names + checklist). It loses badly on:

1. **Eval-3 (lock-group trap)** — 0/11 with_skill on the lock-group bypass
   probe. §5 says "don't acquire non-buffer locks" but doesn't explain *why
   you can't even use them for rendezvous* (lock-group conflict bypass).
   This is the highest-value trap PG patches get wrong and the skill is silent.
2. **Eval-3 (rendezvous primitives)** — ConditionVariable / shm_mq / LWLock
   / Barrier are the actual leader↔worker sync primitives. Not named once
   in the skill. The skill correctly tells you what NOT to do but doesn't
   point at what TO do.
3. **Eval-1 (per-node dispatch site)** — §8 names the hooks but doesn't say
   you have to add a `case` to the `switch (nodeTag(...))` in
   `execParallel.c` (the actual call site). A reader implementing this will
   add the hooks and then wonder why they don't fire.
4. **Eval-1 (parallel_aware flag)** — never named. This is the gating bool
   the executor's per-node dispatch checks; without setting it you get the
   non-parallel path silently.
5. **Eval-1 (ParallelWorkerContext type)** — §8 doesn't show signatures.
   Worker-side hook takes `ParallelWorkerContext *pwcxt`, not
   `ParallelContext *pcxt`; this gotcha bites first-time authors.
6. **Eval-2 (parallel CREATE INDEX context)** — minor. Index expressions
   benefit from PARALLEL SAFE because btree has parallel build; skill doesn't
   give that context for the proparallel choice.

## Concrete edits to consider

### Edit 1 — Add §X "Leader/worker rendezvous: use DSM primitives, NOT the lock manager"

NEW section (placed between current §5 and §6). Text:

> ## 5b. Leader ↔ worker rendezvous — use DSM primitives
>
> Parallel workers join the leader's **lock group**
> (`BecomeLockGroupMember`, called from `ParallelWorkerMain`). The lock
> manager's `LockCheckConflicts` treats locks held by other group members
> as non-conflicting — that's how the leader's already-held table/index
> locks "inherit" to workers without deadlocking against the leader.
> [verified-by-code `source/src/backend/storage/lmgr/lock.c:1591-1614`]
> [verified-by-code `source/src/backend/access/transam/parallel.c:1395-1410`
> for `BecomeLockGroupMember` in worker startup]
>
> **Consequence — the trap:** heavyweight locks (including `LOCKTAG_USERLOCK`
> advisory locks) are useless for leader↔worker mutual exclusion. A worker's
> `LockAcquire` on a tag the leader holds is granted immediately. Don't try
> to "wait on the leader" via userlocks; the wait won't happen. The one
> carve-out is `LOCKTAG_RELATION_EXTEND`, which conflicts even within a
> group [verified-by-code `source/src/backend/storage/lmgr/lock.c:1601-1608`]
> — but only for that one tag, and you're not supposed to use it from
> extension code anyway.
>
> **Use these primitives instead** (all DSM-friendly):
>
> | Need | Primitive | Header |
> |---|---|---|
> | Wait/signal | `ConditionVariable` + `ConditionVariableSleep`/`Broadcast` | `storage/condition_variable.h` |
> | Streaming bytes | `shm_mq` (already used by parallel infra for per-worker error queue) | `storage/shm_mq.h` |
> | Short critical section | `LWLock` allocated via `LWLockNewTrancheId` + `LWLockInitialize` on DSM memory | `storage/lwlock.h` |
> | N-way phase sync | `Barrier` (used by parallel hash join) | `storage/barrier.h` |
> | Simple flags | `pg_atomic_uint32` + `pg_memory_barrier` | `port/atomics.h` |
>
> Allocate the primitive's storage inside your shm_toc chunk during
> `InitializeDSM`, then look it up with `shm_toc_lookup` in
> `InitializeWorker`. The standard CV wait loop is:
>
> ```c
> ConditionVariablePrepareToSleep(&shared->cv);
> while (!shared->ready)
>     ConditionVariableSleep(&shared->cv, WAIT_EVENT_EXTENSION);
> ConditionVariableCancelSleep();
> ```

Rationale: closes 9 of 11 Eval-3 assertion misses in a single section. This
is the single highest-value edit.

### Edit 2 — Expand §8 with the per-node dispatch site and parallel_aware flag

Replace current §8 with (additions in **bold**):

> ## 8. Plumbing into `execParallel.c` (executor-node view)
>
> For a custom executor node that wants to participate in parallel
> execution, **set `path->parallel_aware = true` (and the resulting
> `Plan` inherits it) so the executor's per-node dispatch fires**, then
> override these methods:
>
> - `ExecXXXEstimate(XxxState *node, ParallelContext *pcxt)` — add to the DSM size estimate.
> - `ExecXXXInitializeDSM(XxxState *node, ParallelContext *pcxt)` — allocate and initialize per-node shared state.
> - `ExecXXXReInitializeDSM(XxxState *node, ParallelContext *pcxt)` — reset per-iteration state (rescan).
> - `ExecXXXInitializeWorker(XxxState *node, ParallelWorkerContext *pwcxt)` — find and attach to the shared state in a worker. **Note the second parameter is `ParallelWorkerContext`, not `ParallelContext`.**
> - `ExecXXXShutdown(XxxState *node)` — collect per-worker stats before workers exit.
>
> **You also have to teach `execParallel.c` about your node.** Three `switch
> (nodeTag(planstate))` blocks dispatch into the per-node hooks — one each
> inside `ExecParallelEstimate`, `ExecParallelInitializeDSM`, and
> `ExecParallelReInitializeDSM`. Add a `case T_FooState:` branch to each
> (gated on `planstate->plan->parallel_aware`). See `T_SeqScanState`
> branches at execParallel.c:256-263 for the reference shape.
> [verified-by-code `source/src/backend/executor/execParallel.c:246-345,480-593,608-650`]
>
> **Executor-owned high-magic keys** (don't collide):
> `PARALLEL_KEY_EXECUTOR_FIXED = 0xE000000000000001`,
> `PARALLEL_KEY_PLANNEDSTMT = 0xE000000000000002`,
> instrumentation and DSA keys in the same `0xE...` range.
> [verified-by-code `source/src/backend/executor/execParallel.c:60-66`]
> Per-node code packs the `plan_node_id` into its keys so two parallel-aware
> nodes don't clash; see `nodeSeqscan.c` for the shape.

Rationale: closes 4 of 12 Eval-1 misses (parallel_aware flag, dispatch
switch, ParallelWorkerContext type, PARALLEL_KEY_EXECUTOR_FIXED).

### Edit 3 — Tighten §3 key range cite

Current §3 says the reserved internal range is `0xFFFFFFFFFFFF0001` ..
`0xFFFFFFFFFFFF000F`. That's correct for `parallel.c`'s parallel
infrastructure keys [verified-by-code
`source/src/backend/access/transam/parallel.c:67-81`]. But the executor
adds its own `0xE...` range on top. Add a one-line note:

> The executor adds a second reserved range on top: `0xE000000000000001` and
> up are used by `execParallel.c` for `PARALLEL_KEY_EXECUTOR_FIXED`,
> `PARALLEL_KEY_PLANNEDSTMT`, instrumentation, and DSA. If your code lives
> outside `execParallel.c`, stay clear of both ranges; use small ints.

Rationale: avoids silent key collisions in extension code that pokes into
the executor's TOC.

### Edit 4 — Cross-link `locking` for the lock-group story

Update the bottom Cross-references entry:

> - `.claude/skills/locking/SKILL.md` — what locks workers can/can't acquire;
>   **lock-group conflict bypass (`LockCheckConflicts` group-member rule)
>   and the `LOCKTAG_RELATION_EXTEND` carve-out**; predicate-lock implications.

Rationale: makes the trap discoverable from the locking side too.

### Edit 5 — Add note about parallel CREATE INDEX in §2

Append to §2 (after the markings table):

> **Context note for index expressions:** `CREATE INDEX` on btree can run
> in parallel (`max_parallel_maintenance_workers`); SAFE-marked expression
> functions allow that path. DML evaluation of index expressions runs
> leader-only regardless of marking.

Rationale: closes the Eval-2 CREATE INDEX context assertion. Low-priority.

### Edit 6 — Add `parallel_leader_participation` to §6

Append one line to §6:

> The GUC `parallel_leader_participation` (default on) controls whether
> the leader also runs the parallel subplan after launching workers. If
> off, the leader purely coordinates — relevant when picking
> `pcxt->nworkers` and reading `nworkers_to_launch` vs `nworkers_launched`.
> [verified-by-code `source/src/backend/utils/misc/guc_parameters.dat:2312-2316`]

Rationale: standard tuning knob in parallel-query planning discussions.

### Edit 7 — Replace the SeqScan/IndexScan reference-shape pointer with one concrete cite

§8 currently says "see `nodeSeqscan.c` / `nodeIndexscan.c` for reference
shapes." Tighten:

> See `ExecSeqScanInitializeDSM` and `ExecSeqScanInitializeWorker` in
> `source/src/backend/executor/nodeSeqscan.c:407-450` for the canonical
> per-node implementation shape.

Rationale: saves a grep.

## Non-edits

- §3 lifecycle, §6 nworkers_launched discipline, §7 GUC_ALLOW_IN_PARALLEL,
  and the §9 checklist are all good — keep as-is.
- The 5-hook list in §8 is correct; the issue is missing context around
  it, not the names.

## Expected score delta if all edits applied

Iter-1 with_skill: 20/33 (0.606), baseline: 14/33 (0.424).
- Edit 1: gains ~9 Eval-3 assertions → +0.27.
- Edit 2: gains ~4 Eval-1 assertions → +0.12.
- Edit 5: gains 1 Eval-2 assertion → +0.03.
- Edits 3/4/6/7 don't directly close iter-1 assertions but improve robustness.

Projected iter-2 with_skill: ≥ 32/33 (0.97).
