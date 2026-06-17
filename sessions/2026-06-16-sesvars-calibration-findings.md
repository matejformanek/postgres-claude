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

### F6 — Catalog removal coupling: `opr_sanity` proc-descr check (caught in Phase 0 in-flight)

**Symptom.** Phase 0 dropped 6 `@` unary entries from
`pg_operator.dat`. First regress run failed `opr_sanity`'s
"functions with descriptions" check. The reason: in PG's catalog,
function descriptions are typically supplied via the operator row's
`descr => '...'` field, and the operator→proc pointer carries it
across. Removing the 6 operators ORPHANED the 6 `*abs` functions
w.r.t. descriptions, which `opr_sanity` checks for completeness.

**Resolution.** R7 path-1 in-flight: added `descr => 'absolute
value'` directly to the 6 `*abs` rows in `pg_proc.dat`. 245/245
green after that.

**Why the suite missed it.** Scenario `#11 add-new-sql-keyword.md`
is focused on ADDITIONS to the catalog, not REMOVALS. The planner
relaxed §2's catalog lock for "REMOVAL only" without enumerating
the downstream proc-descr-orphan risk. Plan §3 row 38 didn't
mention pg_proc.dat at all.

**Fix proposal.**
- Add a new scenario `knowledge/scenarios/remove-from-catalog.md`
  covering the inverse direction. Checklist must include:
  - Audit `pg_proc.dat` for functions whose descriptions came via
    the operator/aggregate/cast you're removing.
  - Audit `opr_sanity.sql` and `type_sanity.sql` for queries that
    enumerate by name and would diff in output.
  - Audit any extension catalog (`pg_amop`, `pg_amproc`,
    `pg_opclass`, `pg_opfamily`) for orphaned references.
- Reference this scenario from existing
  `add-new-sql-keyword.md` ("if your decision REMOVES an existing
  operator/keyword as part of reserving the character/keyword for
  the new use, also pin
  `[[scenarios/remove-from-catalog]]`").

### F9 — Walker-flag default mistake: `QTW_EXAMINE_RTES_BEFORE` (caught in Phase 6 in-flight)

**Symptom.** Phase 6's `QueryListHasSessionVar` walker initially
passed `QTW_EXAMINE_RTES_BEFORE` to `query_tree_walker`, thinking
it'd give thorough coverage. The walker landed on `RangeTblEntry`
nodes; the `ScanQueryForSessionVar` callback didn't handle them;
`expression_tree_walker` errored on "unrecognized node type: 111".
100+ regress tests failed.

**Fix.** Use flag 0 (default). Session vars only appear in
expressions inside targetlist/qual/etc., which `query_tree_walker`
already visits without `QTW_EXAMINE_RTES_BEFORE`.

**Why the suite missed it.** `knowledge/idioms/walkers.md` (if it
exists; if not, write it) should document the
`query_tree_walker` flag landscape with examples of when each flag
is needed. The walkers/`QTW_*` flags are subtle and not obvious from
the prototype.

**Fix proposal.**
- New `knowledge/idioms/query-tree-walkers.md` covering the
  `QTW_*` flag matrix: when to use each, what they make the
  walker visit, and which walker functions need handlers if the
  flag is set.
- Reference from scenarios that involve query-tree walking
  (#6 add-new-plan-node, #15 add-new-expression-eval-step).

### F10 — `fixed_result` enforcement is too strict for type-changing plans (caught in Phase 6 in-flight)

**Symptom.** Phase 6's plan-cache invalidation re-analyzes a plan
when a session-var type changes. The new tupdesc differs from the
cached one (e.g. int4 → text). `RevalidateCachedQuery` at line
~907 enforces `fixed_result` strictly:

```c
if (plansource->fixed_result &&
    !equalTupleDescs(plansource->resultDesc, newdesc))
    ereport(ERROR, "...");
```

PREPARE always sets `fixed_result = true`, so this fired on every
type-change EXECUTE. Result: prepared statements couldn't observe
type-shifting session vars.

**Fix.** Relax the enforcement when `plansource->has_session_var`:
`if (plansource->fixed_result && !plansource->has_session_var)
ereport(ERROR, …)`. Session-var-bearing plans accept tupdesc
changes; `plansource->resultDesc` updates to the new shape.

**Why the suite missed it.** No existing scenario or knowledge doc
discusses `fixed_result` and its interaction with plan
invalidation. The plan's §13 risk 1 sketched the polling-counter
sidestep but didn't anticipate that the result-tupdesc shape would
need to evolve.

**Fix proposal.**
- Add a "plan-cache invalidation contract" section to
  `knowledge/idioms/plan-cache.md` (or create it) covering
  `fixed_result`, when it can/can't relax, and how type-changing
  plans are handled.
- Document this trade-off in the sesvars upstream submission
  cover-letter — Tom Lane will want to see the rationale.

### F11 — Wire-RowDescription staleness via `FetchPreparedStatementResultDesc` (caught in Phase 6 in-flight)

**Symptom.** Even after relaxing `fixed_result` (F10), the wire
`RowDescription` for the first EXECUTE after a type-shift was
stale. Client received int4 type info while the executor produced
text — the client interpreted the varlena pointer as int4, yielding
garbage like `2003791379`. The second EXECUTE was always correct
because the first had triggered re-analysis as a side effect.

**Root cause.** `UtilityTupleDescriptor` on `T_ExecuteStmt` calls
`FetchPreparedStatementResultDesc` BEFORE the inner portal's
`ExecuteQuery → GetCachedPlan` revalidation runs. The outer portal
publishes `plansource->resultDesc` which is still stale.

**Fix.** Have `FetchPreparedStatementResultDesc` force
`GetCachedPlan` + immediate `ReleaseCachedPlan` purely for the
revalidation side effect on `resultDesc` — only when counter drift
is detected.

**Why the suite missed it.** The wire-protocol path from
`UtilityTupleDescriptor → FetchPreparedStatementResultDesc → outer
RowDescription` is not documented in any scenario or skill. It's
discoverable only by tracing the divergence between the first and
second EXECUTE of a type-shifted plan.

**Fix proposal.**
- Document the EXECUTE wire-protocol flow in
  `knowledge/subsystems/prepared-statements.md` (or extend the
  existing utility-statement doc).
- The polling-counter pattern in Phase 6 only works if EVERY
  consumer of `plansource->resultDesc` triggers revalidation
  first. List those consumers in the doc.

### F8 — Objective-C keyword collision on macOS clang (caught in Phase 3 in-flight)

**Symptom.** Phase 3 added a `typeid` field to the new `SessionVar`
Expr node in primnodes.h. The build failed on macOS clang with
opaque errors about token expectations and reserved word use —
because **`typeid` is a reserved Objective-C keyword** on macOS
clang. Renamed everywhere to `vartype`. ~30 min lost.

**Why the suite missed it.** No knowledge corpus / scenario / skill
warns about Objective-C reserved words. The PG tree's existing
headers happen to avoid them (the closest precedent, `Param`, uses
`paramtype` not `typeid`), but newcomers wouldn't know.

**Reserved words to avoid in PG headers/identifiers:**
- macOS Objective-C: `typeid`, `id`, `Class`, `SEL`, `IMP`, `BOOL`,
  `nil`, `Nil`, `YES`, `NO`, `self`, `super`, `_cmd`, `IBAction`,
  `IBOutlet`.
- Windows (winnt.h): `BOOL`, `BYTE`, `WORD`, `DWORD`, `HANDLE`,
  `FAR`, `NEAR`, `IN`, `OUT`, `OPTIONAL`.
- Both: `BOOL` (worst offender).

**Fix proposal.**
- Add a `knowledge/idioms/portable-identifiers.md` doc enumerating
  the reserved words to avoid + showing the precedent in existing
  PG headers (e.g. `paramtype`, `funcname` patterns).
- Reference from `pg-feature-plan/SKILL.md` §3 file-table emission:
  when proposing a new typedef field name, the planner should grep
  the existing tree for the proposed name to detect collision.
- Add a note to the brainstorm skill for any DECISION that
  introduces a new C identifier in a backend header.

### F7 — `meson test --suite setup` prerequisite undocumented

**Symptom.** First Phase 0 regress run in the fresh worktree
build-debug failed with "could not bind / Address already in use"
and a missing `initdb-template` directory. The fix was running
`meson test --suite setup` first, which creates the initdb cache
via `initdb_cache` target.

**Why the suite missed it.** Build-and-run skill at
`.claude/skills/build-and-run/SKILL.md` doesn't mention the
`setup` suite as a prerequisite for `regress`. Future phase
orchestration on fresh build trees will hit this same wall.

**Fix proposal.**
- Update `.claude/skills/build-and-run/SKILL.md` with: "On a fresh
  build tree, run `meson test -C build-debug --suite setup` ONCE
  before `--suite regress` to populate the initdb template cache."
- Same note in `.claude/skills/testing/SKILL.md` if that skill
  enumerates suite ordering.
- `.claude/commands/pg-test.md` (slash-command) should auto-detect
  a missing `initdb-template` and run setup first.

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
9. **`knowledge/scenarios/remove-from-catalog.md`** — new scenario
   covering catalog REMOVAL (F6). Must enumerate proc-descr-orphan
   risk + opr_sanity/type_sanity diff risk + extension-catalog
   audit.
10. **`.claude/skills/build-and-run/SKILL.md`** — document
    `meson test --suite setup` prerequisite on fresh build trees
    (F7). Same note in `.claude/commands/pg-test.md`.
11. **`knowledge/idioms/portable-identifiers.md`** — new doc
    enumerating reserved words to avoid (F8): Objective-C
    keywords on macOS clang + Windows winnt.h symbols. Show
    precedent renames (`paramtype`, `funcname`).
12. **`pg-feature-plan/SKILL.md`** — when emitting §3 row for a
    new typedef, grep the proposed field name against the tree to
    detect collision (F8 prevention).
13. **Walker-coverage checklist** (Phase 3 surfaced this): any new
    Expr node needs adds in `nodeFuncs.c` (6 funcs:
    `exprType/Typmod/Collation/SetCollation/Location/walker/
    mutator`), `parse_collate.c assign_collations_walker`, and
    `typedefs.list`. Add to `knowledge/scenarios/add-new-expression-
    eval-step.md` (#15) as a required-step row.
14. **`knowledge/idioms/query-tree-walkers.md`** — `QTW_*` flag
    matrix + when each flag is needed + which walker functions
    require handlers (F9).
15. **`knowledge/idioms/plan-cache.md`** — `fixed_result`
    invariant and when it can/can't relax for type-changing plans
    (F10). Reference from any scenario involving plan invalidation.
16. **`knowledge/subsystems/prepared-statements.md`** — document
    the EXECUTE wire-protocol path from `UtilityTupleDescriptor →
    FetchPreparedStatementResultDesc → outer RowDescription` (F11).
    List all consumers of `plansource->resultDesc` so future
    invalidation work can ensure each triggers revalidation.

These do NOT happen during this run — they get logged here and the
calibration run continues. Post-calibration, the user can decide
which to land.

## Pipeline timing

| Step | Wall-clock | Token usage (cumulative agent runs) |
|---|---|---|
| Step 0 (worktree + brainstorm) | done pre-session | — |
| Step 1 (brainstorm) | done pre-session | — |
| Step 2 (`/pg-feature-plan`) | ~5 min | ~109k |
| Step 2 pre-validation (in-context) | ~2 min | — |
| Step 3 phase 1 (first pass — escalated) | ~13 min | ~128k |
| Step 3 phase 1 amendment + docs (in-context) | ~5 min | — |
| Step 3 phase 0 + phase 1 (final, agent) | ~10 min | ~162k |
| Step 3 phase 0 + phase 1 docs (in-context) | ~3 min | — |

**MVP COMPLETE: all 7 phases (0-6) landed. 246/246 regress green at
every phase boundary. End-of-implementation gate ran 2026-06-17.**

## What's next

MVP is done. The calibration run produced **7 commits ahead of
master** in `dev/`, **6 meta `docs(planning):` commits** in the
worktree, and **3 retro commits** in the meta repo (this file).

Post-calibration backlog (the 16 action items above) is the real
deliverable for the planner suite. Recommended landing order:

1. **Scenario fixes** (items 1, 2, 9, 13) — these are pure
   knowledge-corpus updates with no skill-prompt churn. Land them
   first.
2. **Idiom docs** (items 4, 5, 11, 14, 15, 16) — new
   `knowledge/idioms/*.md` files. Cite from the relevant scenarios
   after writing.
3. **Skill updates** (items 3, 6, 7, 8, 12) — touch the brainstorm
   and plan skill prompts. Higher blast radius; do these after the
   scenario + idiom layer stabilizes.
4. **Build/test workflow** (item 10) — `build-and-run/SKILL.md` +
   `pg-test.md` updates.

The sesvars feature itself is upstream-candidate (245+1 regress
green, JIT mirror in place, walker coverage complete, plan-cache
invalidation working). Before any pgsql-hackers submission:
- Restore the SGML docs scope locked out in §2.
- Run `review-checklist` skill.
- Open a fresh thread per plan §12.
- Add the 6 deferred items (DISCARD ALL, pg_session_variables,
  ACL, pgbouncer reset, benchmarks, EXPR_KIND_SESSION_VAR_*) to
  the cover-letter as known gaps with follow-up patches.
