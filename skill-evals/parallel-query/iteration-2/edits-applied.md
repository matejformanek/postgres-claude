# Iteration 2 — edits applied

Applied edits from `iteration-1/proposed-edits.md` to
`.claude/skills/parallel-query/SKILL.md`.

## Verification of values against source/

Before each edit, the cited source location was Read directly to confirm
the claim. Verifications:

- **Lock-group conflict bypass.**
  `source/src/backend/storage/lmgr/lock.c:1610-1614` carries the comment
  "Locks held in conflicting modes by members of our own lock group are
  not real conflicts; we can subtract those out". Verified by Reading
  lines 1591-1614.
- **LOCKTAG_RELATION_EXTEND carve-out.**
  `source/src/backend/storage/lmgr/lock.c:1600-1608` is the explicit
  carve-out (`LOCK_LOCKTAG(*lock) == LOCKTAG_RELATION_EXTEND`). Verified.
- **`BecomeLockGroupMember` call in worker startup.**
  `source/src/backend/access/transam/parallel.c:1392-1403` —
  `ParallelWorkerMain` calls
  `BecomeLockGroupMember(fps->parallel_leader_pgproc, fps->parallel_leader_pid)`
  before any heavyweight lock can be taken. Verified.
- **Executor-owned PARALLEL_KEY range.**
  `source/src/backend/executor/execParallel.c:60-69` defines
  `PARALLEL_KEY_EXECUTOR_FIXED = 0xE000000000000001`,
  `PARALLEL_KEY_PLANNEDSTMT = 0xE000000000000002`, then
  `PARAMLISTINFO`, `BUFFER_USAGE`, `TUPLE_QUEUE`, `INSTRUMENTATION`,
  `DSA`, `QUERY_TEXT`, `JIT_INSTRUMENTATION`, `WAL_USAGE`. Verified.
- **execParallel.c switch-on-nodeTag dispatch sites.**
  `source/src/backend/executor/execParallel.c:246-345` (Estimate),
  `:480-593` (InitializeDSM) — both have `switch (nodeTag(planstate))`
  with `case T_SeqScanState`, `T_IndexScanState`, etc. gated on
  `planstate->plan->parallel_aware`. Verified.
- **SeqScan reference shape.**
  `source/src/backend/executor/nodeSeqscan.c:391-412` —
  `ExecSeqScanInitializeDSM` calls `shm_toc_allocate`,
  `table_parallelscan_initialize`, and
  `shm_toc_insert(pcxt->toc, node->ss.ps.plan->plan_node_id, pscan)`.
  Verified the `plan_node_id` is the chosen TOC key for per-node state.
  `:437+` — `ExecSeqScanInitializeWorker(SeqScanState *node, ParallelWorkerContext *pwcxt)`
  confirms the second-parameter type is `ParallelWorkerContext *`, not
  `ParallelContext *`. Verified.
- **`parallel_leader_participation` GUC.**
  `source/src/backend/utils/misc/guc_parameters.dat:2312-2317` — bool,
  `PGC_USERSET`, boot_val 'true', short_desc "Controls whether Gather and
  Gather Merge also run subplans." Verified.

All values match source exactly at last check.

## Edits applied

1. **Edit 1 — new §5b "Leader ↔ worker rendezvous: use DSM primitives,
   NOT the lock manager"** — inserted between §5 and §6. Names the
   lock-group conflict bypass (lock.c:1610-1614), the LOCKTAG_RELATION_EXTEND
   carve-out (lock.c:1600-1608), `BecomeLockGroupMember` site
   (parallel.c:1392-1403), the primitives table (ConditionVariable,
   shm_mq, LWLock-on-DSM, Barrier, atomics), and the canonical CV wait
   loop. This is the highest-value edit.
2. **Edit 2 — expand §8** — added the `parallel_aware = true` gating
   flag, the dispatch switch-on-nodeTag site, the `ParallelWorkerContext *`
   parameter type for the worker hook, the `0xE0000...` executor-owned
   key range, the `plan_node_id`-as-key convention, and a precise cite
   to `ExecSeqScanInitializeDSM` at nodeSeqscan.c:391-412.
3. **Edit 3 — §3 reserved-key cite** — restructured the reserved-range
   note into a two-bullet list, one for `parallel.c` infrastructure
   (`0xFFFFFFFFFFFF0001..000F`) and one for `execParallel.c`
   (`0xE000000000000001+`), each with its source cite.
4. **Edit 4 — cross-reference to `locking` skill** — extended the bullet
   to name the lock-group conflict bypass and the
   `LOCKTAG_RELATION_EXTEND` carve-out, so the trap is discoverable from
   the locking side too.
5. **Edit 5 — §2 index-expression context note** — short paragraph
   noting that btree CREATE INDEX has parallel build and benefits from
   SAFE-marked expressions, while DML evaluation is leader-only
   regardless.
6. **Edit 6 — §6 `parallel_leader_participation`** — added one-paragraph
   note about this GUC and its relevance to sizing `pcxt->nworkers`.
7. **Edit 7 — rolled into Edit 2** — the precise `ExecSeqScanInitializeDSM`
   cite (nodeSeqscan.c:391-412) is part of the §8 rewrite, so no
   separate edit needed.

All seven edits applied (Edit 7 merged into Edit 2). `git diff --stat`
reports 107 insertions, 16 deletions on the SKILL.md file.

## Edits NOT applied

None — the iter-1 proposed-edits list was tight and all proved
worthwhile against iter-2 grading. Edit 7 collapsed into Edit 2 rather
than being dropped.
