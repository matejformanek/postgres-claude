# Backbone re-audit — 2026-06-13

Snapshot after the skill-creator pass (PRs #167-#171, plus session log
PR #182 and fixup commits on each branch). Per the end-of-implementation
gate in the plan, this re-runs the methodology from
`progress/backbone-audit-2026-06-12.md` and tags each verdict with
status (`done` / `partial` / `deferred` / `not addressed`).

The pass operated **at the file level only** — verdict resolution is
read from the diffs on the 6 open branches and from the merged state
once they land. No re-derivation of audit findings.

## Skill verdicts (from §"Skills audit")

### Cluster 1 — Patch review trio

| Verdict | Status | Where |
|---|---|---|
| Shrink `patch-submission` 201 → ~80 LOC | **done** (201 → 134; thin wrapper) | PR #169 |
| Leave `review-checklist` / `pg-patch-review` alone for structure | **done** (rubric polish only) | PR #169 |
| Add REJECT-A/B/C verdict track | **done** (M4 from Phase E run 1) | PR #169 (Phase 0 + Critic E + Stage 3) |

### Cluster 2 — Planner suite

| Verdict | Status | Where |
|---|---|---|
| Add M2 context-awareness pre-step to `pg-feature-plan` | **done** | PR #168 |
| Add M3 cite-verify final step to `pg-feature-plan` | **done** | PR #168 |
| Add M5 thread-engagement classification to `pg-feature-plan` | **done** | PR #168 |
| Re-verify R1-R12 references in `pg-implement-discipline.md` | **done** (12 ### R<N> headings confirmed present) | PR #168 |
| Rubric polish all 3 | **done** | PR #168 |

### Cluster 3 — Domain knowledge (12 → 14 skills)

| Verdict | Status | Where |
|---|---|---|
| Split `gucs-bgworker-parallel` (474 LOC) into 3 sibling skills | **done** — `gucs-config` (208) + `bgworker-and-extensions` (251) + `parallel-query` (220) | PR #170 |
| Delete original `gucs-bgworker-parallel/` dir, no shim | **done** | PR #170 |
| Cross-ref retarget for SPLIT in plan scope | **done** (skills + `knowledge/idioms/`) | PR #170 |
| Expand `parser-and-nodes` 89 → ~200 LOC | **done** (212 LOC) | PR #170 |
| Expand `locking` 131 → ~200 LOC | **done** (276 LOC) | PR #170 |
| Leave other 9 alone structurally; rubric polish | **done** | PR #170 |

### Cluster 4 — Workflow / tooling (9 skills)

| Verdict | Status | Where |
|---|---|---|
| Leave all 9 alone structurally | **done** | PR #167 |
| Rubric polish all 9 | **done** | PR #167 |
| Update `pg-claude` to reflect post-SPLIT skill list (stubs) | **done** (PR #167 added stubs; PR #170 replaced with real rows) | PR #167 + PR #170 |

## Slash-command verdicts (from §"Slash commands audit")

| Verdict | Status | Where |
|---|---|---|
| Merge `pg-start.md` + `pg-start-asan.md` into one with `--asan` flag | **done** (this PR) | PR #183 (this PR) |
| Add `refresh-upstream` note about `pg-anchor-refresh` cloud routine | **done** (this PR) | PR #183 (this PR) |
| Add `pg-shadow.md` | **not addressed** — needs new `pg-shadow-implement` skill first (see below) | — |

## Knowledge verdicts (from §"Knowledge structure audit")

### Subsystems — contrib-module docs

| Verdict | Status | Where |
|---|---|---|
| `contrib-pgcrypto.md` | **done** (127 LOC) | PR #171 |
| `contrib-ltree.md` | **done** (128 LOC) | PR #171 |
| `contrib-hstore.md` | **done** (118 LOC) | PR #171 |
| `contrib-pg_prewarm.md` | **done** (111 LOC) | PR #171 |
| `contrib-postgres_fdw.md` | **done** (141 LOC) | PR #171 |
| `contrib-btree_gist.md` | **done** (128 LOC) | PR #171 |
| `contrib-pg_stat_statements.md` | **done** (139 LOC) | PR #171 |
| `contrib-pg_walinspect.md` | **done** (this PR) | PR #183 (this PR) |

The audit named 8; the brief dropped `pg_walinspect`; this PR fills it.
Tier 3 complete.

### Personas

| Verdict | Status |
|---|---|
| Don't touch in this pass; 6-month re-mine on schedule | **done** (untouched) |

### Calibration

| Verdict | Status |
|---|---|
| Read-only; do not rewrite | **done** (untouched) |

### Idioms (10) and data-structures (4)

| Verdict | Status | Note |
|---|---|---|
| Expand idioms (+5-6 new docs) | **deferred** | Out of skill-creator scope per brief; future work. |
| Expand data-structures (+4 new docs) | **deferred** | Same. |
| Audit cross-refs into idioms | **partial** | PR 4's SKILL.md updates link idioms more consistently, but no separate cross-ref audit was run. |

### Architecture

| Verdict | Status |
|---|---|
| Defer to `pg-quality-auditor` | **done** (untouched; cloud auditor #178 already fixed 2 docs overnight) |

### Issue registers, ideologies

| Verdict | Status |
|---|---|
| Leave alone | **done** (untouched) |

## Anti-targets (per plan)

| Path | Status |
|---|---|
| `knowledge/calibration/**` | **untouched** ✓ |
| `knowledge/personas/**` | **untouched** ✓ |
| `knowledge/files/**` | **untouched** ✓ |
| `patches/**` | **untouched** ✓ |
| `progress/STATE.md` | **untouched by this work stream** (cloud routine `pg-evening-merger` did the only update overnight) ✓ |
| `progress/cloud-routines/**` | **untouched** ✓ |
| Top-level `CLAUDE.md` | **untouched** ✓ |
| `pg-claude-plan.md` | **untouched** ✓ |

Diff check empty against all 8 on every PR.

## What this pass did NOT do

1. **`pg-shadow-implement` skill + command** (audit gap #1) — was named
   as "missing" in the audit's §"What's missing". Not addressed; would
   be a new ~200-300 LOC skill plus a `/pg-shadow` command wrapper.
   Pre-requisite for the audit's `pg-shadow.md` command.
2. **Idioms expansion** (5-6 new docs: `fastpath-locks`,
   `sinvaladt-broadcast`, `heap-tuple-decompression-pattern`,
   `list-traversal-conventions`, `visibility-map-update`).
3. **Data-structures expansion** (4 new docs: `Bitmapset`, `Snapshot`,
   `MultiXactId`, `XLogReaderState`).
4. **Cross-corpus link-and-citation verifier** (`pg-corpus-maintainer`
   mode or new routine) — mentioned in §"What's drifting".
5. **`contributor-map.md` top-N cutoff `hf(corpus)` refresh** — Phase B
   #5 finding, low priority.

## Remaining drift items

- **Anchor `e18b0cb7344`** still current — `pg-anchor-refresh`
  cloud routine handles the next bump.
- **Calibration docs cite persona text** — when personas get re-mined
  in 6 months, the calibration bullet citations will drift. Audit
  flagged this; deferred.

## Phase status post-pass

| Phase | Status | Gating |
|---|---|---|
| Phase A (corpus completeness) | **complete** | Phase B took over |
| Phase B (personas) | **on 6-month maintenance cadence** | Next re-mine in early 2027 |
| Phase C (calibration) | **frozen** | Session-of-record |
| Phase D (patch send) | **PARKED** | Needs explicit user re-auth |
| Phase E run 1 (money-fx) | **complete** | A REJECT-A; M1-M5 surfaced |
| Phase E run 2 (Filip Janus temp-file compression) | **unblocked** by PR #168 + #169 merge | Recommended next step |

## Verdict — skill-creator pass outcome

**Net positive.** The audit's headline verdicts (SPLIT, EXPAND × 2,
SHRINK, rubric polish all skills, M1-M5 integration) all resolved.
The unaddressed items are net-new work (`pg-shadow-implement` skill,
idioms expansion, data-structures expansion) rather than leftover
audit findings. Phase E run 2 is the first thing to test the
methodology improvements; that's the natural next session.

## Cross-references

- `progress/backbone-audit-2026-06-12.md` — the audit this snapshot resolves.
- `progress/skill-creator-brief.md` — the rubric applied across all PRs.
- `sessions/2026-06-13-skill-creator-pass-complete.md` — session log of the implementation arc.
- PRs #167 - #171 + #182 + (this PR #183) — the change-stream.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md` — source of M1-M5.
- `knowledge/calibration/shadow-implementation-methodology.md` — Phase E run 2 launches against this.
