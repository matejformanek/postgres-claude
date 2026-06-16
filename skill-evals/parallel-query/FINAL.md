# parallel-query — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/parallel-query/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 20 / 33 = 0.606 | 14 / 33 = 0.424 | +0.182 |
| Iteration 2 | 33 / 33 = 1.000 | 14 / 33 = 0.424 | +0.576 |

Iter-1 lift was weak (+0.18). After applying 7 verified edits, iter-2
with_skill clears all 33 assertions (100%) and the absolute lift jumps
to +0.576. Baseline is unchanged across runs (same prompts, same
honest-no-skill answers).

## What changed between iter-1 and iter-2

Seven edits from `iteration-1/proposed-edits.md` applied; the two most
load-bearing:

1. **Edit 1 — new §5b "Leader ↔ worker rendezvous: use DSM primitives,
   NOT the lock manager".** This is the most important edit. It closes
   the eval-3 trap completely: explains the lock-group conflict bypass
   in `LockCheckConflicts` (lock.c:1610-1614), the
   `LOCKTAG_RELATION_EXTEND` carve-out (lock.c:1600-1608), the
   `BecomeLockGroupMember` worker-startup site (parallel.c:1392-1403),
   and gives a 5-row primitives table (ConditionVariable, shm_mq,
   LWLock-on-DSM, Barrier, atomics) with the canonical CV wait loop.
   In iter-1 the skill scored 0/11 on this eval; in iter-2 it scores 11/11.
2. **Edit 2 — expanded §8 with the dispatch site + parallel_aware flag
   + ParallelWorkerContext type + executor key range.** Closes the
   eval-1 mechanics gap. Previously §8 named the five hooks but didn't
   say where the dispatch lives (the `switch (nodeTag(...))` in three
   places in execParallel.c) or which flag gates it (`parallel_aware`)
   or that the worker-side hook takes a different type
   (`ParallelWorkerContext *`, not `ParallelContext *`).

The other five edits (key-range two-bullet split in §3, locking
cross-ref, CREATE INDEX context paragraph in §2,
`parallel_leader_participation` mention in §6, precise nodeSeqscan.c
cite folded into §8) collectively closed the remaining iter-1 misses
(executor key constants, RESTRICTED-vs-UNSAFE planner detail).

## Source-value verifications performed

Before applying, the following claims were verified against `source/`:

- Lock-group conflict bypass at
  `source/src/backend/storage/lmgr/lock.c:1610-1614` (comment +
  subtract-out logic). Verified.
- `LOCKTAG_RELATION_EXTEND` carve-out at
  `source/src/backend/storage/lmgr/lock.c:1600-1608`. Verified.
- `BecomeLockGroupMember` worker-startup call at
  `source/src/backend/access/transam/parallel.c:1392-1403`. Verified.
- Executor PARALLEL_KEY range at
  `source/src/backend/executor/execParallel.c:60-69`
  (`PARALLEL_KEY_EXECUTOR_FIXED = 0xE000000000000001` etc.). Verified.
- Dispatch switch sites at
  `source/src/backend/executor/execParallel.c:246-345` (Estimate) and
  `:480-593` (InitializeDSM). Verified.
- `ExecSeqScanInitializeDSM` reference shape at
  `source/src/backend/executor/nodeSeqscan.c:391-412`, including the
  `shm_toc_insert(pcxt->toc, plan_node_id, pscan)` pattern. Verified.
- `ExecSeqScanInitializeWorker` signature
  (`SeqScanState *, ParallelWorkerContext *`) at
  `source/src/backend/executor/nodeSeqscan.c:437+`. Verified.
- `parallel_leader_participation` GUC at
  `source/src/backend/utils/misc/guc_parameters.dat:2312-2317`. Verified.
- Internal PARALLEL_KEY_* range at
  `source/src/backend/access/transam/parallel.c:67-81` (already cited
  in skill; re-verified). Verified.

All values used in the edits match source exactly.

## Gotchas surfaced during the eval

- **The lock-group conflict bypass is the highest-value parallel-query
  trap.** A reasonable mental model ("workers wait on the leader's lock")
  is exactly backwards in PG: the lock manager *makes sure they don't*.
  The skill now warns about this in §5b. If you only remember one thing
  about parallel-extension rendezvous, it's: heavyweight locks are
  group-internal no-ops between leader and workers.
- **The worker-side executor hook signature is sneaky.**
  `ExecXXXInitializeWorker(XxxState *, ParallelWorkerContext *)`. The
  second parameter type isn't `ParallelContext` like the other hooks —
  it's a strictly smaller struct (just `dsm_segment *seg` + `shm_toc
  *toc`). This trips first-time authors. §8 now calls it out.
- **Two reserved key ranges, not one.** Original skill §3 cited only
  the `0xFFFFFFFFFFFF0001..000F` range. Executor code carves out a
  second range at `0xE000000000000001+` for its own machinery. Per-node
  state in `nodeXxx.c` uses `plan_node_id` (small int) as the TOC key,
  cleanly avoiding both. §3 now lists both ranges.
- **`SET LOCAL work_mem` inside a function isn't symmetric.** Plain
  GUCs are *inherited* by workers at launch (via `RestoreGUCState`),
  but *changing* one inside a parallel block requires
  `GUC_ALLOW_IN_PARALLEL`, which `work_mem` doesn't carry. Hence
  RESTRICTED, not SAFE, for the variant-b function. The skill already
  named these mechanisms in §7; the iter-2 grading just shows the
  reader follows the chain cleanly when the names are present.

## Verdict

`parallel-query` is **ready**. With the seven edits applied, the skill
clears 100% of assertions in this test set with an absolute lift of
+0.576 over baseline. The structural shape (procedural cookbook with
catalog markings + lifecycle + worker constraints + rendezvous + plan-node
plumbing + checklist) is correct and was preserved — §5b slots between
the existing §5 ("what workers can't do") and §6 (GUC interplay) as a
natural follow-on to the can't-do list.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/skills/parallel-query/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/parallel-query/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/parallel-query/iteration-2/`
