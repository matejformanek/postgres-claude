# pg_session_variables — implementation findings (F17-F20)

**Date:** 2026-06-17
**Branch:** `feature_sesvars` in `postgresql-dev-feature-sesvars`
**Plan:** `planning/pg_session_variables/plan.md` (v1.2 generalization test)
**Outcome:** 3 phases / 6 commits / R12 end-gate 100/0/295.

This log captures the four new F-findings produced while running the
v1.2 planner suite's pg_session_variables plan to completion. Numbered
continuing from the sesvars run (F1-F16 already documented in
`2026-06-16-sesvars-calibration-findings.md`).

The implementation itself shipped cleanly — these findings are about
the **planner suite's plan accuracy**, not the feature's correctness.

---

## F17 — `utils/tuplestore.h` is not transitively included by `funcapi.h`

**Surface:** First Phase 1 build failed with:
```
error: call to undeclared function 'tuplestore_putvalues';
```
`funcapi.h` declares `ReturnSetInfo` (which has a `Tuplestorestate
*setResult` field) but doesn't pull in `tuplestore.h` for the helper
fn. Every materialized-SRF body that wants to call
`tuplestore_putvalues` directly must include `utils/tuplestore.h`.

**How it surfaced:** Plan §2.5 implementation template gave the body
correctly but didn't list `utils/tuplestore.h` in the includes-needed
list. Pure include-graph trap — the existence of `Tuplestorestate *`
in the struct misleads you into thinking the helper is in scope.

**Action item:** `pg-feature-plan` skill's machinery-survey template
needs an explicit "what headers does this template need?" row, with
**every header that appears in a function call**, not just every
header that names a type used in declarations. The
`InitMaterializedSRF` row in the survey is fine; the
`tuplestore_putvalues` row was missing.

**Severity:** low — caught by the first build, ~30s to fix. Adds one
line to the plan template; should be a recurring rule for any SRF.

---

## F18 — Plan test SQL specified `:=` for `SET` where sesvars v1 only accepts `=`

**Surface:** First Phase 3 regress run produced:
```
SET @sv_a := 1;
ERROR:  syntax error at or near ":="
```

**Root cause:** The plan's §7.5 test-case strings (TC-B-1 through
TC-E-8) used `:=` for both the utility-form `SET @x := expr` AND the
inline `SELECT @x := expr`. The brainstorm prose used `:=` colloquially
throughout. But sesvars v1's grammar accepts `:=` only in the **inline
expression** position; the utility-form `SET` keeps the single `=` of
classic PG `SET varname = value`.

**Why the plan got it wrong:** §0 usage surface and §7.5 test cases
were paraphrased from the brainstorm without grepping the actual
sessvar.sql in the feature branch. The plan author trusted the prose
instead of the implemented grammar.

**Action item:** `pg-feature-plan` skill needs a Step 1.6 (or
analogous step in Step 1.5 test-drafting): **when transcribing test
SQL, every literal syntax in TC-* must be checked against an existing
test for the underlying feature.** For a feature that's already
landed (sesvars v1 in this case), the check is
`grep -A2 'SET @' src/test/regress/sql/<feature>.sql`. For a feature
under joint development, the check is `git log -p <feature-grammar-
file>`.

**Severity:** medium — every test case in the plan needed touching.
Cost in this run was ~10 minutes (rewrite + rerun + re-golden); for a
larger test suite the cost scales linearly with the count of `SET`
sites.

---

## F19 — sesvars v1 `SET @x = expr` does NOT accept a subquery RHS

**Surface:** After F18 was fixed, TC-X-2 still failed:
```
SET @sv_id = (SELECT name FROM pg_session_variables() ... LIMIT 1);
ERROR:  unrecognized node type: 24
```
Node type 24 is `T_SubLink`. The utility-form `SET` evaluates its RHS
via a simpler path than the inline assignment (which goes through
`ExprState` + `execExpr.c`).

**Resolution in this run:** TC-X-2 was reformulated to use the inline
form: `SELECT @sv_id := name FROM pg_session_variables() ... LIMIT 1`.
The inline form goes through the full expression evaluator and handles
SubLinks correctly. Test now passes.

**Sesvars v1 limitation worth filing separately:** the asymmetry
between `SET @x = expr` (no subqueries) and `SELECT @x := expr` (full
expr surface) is a sesvars-side bug that should be fixed in a
follow-up: route the utility-form RHS through the same expression
plan/execute path the inline form uses. The fix is probably a small
adjustment in `sessvar_cmd.c` to call `transformExpr` + `ExecPrepareExpr`
rather than relying on `ExecEvalExpr` over a possibly-unanalyzed tree.

**Action item (planner-suite level):** plans for features that
introspect or build on another in-flight feature need a Step 0.8 (or
similar): **enumerate the underlying feature's known limitations.**
For sesvars v1, this meant noting:

- `SET @x = expr` accepts simple exprs only — no subqueries, no
  function calls returning sets, no Param refs.
- `SELECT @x := expr` accepts the full expr surface.
- Multi-target `SET @a = 1, @b = 2` is not yet implemented (also v1).
- `DISCARD ALL` does not yet hook `SessionVarReset`.

These limitations should appear in the brainstorm §0 usage surface
table as "supported / not yet supported" annotations, so the plan
doesn't generate test cases that exercise the gaps.

**Severity:** medium for THIS run (one test case rewritten); high in
principle because a brittle plan with bad tests wastes a phase
iteration cycle every time it hits a sesvars limitation.

---

## F20 — `parallel_schedule` lines have a hard 20-test cap

**Surface:** First Phase 3 regress run:
```
# too many parallel tests (more than 20) in schedule file
# parallel_schedule line 105:
# test: select_views portals_p2 foreign_key dependency guc bitmapops ... sessvar sessvar_advanced pg_session_variablesBail out!
```

The existing `sessvar sessvar_advanced` line already had 20 tests on
it. Appending `pg_session_variables` made it 21 → hard error from
pg_regress.

**Resolution in this run:** put `pg_session_variables` on its own
test line right after the sessvar cluster (a single test on a line is
fine).

**Action item:** `pg-feature-plan`'s "add a regress test" template (in
the `add-new-builtin-function` and `add-new-system-view` scenarios)
must include: **count the tests on the target schedule line before
appending; if ≥20, place the new test on its own line.** Even better:
the plan should pre-pick the target line based on test count, not
based on "where related tests live", since related tests very often
cluster at the cap.

**Severity:** low — clearly errored at regress time, 1-line fix. But
the lesson generalizes: pg_regress has several hard caps and field
limits that planner skills should know about.

---

## Plan-side miss — §3 row 12 (`src/test/regress/meson.build` edit)

Not an F-finding (no surprise in the worktree), but worth recording:
the plan's §3 row 12 said "Add 'pg_session_variables' to the regress
test list" in `meson.build`. **No such list exists in the meson
regress harness** — meson uses `tests += { 'regress': { 'schedule':
files('parallel_schedule') } }`, delegating discovery to the schedule
file alone.

**Origin:** the instruction is a holdover from the legacy Makefile
build where `Makefile.regress` enumerated test names explicitly.

**Action item:** drop the meson.build edit row from
`add-new-builtin-function` and `add-new-system-view` scenarios (or
gate it behind "if you're on the autotools build, also edit
Makefile.regress"). Since PG ≥ 16 defaults to meson, the autotools
branch is the exception.

---

## Cross-cutting: what worked well

Despite the four findings, **every issue was caught at the phase
boundary it occurred in** and resolved within a single retry cycle:

- F17 (Phase 1, build) → 1 retry, ~30s.
- F18 (Phase 3, regress) → 1 retry, ~10 min including test SQL
  rewrite + re-golden.
- F19 (Phase 3, regress) → 1 retry, TC reformulated to use inline
  form, golden re-captured.
- F20 (Phase 3, regress) → 1 retry, schedule line split.

The R4 + R13 phase-end-check protocol is doing its job:
**implementations that break existing tests don't proceed**. The R14
comprehensive own-test-suite is doing its job too — TC-X-1
(JOIN-with-pg_class) and TC-E-3 (EXPLAIN parallel restriction) are
exactly the cross-feature integration cases that would silently regress
if the next sesvars iteration broke them, and they're now in the
golden surface.

Net commit-log shape (R12 result):

```
docs(planning): pg_session_variables R12 end-gate summary
docs(planning): pg_session_variables phase 3 notes
pg_session_variables: comprehensive test suite + SGML docs
docs(planning): pg_session_variables phase 2 notes
pg_session_variables: add system view + rules.out update
docs(planning): pg_session_variables phase 1 notes
pg_session_variables: add introspection SRF
docs(planning): pg_session_variables plan — v1.2 generalization test
docs(planning): pg_session_variables brainstorm — v1.2 generalization test
```

3 code commits, 4 notes/summary commits, all linked to plan.md via
`Plan:` trailer (per R5/R6). Full `meson test --no-rebuild` clean:
**100 OK, 0 Fail, 295 platform-gated SKIP**.

---

## Action items for the next skill iteration (v1.3 candidates)

| # | Source | Lands in | Priority |
|---|---|---|---|
| 21 | F17 — header-graph trap | `pg-feature-plan` machinery-survey template | low |
| 22 | F18 — test SQL must match implemented grammar | `pg-feature-plan` Step 1.6 | medium |
| 23 | F19 — enumerate underlying-feature limitations | `pg-feature-brainstorm` Step 0.8 | medium |
| 24 | F20 — parallel_schedule cap-aware placement | both `add-new-*` scenarios | low |
| 25 | meson.build row obsolete | both `add-new-*` scenarios | low |
| 26 | (sesvars-side) `SET @x = expr` subquery RHS | follow-up patch on `feature_sesvars` | medium |

Items 21-25 are skill-prompt edits, 1-2 lines each. Item 26 is a real
PG code change worth queueing for the next sesvars iteration. None
require a new R-rule — R13/R14 caught every regression already.
