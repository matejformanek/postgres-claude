# 2026-06-14 — Pre-compact handoff round 3

**Operative directive from the user, verbatim:**

> i want u to prepare for compact and then same way continue
> with the skill creator and making sure we have topnotch
> data and skills here

After compact: keep producing skill-creator iterations AND
corpus-mining trios. "Topnotch" = quality bar stays high
(cite verification, established shape, cross-ref discipline,
anti-target rule, intent-verb pattern on every skill touched).

## What this run produced (21 PRs, all merged)

Earlier in this conversation, after the previous compact, the
user said *"do as u feel is right and continue until i tell u
to stop"*. That session produced:

### Phase 1 — PR-queue triage
- **#240** — consolidation PR documenting 60→0 PR triage +
  pg-evening-merger recipe fix (#239 expanded scope to
  ALL PRs, not just `cloud/`).

### Phase 2 — Skill-creator intent-verb sweep (10 PRs, 27 skills)
PR #241 found that **intent-verb + named anti-cues** moves
`run_eval.py` trigger rate from 0/3 to 1/3 (parallel-query).
Pattern then applied to all remaining skills:

| PR | Cluster |
|---|---|
| #241 | parallel-query (eval-validated) |
| #242 | gucs-config + bgworker-and-extensions + extension-development (one eval-validated) |
| #243 | executor-and-planner + parser-and-nodes + catalog-conventions |
| #244 | error-handling + replication-overview + locking |
| #245 | pg-claude + memory-keeping + coding-style |
| #246 | pg-feature-brainstorm + pg-feature-plan + pg-implement |
| #247 | fmgr-and-spi + memory-contexts + access-method-apis |
| #248 | review-checklist + meta-commit-style + wal-and-xlog |
| #249 | pg-patch-review + build-and-run + recap doc |
| #250 | debugging + testing + patch-submission (anti-cue spot-check) |

**Outcome: 27 of 27 skills under the pattern. Recap doc at
`progress/skill-creator-intent-verb-sweep.md`. 0 broken
companion_skills refs (verified).**

### Phase 3 — Corpus mining (10 PRs, ~30 docs)
Resumed 3-doc-cluster pattern:

| PR | Cluster |
|---|---|
| #251 | data-structures r7 — executor state (EState + PlanState + ExprContext) |
| #252 | idioms r16 — storage (relation-extension-lock + vacuum-truncate + tableam-index-fetch) |
| #253 | idioms r17 — plancache (prepared-stmt + generic-vs-custom + invalidation) |
| #254 | data-structures r9 — lock (LOCKTAG + LOCK + PROCLOCK) |
| #255 | idioms r18 — rewriter (RLS + view-pushdown + security-barrier) |
| #256 | idioms r19 — logical decoding (snapshot + output-plugin + replication-origin) |
| #257 | idioms r20 — subscription apply (worker-loop + tablesync + conflict) |
| #258 | idioms r21 — DDL processing (ProcessUtility + event-trigger + DDL-deparse) |
| #259 | idioms r22 — partition (attach-detach + runtime-pruning + bound-comparison) |
| #260 | idioms r23 — FDW pair (routine-callbacks + iterate-scan) — stopped at 2/3 |

**Per-PR pattern (used every time):**
- Worktree-first (`EnterWorktree`).
- Verify struct/function locus in `source/` via `grep -n` before drafting.
- Write 3 docs ~270 LOC each, established shape:
  Anchors → struct/flow summary → field commentary →
  Invariants → Useful greps → Cross-references.
- Anti-target audit: `git diff --stat` against the 8
  protected paths returns empty.
- Cite spot-check at anchor `e18b0cb7344`.
- Commit with meta-style + `Co-Authored-By: Claude Opus 4.7
  (1M context) <noreply@anthropic.com>`.
- Rename branch (drop `worktree-` prefix) → push → PR →
  squash-merge.
- Maintain open-PR count at 0 (merge immediately after each).

## Current state on main

- **Open PRs:** 0
- **Anchor on `source/`:** `e18b0cb7344` (a few weeks behind
  upstream; `/refresh-upstream` needed)
- **Corpus on main:** 80 idiom docs, 34 data-structure docs,
  65 subsystem docs (including contrib-*)
- **Skills:** 27/27 follow intent-verb + named-anti-cue
  pattern
- **Phase D:** PARKED — 5 patches in `patches/` need
  explicit re-auth from user to send upstream
- **Phase E:** 1 of 3-5 shadow runs done (money-fx-exchange,
  REJECT-A grade A)

## Anti-target paths (NEVER touch in foreground work)

```
knowledge/calibration/**
knowledge/personas/**
knowledge/files/**
patches/**
progress/STATE.md             (except consolidation PRs)
progress/cloud-routines/**    (cloud-routine lane only)
CLAUDE.md
pg-claude-plan.md
```

The audit command (run before every commit):

```bash
git diff --stat origin/main..HEAD -- \
    knowledge/calibration knowledge/personas knowledge/files \
    patches progress/STATE.md progress/cloud-routines \
    CLAUDE.md pg-claude-plan.md
```

Empty = clean. Non-empty = STOP and re-think.

## Post-compact resume checklist

1. **Read this doc** at `sessions/2026-06-14-handoff-pre-compact-round3.md`.
2. `git fetch origin && git log --oneline -10` to see what
   merged overnight (cloud routines, if any).
3. Verify anchor: `git -C source rev-parse HEAD` (should be
   `e18b0cb7344` unless `/refresh-upstream` was run).
4. Confirm 0 open PRs: `gh pr list --state open --json
   number | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'`.
5. **Pick the next move** from the catalog below.
6. Apply the per-PR pattern (see Phase 3 section above).

## What's mineable / what to do next post-compact

**Skill-creator side (the user emphasized this):**

The intent-verb description rewrite is done (27/27). Logical
next steps:
- **Build the Agent-SDK eval harness** (the original PR #202
  methodology rec; ~5-10 hours; requires `pip install
  claude-agent-sdk` + Anthropic API auth — needs user OK on
  infra).
- **Strengthen SKILL.md bodies** (not just descriptions) for
  skills where the methodology pass surfaces gaps. E.g.,
  expand parser-and-nodes / locking with richer cheat-sheet
  sections.
- **Add more genuine evals** — pick 3-5 skills that haven't
  had `run_eval.py` run yet, eval them, document benchmark
  trajectory. Cheap; produces signal even with the noisy
  harness.
- **Verify cross-skill `companion_skills` graph** — make
  sure every link is bidirectional where it should be (e.g.,
  if A lists B as a companion, B should list A too in most
  cases).

**Corpus mining side (3-doc trios that fit the proven shape):**

| Trio | Loci |
|---|---|
| Trigger system depth | constraint-deferral + transition-tables + trigger-during-error |
| TOAST internals depth | varatt-struct + toast-chunk-write + detoast-stream-consumption |
| WAL write internals | XLogInsertLock-partitioning + WAL-buffer-state + page-write-flush |
| Foreign-key triggers | RI_FKey_check + RI_FKey_cascade + RI_FKey_setnull |
| Parallel exec depth | Gather/GatherMerge + parallel-hash-join + parallel-bitmap-heap |
| Cost model | cost_seqscan/index/join + cost.h units + parallel-cost adjustments |
| FDW round 23 third | fdw-direct-modify (planned but skipped) |

Each ~3 docs, ~270 LOC each, ~800 LOC per PR. Established
shape applies cleanly.

**Operational items:**
- 75 stale worktree directories under `.claude/worktrees/`.
  Cleanup: `git worktree list | grep '/ft_\|/cloud/' | awk
  '{print $1}' | xargs -I {} git worktree remove --force {}`
  Or selective per-branch.
- `/refresh-upstream` to bump source/ symlink + trigger the
  audits queue in PR #224.
- Cross-corpus link verifier — sketch in a prior handoff;
  build as a cloud routine.

## How to apply skill-creator post-compact

User said *"continue with the skill creator and making sure
we have topnotch data and skills here"*. The pattern that
worked this run:

1. **Description rewrites** when noun-first. (DONE for all
   27; if a new skill is added, apply the same pattern.)
2. **Run `run_eval.py`** for new skills as provenance (one
   datapoint per skill is enough; the methodology gap
   doesn't invalidate the work).
3. **Body audits** for skills with low rubric scores: ensure
   numbered steps, file:line cites, named anti-cues in body
   too, useful greps, cross-references.
4. **Cross-ref consistency** — companion_skills bidirectional.

**Critical mode-of-operation rules:**
- `EnterWorktree` for every code-change task.
- Anti-target check before every commit.
- One PR per cluster; merge immediately to keep queue at 0
  (so `pg-evening-merger` doesn't have to triage anything
  the next morning).
- Cite at file:line, never approximate.

## What the user has NOT authorized (post-compact, hold the line)

- **Phase D send to pgsql-hackers** — staged patches stay
  parked.
- **Anthropic API key setup / claude-agent-sdk install** —
  requires explicit OK before installing dependencies.
- **Touching anti-target paths** — never.

## TL;DR for post-compact-Claude

You just did 21 PRs in one resume run. The user wants more,
specifically on **skill-creator + corpus quality**. The arc
is:

1. Pick a cluster (skill-creator iteration OR corpus trio).
2. Apply the proven per-PR pattern.
3. Merge immediately.
4. Repeat until user stops you.

Queue at 0. Anchor at e18b0cb7344. Phase D still parked.
Phase E still has 2-4 shadow runs queued. Don't break the
rules. Make the data and skills topnotch.
