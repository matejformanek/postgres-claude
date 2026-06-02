# .claude/cloud — daily cloud-task recipes

Each `pg-*.md` file in this directory is the **single source of truth** for one
scheduled claude.ai cloud task. The cloud-task prompt is a thin loader: it
checks out `postgres-claude`, reads the recipe, and follows it exactly.

See `pg-claude-plan.md` at the workspace root for the master design.

## How a routine runs (cloud-side loader prompt)

```
You are running as the `<routine>` daily cloud routine.
Working dir: the postgres-claude repo, checked out at main.
Today's date: <auto-injected by claude.ai>.

1. `git pull --ff-only origin main`.
2. If `.cloud-skip-<routine>` exists at repo root, log "skipped" and exit 0.
3. Read `.claude/cloud/<routine>.md` end-to-end. Follow its recipe exactly.
4. When done, ensure `progress/cloud-routines/<routine>/<YYYY-MM-DD>.md`
   exists and is committed on the branch.
5. Open a PR with title `[cloud:<routine>] <summary>` and body containing:
   the recipe path, sources fetched (URLs + ISO timestamps), and a
   self-review against `.claude/skills/review-checklist/SKILL.md`.

If anything blocks, write a clear failure log and exit non-zero (no PR).
```

## Conventions (apply to every recipe)

1. **Branch per run:** `cloud/<routine>/<YYYY-MM-DD>`.
2. **PR title:** `[cloud:<routine>] <one-line summary>`.
3. **PR body** lists: recipe path, sources fetched (URLs + ISO timestamps),
   self-review against `.claude/skills/review-checklist/SKILL.md`, items
   popped from the queue.
4. **Work queues** at `progress/_queues/<routine>.md` are append-only with
   `[pending]` / `[in-progress:<branch>]` / `[done:<merged-sha>]` markers.
5. **Skip lockfile** `.cloud-skip-<routine>` at repo root → log + exit 0.
6. **Daily run log** at `progress/cloud-routines/<routine>/<YYYY-MM-DD>.md`
   with fields: `tried`, `found`, `skipped`, `sources`, `cost`,
   `exit_reason`. Committed in the same PR.
7. **Source fetch via URL** (no clone). Anchor SHA lives in
   `progress/STATE.md` — routines read it before fetching:
   - File at SHA: `https://raw.githubusercontent.com/postgres/postgres/<sha>/<path>`
   - Recent commits: `https://api.github.com/repos/postgres/postgres/commits?since=<iso>&sha=master&per_page=100`
   - Commit diff: `https://github.com/postgres/postgres/commit/<sha>.diff`
   - Tree listing: `https://api.github.com/repos/postgres/postgres/git/trees/<sha>?recursive=1`
   - Buildfarm RSS: `https://buildfarm.postgresql.org/cgi-bin/show_failures.pl`
8. **Always load** `.claude/skills/pg-claude/SKILL.md` (master navigator) and
   `.claude/skills/memory-keeping/SKILL.md` (ledger discipline).
9. **Token budget** declared in recipe frontmatter; workers self-cap.

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

## Daily-run-log template (committed by every routine)

```markdown
# <routine> — <YYYY-MM-DD>

- tried: <what the routine attempted>
- found: <file paths + line counts>
- skipped: <queue items bypassed and why>
- sources:
  - <url> @ <iso-timestamp> → <http-status>
- cost:
  - input_tokens: <n>
  - output_tokens: <n>
  - total_tokens: <n>
- exit_reason: <ok | rate-limited | queue-empty | error: ...>
```
