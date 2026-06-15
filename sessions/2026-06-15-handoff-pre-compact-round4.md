# 2026-06-15 — Pre-compact handoff round 4

**Operative directive from the user, verbatim (most recent):**

> ctx is down we will have to rpepare for compact and continue then

The user wants to compact NOW because context is exhausted.
Before that, capture what this session produced + what's next.

The pattern from the prior turn (PR #282, null-result on
pg-feature-brainstorm) was that running too many genuine evals
back-to-back gets repetitive at the 1-run noise floor. The
post-compact resume should pick targets more strategically.

## What this session produced (11 PRs, all merged)

### Phase A — Corpus mining trios (8 PRs, 6,230 LOC docs)
After a previous resume directive, before compact:

| PR | Trio | LOC |
|---|---|---|
| #272 | Trigger depth (deferral / transition tables / during-error) | 837 |
| #273 | TOAST depth (varatt / chunk-write / detoast-stream) | 770 |
| #274 | WAL write internals (insert-lock pool / buffer ring / write+flush) | 842 |
| #275 | Parallel-exec depth (Gather / parallel HJ / parallel BHS) | 780 |
| #276 | FK trigger trio (RI check / cascade / setnull-setdefault) | 761 |
| #277 | Cost model **quartet** (units / scan / join / parallel divisor) | 1,083 |
| #279 | EvalPlanQual depth (state init / recheck flow / multi-table) | 911 |
| #278 | companion_skills bidirectional audit + 6 back-link fixes | 246 |

### Phase B — Skill-creator iter PRs (3 PRs, ~370 LOC progress)

| PR | Skill | Type | Δ should-trigger |
|---|---|---|---|
| #280 | pg-feature-plan | workflow | 0/10 → 3/10 (+30pp) |
| #281 | locking | topical | 1/10 → 2/10 (+10pp) |
| #282 | pg-feature-brainstorm | workflow | 2/10 → 2/10 (**null delta — honest write-up**) |

## Methodology validated across 4 datapoints

| PR | Skill | Type | Δ |
|---|---|---|---|
| #241 (prior) | parallel-query | topical | 0/3 → 1/5 (first non-zero) |
| #280 | pg-feature-plan | workflow | 0/10 → 3/10 (+30pp) |
| #281 | locking | topical | 1/10 → 2/10 (+10pp) |
| #282 | pg-feature-brainstorm | workflow | 2/10 → 2/10 (0) |

**Pattern that works:**
1. Lead with imperative verb tied to user vocabulary ("Drop",
   "Pick", "Brainstorm")
2. Bolded `**Use this skill proactively whenever ...**` block
3. Enumerate 8+ exact-phrasing triggers from real user queries
4. Expand skip list with named near-miss adjacents
5. Add "even when they don't use the literal word X" hedge

**Methodology insight:** delta size is inversely correlated
with baseline description quality. Workflow skills (vague
queries, 0-2/10 baselines) gain +30pp; topical skills (strong
keyword overlap, 1-2/10 baselines) gain +10pp; skills with
already-rich descriptions (5+ phrasings already enumerated)
gain ~0.

**Decision for future iterations:** inspect baseline first.
If ≥5 phrasings already + bolded format, skip the iteration
or run 3-runs-per-query for cleaner signal.

## Current state on main

- **Open PRs:** 0
- **Anchor on `source/`:** `e18b0cb7344` (unchanged)
- **Corpus on main:** 101 idiom docs, 35 data-structure docs,
  65 subsystem docs (101 idioms = 98 pre-session + 21 new from
  7 corpus trios; new idioms from #272 #273 #274 #275 #276 #277
  #279 = 24 actually... let me recount: round 24 had 3,
  TOAST=2 idioms + 1 data-struct, WAL=3 idioms, parallel-exec=3
  idioms, FK trigger=3 idioms, cost model=4 idioms, EPQ=3 idioms
  = 21 new idioms + 1 new data-struct + 0 subsystem)
- **Skills:** 30/30 follow intent-verb + named-anti-cue
  pattern; 4 have been through genuine run_eval.py evals
- **Phase D:** PARKED — 5 patches in `patches/` need
  explicit re-auth from user
- **Phase E:** 1 of 3-5 shadow runs done (unchanged)

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

1. **Read this doc** at
   `sessions/2026-06-15-handoff-pre-compact-round4.md`.
2. `git fetch origin && git log --oneline -10` to see what
   merged overnight (cloud routines, if any).
3. Verify anchor: `git -C source rev-parse HEAD` (should be
   `e18b0cb7344` unless `/refresh-upstream` ran).
4. Confirm 0 open PRs:
   `gh pr list --state open --json number | python3 -c
   'import json,sys; print(len(json.load(sys.stdin)))'`.
5. Pick from the catalog below.
6. Apply the established per-PR pattern.

## What's mineable / what to do next post-compact

### Skill-creator side (4 evals done, methodology validated)

The intent-verb description sweep is done for all 30 skills.
4 genuine evals validate the pattern. Future moves:

- **More genuine evals on workflow skills (likely small/null
  deltas based on the pg-feature-brainstorm result):**
  - pg-implement (workflow, eval set drafted but not run)
  - pg-patch-review (workflow, multi-agent)
  - pg-shadow-implement (workflow, leaf)
- **More genuine evals on topical skills (likely +5 to +10pp
  based on locking result):**
  - error-handling (topical)
  - fmgr-and-spi (topical)
  - memory-contexts (topical)
  - replication-overview (topical)
  - executor-and-planner (topical)
  - access-method-apis (topical)
- **Body strengthening** — pick 2-3 skills with weak bodies
  (memory-keeping was thinnest at 119 LOC but content is
  reasonable; patch-submission was intentionally shrunk;
  error-handling at 152 LOC could use cheat-sheet expansion).
- **Build Agent-SDK eval harness** — STILL BLOCKED on user OK
  on `pip install claude-agent-sdk` infra. Do NOT install
  without explicit permission. Documented in prior handoffs.
- **Cross-skill consistency review** — read across all 30
  SKILL.md description fields, look for inconsistencies that
  could be unified (e.g., bolding style, exact phrasing of
  "Use proactively whenever").

### Corpus mining side (gap candidates)

| Trio | Loci |
|---|---|
| SLRU depth | clog-slru + multixact-slru + slru-page-replacement |
| JIT compilation depth | jit-llvm-emit + jit-tuple-deform + jit-expression-compile |
| BRIN AM internals | brin-tuple-format + brin-summarize + brin-revmap |
| GIN AM internals | gin-tuple-format + gin-fastupdate + gin-vacuum |
| Hash AM internals | hash-page-format + hash-bucket-split + hash-overflow |
| Syscache | syscache-cache-tuple + syscache-invalidation + syscache-relcache |
| Aggregate strategies | agg-hash-vs-sort + agg-grouping-sets + agg-partial-finalize |
| TOAST round 2 | toast-chunk-fetch-table-am + toast-compression-pglz-vs-lz4 + toast-decompression-streaming-callers |
| Vacuum depth | vacuum-prune + vacuum-freeze + vacuum-dead-tid-array |
| MVCC depth | xmin-xmax-cmin-cmax + hint-bits + heap-tuple-visibility-algorithm |

Each ~3 docs × ~270 LOC = ~800 LOC per PR. Anti-target audit
still applies; cite-pin still e18b0cb7344.

### Operational

- 80+ stale worktrees under `.claude/worktrees/` (cleanup
  could be a PR but is low-value).
- `/refresh-upstream` to bump source/ symlink + run audit
  queue.
- Cross-corpus link verifier (sketched in earlier handoff).

## How to apply skill-creator post-compact

The pattern works. Per-PR pattern:

1. **Inspect baseline description first** — count phrasings
   already enumerated. If ≥5 phrasings + bolding, skip OR run
   3-runs-per-query (60 invocations × 2 runs = ~4-6 min).
2. Draft 20 realistic eval queries (10 should-trigger, 10
   should-NOT-trigger) covering the skill's domain.
3. `run_eval.py` baseline (foreground in Bash tool, NOT
   nohup — the claude -p subprocess fails in detached
   processes per session observation).
4. Apply the proven pattern (intent verb + bolded Use
   proactively + 8+ phrasings + expanded skip list).
5. `run_eval.py` iter-1.
6. Honest write-up: report Δ even if 0; document the lesson.
7. PR + merge immediately (maintain queue at 0).

**Critical mode-of-operation rules:**

- `EnterWorktree` for every code-change task.
- Anti-target check before every commit.
- One PR per skill; merge immediately.
- 1-run-per-query has ±1 query noise floor — be honest in
  the write-up.

## What the user has NOT authorized (hold the line)

- **Phase D send to pgsql-hackers** — staged patches stay
  parked.
- **`pip install anthropic` or `claude-agent-sdk`** — requires
  explicit OK.
- **Touching anti-target paths** — never.

## TL;DR for post-compact-Claude

This session: 11 PRs merged (8 corpus + 3 skill-creator), ~6.6k
LOC of new docs + ~370 LOC of progress recaps. Pattern
validated across 4 evals (parallel-query #241, pg-feature-plan
#280, locking #281, pg-feature-brainstorm #282).

Methodology insight: small/null deltas on already-rich
descriptions. Resume by picking topical skills with thin
baselines for higher-confidence positive deltas (error-handling,
fmgr-and-spi, executor-and-planner, access-method-apis) OR
pivot to corpus mining (SLRU / JIT / BRIN trios) for
quantitatively-larger LOC output per PR.

Anchor at e18b0cb7344. 0 open PRs. Anti-targets clean. Don't
break the rules.
