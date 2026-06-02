# 2026-06-02 — Three-phase PG planner suite landed

**Type:** interactive (worktree `ft_planner_two_phase`).
**Outcome:** new three-phase planner suite + meta-repo commit style +
binding rules file + master-skill registration. The 7th durable
deliverable of the day (after 4 subsystem syntheses, a validation
run, and a context compaction).

## What this session did

The user's directive after the CF #6402 review validation: "let's have
a Postgres planner; it could be two phased — brainstorm phase, then
heavy planning." Plus: "the implementation should use a special
pg-implement, not the generic /implement, and we should bake in
commit + step + linking discipline."

That decomposes into:

1. Two new planning phases (brainstorm + plan).
2. A new PG-specific implementer (Phase 3).
3. A separate commit-message style for the meta repo.
4. A binding rules file for implementation discipline.
5. Wiring: master skill registration + STATE.md update + a `planning/`
   directory.

All landed in this commit.

## Files created

| Path | Role |
|---|---|
| `.claude/skills/pg-feature-brainstorm/SKILL.md` | Phase 1 — open-ended idea exploration → `planning/<slug>/brainstorm.md` |
| `.claude/skills/pg-feature-plan/SKILL.md` | Phase 2 — heavy file:line-cited plan → `planning/<slug>/plan.md` (14 required sections) |
| `.claude/skills/pg-implement/SKILL.md` | Phase 3 — phase-by-phase execution with plan-linked commits → `dev/feature_<slug>` branch + `planning/<slug>/notes.md` |
| `.claude/skills/meta-commit-style/SKILL.md` | Commit style for `postgres-claude/` (with `Co-Authored-By`) — distinct from upstream `commit-message-style` |
| `.claude/rules/pg-implement-discipline.md` | Binding rules R1–R12 — plan-linked commits, scope discipline, two-repo separation, citation chain |
| `.claude/commands/pg-brainstorm.md` | Thin wrapper around `pg-feature-brainstorm` skill |
| `.claude/commands/pg-plan.md` | Thin wrapper around `pg-feature-plan` skill |
| `.claude/commands/pg-implement.md` | Thin wrapper around `pg-implement` skill (with pre-flight checks for slug + dev/ branch) |
| `planning/README.md` | NEW top-level directory; explains slug layout + cleanup policy + slugs-in-flight queries |

## Files modified

- `.claude/skills/pg-claude/SKILL.md` (master nav): added 3 slash
  commands to the table, added "Planning + implementing a PG feature"
  section, added `meta-commit-style` to project-internal table, added
  `planning/` to the directory tree, added new flowchart entries for
  brainstorm/plan/implement/commit-style choice.
- `progress/STATE.md`: bumped phase to "Tooling buildout"; updated
  Last activity; bumped skills count (21 → 25) + slash commands count
  (14 → 17) + noted 1 new rules file; updated Next queue (priority 1
  is now PG patch-review v2; priority 2 is first real planner-suite
  run); added this session log to Recent.

## The three-phase pipeline (in one diagram)

```
idea
  │
  │  /pg-brainstorm <idea>
  ▼
planning/<slug>/brainstorm.md    ~150-300 lines, 2-3 approaches,
                                 DECISION: questions for user
  │
  │  user picks approach + answers decisions
  │
  │  /pg-plan <slug>
  ▼
planning/<slug>/plan.md          14 required sections incl. §3 files,
                                 §4 catalog, §5 WAL, §6 locking, §7
                                 memory, §8 phased impl, §9 tests,
                                 §13 risks. file:line cites mandatory.
  │
  │  user reviews + approves plan
  │
  │  /pg-implement <slug>
  ▼
dev/feature_<slug> branch        N commits for N phases, each with
                                 Plan: trailer per R5 of the rules.
planning/<slug>/notes.md         Running log appended per phase.
  │
  │  (final phase)
  │
  ▼
patch-submission (if upstream)   format-patch → CF entry → email
```

## Design decisions

### Why three skills not one big "planner" skill

Each phase has different inputs, outputs, length, and discipline. A
one-mega-skill description would trigger imprecisely. Three skills
with three sharp descriptions trigger crisply on the right verb
("brainstorm" vs "plan" vs "implement").

### Why `/pg-implement` distinct from `/implement`

The generic `/implement` skill is project-agnostic. PG implementation
has unusual hard constraints:

- Per-phase test runs against the dev cluster
- File:line citation chain (commit → plan → corpus → source)
- Plan-linked commit messages (with `Plan:` trailer)
- Upstream-vs-meta commit-message split
- Catalog/catversion/WAL preflight
- `/pg-restart` cadence after backend code edits

`/pg-implement` enforces these via the rules file. Inheriting from
`/implement` would either over-burden the generic skill or constantly
override its behavior. Cleaner to make it explicit.

### Why a rules file + a procedural skill (not one or the other)

The user explicitly asked for both "skill and rule" — and there's a
real distinction:

- **Skill** describes *how to do it well* (the procedure).
- **Rules** describe *what must never happen* (the invariants).

Splitting them means we can update the procedure without re-litigating
the invariants, and we can cite the rules from any skill
(`pg-feature-plan`, `pg-implement`, `patch-submission`, `review-checklist`)
without duplication.

The rules file is also intentionally TERSE (12 numbered rules + an
anti-pattern list). The skill file is longer because it walks through
the procedure step-by-step.

### Why a separate `meta-commit-style` skill

The existing `commit-message-style` skill is the **upstream PG style**:
no `Co-Authored-By`, bare imperative title, no conventional-commits
prefix, paragraph body wrapped near 76 cols, Author/Reviewed-by/
Discussion/Backpatch-through trailer block.

This repo (`postgres-claude/`) follows a DIFFERENT style:
`ft(corpus):` / `hf(scope):` prefix, `Co-Authored-By: Claude Opus 4.7
(1M context)` footer (per the user's global default), `Plan:` and
`Sites:` trailers when applicable.

The two styles serve different audiences (pgsql-hackers vs the
meta-repo project history). Forcing them into one skill would make
both worse. Separate skills with sharp triggers (this repo vs
upstream-bound `dev/` commits) is cleaner.

### Why a new `planning/` directory

`knowledge/` is for distilled durable reference. `sessions/` is the
append-only audit trail. Neither fits forward-looking design docs
that may be revised or discarded. `planning/` is the WIP layer —
explicitly tentative, slug-organized, with a documented cleanup
policy in `planning/README.md`.

## What this commit explicitly does NOT do

- **No first real planner run.** The skill chain is wired but the
  first feature to brainstorm-plan-implement is queued as `Next §2`
  in STATE.md. Calibration happens on the first real run.
- **No PG patch-review v2.** The upgraded multi-agent review (analogous
  to `plan-review-comprehensive`) is queued as `Next §1` in STATE.md.
  Today's CF #6402 review remains the v0 reference.
- **No changes to existing skills or rules** outside the master
  `pg-claude` and STATE.md.
- **No changes inside `dev/`.** This is all meta-repo wiring.

## Rules file (R1–R12) — quick summary

For the binding invariants the planner-suite enforces. See the file
itself for detail.

| Rule | What |
|---|---|
| R1 | One plan, one branch |
| R2 | Pre-flight verify before phase 1 (drift > 10% → stop) |
| R3 | One phase at a time |
| R4 | Phase-end check must pass before commit |
| R5 | Per-phase commit, plan-linked, upstream PG style |
| R6 | Cite or don't claim, in commit messages too |
| R7 | Scope creep escalates (no silent expansion) |
| R8 | Per-phase notes log appended to `planning/<slug>/notes.md` |
| R9 | Citation chain stays linked (commit → plan → corpus → source) |
| R10 | Two-repo separation (`dev/` vs `postgres-claude/`) |
| R11 | Test-first when changing behavior |
| R12 | End-of-implementation gate (full tests, review-checklist, memory-keeping) |

## What I learned wiring this up

- The split between "upstream-bound commits" and "meta-repo commits"
  is sharper than I'd realized. Even in the planner suite alone,
  `/pg-implement` commits in `dev/` follow upstream style (because
  they may go to pgsql-hackers), while `meta-commit-style` only
  applies to commits inside `postgres-claude/`. Surfacing this as two
  skills makes the choice non-ambiguous.
- The `planning/` directory is the missing third sibling to
  `knowledge/` and `sessions/`. Now the meta repo has three coherent
  layers: SPEC (knowledge/, what is), LOG (sessions/, what was), PLAN
  (planning/, what will be).
- The rules file pattern (separate from skills) seems strong enough
  that other domains in this repo might benefit. Candidates:
  `corpus-discipline` (rules for `knowledge/` writes), `cite-or-tag`
  (rules for the file:line citation chain). Don't build pre-emptively
  — wait for the second use case to crystallize.

## Followup candidates surfaced

- **First real planner run** (next priority). Pick a small feature
  to brainstorm-plan-implement; will probably surface skill gaps the
  first iteration didn't anticipate.
- **PG patch-review v2** (still priority 1 in STATE.md). The
  4-critic-agent split + synthesizer is sketched in
  `sessions/2026-06-02-cf6402-review-validation.md`. Build when
  another real CF review comes up.
- **`/pg-cf-review <CF#>` slash command** (closes the validation
  loop): fetch + apply + build + test mechanically, then hand to the
  multi-agent reviewer.
- **`coding-style` skill addendum** — note `pg_bsd_indent` is an
  external dependency for the `pgindent` step (gap surfaced by the
  CF #6402 review).
- **`commit-message-style` skill** — add a `Reviewed-by:` trailer
  example for patches the user has reviewed (also from CF #6402 run).

## Repository state after this commit

- New skill files: 4 (`pg-feature-brainstorm`, `pg-feature-plan`,
  `pg-implement`, `meta-commit-style`).
- New command files: 3 (`pg-brainstorm`, `pg-plan`, `pg-implement`).
- New rules file: 1 (`pg-implement-discipline.md`).
- New top-level directory: `planning/` with `README.md`.
- Updated: master `pg-claude` skill, `progress/STATE.md`.
- No changes to `knowledge/`, `dev/`, or other skills.

## Commit message for this work

Per `meta-commit-style` (this repo's commit style — the new skill I
just added defines it):

```
ft(skill): three-phase PG planner + pg-implement + meta-commit-style

Land the planner suite the user signalled as the next big roadmap
item after today's CF #6402 review validation. Three skills + their
slash-command wrappers, a binding rules file, a meta-repo commit
style, and a new planning/ directory.

Skills: pg-feature-brainstorm (Phase 1 — sketch), pg-feature-plan
(Phase 2 — file:line-cited implementable plan with 14 required
sections), pg-implement (Phase 3 — phase-by-phase execution with
plan-linked commits). Each enforces the rules in
.claude/rules/pg-implement-discipline.md (R1–R12: plan-linked
commits, scope discipline, two-repo separation, citation chain
discipline, end-of-implementation gate).

Commit style split: meta-commit-style for THIS repo (with
Co-Authored-By, ft(scope):/hf(scope): prefixes), distinct from the
existing commit-message-style which stays scoped to upstream-bound
dev/ commits.

Master pg-claude skill updated to register all of it. STATE.md Next
queue reordered: priority 1 now the PG patch-review v2 (multi-agent
analogous to plan-review-comprehensive), priority 2 first real run
of the planner.

Session: sessions/2026-06-02-planner-suite.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
