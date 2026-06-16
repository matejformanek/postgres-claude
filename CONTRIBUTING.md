# Contributing to pg-claude

Two contribution paths live in this repo. Pick the right one before
opening a PR.

## 1. Patches to PostgreSQL itself

pg-claude does **not** fork PostgreSQL. The source tree under `source/`
is a read-only reference clone of upstream `master`. Patches to the PG
backend go to the upstream community, not here.

If you have a backend patch, follow the upstream lifecycle:

- [`knowledge/community/patch-workflow.md`](knowledge/community/patch-workflow.md)
  — `format-patch` → `pgsql-hackers` → CommitFest → committer.

GitHub PRs against `matejformanek/postgres-claude` that try to patch
the PG source will be redirected.

## 2. Changes to the meta repo (this repo)

Everything else is fair game: knowledge docs, skills, slash commands,
scenarios, idioms, rules, session logs, planning artifacts.

The bar for meta-repo PRs is the same one the corpus holds itself to:

1. **Work in a worktree.** One topic per branch. Name it
   `<type>_<domain>_<short>` (e.g. `ft_corpus_planner_overview`).
2. **Cite or tag.** Every new factual claim about PG behavior carries
   either a `source/<path>:<line>` cite or an `[unverified]` tag.
3. **Update `progress/STATE.md`** if the change moves the project's
   stated phase, coverage, or open thread.
4. **Drop a session log** under `sessions/YYYY-MM-DD-<slug>.md` for
   any non-trivial change. Future sessions read these.
5. **Match the commit style** in
   [`.claude/skills/meta-commit-style/SKILL.md`](.claude/skills/meta-commit-style/SKILL.md).
   Implementation work additionally follows
   [`.claude/rules/pg-implement-discipline.md`](.claude/rules/pg-implement-discipline.md).

Open the PR with the [pull-request template](.github/PULL_REQUEST_TEMPLATE.md)
filled in — it lists the layer ladder (skill / command / scenario /
knowledge doc / rule / session) so reviewers can place your change
quickly.

## Bug reports & ideas

Broken citations, stale `file:line`, drifted CF numbers, missing
subsystem coverage — file a bug via
[`.github/ISSUE_TEMPLATE/bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md).
New skill / scenario / doc ideas via
[`.github/ISSUE_TEMPLATE/idea.md`](.github/ISSUE_TEMPLATE/idea.md).
