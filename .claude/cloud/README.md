# .claude/cloud — daily cloud-task recipes

Each `pg-*.md` file in this directory is the **single source of truth** for what
one scheduled claude.ai cloud task *does*. `_loader.md` is the single source of
truth for *how every routine runs* (the shared envelope: pull, skip-gate, run
log, PR, exit discipline).

See `pg-claude-plan.md` at the workspace root for the master design.

## How a routine runs

The claude.ai `RemoteTrigger` for each routine bakes in only a **two-line
bootstrap**:

```
You are the `<routine>` daily cloud routine for postgres-claude.
1. git pull --ff-only origin main
2. Read .claude/cloud/_loader.md and follow it exactly, with routine = <routine>.
```

Everything else — the full 8-step workflow, the run-log template, the PR shape,
the failure discipline — lives in **[`_loader.md`](./_loader.md)**, versioned on
`main`. This keeps the workflow fixable over time without re-issuing the 10
triggers: edit `_loader.md`, commit, and the next night's run picks it up.

The routine's own `pg-*.md` recipe governs its domain work (sources, outputs,
budget); `_loader.md` governs the envelope. If the two ever disagree, the recipe
wins for the domain work, the loader wins for the envelope.

## Conventions

The **envelope** conventions — branch-per-run, PR title/body shape, skip
lockfile, daily run-log template, failure discipline — are defined once in
**[`_loader.md`](./_loader.md)**. Don't restate them in recipes; rely on the
loader.

The **recipe-facing** conventions every `pg-*.md` should honor:

1. **Work queues** at `progress/_queues/<routine>.md` are append-only with
   `[pending]` / `[in-progress:<branch>]` / `[done:<merged-sha>]` markers.
2. **Source fetch via URL** (no clone). Anchor SHA lives in
   `progress/STATE.md` — routines read it before fetching:
   - File at SHA: `https://raw.githubusercontent.com/postgres/postgres/<sha>/<path>`
   - Recent commits: `https://api.github.com/repos/postgres/postgres/commits?since=<iso>&sha=master&per_page=100`
   - Commit diff: `https://github.com/postgres/postgres/commit/<sha>.diff`
   - Tree listing: `https://api.github.com/repos/postgres/postgres/git/trees/<sha>?recursive=1`
   - Buildfarm RSS: `https://buildfarm.postgresql.org/cgi-bin/show_failures.pl`
3. **Always load** `.claude/skills/pg-claude/SKILL.md` (master navigator) and
   `.claude/skills/memory-keeping/SKILL.md` (ledger discipline) — plus whatever
   the recipe's `skills_required` frontmatter names.
4. **Token budget** declared in recipe frontmatter; workers self-cap.

## Schedule (Europe/Prague)

| Time | Routine | Fetch | Budget (in/out) |
| --- | --- | --- | --- |
| 20:11 | pg-community-pulse | no | 100k / 30k |
| 20:47 | pg-docs-miner | no | 60k / 20k |
| 21:23 | pg-upstream-watcher | yes | 80k / 25k |
| 22:07 | pg-extension-anthropologist | yes | 70k / 20k |
| 22:53 | pg-file-backfiller | yes | 80k / 15k |
| 23:31 | pg-quality-auditor | yes | 70k / 20k |
| 00:13 | pg-corpus-maintainer | no | 60k / 15k |
| 00:47 | pg-user-question-harvester | no | 70k / 15k |
| 02:11 | pg-evening-merger | no | 150k / 30k |
| 05:43 | pg-state-keeper | no | 60k / 20k |

## Daily-run-log template

Defined once in **[`_loader.md`](./_loader.md)** §6 (committed by every routine,
on every run, including skips and failures). Not restated here to avoid drift.
