---
session_date: 2026-06-16
slug: sesvars
purpose: First end-to-end calibration of the pg-claude planner suite.
status: phase-1 escalation logged; revisions captured; pipeline ongoing.
---

# Calibration findings — sesvars first end-to-end run

The sesvars feature run is the **first end-to-end test** of the
pg-claude planner suite (brainstorm → plan → implement). The goal
isn't to ship session variables — it's to verify the pipeline catches
the right things at the right phases and to surface gaps in the
brainstorm/plan skills, the knowledge corpus, and the discipline
rules.

This document is the running findings log. Phase 1 produced the
first batch; this will be appended to as later phases run.

## TL;DR — what the suite caught vs missed

**Caught (success):**
- The discipline rules (R3, R4, R7, R8) stopped a broken commit from
  landing. The agent ran the regress suite per the phase-end check
  and refused to commit when 39 tests failed.
- R7 path-1 amendment in-flight (the orchestrator-brief typedef
  shape was wrong; the agent corrected by checking source).
- Build-setup variance handled (worktree's fresh build-debug needed
  the icu include flag that sibling `postgresql-dev/build-debug`
  already had).

**Missed (gaps to fix):**
1. **Brainstorm DECISION 1 framing** was too narrow — said "accept
   docs incompat for user-defined `@` ops" but didn't consider PG's
   6 built-in `@` unary operators in `pg_operator.dat`. The whole
   sigil decision was made without auditing the existing catalog
   for conflicts.
2. **Plan §3 missed `src/pl/plpgsql/src/pl_gram.y` token-sync.**
   Core gram.y has a sibling token-block in pl_gram.y that must be
   kept in sync; adding to core without syncing shifts numeric
   token IDs and breaks PL/pgSQL silently.
3. **Scenario `add-new-sql-keyword.md`** doesn't list either of
   those sites as sync-trap concerns. The scenarios are the
   plan-suite's mechanism for "always check these files"; gaps
   propagate to every future plan that pins this scenario.

## Findings by category

### F1 — Brainstorm gap: catalog audit missing from sigil decisions

**Symptom.** Brainstorm DECISION 1 chose new flex rule `@{ident}` →
SESSION_VAR with the framing "accept docs incompat for `@`-prefix
user-defined unary operators on a bare identifier." The phrase
"user-defined" was the bug. PG ships 6 BUILT-IN `@` unary ops:

| Line in pg_operator.dat | Op | Function |
|---|---|---|
| 310 | `@(int8)` | int8abs |
| 603 | `@(float4)` | float4abs |
| 618 | `@(float8)` | float8abs |
| 865 | `@(int2)` | int2abs |
| 1008 | `@(int4)` | int4abs |
| 2121 | `@(numeric)` | numeric_abs |

These regressed the float4 / float8 / opr_sanity regress tests when
the `@x` lexer rule landed.

**Why the suite missed it.** The brainstorm skill doesn't have a
"catalog audit" step. It evaluates decisions on (semantics, parser
impact, executor impact, perf) but not on (existing-catalog
collision). The lexer DECISION questions in particular need a
"grep pg_operator.dat + pg_proc.dat for the sigil/keyword character"
sub-step.

**Fix proposal.**
- Add a "catalog conflict audit" required-step to
  `.claude/skills/pg-feature-brainstorm/SKILL.md` for any DECISION
  that introduces a new lexer token, keyword, or operator. Specifies:
  grep `pg_operator.dat`, `pg_proc.dat`, `pg_aggregate.dat`,
  `kwlist.h`, scan-l `op_chars`/`self` rules for collision with the
  proposed character/keyword.
- Update `knowledge/idioms/lexer-and-grammar.md` (or create if
  missing) with a "Sigil/keyword reservation checklist" section.

### F2 — Plan §3 gap: PL/pgSQL token-sync sibling missed

**Symptom.** `src/pl/plpgsql/src/pl_gram.y:247-250` carries a
synced `%token <str>` block with the in-source comment "Keep this
list in sync with backend/parser/gram.y!". Adding `SESSION_VAR` to
core gram.y without syncing pl_gram.y shifted numeric token IDs in
`gram.h` — COLON_EQUALS went 270→271, DOT_DOT 269→270 — so
`pl_scanner.c`'s integer comparisons (e.g. `if (tok ==
COLON_EQUALS)`) compared against the wrong values. Result: `r :=
'hi'` and `FOR i IN 1..10` stopped parsing in PL/pgSQL. ~30 of the
39 phase-1 regression failures clustered here.

**Why the suite missed it.** Scenario `#11 add-new-sql-keyword.md`
enumerates kwlist.h, check_keywords.pl, psqlscan.l, ECPG pgc.l etc.
as sync-trap concerns — but does NOT list pl_gram.y. The plan §3
table reflected the scenario's checklist; the gap propagated.

**Fix proposal.**
- Add a sync-trap row for `src/pl/plpgsql/src/pl_gram.y` in
  `knowledge/scenarios/add-new-sql-keyword.md` with the rationale
  "any new `%token <str>` in core gram.y shifts numeric token IDs;
  pl_gram.y carries a sibling block that must stay in sync."
- Same row probably belongs in scenarios #13 (utility-statement —
  may add new tokens) and #15 (expression-eval-step — usually not,
  but worth a note).

### F3 — Orchestrator-brief typedef shape error (caught in-flight)

**Symptom.** The Phase 1 orchestrator brief said the `SessionVarRef`
typedef should be `{ Expr xpr; char *name; int location; }`. The
agent grepped `ParamRef` (the simple parse-tree analog) and found it
uses `{ NodeTag type; … ParseLoc location; }`. The `Expr xpr` shape
is for **post-analysis** primnodes.h nodes (like `Param`), not
**parse-tree** nodes.

**Why it wasn't caught earlier.** The orchestrator was working from
the pre-scouted brief, which itself was assembled from the brainstorm
+ plan + scenarios. None of those distinguished parse-tree-Node vs
post-analysis-Expr shape precisely.

**Resolution.** R7 path-1 amendment in-flight. The agent corrected
the typedef shape by checking `ParamRef` precedent (`parsenodes.h:321`)
and proceeded. This is the discipline working: the rule "cite or
don't claim" combined with the agent's willingness to check
precedents before writing.

**Fix proposal (mild).** The `knowledge/idioms/node-types.md` doc (if
it exists; if not, write it) should distinguish parse-tree Node
shape vs Expr shape explicitly, with `ParamRef` and `Param` as
canonical examples.

### F4 — Phase-end-check granularity (works as designed)

**Observation.** The plan's Phase 1 phase-end check said:
"`meson compile -C dev/build-debug` succeeds, the regen produces
T_SessionVarRef in nodetags.h, and `psql -c 'SELECT @x'` reaches
parse-analyze and fails with the expected stub". This is a
**compile-level + targeted-smoke** check.

The agent went further and ran the **full regress suite**, which
caught the 39 failures. The plan's phase-end check would have
PASSED with the broken state (build green; T_SessionVarRef present;
psql smoke produces an error message). The full regress run is
what caught the regression.

**Lesson.** Phase-end checks at the "compile + smoke" granularity
are not load-bearing enough. For phases that touch the lexer,
grammar, or any cross-cutting parsing infrastructure, the phase-end
check **must include the full regress suite**. The v1.1 amendment
tightened Phase 1's check accordingly.

**Fix proposal.**
- `pg-feature-plan` skill should generate phase-end checks that
  default to "full regress" for lexer/grammar/executor phases.
  "Compile + smoke" is acceptable only for phases that touch
  isolated helper code (new file, no cross-cutting impact).
- Add a rule of thumb to `pg-implement-discipline.md` v1.1: "if
  the phase touches gram.y / scan.l / executor dispatch / catalog,
  the phase-end check MUST run `meson test --suite regress`, not
  just compile + smoke."

### F5 — Two-repo separation (R10) worked but needs a tightening

**Observation.** The implementation agent correctly refused to
write `planning/sesvars/notes.md` (knew that meta writes are
orchestrator-only). However, `planning/` actually lives **inside the
worktree** (`postgresql-dev-feature-sesvars/planning/`), not in
`postgres-claude/`. R10 says "meta-repo writes happen in
postgres-claude/", but the `planning/` directory is in dev/ for this
calibration.

**Lesson.** R10 phrasing is ambiguous about `planning/` files. The
implementation agent treated `planning/` as meta-only (good — that's
the spirit), but the actual file location is in dev/. This worked
because the orchestrator handles all `planning/` writes regardless
of which repo they live in.

**Fix proposal.** R10 v1 says: "`dev/` holds the source patch
(upstream-candidate). `postgres-claude/` holds the meta artifacts
(plan, notes, knowledge, sessions)." Tighten in v2 to clarify: "When
the `planning/<slug>/` directory lives inside `dev/` (calibration
runs), treat its contents as meta artifacts — only the orchestrator
writes them, and they get `docs(planning):`-prefixed commits in
meta-style even though they live in `dev/`."

## Action items for the planner suite (post-calibration)

After sesvars completes (or is paused), these should be addressed in
their own commits in `postgres-claude/`:

1. **Scenario `#11 add-new-sql-keyword.md`** — add sync-trap row for
   `src/pl/plpgsql/src/pl_gram.y:247-250`.
2. **Scenario `#11 add-new-sql-keyword.md`** — add a "catalog
   conflict audit" required-step: grep `pg_operator.dat`,
   `pg_proc.dat`, `kwlist.h` for collisions with the proposed
   character/keyword.
3. **Brainstorm skill** (`pg-feature-brainstorm/SKILL.md`) — add
   required catalog audit to any DECISION that introduces a lexer
   token or keyword.
4. **`knowledge/idioms/`** — create or update `lexer-and-grammar.md`
   with sigil-reservation checklist (catalog grep, op_chars audit,
   pl_gram.y sync, ECPG pgc.l sync).
5. **`knowledge/idioms/`** — create or update `node-types.md`
   distinguishing parse-tree-Node shape (NodeTag + ParseLoc) vs
   Expr shape (Expr xpr) with canonical examples.
6. **`pg-feature-plan/SKILL.md`** — default phase-end checks for
   lexer/grammar/executor phases to "full regress", not "compile +
   smoke".
7. **`pg-implement-discipline.md` v2** — add R13: "phase-end check
   granularity must match the phase's blast radius; cross-cutting
   parser/executor phases require full regress."
8. **`pg-implement-discipline.md` v2** — clarify R10 about `planning/`
   files inside `dev/` (calibration runs).

These do NOT happen during this run — they get logged here and the
calibration run continues. Post-calibration, the user can decide
which to land.

## Pipeline timing (so far)

| Step | Wall-clock | Token usage (cumulative agent runs) |
|---|---|---|
| Step 0 (worktree + brainstorm) | done pre-session | — |
| Step 1 (brainstorm) | done pre-session | — |
| Step 2 (`/pg-feature-plan`) | ~5 min | ~109k |
| Step 2 pre-validation (in-context) | ~2 min | — |
| Step 3 phase 1 (first pass) | ~13 min | ~128k |
| Step 3 phase 1 amendment + docs | (in progress) | — |

## What's next

- Land the plan.md amendment + notes.md Phase 1 entry + this retro
  in one meta-style commit on `feature_sesvars`.
- Resume Phase 0 → Phase 1 with the corrected scope.
- After Phase 1 lands, **STOP** per user direction. Do not proceed
  to phases 2-6 autonomously.
- Phases 2-6 + end-of-implementation will resume in a later session
  once the user is ready.
