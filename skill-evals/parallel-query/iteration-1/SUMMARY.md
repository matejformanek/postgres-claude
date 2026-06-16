# parallel-query — iteration 1 summary

## Score

| Run | passed | total | rate |
|---|---|---|---|
| with_skill | 20 | 33 | 0.606 |
| baseline | 14 | 33 | 0.424 |
| delta | +6 | — | +0.182 |

Modest lift. Two strong wins (lifecycle mechanics + GUC story); one severe gap.

## Where the skill won

- Section 3 ParallelContext lifecycle (call order + reserved-key range) — both evals 1/3 baseline missed details the skill nailed.
- Section 7 `GUC_ALLOW_IN_PARALLEL` + `RestoreGUCState` story — baseline punted on the `SET LOCAL work_mem` variant; with_skill answered crisply.
- Section 2 RESTRICTED vs UNSAFE semantics for proparallel — baseline conflated them; skill's table is clear.
- Section 6 `nworkers_launched` discipline — checklist closes the gap.

## Where the skill lost

- **Eval-3 (lock-group trap) — 0/11 from the skill.** Section 5 forbids acquiring non-buffer locks but doesn't explain *why heavyweight locks fail as rendezvous*: the lock-group conflict bypass in `LockCheckConflicts` makes them no-ops between leader and worker. This is THE highest-value parallel-query trap and the skill is silent on it.
- **Rendezvous primitives missing.** `ConditionVariable`, `shm_mq`, `LWLock`-on-DSM, `Barrier` — none named in the skill. Reader is told what NOT to do but not given the working alternatives.
- **Eval-1 dispatch-site gap.** Section 8 names the 5 hooks but doesn't say to add a case to the `switch (nodeTag(...))` in `execParallel.c`, doesn't mention `parallel_aware = true` as the gate, doesn't mention `ParallelWorkerContext` vs `ParallelContext` typing.
- **Executor key range not named.** `PARALLEL_KEY_EXECUTOR_FIXED` / `PARALLEL_KEY_PLANNEDSTMT` at `0xE000000000000001+` are a second reserved range that Section 3 doesn't acknowledge.

## Proposed iter-2 edits

7 edits in `proposed-edits.md`. The two that matter most:

- **Edit 1** — new section "Leader/worker rendezvous: use DSM primitives, NOT the lock manager" with the lock-group bypass explainer and the primitives table. Closes ~9 Eval-3 assertions.
- **Edit 2** — expand Section 8 with the dispatch-switch site, the `parallel_aware` flag, the `ParallelWorkerContext` type, and the executor-owned key range. Closes ~4 Eval-1 assertions.

Projected iter-2 with_skill: ≥ 0.97.
