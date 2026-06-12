# _loader — the shared cloud-routine workflow

**This file is the single source of truth for HOW every cloud routine runs.**
The claude.ai `RemoteTrigger` for each routine is a thin bootstrap that does only
two things:

```
You are the `<routine>` cloud routine for the postgres-claude meta repo.
1. git pull --ff-only origin main
2. Read .claude/cloud/_loader.md and follow it exactly, with routine = <routine>.
```

Everything else — the workflow below — lives here, in the repo, on `main`. That
means any fix to how routines behave (not just what a single recipe does) is a
normal commit to this file and takes effect on the **next** night's run, with no
need to touch the 10 triggers. The only thing permanently baked into a trigger is
the two-line bootstrap above, which never needs to change.

> **Precedence:** if a routine's own recipe (`.claude/cloud/<routine>.md`)
> specifies something that conflicts with a step here, **the recipe wins** for
> that routine's domain-specific work (which sources to fetch, what to produce,
> its token budget, its failure modes). This loader governs the envelope around
> that work (pull, skip-gate, run log, PR shape, exit discipline).

---

## The workflow (every routine, every night)

You are running as the `<routine>` daily cloud routine. Working dir: the
`postgres-claude` repo, checked out at `main`. Today's date is injected by
claude.ai at run time.

### 1. Sync to latest main

```bash
git pull --ff-only origin main
```

If this fails (diverged, conflict), STOP: write a failure run log (step 6 form)
on a fresh branch, push it, exit non-zero. Do NOT proceed against a stale tree.

### 2. Skip gate

If `.cloud-skip-<routine>` exists at repo root:

```bash
test -f .cloud-skip-<routine> && echo "skipped via lockfile"
```

Write a one-line run log with `exit_reason: skipped` (step 6 form) and exit 0.
No branch, no PR.

### 3. Read the recipe + load the standing skills

1. Read `.claude/cloud/<routine>.md` **end-to-end**. It is the single source of
   truth for this routine's domain work: which skills to load, which queues to
   pop, which URLs to fetch, the token budget, the per-section outputs, and the
   recipe-specific failure modes.
2. Always also load, regardless of recipe:
   - `.claude/skills/pg-claude/SKILL.md` (master navigator)
   - `.claude/skills/memory-keeping/SKILL.md` (ledger discipline)
3. Load any additional skills the recipe's `skills_required` frontmatter names.

### 4. Create the run branch

```bash
git checkout -b cloud/<routine>/<YYYY-MM-DD>
```

All file changes for this run live on this branch. One branch per run.

### 5. Do the recipe's work

Follow `.claude/cloud/<routine>.md`'s "Per-run recipe" exactly. Respect:

- **Source fetch via URL only** (no clone of upstream postgres). The anchor SHA
  lives in `progress/STATE.md`; read it before fetching pinned files. URL forms
  are listed in `README.md` §Conventions item 7.
- **Token budget — fill it.** The recipe frontmatter (`max_input_tokens` /
  `max_output_tokens`) is sized so each run produces real volume, not a single
  token-cheap item. **You are expected to keep doing recipe work until you have
  consumed ≥ 70% of `max_output_tokens` OR the recipe's per-run queue is
  empty.** Specifically:
  - If the recipe is queue-driven (`pg-file-backfiller`,
    `pg-quality-auditor`, `pg-extension-anthropologist`,
    `pg-user-question-harvester`, `pg-docs-miner`): pop and process queue
    entries in a loop. After each item, check `output_tokens_so_far`. If
    `< 0.70 * max_output_tokens` AND the queue still has `[pending]` items,
    pop the next one. Only exit the loop when one of:
    `output_tokens_so_far ≥ 0.70 * max_output_tokens`, `queue-empty`, or
    `≥ 3 consecutive failures` (then `exit_reason: queue-error`).
  - If the recipe is sweep-driven (`pg-corpus-maintainer`,
    `pg-upstream-watcher`, `pg-community-pulse`): keep doing passes until
    one of the same exit conditions. e.g. `pg-corpus-maintainer` Pass 2
    (glossary growth) should grow `top-N` until budget allows; don't stop
    at `top-15` if budget for `top-50` remains.
  - **Approaching the ceiling**: only when `output_tokens_so_far ≥ 0.85 *
    max_output_tokens` should you stop mid-item and record
    `exit_reason: budget-capped`. The ceiling is a soft cap with safety
    margin; the goal is the 70% floor.
  - **An empty-handed run is a process bug**, not a graceful no-op. If you
    consistently exit at < 30% budget consumed, the recipe under-uses the
    routine; flag it in the run log so `pg-state-keeper` can surface a
    "routine under-utilization" item.
  - **Frontmatter is authoritative; the recipe's `## Budget` footer
    must match it.** The 2026-06-12 audit found 3 recipes
    (`pg-community-pulse`, `pg-upstream-watcher`, `pg-evening-merger`)
    whose footer claimed a smaller budget than the frontmatter; agents
    were reading the footer and self-capping at half the real budget.
    If you bump a routine's budget, bump BOTH places in the same
    commit. If they disagree, **the frontmatter wins** and the agent
    should ignore the footer and log a "stale footer" warning.
- **Work queues** at `progress/_queues/<routine>.md` are append-only with
  `[pending]` / `[in-progress:<branch>]` / `[done:<merged-sha>]` markers.

### 5.5. STATE.md write serialization (added 2026-06-12)

**Sibling routines must NOT prepend `progress/STATE.md`.** Every routine
prepending a `**Last activity:**` line to STATE.md was the structural
cause of the recurring `cloud/*` merger collisions (multiple PRs from
the same night editing the same head-of-file region; `pg-evening-merger`
can't auto-resolve because both sides are real content).

Instead, sibling routines (every routine EXCEPT `pg-evening-merger`)
write a single-line entry to:

```
progress/cloud-routines/_state-log/<routine>-<YYYY-MM-DD>.md
```

Schema: one line, `**<routine>** <YYYY-MM-DD> — <summary> (PR #<n>).`
Identical content to what used to go into STATE.md, just written to a
per-routine file that no other routine touches.

`pg-evening-merger` reads every file matching that glob each night,
synthesises ONE consolidated "Last activity" line, and prepends THAT
single line to `progress/STATE.md`. Result: STATE.md only sees one
prepend per night, no collision surface.

If a routine genuinely must edit STATE.md outside the "Last activity"
prepend (e.g. anchor SHA bump in `pg-upstream-watcher` step 9), it
edits the line in place rather than prepending — non-overlapping
diff hunk, no collision with the merger's prepend.

### 6. Write the daily run log

Always, even on failure or skip. Path:

```
progress/cloud-routines/<routine>/<YYYY-MM-DD>.md
```

Template:

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
- exit_reason: <ok | skipped | queue-empty | rate-limited | budget-capped | error: ...>
```

Commit it on the run branch in the same PR as the work.

### 7. Self-review + open the PR

1. Self-review the diff against `.claude/skills/review-checklist/SKILL.md`.
2. Open the PR:
   - **Title:** `[cloud:<routine>] <one-line summary>`
   - **Body**, containing:
     - (a) the recipe path (`.claude/cloud/<routine>.md`)
     - (b) sources fetched: each as URL + ISO timestamp + HTTP status
     - (c) the self-review result against `review-checklist`
     - (d) the queue items popped (with their new `[in-progress:<branch>]` marker)

### Environment / tooling notes (cloud CCR specifics)

- **`gh` CLI may be absent.** If `gh --version` fails, use the **GitHub MCP
  tools** instead for all repo write operations (create branch, write/commit
  files, open PR, merge PR) — they work through the same auth.
- **`GH_TOKEN` is set** in the cloud environment for authenticated
  `api.github.com` access (5000 req/hr). Never print its value. Use it for
  raw/API fetches that would otherwise hit the 60/hr unauthenticated limit.
- **Sources are fetched, not cloned.** Don't `git clone` upstream postgres;
  fetch by URL (forms in `README.md` §Conventions).

### 8. Failure discipline

If anything blocks at any step:

1. Write a clear failure run log at the step-6 path, with a specific
   `exit_reason: error: <what>`.
2. Commit it on the run branch and push.
3. Exit **non-zero, with no PR** — so `pg-state-keeper` classifies the run
   `FAILED` (log present, non-ok exit) rather than `SILENT` (no log at all).

The one outcome to avoid is dying before writing ANY log: that's the `SILENT`
state the watchdog most wants to catch, and it's the least diagnosable. Whenever
possible, write the log first, then do the risky thing.

---

## Why this indirection exists

Before this file, the 7-step workflow was duplicated in two places that could
drift: the baked `message.content` of each of the 10 `RemoteTrigger`s, and a
prose copy in `README.md`. A fix to the workflow itself meant re-issuing all 10
triggers; the README copy could silently fall out of sync with the baked copy.

With the bootstrap-only trigger + this loader:

- **One operative copy** of the workflow, versioned on `main`.
- **Fixable in time:** edit this file, commit, and the next run uses it — no
  trigger touches.
- **README** stops duplicating; it points here.

The only thing a trigger still bakes in is "pull main + read this file", which is
irreducible (you need at least that to know where to look) and effectively never
changes.

## For maintainers wiring or re-wiring a trigger

The `RemoteTrigger` `message.content` for routine `<routine>` should be exactly:

```
You are the `<routine>` daily cloud routine for the postgres-claude meta repo
(github.com/matejformanek/postgres-claude). Working dir: the repo at main.
Today's date is injected below.

1. git pull --ff-only origin main
2. Read .claude/cloud/_loader.md end-to-end and follow it exactly, treating
   `<routine>` as your routine name. The loader (and the recipe it points you
   to) is the single source of truth; if anything here disagrees with it, the
   repo wins.
```

Keep it that short. Resist re-inlining workflow steps into the trigger — that
re-introduces the drift this file exists to remove.
