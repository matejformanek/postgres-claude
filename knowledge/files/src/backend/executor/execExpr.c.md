# execExpr.c

- **Source:** `source/src/backend/executor/execExpr.c` (5101 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (compilation entry points + key builders)

## Purpose

Expression **compilation**. Takes a planner-produced `Expr` tree and walks it
to produce a flat `ExprState->steps[]` array of `ExprEvalStep` "instructions"
that the interpreter (or JIT) will later execute. Implementation-agnostic: knows
nothing about whether the final code path is interp / JIT / switch / direct-thread.
[from-comment] `:3-15`

## Mental model

- One Expr tree → one `ExprState`. Each Expr node is rewritten into 0/1/many
  steps with explicit `resvalue/resnull` pointers; subexpression results are
  placed directly where the consumer step expects them (often into
  `FunctionCallInfo->args[i]`). [from-comment in README] `:81-160`
- A **scratch** `ExprEvalStep` lives on the stack in each ExecInitExprRec frame;
  it is filled in then `ExprEvalPushStep`-ed into the array (which may repalloc,
  hence no raw pointers into the array can be held during init). `:2704`
- Setup-prefix steps (`EEOP_*_FETCHSOME`) are emitted up front to deconstruct
  the relevant inner/outer/scan/old/new slot once. The `ExprSetupInfo` walker
  collects `last_inner/outer/scan/old/new` AttrNumbers; then
  `ExecPushExprSetupSteps` emits one FETCHSOME per used slot. `:56-69` and walker.
- Jumps for short-circuit operators are emitted with placeholder `jumpdone`
  indices, then patched after the subexpression has been pushed
  (`adjust_jumps`-style pattern referenced in README).

## Top-level entry points

- `ExecInitExpr(Expr*, PlanState *parent)` `:142` — most common; wraps the Expr
  tree with the parent PlanState so Vars can resolve and Params can pull from
  estate->es_param_list_info. Calls `ExecInitExprRec` then `ExecReadyExpr`.
- `ExecInitExprWithContext` `:162` — variant for cases needing an
  `ErrorSaveContext` (soft-error catching: `SQL/JSON`, `COPY ON_ERROR`). 
- `ExecInitExprWithParams(Expr*, ParamListInfo)` `:200` — context-less
  variant used by SPI/plpgsql when there is no parent PlanState; only EXTERN
  params are usable.
- `ExecInitQual(List *qual, PlanState*)` `:249` — compiles an implicit-AND
  list of quals into a single ExprState with `EEOP_QUAL` short-circuit semantics
  (treats NULL as false, jumps on first false). Result is a boolean Datum.
- `ExecInitCheck(List *qual, PlanState*)` `:335` — like ExecInitQual but
  preserves NULL (used for CHECK constraints).
- `ExecInitExprList(List, PlanState)` — compiles a list of Exprs into a list
  of ExprStates (one per element).
- `ExecPrepareExpr` / `ExecPrepareQual` / `ExecPrepareCheck` / `ExecPrepareExprList`
  `:785+` — for use with a bare `EState` (no parent PlanState); each switches
  to per-query context and runs `expression_planner` first to const-fold etc.

## Projection / aggregate / hash builders

- `ExecBuildProjectionInfo(targetList, ExprContext, ProjSlot, parent, inputDesc)`
  `:391` — compiles a TLIST into a `ProjectionInfo`. Fast-path uses
  `EEOP_ASSIGN_{INNER,OUTER,SCAN}_VAR` (one step per "trivial Var copy"),
  general path uses `ExecInitExprRec` to compute then `EEOP_ASSIGN_TMP` to
  copy into `resultslot->tts_values/isnull`. `:391-565`
- `ExecBuildUpdateProjection` `:568` — specialized projection for UPDATE
  ModifyTable. Combines unchanged columns of the old tuple with new-value
  expressions from the SET list; sets `EEOP_ASSIGN_TMP_MAKE_RO` so that
  unchanged-column references survive into the result slot without
  expanded-datum issues. Used both for the "new tuple" projection and (with
  flag) for MERGE WHEN MATCHED ... UPDATE.
- `ExecBuildAggTrans(AggState, AggStatePerPhase, doSort, doHash, nullcheck)`
  `:3704` — produces one ExprState that, when run, advances every transition
  function for the given Agg phase. Calls `ExecBuildAggTransCall` `:4046`
  per-transition. Holds the EEOP_AGG_PLAIN_TRANS / `*_BYVAL` /
  `*_STRICT_BYREF` opcodes plus filter/distinct handling steps.
- `ExecBuildHash32FromAttrs(desc, ops, hashfunctions, collations, numCols, keyColIdx, parent, init_value)`
  `:4168` — compiles "hash these N attributes of a slot to a uint32"; used by
  HashAgg / Memoize / Hash for grouping keys directly out of a stored tuple.
- `ExecBuildHash32Expr(desc, ops, hashfunctions, collations, hash_exprs, opstrict, parent, init_value, keep_nulls)`
  `:4329` — same but where keys are general Exprs (used by Hashjoin which hashes
  arbitrary expressions, not raw columns).
- `ExecBuildGroupingEqual(ldesc, rdesc, lops, rops, numCols, keyColIdx, eqfunctions, collations, parent)`
  `:4493` — compiles a column-by-column equality check between two slots; one
  ExprState containing EEOP_GROUPING steps that early-exit on first mismatch
  (returns boolean).
- `ExecBuildParamSetEqual` `:4653` — compiles Param-set equality used by
  `nodeMemoize` to compare a probe parameter vector against a cached entry.

## Notable details

- `ExecCreateExprSetupSteps` `:80,82` — runs the setup walker over the whole
  Expr tree before any other step is pushed, so FETCHSOME steps know the high
  watermark of attributes needed; this is what lets each Var step become a
  pure array fetch with no slot-deconstruct branch.
- `multiexpr_subplans` in `ExprSetupInfo` `:67` — MULTIEXPR SubPlans (the
  `UPDATE t SET (a,b)=(SELECT ...)` pattern) appear once but evaluate multiple
  output columns; the setup pass collects them so each is executed exactly once
  and its outputs distributed to all referencing PARAM_MULTIEXPR Params.
- `ExecInitSubscriptingRef` `:86` — handles container subscripting (array,
  jsonb, …) including assignment indirection (the "indirection chain" for
  `arr[3].foo := …` style). Delegates element-type details to the type's
  SubscriptRoutines (typsubscript).
- `ExecInitCoerceToDomain` `:91` — emits one CHECK-constraint step per active
  domain constraint, fetched once at compile time; this is the optimization
  the README emphasises: domain constraints are not re-fetched per row.
- `ExecInitJsonExpr` `:99` / `ExecInitJsonCoercion` `:102` — SQL/JSON path-expr
  evaluation; uses ErrorSaveContext to implement ON ERROR / ON EMPTY behaviour
  without throwing.

## Final step

`ExecReadyExpr(state)` `:71` is the post-compile finalizer: it appends the
terminating `EEOP_DONE_RETURN` or `EEOP_DONE_NO_RETURN`, then dispatches to
either `ExecReadyInterpretedExpr` (execExprInterp.c) or, if the JIT provider
decides so, swaps `state->evalfunc` for compiled native code.

## Tags

- [verified-by-code] entry points and line numbers; ExecBuild* signatures.
- [from-comment] expression compilation invariants in the file header.
- [from-README] the executor README "Expression Initialization" section is the
  authoritative narrative; code matches it.
- [inferred] performance rationale for the FETCHSOME-once design.
