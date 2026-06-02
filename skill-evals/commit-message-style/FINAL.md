# FINAL — commit-message-style skill eval

## Summary

Two-iteration eval, single-context methodology, 3 realistic prompts
graded with 8-9 assertions each.

| Iteration | with_skill | baseline | uplift |
|-----------|------------|----------|--------|
| 1         | 21/21      | 4/21     | +17    |
| 2         | 24/24      | 4/24     | +20    |

The skill was already strong at iteration 1 — all assertions passed.
Iteration 2 added 3 precision details (omit `Author:` when committer
is sole author, https-vs-http on Discussion URL, explicit BP-through
good/bad examples) which became 3 new assertions, all of which pass.

## Eval prompts

- **E1** — Generate a commit message for a small pg_dump bugfix on master.
- **E2** — Is `Co-Authored-By: Claude` appropriate for upstream PG?
- **E3** — Backpatch-through value and message identity across branches
  for a multi-branch fix.

## Skill edits applied (iter-1 → iter-2)

1. `Co-authored-by:` table row reworded to clarify first-author vs
   subsequent-author placement.
2. New §4 bullet: omit `Author:` entirely when committer is sole
   patch author (verified against `08127c641c0`).
3. `Discussion:` URL note expanded: `https://` is dominant (93/95 in
   recent log); `http://` rare but accepted.
4. `Backpatch-through:` bullet expanded with explicit good/bad
   examples; verified bare-version form in 63/63 recent observed
   instances.

## Edits proposed but dropped after verification

- "Two spaces after sentence-ending period." Initially proposed based
  on `db5ed03217b`. But `08127c641c0` uses single-space; full-log
  sample shows 32 two-space vs 41 one-space — per-committer
  preference, not a house-style rule. Dropped.

## Baseline behavior (what a model without this skill does wrong)

Consistent failure modes when prompted to write a PG commit without
the skill loaded:

- Uses Conventional Commits prefix (`fix(pg_dump):`).
- Uses raw archives URL (`www.postgresql.org/message-id/...`) instead
  of the `postgr.es/m/` shortener.
- Adds `Co-Authored-By: Claude` (uppercase, GitHub-style) trailer.
- Adds `Signed-off-by:` thinking PG follows DCO.
- Writes `Backpatch-through: 16-18` (range form) instead of bare
  oldest version.
- Comma-separates multiple `Reviewed-by:` entries on one line.
- Includes a bullet-list diff recap in the body.

The skill correctly steers away from all of these.

## Status

Ready. The skill description and body cover the verified PG
convention space well enough that further iteration would be
diminishing returns until new failure modes surface in real use.
File: `/Users/matej/Work/postgres/postgres-claude/.claude/skills/commit-message-style/SKILL.md`.
