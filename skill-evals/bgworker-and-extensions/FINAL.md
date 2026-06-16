# bgworker-and-extensions — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/bgworker-and-extensions/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 29 / 30 = 0.967 | 17 / 30 = 0.567 | +0.400 |
| Iteration 2 | 30 / 30 = 1.000 | 17 / 30 = 0.567 | +0.433 |

iter-2 closes the single iter-1 with_skill miss (the 5-parameter
`planner_hook` prototype). Baseline is unchanged because the prompts
and general-PG-knowledge cohort are identical between iterations.
Absolute lift over baseline holds at +0.40-0.43 — bgworker registration
specifics, signal-handler discipline, and WaitLatch flag set are the
load-bearing knowledge the skill carries that baseline cannot recover.

## What changed between iter-1 and iter-2

Five edits from `iteration-1/proposed-edits.md` were applied to
SKILL.md:

1. **Edit #1 (HIGH)** — Fixed the §8 `planner_hook` example: 4-param
   prototype → real 5-param `planner_hook_type` with `ExplainState *es`
   as the trailing argument, in the callback signature AND both
   recursive call sites. Added cite to
   `source/src/include/optimizer/planner.h:28-32`. **This is the
   highest-value edit of the round** — without it, any agent copy-
   pasting the example would write code that doesn't compile.
2. **Edit #2 (LOW)** — Named `local_preload_libraries` alongside the
   other two preload buckets in §8 opener; distinguishes the three
   load-timing / privilege contexts.
3. **Edit #3 (MED)** — Added `### No _PG_fini: libraries never unload`
   subsection at the end of §8; three explicit bullets covering hook
   persistence, DROP EXTENSION semantics, and postmaster-shutdown
   cleanup. Cite to `dfmgr.c:295-299`.
4. **Edit #4 (MED)** — Inserted "Why these signal handlers?" bullet at
   the top of §6 "Hard rules inside a worker"; explains why `die` and
   `SignalHandlerForConfigReload` are correct and what three things go
   wrong with a custom `proc_exit(0)` handler. Cites to
   `postgres.c:3023-3058` and `interrupt.c:60-65`.
5. **Edit #5 (LOW)** — Replaced bare `bgw_extra` comment in the §2
   struct-fill example with canonical packing/unpacking pointer to
   `worker_spi.c:470-475` and `:152-157`.

## Source-value verifications performed

Before applying, each cite was verified by Read against the main repo's
`source/` symlink:

- `planner_hook_type` at `source/src/include/optimizer/planner.h:28-32` —
  5-parameter signature confirmed; trailing `ExplainState *es` is real.
- `_PG_init` dynamic-load call site at
  `source/src/backend/utils/fmgr/dfmgr.c:295-299`; no `_PG_fini` exists
  elsewhere in dfmgr.c (grep confirmed).
- `die()` at `source/src/backend/tcop/postgres.c:3023-3058`; flag-and-
  latch body confirmed.
- `SignalHandlerForConfigReload` at
  `source/src/backend/postmaster/interrupt.c:60-65`; two-line body
  confirmed.
- `bgw_extra` pack at `source/src/test/modules/worker_spi/worker_spi.c:470-475`,
  unpack at `:152-157`; both confirmed.

All five cites match source exactly. No off-by-line errors found in the
iter-1 proposal — unlike the `parser-and-nodes` round which had 5
off-by-one corrections.

## git diff --stat

```
.claude/skills/bgworker-and-extensions/SKILL.md | 59 +++++++++++++++++++++----
 1 file changed, 51 insertions(+), 8 deletions(-)
```

Non-zero diff confirmed.

## Verdict

`bgworker-and-extensions` is **ready**. The skill now clears 100% of
assertions in this test set. The single iter-1 bug (stale 4-param
`planner_hook` example) is fixed; four supporting edits harden the
signal-handler discipline, hook-unload semantics, and `bgw_extra`
canonical layout against future regression. Structural split
(SKILL.md = procedural cookbook, `knowledge/idioms/bgworker-and-parallel.md`
= conceptual model) is preserved.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/.claude/skills/bgworker-and-extensions/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/bgworker-and-extensions/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/bgworker-and-extensions/iteration-2/`
