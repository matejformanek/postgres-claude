# psql — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/psql/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 28 / 29 = 0.966 | 10 / 29 = 0.345 | +0.621 |
| Iteration 2 | 30 / 30 = 1.000 | 11 / 30 = 0.367 | +0.633 |

The skill clears 100% after iteration 2 against a slightly harder
rubric (one extra assertion specifically checking the corrected column
set for `pg_backend_memory_contexts`). The absolute lift over baseline
sits at +0.6 across both runs — baseline knows generic psql mechanics
(`SET enable_*`, `pg_log_backend_memory_contexts`, `pg_sleep` hold) but
loses every dev-cluster-specific assertion (connection idiom on /tmp,
`$USER` vs `postgres` role, `/pg-attach`, log path, `application_name=hold`
recipe).

## What changed between iter-1 and iter-2

Six edits from `iteration-1/proposed-edits.md` applied to SKILL.md:

1. **Edit #1 (bug fix)** — replaced the broken
   `pg_backend_memory_contexts` query that referenced a non-existent
   `parent` column with the correct schema (`name, type, level, path,
   total_bytes, used_bytes`). Plus a 3-line comment naming the full
   column set and clarifying that `path` is the ancestor `context_id`
   array.
2. **Edit #2** — added a "wrong tool" bullet to §Common gotchas naming
   managed-PG vendors (RDS / Cloud SQL / Supabase / Neon / Aurora) so
   the dev-vs-prod boundary is visible inside the skill body, not only
   in frontmatter.
3. **Edit #3** — inlined the full race-safe `PGAPPNAME=hold` +
   `pg_sleep` + `application_name='hold'` + `/pg-attach` recipe (4-step
   bash block) into §"Capturing a backend PID", with the
   libpq-env-var-not-`\set` note.
4. **Edit #4** — expanded the leak-workflow to explain MessageContext's
   role (per-message context, reset between client protocol messages)
   plus three other commonly-watched contexts.
5. **Edit #5** — added a one-sentence per-connection-fork note under
   §"Capturing a backend PID" (the PID is the BACKEND's, not psql's).
   Closes the only iter-1 with_skill miss.
6. **Edit #6** — added a 3-line inline comment that `enable_*` GUCs
   don't hard-disable a node type; they apply `disable_cost`.

The one with_skill miss in iter-1 (per-connection-fork model) was
closed by edit #5. The added iter-2 assertion (correct column set) is
satisfied by edit #1.

## Source-value verifications performed

- `pg_backend_memory_contexts` column set: verified at
  `source/src/include/catalog/pg_proc.dat:8709-8715`. Exact
  `proargnames` field: `{name, ident, type, level, path, total_bytes,
  total_nblocks, free_bytes, free_chunks, used_bytes}` — no `parent`
  column. `path` is `int4[]` (ancestor context_ids).
- `pg_log_backend_memory_contexts`: verified at
  `source/src/backend/utils/adt/mcxtfuncs.c:267-310` (signal delivery
  at line 301: `SendProcSignal(pid, PROCSIG_LOG_MEMORY_CONTEXT,
  procNumber)`). Introduced 2021-04-06 (commit `43620e32861`), PG 14 dev
  cycle — the skill's "PG 14+" note is correct.
- `\errverbose` semantics: verified at
  `source/src/bin/psql/command.c:1641-1644`. SKILL.md row is correct.
- `PGAPPNAME=hold` recipe: verified against sister skill at
  `.claude/skills/debugging/SKILL.md:47-71`. Inlined verbatim, no drift.

All values used in the edits match source exactly.

## Honest gotchas

1. **SKILL.md shipped a copy-paste error.** Lines 98-100 referenced a
   `parent` column that doesn't exist in `pg_backend_memory_contexts` —
   running the query verbatim errors with `column "parent" does not
   exist`. This was the highest-value finding of the iteration. It's
   the kind of error that only surfaces when an eval actually walks
   through the query the skill suggests.
2. **Iter-2 added a discriminating assertion.** The path-vs-parent
   column check was added to iter-2 specifically to verify edit #1
   landed. Without it, the with_skill score would have plateaued at
   28/29 → 29/29 (just edit #5's per-connection-fork closure), masking
   the more important bug-fix gain. The honest read is that the
   numerical lift in this round is conservative — the qualitative win
   is that pasting the SKILL.md query no longer errors.

## Verdict

`psql` skill is **ready**. Lift over baseline is large and stable
(~+0.6), and the highest-priority edit (#1) eliminated a real
copy-paste error. The dev-vs-prod boundary is now explicit inside the
skill body, and the held-PID handoff recipe no longer requires a
context-switch to `debugging/SKILL.md`.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/.claude/skills/psql/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/psql/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/psql/iteration-2/`
