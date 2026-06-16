# `src/backend/utils/adt/arraysubs.c`

- **File:** `source/src/backend/utils/adt/arraysubs.c` (612 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **`SubscriptRoutines`** implementation for standard varlena arrays
and "raw" fixed-length arrays — i.e. the back end of the `arr[i]` and
`arr[i:j]` syntax. Pluggable subscripting was added in PG14 (commit
`c7aba7c14ef`); this file is the canonical implementation.

Two main responsibilities:
1. Parse-time `transform` (`array_subscript_transform`, `:57-166`) —
   coerce subscript exprs to int4, separate upper/lower lists, enforce
   `MAXDIM`, set the result type.
2. Exec-time `check_subscripts`/`fetch`/`assign`/`fetch_old` steps —
   driven by `ExecEvalSubscriptingRef` in `execExpr.c`.

## Key functions

- `ArraySubWorkspace` (`:31-47`) — per-expression scratch struct stored
  in `SubscriptingRefState.workspace`. `upperindex[MAXDIM]` /
  `lowerindex[MAXDIM]` arrays are always full-size because
  `array_get/set_slice` may scribble extras (`:40-46` [from-comment]).
- `array_subscript_transform(sbsref, indirection, pstate, isSlice,
  isAssignment)` (`:57-166`) — runs each `A_Indices` through
  `transformExpr` then `coerce_to_target_type` to INT4OID. Missing
  lower bound becomes Const(1) in non-slice context (`:99-107`) or NULL
  in slice context. Enforces `MAXDIM` (`:149-153`). Result type =
  array type if slice, element type otherwise (`:162-166`).
  [verified-by-code]
- `array_subscript_check_subscripts(state, op, econtext)` (`:182-228`)
  — exec-time NULL handling. NULL subscript → either ereport
  `ERRCODE_NULL_VALUE_NOT_ALLOWED` (assignment, `:197-200`) or set
  result NULL and skip the fetch step (`:200-203`). Converts Datums
  to plain int32 in workspace. [verified-by-code]
- `array_subscript_fetch` (`:238-256`) / `array_subscript_fetch_slice`
  (`:266-287`) — thin wrappers over `array_get_element` /
  `array_get_slice` in `arrayfuncs.c`. Fetch is `fetch_strict=true,
  fetch_leakproof=true` (`:547-548`). [verified-by-code]
- `array_subscript_assign` (`:296-337`) /
  `array_subscript_assign_slice` (`:346-390`) — handles fixed-length
  arrays specially (NULL source OR NULL replacement → return original,
  `:309-313`), and substitutes an empty constructed array for NULL
  varlena sources (`:321-325`). Calls into
  `array_set_element`/`array_set_slice`. `store_leakproof=false`
  (`:548`). [verified-by-code]
- `array_subscript_fetch_old`/`_slice` (`:401-469`) — fetches the
  pre-existing element value for read-modify-write expressions
  (nested SubscriptingRef or FieldStore). The `_slice` variant is
  dead code today per `:431-438` [from-comment] but kept for future
  syntactic generalizations.
- `array_exec_setup(sbsref, sbsrefstate, methods)` (`:475-530`) —
  builds the workspace, looks up element type pass-by-val/length/align
  via `get_typlenbyvalalign`. Re-enforces `MAXDIM` at runtime against
  potentially-different-vintage stored expressions (`:482-491`
  [from-comment]). [verified-by-code]
- `array_subscript_handler(PG_FUNCTION_ARGS)` (`:541-552`) — the
  `pg_proc.prosrc` referenced from `pg_type.typsubscript` for the
  standard varlena array types. Returns a pointer to the static
  `SubscriptRoutines`. `raw_array_subscript_handler` (`:568-579`) is
  the same routines, but distinct so `pg_type.typsubscript` semantics
  are explicit. [verified-by-code]
- `array_subscript_handler_support(PG_FUNCTION_ARGS)` (`:587-612`) —
  planner support function. Handles `SupportRequestModifyInPlace`:
  optimizes `param[i] := val` when refexpr is the same PARAM_EXTERN
  being assigned to. [verified-by-code]

## Phase D notes

- **Negative indices** are not specially handled here — `int4` subscript
  range is bounded only at the parser by `coerce_to_target_type` to
  INT4OID. The actual bound check happens downstream in
  `array_get_element`/`array_set_element` against `ARR_LBOUND`+`ARR_DIMS`.
- **MAXDIM enforcement** is twofold: at parse (`:149-153`) and at exec
  (`:487-491`). The exec-time check is explicitly defensive against
  pg_node stored by a backend with a larger `MAXDIM` setting
  (`:482-486` [from-comment]). [verified-by-code]
- **Subscript NULL semantics**: fetch returns NULL (leakproof), assign
  ereports — comment at `:547-548` `fetch_leakproof = true` lets the
  planner push fetch through security barriers. [verified-by-code]

## Potential issues

- [ISSUE-trust-boundary: stored expression's `numupper`/`numlower`
  is re-checked against `MAXDIM` at exec setup, but the workspace
  arrays are sized `MAXDIM` so a future increase of `MAXDIM` without
  rebuilding stored plans could undersize the workspace — currently
  protected by exec-time ereport (info)]
- [ISSUE-dead-code: `array_subscript_fetch_old_slice` is unreachable
  today per `:431-438` comment, but kept for future extensibility
  (info)]

## Cross-references

- `source/src/include/nodes/subscripting.h` — `SubscriptRoutines`,
  `SubscriptExecSteps`, `SubscriptingRefState`.
- `source/src/backend/executor/execExpr.c` — `ExecInitSubscriptingRef`
  drives this.
- `source/src/backend/utils/adt/arrayfuncs.c` — `array_get_element`,
  `array_get_slice`, `array_set_element`, `array_set_slice`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[verified-by-code]` × 8
- `[from-comment]` × 4
