# parse_expr.c

- **Source:** `source/src/backend/parser/parse_expr.c` (5074 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entry + dispatch; per-node bodies skim)

## Purpose

General expression transformation: take the syntactic expression tree the
grammar produced (`A_Expr`, `ColumnRef`, `A_Const`, `FuncCall`, etc.) and
produce a fully-resolved expression tree with all types determined, all
operators / functions / coercions resolved, all column refs turned into
`Var`s. The transformed tree uses the runtime nodes in `primnodes.h`
(`OpExpr`, `FuncExpr`, `Var`, `Const`, …). [from-comment] `:114-118`

## Public entry

`transformExpr(pstate, expr, exprKind)` (`:120` onward) is the workhorse,
called from everywhere — `parse_clause.c`, `parse_target.c`, `parse_cte.c`,
even DDL paths in `parse_utilcmd.c`. The `ParseExprKind` enum (in
`parse_node.h:38-87`) tags the surrounding context so that error messages
and feature gating can be context-specific (e.g. window functions allowed
in SELECT target but not in WHERE).

`transformExpr` calls `transformExprRecurse` `:49`, which dispatches by
node tag.

## Per-node transformers (static prototypes `:49-111`)

| Raw node | Transformer | Produces |
|---|---|---|
| `A_Expr` (op kinds) | `transformAExprOp/Any/All/Distinct/NullIf/In/Between` | `OpExpr`, `ScalarArrayOpExpr`, `DistinctExpr`, `NullIfExpr`, OR-tree of `=`, AND of `>=`/`<=` |
| `BoolExpr` | `transformBoolExpr` | `BoolExpr` with bool-typed args |
| `FuncCall` | `transformFuncCall` (delegates to `parse_func.c`) | `FuncExpr` / `Aggref` / `WindowFunc` |
| `CaseExpr` | `transformCaseExpr` | `CaseExpr` with unified result type |
| `SubLink` | `transformSubLink` | `SubLink` (subselect re-analyzed via `parse_sub_analyze`) |
| `A_ArrayExpr` | `transformArrayExpr` | `ArrayExpr` or `ArrayCoerceExpr` |
| `RowExpr` | `transformRowExpr` | `RowExpr` |
| `CoalesceExpr` / `MinMaxExpr` | dedicated transformers | same node post-typing |
| `SQLValueFunction` (`CURRENT_DATE`, …) | `transformSQLValueFunction` | tagged node |
| `XmlExpr` / `XmlSerialize` | dedicated | `XmlExpr` |
| `BooleanTest` | `transformBooleanTest` | `BooleanTest` |
| `CurrentOfExpr` | `transformCurrentOfExpr` | `CurrentOfExpr` (used by WHERE CURRENT OF cursor) |
| `ColumnRef` | `transformColumnRef` | `Var` (via `parse_relation.c`) or `Param` |
| `A_Indirection` | `transformIndirection` | field selection / subscripting |
| `TypeCast` | `transformTypeCast` | injects `CoerceToDomain`, `RelabelType`, `CoerceViaIO`, `FuncExpr` etc. (delegates to `parse_coerce.c`) |
| `CollateClause` | `transformCollateClause` | `CollateExpr` |
| `ParamRef` | `transformParamRef` (delegates to `pstate->p_paramref_hook`) | `Param` |
| `MergeSupportFunc` | `transformMergeSupportFunc` | tagged node |
| JSON family (`JsonObjectConstructor`, `JsonArrayAgg`, `JsonIsPredicate`, `JsonParseExpr`, `JsonScalarExpr`, `JsonSerializeExpr`, `JsonFuncExpr`) | `transformJson*` | `JsonConstructorExpr` / `JsonExpr` |
| `MultiAssignRef` | `transformMultiAssignRef` | helper for `(c1, c2) = (subquery)` |

## Row comparisons

`make_row_comparison_op` `:104` and `make_row_distinct_op` `:106` build the
nested AND-of-ops that implements `(a,b) = (c,d)` and `IS [NOT] DISTINCT
FROM` on rows.

## Cooperation with other parser files

- column references → `parse_relation.c` (`transformWholeRowRef`, the
  namespace lookups).
- coercions → `parse_coerce.c` (`coerce_to_target_type`, `coerce_type`).
- function/operator resolution → `parse_func.c` / `parse_oper.c`.
- aggregates / window funcs → routed through `parse_func.c` →
  `parse_agg.c` (which sets `Query.hasAggs` / `hasWindowFuncs`).
- sublinks → recursive `parse_sub_analyze` from `analyze.c`.

## Caveats

- `Transform_null_equals` GUC `:46` — when on, `expr = NULL` becomes
  `expr IS NULL`. Backward-compat knob; off by default.
- `transformAExprOp` handles the special `IS [NOT] DISTINCT FROM` rewrite
  in `make_nulltest_from_distinct` `:110` when one side is a literal NULL.
- Many JSON transformers (`transformJsonFuncExpr` family) are recent (PG 15+)
  and share `transformJsonPassingArgs` `:96` and `transformJsonBehavior`
  `:99` helpers.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
