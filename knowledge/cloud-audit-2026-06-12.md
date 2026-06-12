# Cloud-routine audit — 2026-06-12

Snapshot of how the 10 nightly cloud routines have performed over the last
~11 days (2026-06-02 first run … 2026-06-12 last run). Triggered by a user
observation that the routines were producing less than the budget allows.

## TL;DR

- **PR cadence is healthy**: 9 of the 10 routines opened a merged PR on
  most days; only `pg-state-keeper` has stuck-open PRs (3 of its 8 PRs
  are unmerged, all blocked on a real human-call — the `origin/main`
  rewrite that dropped #115, and the recurring `STATE.md` co-merge
  collision).
- **Budget utilization is the real problem**: 5 of 10 routines consistently
  exit at 23-35% of their `max_output_tokens`, *under the 70% "fill the
  budget" floor enforced by `_loader.md` §5*. The structural causes are
  three: stale `## Budget` footers contradicting the post-2026-06-02
  frontmatter; per-run targets that pre-date the budget bump; lack of a
  parallel-fanout pattern for queue-driven routines.
- **One structural defect blocks the merger repeatedly**: every sibling
  routine prepends `progress/STATE.md` "Last activity" lines; with 7-8
  routines doing this each night, the second-and-later PRs of the night
  conflict. The merger handles single-PR-of-the-day cleanly but stalls
  on every batch.

## Per-routine scorecard

Numbers are output-token consumption in the most-recent run, against the
routine's frontmatter `max_output_tokens`. PR counts are 11-day totals.

| Routine | Budget (out) | Recent (out) | Util. | Merged | Open | Closed unmerged | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| `pg-community-pulse` | 60k | 14k | **23%** | 10 | 0 | 0 | UNDER — stale footer, narrow source list |
| `pg-corpus-maintainer` | 60k | 44k | 73% | 11 | 0 | 1 | OK |
| `pg-docs-miner` | 50k | 28k | 56% | 11 | 0 | 1 | mild under — queue depth |
| `pg-evening-merger` | 60k | 16k | **27%** | (direct push) | — | — | UNDER — input-bound by # of PRs, but stale footer says 30k cap |
| `pg-extension-anthropologist` | 60k | 46k | 77% | 9 | 1 | 1 | OK; the one open PR (#143) is the STATE.md collision |
| `pg-file-backfiller` | 100k | 33k | **33%** | 10 | 0 | 2 | UNDER significantly — no parallel-fanout |
| `pg-quality-auditor` | 60k | 33-46k | 55-77% | 9 | 0 | 0 | OK on busy days, low on others |
| `pg-state-keeper` | 20k | 13k | 65% | 3 | 2 | 3 | **structurally blocked** (see "Watchdog hazards") |
| `pg-upstream-watcher` | 50k | 13k | **26%** | 9 | 0 | 0 | UNDER — recipe hard-caps "5 deep commits" |
| `pg-user-question-harvester` | 50k | 16-18k | **35%** | 10 | 0 | 1 | UNDER — narrow source set (sandbox blocks SE/Reddit) |

5 of 10 are under the 70% "fill the budget" floor. **The recipes assume
the routines push themselves to the floor; the agents are not doing so.**

## Root causes

### 1. Stale `## Budget` footers contradict frontmatter (3 routines)

Three recipes carry pre-2026-06-02 footers that name a smaller budget
than the post-bump frontmatter:

| Recipe | Frontmatter `max_output` | Footer claim | Effect |
|---|---:|---:|---|
| `pg-community-pulse` | 60k | "100k input / 30k output" | Agent reads the footer first and caps itself at 30k — half the real budget. |
| `pg-upstream-watcher` | 50k | "80k input / 25k output" | Same: caps at 25k. |
| `pg-evening-merger` | 60k | "150k input / 30k output" | Same: caps at 30k. |

This is the single highest-leverage fix in this audit.

### 2. Per-run targets pre-date the budget bump (2 routines)

`pg-upstream-watcher` says "Pick up to 5 commits flagged 'interesting'"
and "buildfarm: pick 3-5 failures" — these targets were sized for the
old 25k output budget. At 50k they should be ~10-15 deep commits + 6-8
buildfarm rootcauses.

`pg-file-backfiller` says "target 10-20 small files OR 3-5 medium OR
1-2 large" — targets are correct, but the agent has been hitting the
low end of the small-file band (7 small files on 2026-06-11). Either
the queue-pop logic exits early, or the per-file size has crept up. The
recipe should explicitly *re-pop* up to N times rather than rely on the
agent's "check budget" judgment.

### 3. No parallel-fanout pattern for queue-driven routines

The queue-driven routines (`pg-file-backfiller`,
`pg-extension-anthropologist`, `pg-quality-auditor`,
`pg-user-question-harvester`, `pg-docs-miner`) all process one queue
item at a time, in a sequential loop. With a 50-100k output budget per
run, that's 4-10 items — but each item is independent and could be
processed by a separate sub-agent in parallel within the same run. The
foreground sweep pattern (`memory: foreground-sweep-pattern`) already
canonized this: 4 parallel sub-agents per sweep produced ~50 docs in
A21. The cloud routines have never used it.

### 4. `pg-state-keeper` is structurally blocked

`pg-state-keeper` has 2 open PRs (#126, #146) and 3 closed-unmerged. It
is *correctly* surfacing real human-call issues — `origin/main`
rewrite that dropped #115, and the recurring `STATE.md` co-merge
collision. The watchdog itself is healthy; the merger and the
STATE.md serialization are the things that need fixing.

### 5. Every routine prepends `progress/STATE.md` "Last activity"

The structural cause behind #143/#146 staying open. Each routine writes
a `**Last activity:** <YYYY-MM-DD> (cloud/...)` line at the head of
STATE.md. With 7-8 routines doing this each night, only the first to
land merges cleanly; the rest conflict on the same head-of-file region.
The merger can't auto-resolve because both sides are real content.

Fix shape: **one designated routine** (the merger) prepends a
*consolidated* "Last activity" line summarizing the night's work; the
sibling routines write to a per-routine file (`progress/STATE-log.md`
or `progress/cloud-routines/_state-log/<routine>-<date>.md`) which has
no collision surface.

## Recommended recipe edits

Landing this session (separate commit alongside this audit doc):

1. **Fix the three stale `## Budget` footers**
   (`pg-community-pulse`, `pg-upstream-watcher`, `pg-evening-merger`)
   to match the post-2026-06-02 frontmatter. Add a "Budgets must match
   frontmatter; if you bump, bump both" note to `_loader.md` §6.
2. **Bump per-run targets in `pg-upstream-watcher`**:
   "5 interesting commits → 10-15; cap each diff at 12k (was 8k); 3-5
   buildfarm failures → 6-10."
3. **Add explicit re-pop loop in `pg-file-backfiller`** §7:
   "After each doc, if `output_tokens_so_far < 0.50 * max_output_tokens`,
   pop AT LEAST 3 more queue entries before re-checking budget." (The
   current "0.70 floor" is right but the per-iteration check exits too
   eagerly when the agent expects an upcoming large file.)
4. **Add a `parallel:` block in queue-driven recipes** describing the
   sub-agent fanout pattern: pop 3-4 queue entries up front, dispatch
   each to a sub-agent with the brief from
   `memory: foreground-sweep-pattern`. Add to:
   `pg-file-backfiller`, `pg-extension-anthropologist`,
   `pg-user-question-harvester`. (`pg-docs-miner`'s per-source fetch
   serialization makes it less fanout-friendly; skip for v1.)
5. **Serialize `STATE.md` writes**: add `_loader.md` §5.5 — siblings
   write to `progress/cloud-routines/_state-log/<routine>-<date>.md`
   (one-line entry per run); only the merger prepends a consolidated
   line to `progress/STATE.md`. Update sibling recipes' "Per-run
   recipe" to reference the new path.
6. **Auto-rebase STATE.md-only conflicts in `pg-evening-merger`**: when
   a PR's only conflict is `progress/STATE.md` and both sides are
   "Last activity" prepends, accept main's version and re-prepend the
   sibling's line (no information lost). Drop after #5 lands (will
   become unnecessary).

Deferred (need user input on source-set additions, not landed here):

7. **Broaden `pg-community-pulse` source list**: Postgres weekly,
   Postgres podcast RSS, Postgres-related conference CFPs, planet
   Postgres German/Russian/Japanese feeds for non-English misses. User
   should pick the additions.
8. **Broaden `pg-user-question-harvester` source list**: GitHub
   Discussions on `postgres/postgres` and major extensions
   (`pgvector`, `citus`, `timescaledb`), depesz/Hacker News PG-tagged
   posts. The recipe note about SE/Reddit being CDN-blocked is correct
   and stands.

## What I did NOT audit

- Per-recipe code-correctness of every step. Read recipes end-to-end,
  spot-checked the run logs against the recipes; didn't re-verify each
  source-fetch URL.
- The `_preflight` routine's history — 4 merged PRs, all 2026-06-02
  diagnostic noise; not relevant to the steady-state audit.
- Cost in dollars or per-routine token spend. Budgets are in tokens,
  spend rolls up to claude.ai's billing surface, no visibility from
  inside the repo. (Could add to `pg-state-keeper`'s briefing as a
  cumulative `~$N/day` ballpark using model pricing × measured
  tokens.)

## Cross-references

- `.claude/cloud/_loader.md` — shared workflow.
- `.claude/cloud/pg-*.md` — the 10 recipes audited.
- `progress/cloud-routines/<routine>/<date>.md` — per-run logs (source of
  the cost/util numbers).
- `progress/cloud-routines/_digest/<date>.md` — merger digests.
- `memory: foreground-sweep-pattern` — the parallel-agent pattern not
  yet used by the cloud routines.
