# pg-claude SKILL.md — eval FINAL

## Scores

| Iteration | with_skill | baseline |
|---|---|---|
| 1 | 21/21 | 0/21 |
| 2 | 22/22 | 0/22 (unchanged) |

Baseline (no SKILL.md) scored 0 on every dispatch-to-X-skill assertion — as
expected for a master-navigator skill whose entire purpose is to point at
project-specific skills, commands, and knowledge paths that a general LLM
cannot guess.

## What the eval covered

Three realistic master-navigator prompts:

1. **orient-new-sql-fn** — multi-skill routing (catalog-conventions +
   fmgr-and-spi + coding-style + commands + upstream-prep).
2. **debug-deadlock** — operational recipe (commands + skills + knowledge
   docs + a known gotcha).
3. **learn-mvcc** — pure knowledge-corpus routing as an ordered reading list.

## What iteration-1 found

The existing SKILL.md is already strong: comprehensive table of contents for
slash commands, every specialised skill, and the `knowledge/` layout, with a
quick-orientation flowchart and clear scope guards in the description.
Iteration 1 hit 21/21.

Three minor robustness gaps surfaced:

- The flowchart's `"debug"` row was a single line; "debug a deadlock" deserved
  an explicit recipe naming the lmgr docs and the fork-model gotcha.
- The flowchart's `"add a feature"` row was generic; a built-in-SQL-function
  sub-recipe ties together two skills plus the right `dev/` subdir.
- "Explain how X works" prompts benefit from an ordered architecture →
  subsystem walk rather than a folder dump.

## What iteration-2 changed

`.claude/skills/pg-claude/SKILL.md` got three additive edits (no removals):

1. Dedicated `"debug a deadlock"` row in the flowchart.
2. Dedicated `"add a built-in SQL fn"` row in the flowchart pointing at
   `dev/src/backend/utils/adt/` and the `/setup-pg → /pg-restart → /pg-psql
   → /pg-test` loop.
3. New `## Suggested reading orders for "explain how X works"` section with
   ordered paths for MVCC, WAL/crash, planner, executor, buffer manager,
   replication, plus a reminder that cites use `source/...`.

All 16 referenced knowledge paths were verified to exist on disk.

## Outcome

Iteration 2 scored 22/22 on a slightly stricter assertion set (one new
assertion added for naming the specific built-in target directory). The skill
remains a clean master navigator — the additions sharpen routing on two
common operational recipes and one common learning prompt without bloating
the description line or reshuffling the table-of-contents structure.

## Files

- `.claude/skills/pg-claude/SKILL.md` — edited (3 additive changes).
- `skill-evals/pg-claude/iteration-1/{evals.json,answers.md,grading.json,proposed-edits.md}`
- `skill-evals/pg-claude/iteration-2/{evals.json,answers.md,grading.json,edits-applied.md}`
