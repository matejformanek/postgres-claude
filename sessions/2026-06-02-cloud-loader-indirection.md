# 2026-06-02 — Cloud-routine loader indirection

**Type:** interactive (worktree `ft_cloud_loader_indirection`).
**Outcome:** extracted the shared cloud-routine workflow into a single
versioned `.claude/cloud/_loader.md`, slimmed the README to point at it,
and shrank the 10 live `RemoteTrigger`s to a 2-line bootstrap that reads
the loader from `main` at run time.

## The ask

User: "couldn't we rather instruct [the routines] to take from main the
MD file on github, if not already, so they always act based on what we
possibly even fix in time?"

Correct instinct. The design already read **recipes** and **skills** fresh
from main each night (the recipe is declared single-source-of-truth, "recipe
wins"). But the **workflow envelope** — the 7 steps every routine runs (pull,
skip-gate, read recipe, branch, run log, self-review, PR, failure handling) —
was **baked into each trigger's `message.content`** and **duplicated** in the
README. A fix to the workflow itself meant re-issuing 10 triggers; the README
copy could silently drift from the baked copy.

## What changed

| Path | Change |
|---|---|
| `.claude/cloud/_loader.md` | **NEW.** The single source of truth for HOW every routine runs: 8 numbered steps + run-log template + env/tooling notes (gh→MCP fallback, GH_TOKEN) + the canonical bootstrap-prompt text for maintainers. |
| `.claude/cloud/README.md` | Slimmed: "How a routine runs" → 2-line bootstrap + pointer to `_loader.md`; Conventions split into envelope (→ loader) vs recipe-facing (queues, source URLs, skills, budget); run-log template → pointer. |

## The trigger model, before → after

**Before** (baked into all 10 triggers): the full 7-step prompt.

**After** (bootstrap only):
```
You are the `<routine>` daily cloud routine for postgres-claude.
1. git pull --ff-only origin main
2. Read .claude/cloud/_loader.md and follow it exactly, with routine=<routine>.
```
Everything else lives in `_loader.md` on `main` → fixable in time, no trigger
touches. The only permanently-baked thing is "pull + read the loader", which is
irreducible and never changes.

## RemoteTrigger facts (captured from `list`)

- `RemoteTrigger update` is a **partial in-place POST** to
  `/v1/code/triggers/{id}` — so `message.content` can be edited without
  recreating. (Triggers can't be deleted via API, but update + disable work.)
- The 10 live routine trigger IDs:

  | routine | trigger_id | UTC cron |
  |---|---|---|
  | pg-community-pulse | trig_01GWYbSQkjw27M13Nb3tNfET | 7 15 * * * |
  | pg-docs-miner | trig_018P5RFZsVmtVUKD7Jyk8ZDU | 51 19 * * * |
  | pg-upstream-watcher | trig_01JnKrULA888NbGX497N846X | 29 21 * * * |
  | pg-extension-anthropologist | trig_011XvZ4k1Gv8bx3yiVgbYh2P | 3 23 * * * |
  | pg-file-backfiller | trig_01SyhHRtD5yXEBJSuyTv8iVH | 43 16 * * * |
  | pg-quality-auditor | trig_01Mt619qszD3nCw16KDNg43V | 11 2 * * * |
  | pg-corpus-maintainer | trig_01MvzAnBFBeFeHMnc2xpJH55 | 37 0 * * * |
  | pg-user-question-harvester | trig_01QRi1mXXxVpXQTT7kYFEFRo | 47 3 * * * |
  | pg-evening-merger | trig_01PKtwdybZ9h8qZJLCsQUfcY | 11 2 * * * |
  | pg-state-keeper | trig_018GiWYkKH9EzGC5iLqe1GZK | 43 5 * * * |

  (Crons differ from the Prague-time plan because they're stored UTC; the next_run_at values map back to the intended local times.)

- 3 throwaway preflight triggers (`pg-preflight`, `-egress`, `-egress2`) are
  `enabled:false`, `run_once_fired`. Harmless; leave them.
- Every routine also carries the **gh→MCP fallback + GH_TOKEN** tooling note —
  now preserved in `_loader.md` §Environment so it survives the shrink.

## Sequencing (important)

`_loader.md` must be on `main` **before** any trigger is pointed at it, else the
next run can't find it. Order:

1. Land `_loader.md` + README slim on `main` (this PR).
2. Then `RemoteTrigger update` each of the 10 triggers to the bootstrap prompt.
3. Verify with `list` that next_run_at is unchanged and message.content is the
   2-liner.

Until step 2, the existing baked prompts keep working — they read the recipe
fresh anyway, and the README still resolves the run-log-template pointer (one
extra hop to `_loader.md` §6).

## What this did NOT do

- Did not change any recipe's domain behavior.
- Did not touch the watchdog (`pg-state-keeper`) logic — only the envelope it
  shares with siblings.
- Did not investigate the pg-quality-auditor SILENT run from 2026-06-02 (still
  open; tracked in STATE.md).

## Commit (meta-commit-style)

```
ft(cloud): extract routine workflow into _loader.md, shrink triggers to bootstrap

Move the shared 7-step routine envelope (pull, skip-gate, read recipe,
branch, run log, self-review, PR, failure handling) out of each baked
RemoteTrigger prompt and the duplicated README block into one versioned
.claude/cloud/_loader.md. Triggers shrink to a 2-line bootstrap (pull
main + read _loader.md), so the workflow itself becomes fixable from
main with no trigger re-issue. README points at the loader instead of
restating it.

Preserves the env/tooling note (gh-absent -> GitHub MCP fallback,
GH_TOKEN 5000/hr) in the loader so nothing is lost when the triggers
are shrunk.

Session: sessions/2026-06-02-cloud-loader-indirection.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
