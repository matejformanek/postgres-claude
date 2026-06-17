# Rules — PG implementation discipline

**Status:** binding. Where a skill and these rules disagree, the rules
win. These cover the implementation phase of the PG planner suite —
i.e. when `/pg-implement` is executing a `planning/<slug>/plan.md`.

The procedural side lives in `.claude/skills/pg-implement/SKILL.md`.
This file is the constitution.

## Why rules separate from skills

Skills describe procedures (the how). Rules are non-negotiable
invariants (the what-must-never-happen). Splitting them lets us:

- Update the procedure without re-litigating the invariants.
- Cite the rules from any skill (`pg-feature-plan`, `pg-implement`,
  `patch-submission`, `review-checklist`) without duplication.
- Make audits cheap: if every commit violates Rule 4, that's a
  process bug, not a coding mistake.

## The 12 rules

### R1 — One plan, one branch

Every implementation runs against exactly one
`planning/<slug>/plan.md`. The work happens on a single feature branch
in `dev/`, named after the slug (e.g. `feature_server_side_vars`). No
mixing multiple plans on one branch.

### R2 — Pre-flight verify before phase 1

Before any edit in phase 1, spot-check 3-5 file:line citations from
the plan against current source. If drift > 10% (citations off by
more than ~20 lines or naming a since-removed symbol), STOP. Re-run
`/pg-plan` to refresh; don't push through with a stale plan.

### R3 — One phase at a time

No interleaving. Finish phase N (including the phase-end check + the
commit) before opening phase N+1. If phase N reveals work that belongs
in phase M ≠ N+1, escalate to the user — don't quietly merge.

### R4 — Phase-end check must pass before commit

The plan's "Phase-end check" for phase N (regress / iso / TAP scope as
specified) must run green. Failures are this phase's problem; don't
commit broken state and "follow up".

### R5 — Per-phase commit, plan-linked

Every phase ends with exactly one commit. The commit message has:

- Imperative title scoped to the phase (NOT to the whole feature).
- A `Plan:` trailer: `Plan: planning/<slug>/plan.md (phase <N>:
  <phase title>)`.
- A `Sites:` trailer when the diff spans >1 non-obvious file.
- Format per the **upstream PG style** (`commit-message-style` skill):
  no `Co-Authored-By` (these commits may go upstream via
  `format-patch`). This is the one place where meta-style does NOT
  apply — `dev/` commits ARE upstream-candidates.

### R6 — Cite or don't claim, in commit messages too

Any "addresses", "fixes", or "implements" claim in a commit message
must point to a file:line in `source/` (for plan-cited sites) or a
specific section in the plan (`§4 Catalog impact`, etc.). Vague
language like "fix the bug" is forbidden.

### R7 — Scope creep escalates

If a phase reveals a needed change outside the plan's §3 "Files that
change" table, STOP. Three options, in order of preference:

1. The new site is small + tightly coupled → update the plan + the
   `Sites:` trailer; continue.
2. The new site is a separate concern → defer to a follow-up patch,
   note in `notes.md` under "Surprises / drift".
3. The new site invalidates the phase boundary → escalate to the user
   for a re-plan.

Never silently expand scope.

### R8 — Per-phase notes log

Every phase appends a section to `planning/<slug>/notes.md` per the
template in `pg-implement/SKILL.md`. Required: phase number, status
(done / partial / deferred), commit SHA + title, test scope + result,
what changed (one line per site), surprises/drift, what this phase
did NOT do.

This log is the trail that lets a future session pick up
mid-implementation without re-reading every commit.

### R9 — Citation chain stays linked

The full chain: **commit `Plan:` trailer → plan file → plan's `[via
knowledge/subsystems/...]` cites → corpus's `source/<path>:<line>` cites
→ live source.**

Don't break the chain. If a commit references a plan that doesn't
exist, you've violated R1 or R5. If a plan cites a corpus doc that
doesn't exist, the plan is invalid. If a corpus doc cites a
`file:line` that's been refactored away, the corpus needs a `hf(corpus)`
fix in a SEPARATE meta-repo commit.

### R10 — Two-repo separation

`dev/` holds the source patch (upstream-candidate). `postgres-claude/`
holds the meta artifacts (plan, notes, knowledge, sessions).

- Per-phase code commits live in `dev/` only.
- Per-phase `notes.md` appends live in `postgres-claude/`.
- A single conceptual change that touches both → TWO commits, one per
  repo, with the appropriate style each (`commit-message-style` for
  `dev/`, `meta-commit-style` for `postgres-claude/`).

This is enforced by the existing CLAUDE.md scope discipline
("Patches to PG itself live inside `../postgresql-dev/` and never
touch `.claude/` or `knowledge/`"). R10 restates it as a hard rule.

### R11 — Test-first when changing behavior

For phases that change behavior (not pure refactors), the phase plan
should name the test added in the same phase. If the plan says "phase
3: implement X; phase 4: add tests for X", reorder — bring the test
into phase 3 so the phase-end check actually exercises the new code.

Pure refactors (like CF #6402) are exempt: existing tests cover the
refactored code.

### R12 — End-of-implementation gate

After the last phase:

1. Full `meson test --no-rebuild`. Document any pre-existing flakes
   (e.g. macOS `recovery/040_*` failures).
2. `git -C dev log --oneline <base>..HEAD` shows exactly N commits for
   N phases, each with a `Plan:` trailer.
3. If upstream-bound: invoke `review-checklist` skill, then
   `patch-submission` skill.
4. If staying local: leave the branch, append final summary to
   `notes.md`.
5. Invoke `memory-keeping` to update `progress/STATE.md`.

### R13 — Phase-end check scope matches phase blast radius

A phase's phase-end check MUST cover every test suite that could
plausibly regress from the change. The default `--suite regress`
covers `src/test/regress` ONLY; contrib modules, isolation tests,
TAP recovery tests, and ECPG tests are SEPARATE suites and are
INVISIBLE to a regress-only check.

The scope ladder (apply the broadest matching tier):

- **Helper-only changes** (utility function, new internal API, no
  cross-cutting impact): `--suite regress` is sufficient.
- **Catalog changes** (`pg_operator.dat`, `pg_proc.dat`,
  `pg_type.dat`, `pg_aggregate.dat`, etc.) — REQUIRED:
  `--suite regress` + `--suite contrib-*` (contrib modules often
  exercise operators / functions by name and silently regress
  when entries change). Origin: sesvars F12, where Phase 0's
  catalog cleanup broke `pg_stat_statements/squashing.sql` and
  the regress-only gate missed it.
- **Grammar / lexer changes** (`gram.y`, `scan.l`, `pl_gram.y`,
  ECPG `pgc.l`) — REQUIRED: `--suite regress` + `--suite ecpg` +
  every `contrib/*` suite that may parse SQL.
- **Executor / planner changes** (`execExpr*.c`, `clauses.c`,
  `plancache.c`, etc.) — REQUIRED: `--suite regress` +
  `--suite isolation` + every `contrib/*` suite.
- **WAL / replication / catalog-version-bumping changes** —
  REQUIRED: above + `--suite recovery`.
- **Ruleutils / parse-tree formatting** — REQUIRED: above + a
  spot-check on `CREATE VIEW`, `EXPLAIN VERBOSE`, and
  `pg_get_*def` output (origin: sesvars F14, where `T_SessionVar`
  was missing from `ruleutils.c get_rule_expr` and broke
  `EXPLAIN VERBOSE` silently).

The end-of-implementation gate (R12) ALWAYS runs full
`meson test --no-rebuild` regardless of phase scope — it's the
backstop for any phase that under-scoped its check.

### R14 — Comprehensive own-test-suite

Every implementation MUST ship its OWN focused test suite covering
edge cases, cross-feature integration, and adversarial scenarios
— beyond the per-phase happy-path regress rows.

A "good implementation" test suite at minimum exercises:

1. **Identifier / boundary edge cases** — long names (near
   NAMEDATALEN), unusual characters, empty inputs, NULL.
2. **Type variety** — bool, int, numeric, text, jsonb, array,
   composite (every type domain the feature spans).
3. **Cross-feature integration** — PL/pgSQL DO blocks, CTEs,
   subqueries, EXPLAIN, savepoints, prepared statements with
   parameter mixing.
4. **Adversarial behavior** — assignment side-effects in odd
   positions, volatility marking validation, NULL propagation,
   ROLLBACK / SAVEPOINT semantics.
5. **Cross-backend / session-isolation** (TAP) — exit, reconnect,
   verify isolation invariants.

This separate suite ships AS PART OF the feature, NOT as a
follow-up. Per-phase regress rows verify the happy path WITHIN
each phase's commit; the comprehensive suite verifies the
*completed feature* holds together across edge cases. Reference:
sesvars ships both `src/test/regress/sql/sessvar.sql` (per-phase
happy path) AND `src/test/regress/sql/sessvar_advanced.sql`
(comprehensive own-test-suite) AND
`src/test/recovery/t/054_sessvar_lifecycle.pl` (cross-backend
TAP). The comprehensive suite directly surfaced F14 (ruleutils
gap) which the per-phase gate had missed.

**Best-practice corollary (classic):** an implementation that
breaks existing tests is broken. The combination of R4 +
R13 + R14 enforces this end-to-end: R4 says phase-end check must
pass (no breakage allowed forward); R13 says the check scope
must match the blast radius (so breakage isn't merely hidden);
R14 says the implementation's own suite must be comprehensive
enough to catch what the cross-cutting suites would miss.

### R15 — Default to comprehensive scope, not minimal MVP

Scope decisions made at brainstorm + plan time bind every
downstream phase. The default at brainstorm MUST be "what is the
COMPREHENSIVE usage surface this feature must serve?" — NOT
"what's the smallest thing we can ship?"

**Why this rule exists.** The sesvars first end-to-end
calibration (2026-06-17) shipped a working 7-phase MVP. The
user's manual reference implementation
(`/Users/matej/Work/PostgreSQL/pgsql`) was ~3× more
comprehensive and ~30% smaller in code (because it reused
existing PARAM infrastructure). The planner-suite under-scope was
a brainstorm-skill failure, NOT a code-quality failure: the
plan faithfully implemented what the brainstorm prescribed, but
the brainstorm prescribed too little.

Concretely missed scope that should have been on the table at
brainstorm time:
- Array indirection (`@arr[2] := v`, `@arr[2:3] := v`).
- Composite type access (`(@typ).field`).
- Strict-type declaration (`SET @x TYPE DATE := …`).
- PL/pgSQL direct `SET @x := …` (no `EXECUTE format(...)`).
- `SELECT col INTO @x` syntax.
- DDL `DEFAULT @v` and `DEFAULT @v := 2`.
- Quoted identifiers `@"name"`.
- Per-variable collation.
- Aggregate semantics (`@x := MIN(col)` vs `@x := MIN(col) + …`).
- Multi-target SET (`SET @a := 1, @b := 2`).

**How to apply.**

1. **Brainstorm must enumerate 20-30 concrete usage examples**
   BEFORE answering DECISION questions. Each example is one
   `SET …` or `SELECT …` line the feature must handle. The
   DECISION questions then take these as inputs, not
   abstractions.
2. **If a user-reference implementation exists, READ IT first.**
   The `pg-feature-brainstorm/SKILL.md` must include a step:
   "if the user has a manual implementation, parse it as the
   upper-bound spec; the planner suite produces something
   *comparable* to it, not 30% of it." The §2 out-of-scope lock
   is for *features the user explicitly excluded*, not for
   "things we don't have context on yet."
3. **Plan §3 must show the comprehensive file table.** If a
   plan touches only 21 files when the comparable reference
   touches 35, the plan is under-scoped. Escalate at plan-end.
4. **MVP framing requires explicit user consent.** "Should we
   ship a minimal MVP or comprehensive feature?" is a question
   for the user, not a default for the orchestrator. Default to
   comprehensive; let the user opt down.

**Anti-patterns this rule forbids.**
- Brainstorm DECISION questions phrased so narrowly they
  exclude entire usage surfaces (e.g. asking "what writer
  syntax?" without asking "do we support array element
  assignment?").
- Plan §2 out-of-scope locks justified only by "calibration
  scope guard" without user confirmation that the lock is real.
- §13 risks that enumerate *implementation* unknowns without
  enumerating *scope* unknowns ("does the user want X?").

This rule lands as direct output of the sesvars first end-to-end
calibration. Full comparison at
`postgresql-dev-feature-sesvars/planning/sesvars/comparison.md`.

## Anti-patterns (explicitly forbidden)

- **"WIP" commits.** Every commit in `dev/` is a complete phase. No
  "wip: more of phase 3".
- **`--amend` to fix a previous phase's commit.** Use a NEW commit
  with a `Fixes: <sha>` trailer if you genuinely need to correct.
- **Committing without a `Plan:` trailer.** If you're committing in
  `dev/`, you're implementing a plan — name it.
- **Cherry-picking phases.** All phases or none. Cherry-pick across
  features is a sign the plan was wrong; re-plan instead.
- **Mixing meta-repo + `dev/` writes in one bash invocation.** Even if
  technically fine, the cognitive split matters; pick one direction
  per phase.

## Cross-references

- `.claude/skills/pg-implement/SKILL.md` — the procedure these rules
  govern.
- `.claude/skills/pg-feature-plan/SKILL.md` — produces the plans that
  Rule 1 binds to.
- `.claude/skills/commit-message-style/SKILL.md` — the upstream PG
  commit format Rule 5 references.
- `.claude/skills/meta-commit-style/SKILL.md` — the meta-repo commit
  format Rule 10 references.
- `.claude/skills/review-checklist/SKILL.md` — Rule 12 invokes this
  pre-submission.
- `.claude/skills/memory-keeping/SKILL.md` — Rule 12 invokes this
  post-implementation.
- Top-level `CLAUDE.md` — Rule 10 echoes the project's scope-discipline
  rule.

## Versioning

These rules are intentionally short and stable. When they change,
update the version note here and call it out in the commit message.

**Version:** v1 (2026-06-02) — initial.
**Version:** v1.1 (2026-06-17) — adds R13 (phase-end check scope
ladder) and R14 (comprehensive own-test-suite). Both motivated by
the sesvars first end-to-end calibration: F12 (contrib silently
breaks when catalog changes) → R13; F14 (`EXPLAIN VERBOSE` broken
because `T_SessionVar` missing from `ruleutils.c`, caught only by
the comprehensive own-test-suite) → R14.
**Version:** v1.2 (2026-06-17) — adds R15 (default to
comprehensive scope, not minimal MVP). Motivated by the sesvars
final-calibration comparison: my AI-driven implementation shipped
~30% of what the user's manual implementation covered, because
brainstorm + plan under-scoped. R15 codifies the lesson:
comprehensive scope is the default; MVP framing requires explicit
user consent.
