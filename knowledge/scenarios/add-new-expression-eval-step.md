---
scenario: add-new-expression-eval-step
when_to_use: I want to add a new opcode to the flat expression evaluator (a new `EEOP_*` step kind) — both the interpreter case in `execExprInterp.c` and the LLVM JIT mirror in `llvmjit_expr.c`.
companion_skills: ["executor-and-planner"]
related_scenarios: ["add-new-node-type", "add-new-plan-node"]
canonical_commit: 8dd7c7cd0a2
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new expression-eval step

## Scope — what's in / out

**In scope:**
- One new `ExprEvalOp` enum value (`EEOP_FOO`) plus the four-place
  lockstep edit: enum, dispatch table, interpreter case, JIT case.
- The emit-side helper in `execExpr.c` that pushes the new step into the
  `ExprState->steps` array via `ExprEvalPushStep()`.
- Optional out-of-line helper in `execExprInterp.c` for non-fast-path
  cases (signature `void ExecEvalXxx(ExprState *, ExprEvalStep *, ...)`),
  declared `extern` in `execExpr.h` so the JIT can call it.
- Optional union member in `ExprEvalStep->d` if the new step needs more
  state than fits in an existing union arm.

**Out of scope:**
- New parse `Expr` Node kind that this step services — see
  `add-new-node-type`. A step is the *runtime* representation; the
  `Expr` is the parse-time representation. Most patches add both, but
  the file sweeps are disjoint.
- New plan node that emits a custom expression — see `add-new-plan-node`.
- Pure FMGR-callable built-in function — see `add-new-builtin-function`.
  EEOP steps are for cases that can't (or shouldn't) be expressed as a
  regular C-callable function: jumps, short-circuit, batched fetches,
  type-coercion machinery.

## Pre-flight

- **Companion skills:** load `executor-and-planner` (covers the flat
  expression evaluator, `ExprState`, the dispatch table, and the JIT
  provider contract).
- **Canonical commit:** `8dd7c7cd0a2` — *Replace EEOP_DONE with special
  steps for return/no return* (Daniel Gustafsson + Andres Freund,
  2025-03-11). Touches exactly the four pivot files for this
  change-class — `execExpr.h` (enum), `execExpr.c` (emit), `execExprInterp.c`
  (dispatch + case), `llvmjit_expr.c` (JIT mirror) — plus the README and
  one caller in `nodeAgg.c`. Smallest end-to-end example of the pattern.
  Read it before starting.
- **Common pitfalls (one-line each):**
  - Forgot to add the entry to `dispatch_table[]` in `execExprInterp.c`
    — direct-threaded build crashes immediately
    [from-comment](source/src/include/executor/execExpr.h:248-252).
  - Forgot the JIT case — non-JIT regress passes, `jit_above_cost=0`
    regress segfaults or `LLVMVerifyFunction` errors
    [verified-by-code](source/src/backend/jit/llvm/llvmjit_expr.c:80).
  - Enum entry order in `execExpr.h` doesn't match `dispatch_table[]`
    order in `execExprInterp.c` — direct-threaded dispatch jumps to the
    wrong label and corrupts state
    [from-comment](source/src/include/executor/execExpr.h:248-252).
  - Pushed step but never updated `ExprEvalPushStep`'s caller jump
    targets / `adjust_jumps` lists — short-circuit semantics break for
    nested expressions
    [from-README](source/src/backend/executor/README:181-186).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/executor/execExpr.h` | Add `EEOP_FOO` to the `ExprEvalOp` enum (keep grouped with semantically related entries; the comment at line 248 demands order match `dispatch_table[]` in `execExprInterp.c`) [verified-by-code](source/src/include/executor/execExpr.h:248-297). If the step needs per-instance data, add a new arm to the `ExprEvalStep->d` union (line 319 onwards) — keep total union ≤ 40 bytes [from-comment](source/src/include/executor/execExpr.h:316-318). If using an out-of-line helper, add its `extern` prototype at line ~855 alongside the other `ExecEvalXxx` decls. | [execExpr.h.md](../files/src/include/executor/execExpr.h.md) | executor-and-planner |
| 2 | `src/backend/executor/execExpr.c` | Add the emit-side code that pushes the step. Pattern: `scratch.opcode = EEOP_FOO; scratch.d.foo.field = …; ExprEvalPushStep(state, &scratch);` [verified-by-code](source/src/backend/executor/execExpr.c:166). Place inside the right branch of `ExecInitExprRec()` (the recursive `Expr → step` walker) or inside a dedicated `ExecBuildXxx` helper if the step is emitted by a higher-level builder (cf. `ExecBuildAggTransCall`). If the step participates in jumps, manage `adjust_jumps` lists per the README [from-README](source/src/backend/executor/README:181-186). | [execExpr.c.md](../files/src/backend/executor/execExpr.c.md) | executor-and-planner |
| 3 | `src/backend/executor/execExprInterp.c` | Two synchronized edits in this file. (a) Add `&&CASE_EEOP_FOO,` to the `dispatch_table[]` initializer at the position matching the enum [verified-by-code](source/src/backend/executor/execExprInterp.c:484-510). (b) Add the case body `EEO_CASE(EEOP_FOO) { … EEO_NEXT(); }` inside `ExecInterpExpr()` near related step kinds [verified-by-code](source/src/backend/executor/execExprInterp.c:632-680). For non-trivial bodies write a `void ExecEvalFoo(ExprState *, ExprEvalStep *, ...)` out-of-line helper later in this file and have the case dispatch to it — keeps the hot path small and lets the JIT share the helper [from-README](source/src/backend/executor/README:206-215). If the step is reachable from `ExecEvalStepOp()` callers (EXPLAIN, etc.), it falls out automatically — no edit needed there. | [execExprInterp.c.md](../files/src/backend/executor/execExprInterp.c.md) | executor-and-planner |
| 4 | `src/backend/jit/llvm/llvmjit_expr.c` | Add the JIT mirror. Inside the giant `switch (opcode)` of `llvm_compile_expr()` [verified-by-code](source/src/backend/jit/llvm/llvmjit_expr.c:80), add `case EEOP_FOO:` that emits the LLVM IR equivalent. For simple steps, build the IR inline; for complex/share-with-interp logic, emit a call to the out-of-line `ExecEvalFoo` helper via `build_EvalXFunc()`. The JIT case MUST exist — `llvm_compile_expr` aborts on unhandled opcodes, so an interpreter-only step segfaults under `jit=on`. | [llvmjit_expr.c.md](../files/src/backend/jit/llvm/llvmjit_expr.c.md) | executor-and-planner |
| 5 | `src/backend/executor/README` | If the new step changes any documented invariant — final-step requirement, jump semantics, the helper-function shared-with-JIT contract — update the "Expression Trees and ExecInitExpr / ExecEvalExpr" section [verified-by-code](source/src/backend/executor/README:120-215). Pure additions to the opcode set don't require a README edit; reshaping the dispatch protocol does. | — | executor-and-planner |
| 6 | `src/backend/executor/nodeXxx.c` (caller) | Whichever planner-emitted node first uses the new step (e.g. `nodeAgg.c` for an aggregate-flow step, `execGrouping.c` for hashing). The caller invokes `ExecInitExpr` / `ExecBuildXxx` which then pushes the new opcode. Without a caller the step is dead code; the regress run will not exercise it [verified-by-code](source/src/backend/executor/nodeAgg.c). | — | executor-and-planner |
| 7 | `src/test/regress/sql/<group>.sql` + `expected/<group>.out` | Add a SQL exercise that triggers the new step. Existing groups by domain: `expressions`, `case`, `domain`, `jsonb_jsonpath` (for JSON_EXPR), `aggregates` (for agg-internal steps). [verified-by-code](source/src/test/regress/sql/expressions.sql) | — | testing |
| 8 | (NEW or existing) JIT smoke under `jit_above_cost = 0` | The standard regress suite doesn't force JIT. To exercise the JIT mirror, either add a `SET jit_above_cost = 0; SET jit_expressions = on; <stmt>` block to an existing test, or rely on the `pg_regress` flag to set those via `PGOPTIONS`. Without this you can ship an unhandled JIT case and CI greens. [verified-by-code](source/src/backend/jit/jit.c:37-42) | — | executor-and-planner |
| 9 | `src/backend/nodes/nodeFuncs.c` | **Walker coverage (REQUIRED when the new step services a new `Expr` Node).** Every new Expr Node needs 6+ case adds across the walker family in this file: `exprType()`, `exprTypmod()`, `exprCollation()`, `exprSetCollation()`, `exprLocation()`, plus the recursive walks in `expression_tree_walker()` and `expression_tree_mutator()`. Missing any of these manifests as `elog(ERROR, "unrecognized node type")` from a code path that the per-phase regress may not exercise. Origin: sesvars F3. (Compose with `scenarios/add-new-node-type.md` — the Node-add scenario owns the broader walker sweep; this row is the EEOP-side reminder that an `Expr`-bearing step needs the same coverage.) | — | parser-and-nodes |
| 10 | `src/backend/parser/parse_collate.c` | **Collation walker leaf-case (REQUIRED when the new step services a new `Expr` Node that can produce a TEXT-family result).** `assign_collations_walker()` needs a leaf-Expr case for the new node. Missing this triggers a `SIGABRT` on the first collation-walker pass for any TEXT-resulting expression — the assertion fails before any user-visible error message, so the symptom is a backend crash on a SELECT that mentions the new Expr. The crash happens in parse-analysis, not execution, so JIT-on/JIT-off both crash identically. Origin: sesvars F3. | — | parser-and-nodes |
| 11 | `src/backend/utils/adt/ruleutils.c` | **Parse-tree pretty-printer (REQUIRED when the new step services a new `Expr` Node).** Both `get_rule_expr()` and `is_simple_node()` need `case T_FooExpr:` entries for the new node. Without these, `EXPLAIN VERBOSE`, `CREATE VIEW`, `pg_get_viewdef()`, `pg_get_ruledef()`, `pg_get_*def()` — every parse-tree-to-text path — error with `unrecognized node type: N` at runtime. Per-phase happy-path regress almost never invokes `EXPLAIN VERBOSE` on the new Expr, so this gap is **invisible to per-phase gates** and only surfaces under a comprehensive own-test-suite (R14). Origin: sesvars F14 — `EXPLAIN VERBOSE SELECT @x` and `CREATE VIEW v AS SELECT @x` errored with `unrecognized node type: 9` because `T_SessionVar` was missing from both functions. Fix shape: `case T_SessionVar: appendStringInfo(buf, "@%s", node->name); break;` plus inclusion in `is_simple_node`'s "no parens needed" list if appropriate. | — | parser-and-nodes |

(Use `—` in the per-file doc column for files whose per-file doc hasn't
been written yet; otherwise the entry should exist in `knowledge/files/`
and link.)

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Wire the opcode (no callers yet).** Files: [1, 3].
   Add `EEOP_FOO` to the enum and matching union arm in `execExpr.h`.
   Add `&&CASE_EEOP_FOO,` to `dispatch_table[]` and a stub
   `EEO_CASE(EEOP_FOO) { /* TODO */ EEO_NEXT(); }` body in
   `ExecInterpExpr()`. Phase-end check: `meson compile -C dev/build-debug`
   succeeds; nothing emits the step yet so regress is unchanged.

2. **Phase 2 — Emit + interpreter body.** Files: [2, 3, 6, 5 (if needed)].
   Implement the emit-side `ExprEvalPushStep` call in `execExpr.c`. Wire
   the caller (`nodeXxx.c`) so the planner can produce the step. Fill in
   the interpreter case body — direct or via an out-of-line
   `ExecEvalFoo` helper. Update the README if dispatch semantics change.
   Phase-end check: `meson test -C dev/build-debug --suite regress`
   passes under default JIT settings (`jit_above_cost = 100000` — JIT
   off for cheap queries).

3. **Phase 3 — JIT mirror.** Files: [4].
   Add the `case EEOP_FOO:` to `llvm_compile_expr()` in
   `llvmjit_expr.c`. For trivial steps emit IR inline; for shared logic
   call the `ExecEvalFoo` helper via `build_EvalXFunc()`. Phase-end
   check: `PGOPTIONS='-c jit_above_cost=0 -c jit_expressions=on
   -c jit_optimize_above_cost=0' meson test … --suite regress` passes
   end-to-end.

4. **Phase 4 — Tests + docs.** Files: [7, 8].
   Add SQL exercise to the appropriate regress group. Add an explicit
   JIT-on block (`SET jit_above_cost = 0`) so future refactors that
   break the JIT mirror surface in CI. Phase-end check: both JIT-on and
   JIT-off regress runs are green.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`aggregate-grouping-sets`](../idioms/aggregate-grouping-sets.md) | shares files: `src/backend/executor/nodeAgg.c` |
| [`aggregate-hash-vs-sort`](../idioms/aggregate-hash-vs-sort.md) | shares files: `src/backend/executor/nodeAgg.c` |
| [`aggregate-partial-finalize`](../idioms/aggregate-partial-finalize.md) | shares files: `src/backend/executor/nodeAgg.c` |
| [`aggregate-trans-state`](../idioms/aggregate-trans-state.md) | shares files: `src/backend/executor/nodeAgg.c` |
| [`expression-evaluator-flow`](../idioms/expression-evaluator-flow.md) | direct reference |
| [`exprevalstep-shape`](../idioms/exprevalstep-shape.md) | shares files: `src/backend/executor/execExpr.c`, `src/backend/executor/execExprInterp.c`, `src/include/executor/execExpr.h` |
| [`jit-expression-codegen`](../idioms/jit-expression-codegen.md) | direct reference |
| [`jit-provider-and-context`](../idioms/jit-provider-and-context.md) | shares files: `src/backend/jit/jit.c` |
| [`jit-tuple-deform-and-inline`](../idioms/jit-tuple-deform-and-inline.md) | direct reference |
| [`memory-context-slab-generation-bump`](../idioms/memory-context-slab-generation-bump.md) | shares files: `src/backend/executor/nodeAgg.c` |
| [`query-tree-walkers`](../idioms/query-tree-walkers.md) | shares files: `src/backend/nodes/nodeFuncs.c` |
| [`utility-stmt-planning`](../idioms/utility-stmt-planning.md) | shares files: `src/backend/executor/execExpr.c` |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **Enum / dispatch_table order drift** — `execExpr.h` enum order MUST
  match `dispatch_table[]` initializer order in `execExprInterp.c` line
  by line, because direct-threaded dispatch indexes by integer opcode
  and replaces it with the label pointer at the matching offset
  [from-comment](source/src/include/executor/execExpr.h:248-252),
  [verified-by-code](source/src/backend/executor/execExprInterp.c:450).
  Adding the enum entry without the dispatch row = wrong label on every
  threaded build, often crashes inside an unrelated step.
- **Missing JIT case** — `llvm_compile_expr()` is an exhaustive switch
  on `ExprEvalOp`. An unhandled opcode trips `elog(ERROR, "unknown op
  code: %d", …)` or silently emits malformed IR (LLVM verifier
  failure). Regress under default GUCs may never hit JIT compilation so
  the omission ships. Mitigation: run regress with `jit_above_cost = 0`
  before submit
  [verified-by-code](source/src/backend/jit/jit.c:37-42).
- **Union bloat > 40 bytes** — the `ExprEvalStep->d` union has a strict
  cacheline-driven budget. Adding a fat arm bloats every step,
  including the millions used in `EEOP_*_VAR` fast paths
  [from-comment](source/src/include/executor/execExpr.h:316-318).
  Mitigation: stash large state in a side struct, point to it from the
  union, allocate in `ExecInitExprRec()`.
- **Out-of-line helper calls into the dispatch loop** — helpers shared
  between the interpreter and the JIT MUST NOT perform their own step
  dispatch. They compute, return, and let the caller (`EEO_NEXT()` or
  the JIT-emitted `br` to the next step) advance
  [from-README](source/src/backend/executor/README:206-215). Violating
  this works for interpreter-only paths and breaks under JIT.
- **`adjust_jumps` not updated** — if the new step participates in
  short-circuiting (boolean AND/OR pattern), the emit-side must record
  jump targets and back-patch them after the subexpression's length is
  known
  [from-README](source/src/backend/executor/README:181-186). Forgetting
  this manifests as wrong-result for nested expressions, not a crash.
- **Caller in `nodeAgg.c` / `execGrouping.c` not wired** — the step
  compiles and the regress passes, but nothing ever emits the opcode.
  Mitigation: add an `Assert(found_new_step)` instrumentation locally,
  or grep `EEOP_FOO` to confirm at least one `scratch.opcode =`
  assignment exists in `execExpr.c`.

- **Walker coverage drift** — if the new step services a new `Expr`
  Node, missing cases in `nodeFuncs.c` (6 functions) or
  `parse_collate.c assign_collations_walker` produce confusing
  failures far from the edit site: `elog(ERROR, "unrecognized node
  type")` from a random query, or `SIGABRT` in parse-analysis for any
  TEXT-resulting expression that mentions the new Node. Origin:
  sesvars F3 retro.
- **Ruleutils.c pretty-printer omission** — `EXPLAIN VERBOSE`,
  `CREATE VIEW`, and `pg_get_*def()` all walk the parse tree through
  `ruleutils.c get_rule_expr` + `is_simple_node`. Missing a case for
  the new Expr Node makes those paths error with `unrecognized node
  type: N`. **Per-phase happy-path regress will not catch this** —
  the standard test scripts don't `EXPLAIN VERBOSE` arbitrary new
  expressions. This is the prototypical R14 case ("comprehensive
  own-test-suite required"): only a feature-specific test that
  explicitly runs `EXPLAIN (VERBOSE, COSTS OFF) SELECT <new-expr>`
  and `CREATE VIEW v AS SELECT <new-expr>` will catch the gap before
  ship. Origin: sesvars F14 retro.

- **Synchronization traps** (sibling files that must change together):
  - `execExpr.h` enum entry ↔ `execExprInterp.c` `dispatch_table[]` row
    (same relative position, every time).
  - `execExpr.h` enum entry ↔ `execExprInterp.c` `EEO_CASE(...)` body.
  - `execExprInterp.c` case ↔ `llvmjit_expr.c` `case`. JIT-on and
    JIT-off must produce identical observable behavior.
  - Out-of-line `ExecEvalFoo` helper ↔ `execExpr.h` `extern`
    declaration ↔ `llvmjit_types.c` (only if the helper's signature
    needs a new LLVM `FunctionType` mapping; most reuse existing ones).
  - **`nodeFuncs.c` walker cases (6 functions) ↔ `parse_collate.c
    assign_collations_walker` leaf case ↔ `ruleutils.c get_rule_expr`
    + `is_simple_node` cases.** All three sites must gain entries for
    any new `Expr` Node the step services. Not enforced by any
    script. Origin: sesvars F3 + F14.

## Verification (exact test invocations)

```bash
# Default build (JIT optional, depends on LLVM)
meson compile -C dev/build-debug

# Regress under default GUCs (jit_above_cost = 100000 — JIT effectively off)
meson test -C dev/build-debug --suite regress

# Regress with JIT *forced on* for every plan (this is the load-bearing
# run for this scenario — exercises the JIT mirror)
PGOPTIONS='-c jit_above_cost=0 -c jit_inline_above_cost=0 -c jit_optimize_above_cost=0 -c jit_expressions=on' \
  meson test -C dev/build-debug --suite regress

# Targeted expression / domain / aggregate tests if you wired into those
meson test -C dev/build-debug --suite regress --test expressions
meson test -C dev/build-debug --suite regress --test case
meson test -C dev/build-debug --suite regress --test domain
meson test -C dev/build-debug --suite regress --test aggregates

# Sanity-grep to confirm the four lockstep edits landed
git diff --stat | grep -E 'execExpr\.(h|c)|execExprInterp\.c|llvmjit_expr\.c'
# Expect all four files in the diff.
```

If the change adds a brand-new SQL test file (rather than extending an
existing group), wire it into `src/test/regress/parallel_schedule` and
name it explicitly here.

## Cross-refs

- Companion skills: `.claude/skills/executor-and-planner/SKILL.md`.
- Related scenarios: `scenarios/add-new-node-type.md` (the `Expr` Node
  that the new step services usually comes from here),
  `scenarios/add-new-plan-node.md` (if the step is emitted by a new
  plan node's expression).
- Idioms: `knowledge/idioms/expression-evaluator-flow.md` (the
  flat-step model and dispatch),
  `knowledge/idioms/jit-expression-codegen.md` (how the JIT mirrors
  each step),
  `knowledge/idioms/jit-tuple-deform-and-inline.md` (helper-sharing
  contract).
- Subsystems: `knowledge/subsystems/executor.md`,
  `knowledge/subsystems/jit.md`.
- Issues: `knowledge/issues/executor.md`,
  `knowledge/issues/include-executor.md`,
  `knowledge/issues/jit.md`.
- Reference patch (canonical_commit): `git -C source show 8dd7c7cd0a2`.
