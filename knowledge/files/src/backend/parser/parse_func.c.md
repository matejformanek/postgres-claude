# parse_func.c

- **Source:** `source/src/backend/parser/parse_func.c` (2816 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top-level entry points + dispatch logic)

## Purpose

Function-call resolution. Given a `FuncCall` raw node, decide whether it's:

- a function (regular / set-returning / aggregate / window),
- a `table.column` indirection that the grammar accidentally parsed as a
  function call (`foo(bar)` could be either),
- a column being accessed as a function (`row(c).field` written as
  `field(row)`), or
- a coercion (`int4(x)`).

It produces the appropriate `FuncExpr`, `Aggref`, `WindowFunc`, `Var`, or
coercion node.

## Entry points

- `ParseFuncOrColumn(pstate, funcname, fargs, last_srf, fn, proc_call, location)`
  — the main entry, called from `parse_expr.c:transformFuncCall`. Walks
  the candidate-resolution path.
- `func_get_detail` — the heart: look up matching `pg_proc` rows by name +
  argtypes, then pick the best match via `func_select_candidate` (handles
  type promotion / overload resolution rules from the SQL spec).
- `make_fn_arguments` — apply coercions from argument types to declared
  parameter types.

## Aggregates and window functions

When the resolved proc is an aggregate (`pg_proc.prokind == 'a'`),
`ParseFuncOrColumn` builds an `Aggref` and routes through
`transformAggregateCall` (in `parse_agg.c`), which performs the
aggregate-specific checks (FILTER, ORDER BY inside, DISTINCT, ordered-set
arguments) and flips `Query.hasAggs`.

A function call with an `OVER (...)` clause becomes a `WindowFunc`; that's
routed through `transformWindowFuncCall` in `parse_agg.c` and flips
`Query.hasWindowFuncs`.

## The "is it a function or a column?" dance

The grammar can't tell `t.c` from `c(t)`. `ParseFuncOrColumn` resolves the
ambiguity by:

1. Trying the function path first (catalog lookup by name).
2. If no candidate matches and the single arg is a composite, fall back to
   field selection (`ParseComplexProjection`).
3. If still nothing, emit the "function does not exist" error with a hint.

## Procedure call (CALL)

`proc_call=true` switches the path: only `prokind='p'` is acceptable, and
the result is wrapped in a `CallStmt` by `transformCallStmt` in
`analyze.c`.

## Related

- `parse_oper.c` — analogous logic for operators (which are also functions
  under the hood).
- `parse_coerce.c` — argument-type coercion machinery used by
  `make_fn_arguments`.
- `parse_agg.c` — aggregate/window-specific validation.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
