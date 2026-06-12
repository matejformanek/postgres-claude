# Backbone audit — 2026-06-12

Honest review of every skill, command, knowledge area, cloud recipe,
persona, and calibration doc — the "backbone" that any future work
on this project sits on. Goal: identify where the skill-creator
review pass + a future cleanup will pay off most.

Tone is intentionally direct. **Each finding includes an action**
(merge / split / rewrite / leave) so the skill-creator pass has
clear instructions.

## What this audit is NOT

- Not a critique of the work itself — the corpus + skills produced
  every Phase A/B/C deliverable, and the methodology generalised.
  Audit-flagging is about future leverage, not retroactive judgment.
- Not a checklist of doctrinal fixes — code-level nits go to a
  `hf(corpus)` PR, not here.
- Not a list of personas to rewrite (Phase B did that work; the
  data is correct).
- Not a list of calibration findings to redo (Phase C froze those).

## Summary table

| Area | Items | Total LOC | Verdict | Top action |
|---|---:|---:|---|---|
| Skills | 27 | ~6 700 | **Strong** with 4 overlap clusters | Tighten boundaries + cross-refs |
| Slash commands | 20 | ~70 KB | **Strong**; one duplication | Merge `pg-start.md` + `pg-start-asan.md` |
| Rules | 1 | 280 | **Strong** | Leave alone |
| Cloud recipes | 11 | ~50 KB | **Recently audited (#151, #160)** | Leave alone for now |
| Knowledge subsystems | 20 | ~variable | Mature; contrib modules are missing | Phase A+ add contrib subsystem docs |
| Knowledge personas | 26 | ~3 800 lines | Mature; data correct | Re-mine in 6mo per per-persona maintenance notes |
| Knowledge calibration | 7 | ~1 200 lines | **Frozen — session-of-record** | Do not rewrite |
| Knowledge idioms | 10 | ~moderate | Underused — only referenced by a few skills | Audit cross-refs |
| Knowledge data-structures | 4 | ~moderate | Sparse — only 4 docs for a large surface | Consider expansion to 8-10 |
| Knowledge architecture | 9 | ~moderate | Stable; some 1+ year old | Spot-check with `pg-quality-auditor` |
| Knowledge issue registers | 124 | ~variable | Active; well-served by `pg-corpus-maintainer` | Leave alone |
| Knowledge ideologies (extensions) | 28 | ~variable | Recent additions (#162); cloud-routine fed | Leave alone |
| Phase D patches | 5 | ~5 KB each | **Pre-send prep done (#163)** | Don't touch in skill-creator pass |

## Skills audit (the big surface)

### Cluster 1 — Patch review trio (THE biggest overlap)

| Skill | LOC | Scope |
|---|---:|---|
| `review-checklist` | 246 | The 8-phase scaffold (incl. Phase 0 reflexes from Phase C) |
| `pg-patch-review` | 524 | Parallel-critic orchestration (5 critics incl. Critic E) |
| `patch-submission` | 201 | Pre-submission self-review |

**Status:** they cross-reference each other correctly (the docs are
consistent). But **`patch-submission` and `pg-patch-review` cover
overlapping ground**: both walk through the same checklist (patch +
checklist + critics) — `patch-submission` does it on YOUR patch
pre-send, `pg-patch-review` does it on OTHERS' patches.

**Skill-creator targets:**
- **Tighten `patch-submission`** to be a thin wrapper around
  `pg-patch-review` invoked with `--self` mode + the
  `commit-message-style` finalize step. Right now it duplicates the
  critic descriptions. Estimated reduction: 201 → ~80 LOC.
- **Leave `review-checklist` + `pg-patch-review` alone** — they're
  the just-landed Phase C surface; redundancy is intentional
  (skill describes WHAT to check, pg-patch-review describes HOW to
  parallelize).

### Cluster 2 — Three-phase planner suite

| Skill | LOC | Scope |
|---|---:|---|
| `pg-feature-brainstorm` | 174 | Phase 1: idea-shaping |
| `pg-feature-plan` | 226 | Phase 2: detailed plan with file:line cites |
| `pg-implement` | 229 | Phase 3: execution against the plan |

**Status:** clean three-phase pipeline. Each has a focused purpose;
the boundaries are sharp. **`pg-implement-discipline.md` rule** is
the constitution that `pg-implement` SKILL.md executes against.

**Skill-creator targets:**
- **Leave the three skills alone** — they're the canonical
  development workflow. Phase C's calibration loop is the test of
  this pipeline; it passed.
- **Add a 4th step** for the upcoming shadow-implementation
  calibration: `pg-shadow-implement` — same plan/implement loop,
  but with a "fetch upstream patch + diff against ours" final
  step. See `knowledge/calibration/shadow-implementation-methodology.md`
  (to be added in the same PR as this audit).

### Cluster 3 — Domain knowledge skills (the bulk)

| Skill | LOC | Status |
|---|---:|---|
| `fmgr-and-spi` | 573 | Largest; well-structured; safe to leave |
| `gucs-bgworker-parallel` | 474 | Large; 3 domains in one skill — **consider splitting** |
| `extension-development` | 407 | Good; recently used in cloud-routine |
| `wal-and-xlog` | 345 | Mature; high-value |
| `executor-and-planner` | 332 | Mature |
| `access-method-apis` | 251 | Mature |
| `catalog-conventions` | 212 | Mature |
| `replication-overview` | 186 | Mid-size; complete |
| `memory-contexts` | 167 | Small but sharply focused |
| `error-handling` | 135 | Small but sharply focused |
| `locking` | 131 | Small; could be expanded with multi-XID + LWLock-rank discipline |
| `parser-and-nodes` | 89 | **Smallest; possibly skeletal** |

**Skill-creator targets:**
- **`gucs-bgworker-parallel`** (474 LOC) — split into 3 focused
  skills: `gucs-config`, `bgworker-and-extensions`, `parallel-query`.
  Three domains crammed into one skill makes lazy-loading awkward
  (the bg-worker user doesn't need parallel-query content + vice
  versa).
- **`parser-and-nodes`** (89 LOC) — likely incomplete. Expand to
  cover: AST → Query → Plan tree shape, mutator/walker conventions,
  the major node types reference. Target: ~200 LOC.
- **`locking`** (131) — expand with multi-XID interaction +
  LWLock rank ordering + a "common deadlock patterns" cheat-sheet.
  Target: ~200 LOC.
- **Leave the rest alone** — they were used in Phase A and
  produced correct citations.

### Cluster 4 — Workflow / tooling skills

| Skill | LOC | Status |
|---|---:|---|
| `build-and-run` | 285 | Slash-command-adjacent; mostly mechanical |
| `debugging` | 455 | Large; consolidates gdb + lldb + AddressSanitizer flows |
| `testing` | 149 | Mid-size; complete |
| `psql` | 193 | Complete |
| `coding-style` | 225 | Complete |
| `commit-message-style` | 268 | Complete |
| `meta-commit-style` | 208 | Complete |
| `pg-claude` | 238 | Master navigator |
| `memory-keeping` | 105 | Memory-system discipline; small but right-sized |

**Skill-creator targets:**
- **Leave all of these alone.** They're the tooling layer; they
  were used heavily in this session and produced correct output.

## Slash commands audit

`.claude/commands/*.md` — 20 commands. Most are PG dev workflow
(setup / start / stop / restart / test / psql / log). The
substantive ones:

- **`pg-review.md`** (8.7 KB) — wraps the `pg-patch-review` skill;
  the entry point for `/pg-review <CF#|PR#|path>`.
- **`pg-plan.md`** (4.1 KB) — wraps `pg-feature-plan`.
- **`pg-implement.md`** (5.9 KB) — wraps `pg-implement`.
- **`pg-brainstorm.md`** (3.5 KB) — wraps `pg-feature-brainstorm`.
- **`refresh-upstream.md`** (5.2 KB) — manual anchor-bump + corpus
  refresh; will partially overlap with the new `pg-anchor-refresh`
  cloud routine.

**Skill-creator targets:**
- **`pg-start.md`** (2.6 KB) and **`pg-start-asan.md`** (3.3 KB) —
  duplicate ~60% of content. Merge into one `pg-start.md` that takes
  `--asan` as a flag.
- **`refresh-upstream.md`** — needs a note that this is the
  *manual* anchor-bump path; the daily one is the new
  `pg-anchor-refresh` cloud routine.
- **Add `pg-shadow.md`** for the shadow-implementation calibration
  loop (alongside the new skill).
- **Leave the rest alone.**

## Knowledge structure audit

### Per-file docs (2 170)
- 95%+ substantive coverage after #161
- Remaining gap (~240 files) explicitly queued for `pg-file-backfiller`
- Anchor freshness: 2-day lag, `pg-anchor-refresh` recipe ready to handle this
- **No action needed.** This is the corpus payload — leave it to
  the cloud routines to grow.

### Subsystems (20)
- All backend subsystems documented
- **No contrib-module subsystem docs** — flagged across multiple
  Phase C calibration docs. The 28 ideology docs cover extensions
  loosely, but key contrib modules (pgcrypto, ltree, hstore, pg_prewarm,
  postgres_fdw, btree_gist, etc.) deserve subsystem-style docs.

**Action:** Add 6-8 contrib subsystem docs in a follow-up:
- `contrib-pgcrypto.md` (used by CB1 calibration)
- `contrib-ltree.md` (CB7)
- `contrib-hstore.md` (CB8)
- `contrib-pg_prewarm.md` (SP6)
- `contrib-postgres_fdw.md` (mentioned in many threads)
- `contrib-btree_gist.md` (Tomas Vondra commits + amcheck)
- `contrib-pg_stat_statements.md`
- `contrib-pg_walinspect.md`

### Personas (26)
- Phase B work was thorough; data correct as of 2026-06-12
- 6-month re-mine canonized for `chao-li.md` (most recent) and
  `noah-misch.md` (newest persona)
- Phase B #5 archive-mining revealed ~15 names below the
  contributor-map display cutoff (`hf(corpus)` follow-up available)

**Action:** Don't touch in this audit. Refresh on schedule.

### Calibration (7 docs)
- 5 per-patch + README + gap-catalog
- **Frozen as session-of-record** — they're the source of the
  `notes.md` files in `patches/<slug>/`
- Future calibrations will land alongside these; do not rewrite
  retroactively

**Action:** Read-only. Skill-creator must NOT touch these.

### Idioms (10) and data-structures (4)
- **Underused** — only ~3 skills reference idioms directly via
  `[[link]]`, and data-structures is sparse (only 4 docs for the
  whole PG type-system + buffer-state + lock-state surface)
- These are the "patterns" layer the skill-creator pass could
  expand

**Action:**
- Audit which idioms exist + which are missing. Common candidates
  to add: `idioms/fastpath-locks.md`, `idioms/sinvaladt-broadcast.md`,
  `idioms/heap-tuple-decompression-pattern.md`,
  `idioms/list-traversal-conventions.md`.
- Expand data-structures to cover: `Bitmapset`, `MemoryContext`,
  `Snapshot`, `MultiXactId`, `XLogReaderState`, `BufferDesc` (already
  partial), `PROC + PROCARRAY + lock-waits chain` (more depth).

### Architecture (9)
- Stable; some 1+ year old at the anchor
- `pg-quality-auditor` audits these on its AUDIT-mode rotation

**Action:** Defer — auditor handles drift.

### Issue registers (124)
- Healthy, active; `pg-corpus-maintainer` mirrors them; auditor
  triages

**Action:** Leave alone.

### Ideologies (28)
- Recent (most added in last 2 weeks via `pg-extension-anthropologist`)

**Action:** Leave alone.

## What's missing (gaps the skill-creator could close)

In rough priority order:

1. **`pg-shadow-implement` skill + command** (new) — the
   implementation-side calibration loop. See methodology doc this
   PR also lands.
2. **Contrib-subsystem docs** (8) — under `knowledge/subsystems/`,
   adjacent to the 20 backend ones. ~150 LOC each.
3. **Idioms expansion** (5-6 new docs) — fastpath-locks,
   sinvaladt-broadcast, heap-tuple-deform pattern, list-traversal,
   visibility-map-update.
4. **Data-structures expansion** (4 new) — Bitmapset, Snapshot,
   MultiXactId, XLogReaderState.
5. **`gucs-bgworker-parallel` → 3 skills** — clean separation of
   concerns; better lazy-loading.
6. **`parser-and-nodes` + `locking` expansion** — bring the small
   skills to ~200 LOC each.
7. **`patch-submission` shrink** — collapse redundancy with
   `pg-patch-review`.
8. **Slash command merges** — `pg-start.md` + `pg-start-asan.md` →
   one.

## What's drifting (and the fix)

- **Anchor 2-day lag** → `pg-anchor-refresh` recipe (#160) handles
  this once you create the RemoteTrigger. Confirmed by you in this
  session.
- **`contributor-map.md` top-N cutoff** (Phase B #5 finding) →
  `hf(corpus)` refresh available, low effort, not urgent.
- **Calibration docs cite specific Phase B persona text** that
  was correct when written — if persona docs get rewritten in
  6-month re-mine, the calibration docs' bullet citations will
  drift. `pg-quality-auditor` won't catch this since it audits
  per-file knowledge against source, not knowledge against
  knowledge.

**Action:** Add a `pg-corpus-maintainer` pass mode (or new routine)
that does cross-corpus link-and-citation verification. Defer this —
it's a polish item, not urgent.

## Skill-creator readiness verdict

**Ready.** The corpus is mature enough that a skill-creator pass
will produce measurable improvements without breaking things. Top
3 highest-value targets:

1. **Split `gucs-bgworker-parallel`** — clean win, no behavioural risk
2. **Expand `parser-and-nodes` + `locking`** — fills clear gaps
3. **Shrink `patch-submission`** — reduces drift between it and
   `pg-patch-review`

The skill-creator brief doc (this PR) names the exact files in
scope, anti-targets, and the form of output expected.

## Cross-references

- `.claude/skills/*/SKILL.md` — the 27 skills audited
- `.claude/commands/*.md` — the 20 slash commands audited
- `progress/skill-creator-brief.md` — input doc for your plugin
- `knowledge/calibration/shadow-implementation-methodology.md` —
  the new calibration loop (lands in this same PR)
- `progress/STATE.md` — Phase E start declared in this PR
