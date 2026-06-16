# 2026-06-16 — scenarios layer landed (web-of-context plan, Layers A+B+C1+C3)

**Phase:** Phase F (corpus hardening) — new layer addition.
**Anchor:** `e18b0cb7344` (unchanged).
**Worktree:** `worktree-ft_pg_scenarios_web_of_context`.

## What landed

A new task-shaped layer in the knowledge corpus answering the
"I want to do X — what's the full sweep of files I touch?" question
that the existing reference-shaped corpus didn't handle well.

User stress-tested the gap with three concrete asks: "add a new SQL
data type", "add new grammar with scan.l sync", "hook into the main
ring in postgres.c". Pre-work the planner would have named ~4-5 of
the 12-14 files involved in each. Post-work: the matching scenario's
checklist is pinned by `pg-feature-plan` Step 0 as the authoritative
§3 table — no more file-by-file rediscovery on every planner run.

### Layer A — `knowledge/scenarios/` (NEW directory)

- `README.md` — layer doc: when to write a scenario, the linking
  rules, the refresh discipline, the hard-integration contract with
  `pg-feature-plan`.
- `_template.md` — the playbook skeleton (frontmatter +
  file-checklist + phases + pitfalls + verification + cross-refs).
- `_index.md` — table of all 31 scenarios + a decision tree the
  planner uses for routing.
- **31 scenario playbooks** covering the comprehensive set the user
  locked into:
  - Catalog basics (10): bump-catversion, add-new-builtin-function,
    add-new-data-type, add-new-operator-class, add-new-operator,
    add-new-cast, add-new-aggregate-function, add-new-error-code,
    add-new-system-catalog-column, add-new-system-view.
  - Parser/grammar (3): add-new-sql-keyword (the
    `psqlscan.l`+`pgc.l` sync trap), add-new-node-type
    (gen_node_support.pl), add-new-utility-statement.
  - Executor/planner (3): add-new-plan-node, add-new-expression-
    eval-step (interpreter+JIT lockstep), add-new-cost-model-knob.
  - Storage/AM (4): add-new-index-am, add-new-table-am,
    add-new-wal-record, add-new-buffer-strategy.
  - Infrastructure/runtime (7): add-new-guc, add-startup-hook
    (the "main ring" question), add-new-bgworker, add-new-hook,
    add-new-lwlock-tranche, add-new-shared-memory-region,
    add-new-pg-stat-view.
  - Replication/wire/extensions (4): add-new-protocol-message,
    add-new-replication-message, add-new-extension,
    add-new-test-module.

**Totals: 31 scenarios, 449 checklist rows.** Every file:line cite
verified against `source/` at `e18b0cb7344`. Every scenario carries
`canonical_commit` + `last_verified_commit` (the refresh-discipline
field).

### Layer B — hard integration with the planner

- `.claude/skills/pg-feature-plan/SKILL.md` — added Step 0 ("Match
  the brainstorm against `knowledge/scenarios/`"), the M3-extension
  scenario-coverage gate (every file in the pinned scenario MUST
  land in the plan's §3 table; planner can ADD but never DROP),
  anchor-drift handling, and a `companion_scenarios:` frontmatter
  listing all 31 slugs.
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — extended §4
  "Has this been tried?" with the scenario-match step: brainstorm
  names the candidate scenario(s) so Phase 2 has the pin
  pre-identified.
- `.claude/skills/pg-claude/SKILL.md` — added `scenarios/` to the
  corpus map + the routing-rule table + the slash-command table.
- `.claude/commands/pg-scenario.md` — NEW slash command for the
  case where the user already knows the change-class. Skips
  brainstorm, loads the scenario directly, emits a starter plan from
  its checklist with anchor-drift re-verification.
- `CLAUDE.md` (project) — added `scenarios/` to the Layout list.

### Layer C — cross-reference backfill

- **C1: file → scenario backlinks.** 143 backlink edges applied to
  96 per-file docs under `knowledge/files/`. Idempotent script at
  `.claude/scripts/backfill_scenario_backlinks.py`. Handles the
  `.dat → .h` fallback for catalog files (pg_proc.dat → pg_proc.h.md,
  etc.) and skips wildcard / NEW-file paths.
- **C3: file → issue-register backlinks.** 749 per-file docs with
  `[ISSUE-*]` tags now link to their matching
  `knowledge/issues/<subsystem>.md`. 100% mapped (zero unresolved).
  Heuristic handles the various subsystem-naming conventions
  (`include-<area>.md`, `<area>-<sub>.md`, `bin-singletons.md`
  rollup, `_` ↔ `-` for storage-large-object). Idempotent script at
  `.claude/scripts/backfill_issue_backlinks.py`.
- **C2: file → idiom backlinks** — DEFERRED. The plan called for
  ~50-100 high-confidence matches via symbol-overlap with manual
  spot-check. Adding to follow-up queue rather than rushing the
  heuristic.
- **C4: glossary internal hyperlinking** — DEFERRED.
  `knowledge/glossary.md` is ~6,274 lines × ~700 terms. Mechanical
  pass left for a follow-up session.
- **C5: scenario validation.** `.claude/scripts/validate_scenarios.py`
  checks frontmatter completeness, `related_scenarios:` cross-link
  integrity (every pointer is a real scenario), `companion_skills:`
  cross-link integrity (every pointer is a real skill), and
  `_index.md` coverage. **Current status: OK, 31 scenarios validated,
  0 warnings.**

### New scripts under `.claude/scripts/`

- `backfill_scenario_backlinks.py` — Layer C1.
- `backfill_issue_backlinks.py` — Layer C3.
- `validate_scenarios.py` — Layer C5.

All three are idempotent — re-running replaces auto-blocks rather
than appending. Sentinels (`<!-- scenarios:auto:begin -->`,
`<!-- issues:auto:begin -->`) bound the auto-generated content so
human edits to surrounding sections survive.

## Why this matters

The user's locked decisions:

1. **Hard integration**: scenario is authoritative starting §3
   table; planner can only ADD, never DROP. Forces the planner to
   honor the playbook's full sweep, eliminating the "we forgot
   pg_amop.dat" failure mode.
2. **Comprehensive set, no priority cuts**: all 31 scenarios written
   in the first pass, sequenced by natural dependency (catalog basics
   first, then parser, then executor, then storage/AM, then
   infrastructure, then replication/extensions).
3. **Refresh discipline mandatory**: every scenario carries
   `last_verified_commit`. Planner emits "scenario stale" warning on
   anchor drift and runs fresh grep to validate the checklist before
   pinning.
4. **Skills stay as-is**: scenarios carry task structure; the 31
   skills (parser-and-nodes, catalog-conventions, …) stay as
   procedural-knowledge layer. No skill splits.

## What this DOES NOT do (out of scope for this PR)

- C2 (file→idiom backlinks) — deferred to follow-up; ~50-100
  matches with manual spot-check is its own session.
- C4 (glossary internal links) — deferred; mechanical but
  6,000+ line file.
- Re-running the whole corpus against a newer source anchor —
  separate cloud routine (`pg-anchor-refresh`).
- Phase D upstream sends, Phase E shadow runs (orthogonal).
- Filling scenarios for the niche change-classes not in the 31 —
  gaps will be discovered organically via the `gaps surfaced by
  planner runs` table in `scenarios-coverage.md`.

## How to verify

Cold-start tests (per the plan's verification section):

1. **Data type scenario test.** Ask the planner to plan adding a
   built-in `complex_number` type with btree+hash opclass + text
   cast. **Expected:** §3 table contains all 18 checklist rows from
   `add-new-data-type.md` plus union with `add-new-operator-class`
   plus `add-new-cast` — well beyond the 4-5 the old planner would
   have named.

2. **Grammar scenario test.** Ask for a plan adding a `MERGE THEN`
   keyword. **Expected:** §3 names `gram.y` + `kwlist.h` +
   `parsenodes.h` + `analyze.c` + `psqlscan.l` (sync warning) +
   `ecpg pgc.l` (sync warning) + `outfuncs/readfuncs` + tests —
   the full 16-row sweep from `add-new-sql-keyword.md`.

3. **Startup-hook test.** Ask for a plan adding a hook point in
   `PostmasterMain`. **Expected:** plan cites the lifecycle slot,
   the existing peer hooks, the install pattern — 11-row sweep
   from `add-startup-hook.md`.

4. **Cross-ref density.** `grep -l 'Appears in scenarios' knowledge/files`
   count ≥ unique files across all scenarios. **Current: 96.**

5. **Issue-backlink density.** Every per-file doc with `[ISSUE-*]`
   tags links to its issue register. **Current: 749/749 (100%).**

6. **No regression.** `progress/coverage.md` still shows 100%
   strict coverage; existing skill `companion_skills:` graphs
   unchanged; the new layer is purely additive.

## Open follow-ups

| Item | Owner | Notes |
|---|---|---|
| Layer C2 (file→idiom backlinks) | cloud routine `pg-corpus-maintainer` next pass | ~50-100 high-confidence matches; manual spot-check before bulk apply |
| Layer C4 (glossary internal linking) | cloud routine `pg-corpus-maintainer` next pass | ~700 terms × 6,000 lines; mechanical |
| Cold-start scenario tests #1-3 | next interactive session | Confirms the planner's Step 0 actually pins to scenarios |
| `pg-anchor-refresh` interaction | TBD | When the next anchor refresh fires, the cloud routine must also bump `last_verified_commit:` on every scenario whose checklist still validates |
| Scenario gap-tracker | planner runs | Populated organically as the planner encounters change-classes with no matching scenario |

## Commit shape

This session lands as one meta-repo commit on the worktree branch:

- `knowledge/scenarios/*.md` — 34 NEW (README, _template, _index, 31
  scenarios).
- `knowledge/files/**/*.md` — 96 EDITED (Appears-in-scenarios
  backlinks) + 749 EDITED (issue-register backlinks). Note: many
  files are touched by both passes; total unique edited files is
  ~750.
- `.claude/skills/pg-feature-plan/SKILL.md` — EDITED (Step 0 + M3
  gate + companion_scenarios frontmatter).
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — EDITED (§4
  scenario-match step + cross-ref).
- `.claude/skills/pg-claude/SKILL.md` — EDITED (corpus map +
  slash-command table + routing rule).
- `.claude/commands/pg-scenario.md` — NEW slash command.
- `.claude/scripts/*.py` — 3 NEW (validator + 2 backfill scripts).
- `.claude/worktree-scenarios-workflow.mjs` — NEW (workflow script
  used to spawn the 31 parallel agents; kept for resume / future
  refreshes).
- `CLAUDE.md` — EDITED (Layout list includes scenarios/).
- `progress/scenarios-coverage.md` — NEW.
- `progress/STATE.md` — EDITED (new activity entry prepended).
- `sessions/2026-06-16-scenarios-layer.md` — this file.

## Cross-refs

- `knowledge/scenarios/README.md` — layer doc.
- `knowledge/scenarios/_index.md` — decision tree.
- `progress/scenarios-coverage.md` — coverage ledger.
- `.claude/skills/pg-feature-plan/SKILL.md` Step 0 + §8a — the hard
  integration contract.
- `.claude/commands/pg-scenario.md` — the brainstorm-skip slash
  command.
