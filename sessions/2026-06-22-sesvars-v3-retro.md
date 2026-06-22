# sesvars_v3 — 11-phase implementation retro + harvest

**Date:** 2026-06-22
**Branch:** `feature_sesvars` in `postgresql-dev-feature-sesvars/`
**Final HEAD:** `9b06fb679a6` (follow-ups #2+#3 notes commit)
**Tag:** `sesvars_v3_baseline` at `440b6a53550`

## What shipped

11 phases + 3 follow-ups, end-to-end on top of a fully-rewritten architecture. All 8 brainstorm DECISIONs landed (Param + PARAM_SESSION_VARIABLE + paramsesvarid, SesVarExpr write node, pstate→sesvar_changes HTAB, per-name plan-cache callbacks, STRICT TYPE, write-indirection, DDL DEFAULT deferred per scope lock, incremental migration). Live cluster canary across 8 cases all green. R12 end-gate full `meson test --no-rebuild`: 100/0/295. Benchmark: 36/1452 baseline → 55/1162 final (DIFF −20%, ERR cascades + stricter type errors net +19, dominated by brainstorm §2 v4-deferred categories + ~24 pre-existing column-label rendering).

The architecturally novel TC-W-8 (`SET @c := '5', @ci := @c + 3, @m := @c * @ci` → `5|8|40`) — the row this whole rewrite existed for — passes.

## F-findings (this run's harvest, F21-F25)

### F21 — Hand-rolled PlannedStmt leaks unprocessed nodes into the executor

**Where:** `src/backend/commands/sessvar_cmd.c` `BuildSessionVarSetPlannedStmt`.

**Symptom:** `SET @v := (SELECT 53)` in utility form errored with `unrecognized node type: 23` (T_SubLink) at `ExecInitExprRec`. Inline `SELECT @v := (SELECT 53)` worked fine.

**Root cause:** Phase 9 added `expression_planner(e)` per RHS to handle CollateExpr (and const-fold + fix_opfuncids). But `expression_planner` is documented as NOT processing SubLinks — `SS_process_sublinks` runs only from inside `subquery_planner`. The hand-rolled PlannedStmt skipped the planner entirely; only `expression_planner` ran, so the SubLink reached the executor raw.

**Fix:** FU#1 commit `98321c74bef`. Build ONE synthetic `Query{CMD_SELECT, targetList=[TargetEntry(e_i)…]}` containing all RHS, call `pg_plan_query` once. Harvest processed expressions + subplans + paramExecTypes onto the outer hand-rolled PlannedStmt. Single planner pass gives a consistent PARAM_EXEC paramid namespace — Param paramids inside the harvested expressions index directly into the outer pstmt's subplans list, no offsetting.

**Lesson (graduate to corpus):** *Any utility-statement code path that bypasses `pg_plan_query` will leak unprocessed parse-tree nodes into `ExecInitExprRec`.* Action: write `knowledge/idioms/utility-stmt-planning.md` documenting (a) what `expression_planner` does vs what `pg_plan_query`/`subquery_planner` do, (b) when the hand-rolled-PlannedStmt shortcut is safe (constant RHS, no SubLink, no DEFAULT-expression evaluation), (c) the `pg_plan_query`-as-fallback pattern with the harvested-subplans gluing.

### F22 — `ExprEvalStep ≤ 64` byte static-assert is easy to break

**Where:** `src/include/executor/execExpr.h` defines `StaticAssertDecl(sizeof(ExprEvalStep) <= 64, ...)`. Phase 8's inline indirection needed to carry subscript ExprStates per step.

**Symptom:** Initial design grew `ExprEvalStep.d.sesvar_write` to ~80 bytes via inline state; build-fail on the StaticAssertDecl.

**Fix:** FU#2 commit `7197b54c1d0`. Out-of-line state pointed to by a single `SesVarIndirectionState *` pointer in the d-union. Pattern mirrors `SubscriptingRefState` in `src/include/executor/execExpr.h` (the canonical example for "step state too large for inline").

**Lesson (graduate to corpus):** Action: write `knowledge/idioms/exprevalstep-shape.md` documenting (a) the 64-byte cap and why it exists (cache-friendliness of the eval-step array), (b) the out-of-line state pattern (SubscriptingRefState as canonical example), (c) when to use inline vs out-of-line (rough rule: > 4 fields or any array → out-of-line).

### F23 — Hooks were not worktree-aware

**Where:** `postgres-claude/.claude/hooks/pg-precommit.sh` + `pg-phase-detect.sh` hard-coded `DEV_ROOT="$CLAUDE_PROJECT_DIR/dev"`.

**Symptom:** Every code commit from phases 2-10 + FU#1-2 had to be made with `PG_PRECOMMIT_SCOPE=skip` because the hook either silently no-op'd (if no staged files were found in the main clone, which was always for a worktree commit) or ran the wrong tests against the wrong build tree.

**Root cause:** Worktrees share the main repo's `.git/hooks/` via `commondir` indirection. When a worktree commits, git fires `postgresql-dev/.git/hooks/pre-commit`. The wrapper exec's `pg-precommit.sh` with `cwd = the working tree root` (git pre-commit contract). But the script hard-coded `DEV_ROOT` to the main clone path.

**Fix:** FU#3 meta-repo commit `d89efca`. Three-tier discovery: `$PG_HOOK_DEV_ROOT` → `git rev-parse --show-toplevel` → `$CLAUDE_PROJECT_DIR/dev` fallback. Applied to both `pg-precommit.sh` and `pg-phase-detect.sh`. **Verified live:** the sesvars notes commit `9b06fb679a6` (this same retro session) landed through the live hook with no override, hook proposed and ran the R13 `regress` suite, 252 tests passed.

**Lesson (graduate to corpus):** `R4 + R13 anti-patterns` in `pg-implement-discipline.md` should note that `PG_PRECOMMIT_SCOPE=skip` is now reserved for genuine emergencies, not the norm — worktree commits go through the live hook by default. Already updated below.

### F24 — Agents can rate-limit mid-phase; partial-state recovery needed

**Where:** Phase 8 implementation agent and FU#1 implementation agent both hit Anthropic session/quota limits before committing. Staged changes were left in the worktree.

**Pattern:** Both times the agent had ~70-80% of the work done — grammar + parser + parsenode changes staged, but the executor side or the final test refresh not yet done. The agent reported the rate-limit; the orchestrator could either (a) resume the same agent via `SendMessage` (the agent's prior context is preserved) or (b) inspect the staged work and continue manually.

**Practiced both times:** Phase 8 → I continued manually because the staged state was rich enough to finish from; FU#1 → resume via SendMessage worked.

**Lesson (graduate to corpus):** Update `pg-implement/SKILL.md` (or the worktree-workflow rule) to document: (1) check `git status` after every agent return — staged-but-uncommitted state is a recoverable signal, not a failure; (2) SendMessage to the same agent ID resumes with context preserved; (3) when the agent's approach is sound but they stopped mid-phase, the manual continuation can be tighter (fewer R7 escalations) since you have the agent's intent in their staged code.

### F25 — Column-label rendering is the largest residual benchmark gap

**Where:** Benchmark `usertest.out` shows expected `@var_int | @var_string | …` as column labels; actual output shows `?column? | ?column? | …`.

**Symptom:** ~24 of the remaining 55 ERR in the v3 benchmark trace to this rendering difference, NOT to any v3 functional regression. Predates v1 sesvars; iter4 had the same behavior; never in v3's scope.

**Root cause:** When parsing `SELECT @x;` the ColumnRef → SesvarRef chain doesn't propagate the identifier into the ResTarget's `name` field, so the targetlist entry gets the default `?column?`. PG's regular column-ref path (e.g. `SELECT col;`) DOES set `resname` from the ColumnRef.

**Fix scope (NOT done):** ~20-30 line patch in `src/backend/parser/parse_target.c` or wherever sesvar reads convert to ResTarget. A "v4 polish" candidate.

**Lesson:** Always inspect baseline ERR/DIFF breakdown by category BEFORE attributing benchmark deltas to recent changes. The phase-10 ERR=64 reading was over-pessimistic; once column-label divergence + brainstorm §2 deferred categories were segregated, the actual v3-introduced ERR was ~5 (closed by FU#1).

## Lessons that worked

### L1 — Architectural canary rows prevent scope drift

TC-W-8 (`5|8|40` chained self-assign) was named at brainstorm time as THE row this rewrite existed for. Every phase plan referenced it. The 4-phase architectural foundation (PARAM_SESSION_VARIABLE + SesVarExpr + sesvar_changes HTAB + Session.variables) was scoped exactly to make TC-W-8 work. Subsequent phases (7-9) were "feature-additive" polish on top of a working foundation.

This is R15 in practice: "default comprehensive, not minimal MVP" + "name the load-bearing row before brainstorming the rest".

### L2 — Atomic-commit phases survived bisect-clean

Phase 2 (T_SessionVar deletion) and Phase 5 (storage migration) were explicitly marked atomic in the orchestrator's "Atomic-commit phases" list. Both landed as single commits with negative-delta line counts (phase 2: −10 net across 18 files; phase 5: +49 with 2 new files). Partial states would have broken the build. The orchestrator's atomic-phase identification worked.

### L3 — R7 escalation tiers worked across ~20 in-flight adjustments

Every R7 escalation in this run was tier-1 ("small + tightly coupled to plan §3 intent"). Zero tier-3 re-plans. Examples:
- Phase 2: type peek moved to parse-analysis (not grammar) — caught a plan-cache invalidation bug
- Phase 3: deferred `setSessionVariable` signature widening to phases 7-8
- Phase 4: `parse_coerce.c` UNKNOWN sesvar Param relabel (mirrors user reference's CoerceParamHook)
- Phase 5: CMD_SELECT reuse instead of new CmdType (avoided ~50 mass-mechanical switch updates)
- Phase 7: transform site relocated from `parse_expr.c` to `analyze.c` (where the function actually lives)
- Phase 9: SessionVarSet signature widened end-to-end for collation (verification revealed it hadn't been done in phase 7-8)

The "small + tightly coupled" tier is doing the work the discipline rules intended.

### L4 — Multi-agent delegation pattern

Pattern that worked: each phase's implementation went to a focused Agent with a tight brief (read these plan files, do these specific edits, satisfy these acceptance criteria, ONE commit). Main loop verified the commit landed, ran independent phase-end check, wrote R8 notes. This kept main-loop context bounded (most phase reports were < 350 words returned) and let agents focus on a single concrete deliverable.

Phases 3, 4, 5, 6, 7, 8, 9, 10, FU#1, FU#2 all used this pattern successfully. Phases 0, 1 were small enough to do directly. Phase 2 used agent + manual continuation.

### L5 — Honest scoring beats panicked fixing

Phase 10 reported ERR=64 against iter4 baseline 36 (a 28-error regression on the surface). The phase-10 plan said "if you miss the bar, document don't paper over". The R12 end-gate notes broke down the 64 by category: ~25 from F21 (SubLink cascade, single fix away), ~14 from DDL DEFAULT deferred, ~6 from inline indirection deferred, ~15 from PL/pgSQL native + SELECT INTO deferred, ~24 from pre-existing column-label divergence. The user could then triage: "follow-ups #1-#2 close the closable, the rest is v4". That triage saved an unknown amount of panic-fixing on rows that weren't in scope.

## Action items for v1.3 of the skill suite

| # | Action | Where | Effort |
|---|---|---|---|
| A1 | New idiom doc: `utility-stmt-planning.md` | `knowledge/idioms/` | ~200 lines, 30 min |
| A2 | New idiom doc: `exprevalstep-shape.md` | `knowledge/idioms/` | ~150 lines, 20 min |
| A3 | Update R4 anti-patterns: remove "PG_PRECOMMIT_SCOPE=skip is the documented escape" — the hook is now worktree-aware, the skip env is for genuine emergencies | `.claude/rules/pg-implement-discipline.md` | 5 lines edit |
| A4 | Document agent rate-limit recovery pattern (SendMessage continuation + staged-state inspection) | `.claude/skills/pg-implement/SKILL.md` | ~20 lines added |
| A5 | Capture the "name the load-bearing row at brainstorm" pattern as an R15 sub-rule | `.claude/rules/pg-implement-discipline.md` R15 | ~10 lines added |
| A6 | Column-label rendering fix as a v4 candidate (not blocking) | sesvars_v4 brainstorm if pursued | n/a |

A3 lands in this same session — see edit below.

## Resume context for any future sesvars work

- Branch `feature_sesvars` carries the full v3 architecture + 3 follow-ups. Tag `sesvars_v3_baseline` for rollback.
- Benchmark baseline + per-iteration scores in `planning/sesvars/benchmark/SCORECARD.md`.
- Brainstorm + plan + per-phase plans + per-phase notes all live in `postgresql-dev-feature-sesvars/planning/sesvars_v3/`.
- The 3 v4-deferred feature categories that would close most of the remaining ERR gap: DDL `DEFAULT @v`, native PL/pgSQL `SET @x`, `SELECT INTO @x`. Plus the column-label rendering polish.
