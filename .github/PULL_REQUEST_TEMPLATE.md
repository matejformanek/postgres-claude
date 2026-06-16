## Which layer

- [ ] Skill (`.claude/skills/`)
- [ ] Slash command (`.claude/commands/`)
- [ ] Scenario (`knowledge/scenarios/`)
- [ ] Knowledge doc (`knowledge/{subsystems,data-structures,idioms,architecture}/`)
- [ ] Rule (`.claude/rules/`)
- [ ] Session log (`sessions/`)
- [ ] Progress / state update (`progress/`)
- [ ] Tooling / repo plumbing

## Summary

One paragraph: what changed and why.

## Citations

- [ ] Every new factual claim about PG behavior carries a
      `source/<path>:<line>` cite, **or** is tagged `[unverified]` /
      `[inferred]`.
- [ ] All `source/<path>:<line>` cites resolve against current upstream
      `master`.
- [ ] All internal links (`knowledge/...`, `.claude/...`, `sessions/...`)
      resolve.

## Trail

- [ ] `progress/STATE.md` updated if this change moves the project's
      phase, coverage, or open thread.
- [ ] A session log under `sessions/YYYY-MM-DD-<slug>.md` was added or
      updated for non-trivial work.

## Scope

- [ ] Diff stays inside the chosen layer(s). Unrelated drive-by edits
      are split into separate PRs.
- [ ] No changes under `source/` or `dev/` (upstream PG patches go to
      `pgsql-hackers` via the
      [patch workflow](../knowledge/community/patch-workflow.md), not
      this repo).

## Commit style

- [ ] Commits follow
      [`meta-commit-style`](../.claude/skills/meta-commit-style/SKILL.md).
- [ ] If this is implementation work, it also follows
      [`pg-implement-discipline`](../.claude/rules/pg-implement-discipline.md)
      (one plan per branch, per-phase commits, `Plan:` trailer).
