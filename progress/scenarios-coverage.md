# Scenarios coverage

Mirror of `progress/coverage.md` for the `knowledge/scenarios/` layer.
Tracks per-scenario freshness, anchor drift, and gaps surfaced by
planner runs.

**Layer:** `knowledge/scenarios/` (task-shaped playbooks).
**Layer doc:** `knowledge/scenarios/README.md`.
**Decision tree:** `knowledge/scenarios/_index.md`.
**Anchor at last refresh:** `e18b0cb7344` (2026-06-16).

## Per-scenario freshness

Every scenario carries a `canonical_commit` (historical reference,
never auto-bumped) and a `last_verified_commit` (bumped by the
refresh discipline). The table below reflects each scenario's
`last_verified_commit` against the current `source/` HEAD.

`pg-feature-plan` Step 0 reads `last_verified_commit` and emits a
"scenario stale" warning if the plan's anchor SHA differs from it.

| # | Scenario | last_verified_commit | Drift vs current HEAD | Checklist rows |
|---|---|---|---|---|
| 1 | bump-catversion | `e18b0cb7344` | ✓ fresh | 7 |
| 2 | add-new-builtin-function | `e18b0cb7344` | ✓ fresh | 11 |
| 3 | add-new-data-type | `e18b0cb7344` | ✓ fresh | 18 |
| 4 | add-new-operator-class | `e18b0cb7344` | ✓ fresh | 12 |
| 5 | add-new-operator | `e18b0cb7344` | ✓ fresh | 10 |
| 6 | add-new-cast | `e18b0cb7344` | ✓ fresh | 9 |
| 7 | add-new-aggregate-function | `e18b0cb7344` | ✓ fresh | 10 |
| 8 | add-new-error-code | `e18b0cb7344` | ✓ fresh | 10 |
| 9 | add-new-system-catalog-column | `e18b0cb7344` | ✓ fresh | 14 |
| 10 | add-new-system-view | `e18b0cb7344` | ✓ fresh | 10 |
| 11 | add-new-sql-keyword | `e18b0cb7344` | ✓ fresh | 16 |
| 12 | add-new-node-type | `e18b0cb7344` | ✓ fresh | 21 |
| 13 | add-new-utility-statement | `e18b0cb7344` | ✓ fresh | 21 |
| 14 | add-new-plan-node | `e18b0cb7344` | ✓ fresh | 23 |
| 15 | add-new-expression-eval-step | `e18b0cb7344` | ✓ fresh | 8 |
| 16 | add-new-cost-model-knob | `e18b0cb7344` | ✓ fresh | 11 |
| 17 | add-new-index-am | `e18b0cb7344` | ✓ fresh | 36 |
| 18 | add-new-table-am | `e18b0cb7344` | ✓ fresh | 16 |
| 19 | add-new-wal-record | `e18b0cb7344` | ✓ fresh | 13 |
| 20 | add-new-buffer-strategy | `e18b0cb7344` | ✓ fresh | 17 |
| 21 | add-new-guc | `e18b0cb7344` | ✓ fresh | 18 |
| 22 | add-startup-hook | `e18b0cb7344` | ✓ fresh | 11 |
| 23 | add-new-bgworker | `e18b0cb7344` | ✓ fresh | 17 |
| 24 | add-new-hook | `e18b0cb7344` | ✓ fresh | 10 |
| 25 | add-new-lwlock-tranche | `e18b0cb7344` | ✓ fresh | 17 |
| 26 | add-new-shared-memory-region | `e18b0cb7344` | ✓ fresh | 17 |
| 27 | add-new-pg-stat-view | `e18b0cb7344` | ✓ fresh | 19 |
| 28 | add-new-protocol-message | `e18b0cb7344` | ✓ fresh | 19 |
| 29 | add-new-replication-message | `e18b0cb7344` | ✓ fresh | 20 |
| 30 | add-new-extension | `e18b0cb7344` | ✓ fresh | 15 |
| 31 | add-new-test-module | `e18b0cb7344` | ✓ fresh | 15 |

**Total: 31 scenarios, 449 checklist rows.**

## Validation

Run `python3 .claude/scripts/validate_scenarios.py` to check:

- Every scenario has the required frontmatter
  (`scenario:`, `when_to_use:`, `companion_skills:`,
  `related_scenarios:`, `canonical_commit:`, `last_verified_commit:`).
- Every `related_scenarios:` entry points at a real scenario file.
- Every `companion_skills:` entry points at a real `.claude/skills/X/SKILL.md`.
- Every scenario is referenced in `_index.md`.

Current status (2026-06-16): **OK: 31 scenarios validated, 0 warnings.**

## Refresh discipline

A scenario refresh = re-verify every file in the checklist still
exists at its cited path, that the rationale still holds, and that
no new required files have crept into the change-class. Bump
`last_verified_commit:` only after a full re-verification.

Cloud routine `.claude/cloud/pg-corpus-maintainer.md` owns the
scheduled refresh; manual refresh is fine for one-offs.

**Stale-after rule:** if `last_verified_commit` is more than ~50
upstream commits behind current master, schedule a refresh. The
checklist drift risk grows with the gap.

## Bidirectional cross-references applied

When the scenarios landed (2026-06-16), two backfill passes wired
the new layer into the rest of the corpus:

- **Layer C1 (file → scenario):** 143 backlink edges across 96
  per-file docs under `knowledge/files/`. Every file referenced in
  a scenario's checklist now carries an `## Appears in scenarios`
  section linking back. Idempotent — re-running the script replaces
  the auto-block rather than appending.
  Script: `.claude/scripts/backfill_scenario_backlinks.py`.

- **Layer C3 (file → issue register):** 749 per-file docs that
  contain `[ISSUE-*]` tags now link to their matching
  `knowledge/issues/<subsystem>.md` register. 100% mapped (no
  unresolved). Idempotent.
  Script: `.claude/scripts/backfill_issue_backlinks.py`.

Remaining cross-reference passes (enhancement, not load-bearing):

- **Layer C2 (file → idiom backlinks):** ~50-100 high-confidence
  matches identified by symbol-overlap. Manual spot-check needed
  before bulk apply. Deferred to follow-up.
- **Layer C4 (glossary internal hyperlinking):** within each
  `knowledge/glossary.md` entry, link any term that has its own
  glossary entry. ~6,274 lines × ~700 terms. Deferred to follow-up.

## Gaps surfaced by planner runs

When `pg-feature-plan` Step 0 encounters a change-class with no
matching scenario, it MUST flag the gap here. Future-us fills the
gap by writing a new scenario.

| Date | Planner invocation | Change-class | Notes |
|---|---|---|---|
| (none yet) | — | — | First planner runs against the new layer pending. |

## How `pg-feature-plan` uses this layer

Per `.claude/skills/pg-feature-plan/SKILL.md` Step 0 + M3 gate:

1. Match the brainstorm's change-class against `_index.md`.
2. Pinned scenario's file checklist becomes the **authoritative §3
   table**. Planner can ADD sites discovered by grep; can NEVER drop
   sites the scenario named.
3. Composite features (multiple matching scenarios) union the
   checklists.
4. No match → escalate to user, record gap above.
5. Anchor drift between plan and scenario triggers a fresh-grep
   re-verification before treating the checklist as authoritative.

## Cross-refs

- `knowledge/scenarios/README.md` — layer doc.
- `knowledge/scenarios/_index.md` — decision tree + one-liner per
  scenario.
- `.claude/skills/pg-feature-plan/SKILL.md` — Step 0 + M3
  scenario-coverage gate.
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — §4 scenario-match
  in "Has this been tried?".
- `.claude/commands/pg-scenario.md` — slash command bypassing
  brainstorm when the change-class is already known.
- `progress/coverage.md` — sibling coverage doc for per-file +
  subsystem docs.
- `progress/STATE.md` — the running ledger of pg-claude state.
