# Iteration 1 — Summary

**Skill**: `bgworker-and-extensions`
**Date**: 2026-06-16
**Method**: single-context, no subagents

## Prompts evaluated

1. Write a periodic 30s bgworker that scans pg_stat_activity for idle-in-transaction sessions over 10s.
2. Layer planner_hook from _PG_init; chain-with-previous-hook pattern; unload story.
3. Trap: why `die` (not `proc_exit(0)`) for SIGTERM, why `SignalHandlerForConfigReload` (not `ProcessConfigFile`) for SIGHUP.

## Scores

| Cohort | Passed / Total | Pass rate |
|---|---|---|
| with_skill | 29 / 30 | 0.967 |
| baseline   | 17 / 30 | 0.567 |

Skill delta: **+0.40** (12 extra assertions out of 30).

## What the skill clearly helped with

- **Flag selection rationale** — explicitly says "do NOT set `BGWORKER_CLASS_PARALLEL`" and explains the SHMEM_ACCESS / DB_CONNECTION dependency chain.
- **Start-time picker** — `BgWorkerStart_PostmasterStart` vs `_ConsistentState` vs `_RecoveryFinished`. Baseline reached for the latter but didn't name the other two.
- **Restart-policy subtlety** — `proc_exit(0)` retires the slot regardless of `bgw_restart_time`. This is in §5 and worth gold.
- **WaitLatch flag set** — all three flags named (`WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH`); baseline waffled on the postmaster-death flag name.
- **Source pointers** — `worker_spi.c:134-225` and `worker_spi.c:362-385` as canonical examples. Baseline had no cites.

## Where baseline kept up

- High-level shape of `_PG_init` → `RegisterBackgroundWorker` → main loop with WaitLatch.
- The "no `_PG_fini` / library never unloads" story is common PG-internals knowledge.
- The "why die() not proc_exit() from handler" reasoning falls out of general async-signal-safety knowledge.
- DROP EXTENSION doesn't unload the .so.

## The miss against the skill

Skill §8 shows `planner_hook` callback with **4 parameters** (`Query *parse, const char *query_string, int cursorOptions, ParamListInfo boundParams`). Real signature at `source/src/include/optimizer/planner.h:28-32` has **5 parameters** — the trailing `ExplainState *es` is missing from the skill example. Any agent copy-pasting the skill would write code that does not compile.

This is the same class of bug caught in earlier campaigns (`parser-and-nodes` off-by-one lines, `executor-and-planner` setrefs cite). Iteration 2 must fix it.

## Recommended edits (see proposed-edits.md)

1. **HIGH** — Fix planner_hook prototype: add `ExplainState *es` 5th param to example + both recursive call sites.
2. **MED** — Add explicit "no `_PG_fini`, library never unloads" note in §8 with cite to `dfmgr.c:295-299`.
3. **MED** — Annotate why `die` and `SignalHandlerForConfigReload` are the right handlers (signal-safety + transaction abort + restart contract).
4. **LOW** — Name `local_preload_libraries` alongside the other two preload buckets.
5. **LOW** — `bgw_extra` canonical layout pointer (worker_spi packs dboid+roleoid+flags).

## Decision

Skill is solid in structure but has one bug to fix (Edit 1) before it can claim 100%. Edits 3 and 4 harden the signal-handler discipline against regression. Apply 1-4 before iteration 2; Edit 5 is optional.
