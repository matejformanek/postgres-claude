# primnodes.h

- **Source:** `source/src/include/nodes/primnodes.h` (~2450 lines)
- **Last verified commit:** `d774576f6f05`
- **Depth:** skim (top comment + struct inventory)

## Purpose

"Primitive" nodes — types used in **more than one** of the
parse/plan/execute stages. Mostly executable expressions and join
trees. `:1-10` `[from-comment]`

## Major struct families

### Identifiers / references

- `Alias` `:49`, `RangeVar` `:73`, `TableFunc` `:111`,
  `IntoClause` `:160`

### Executable expressions (all inherit `Expr` `:189`)

Variables and constants:
- `Var` `:262` — column reference. `varno` (RTE index or special
  INNER_VAR/OUTER_VAR/INDEX_VAR), `varattno`, `vartype`, `vartypmod`,
  `varcollid`, `varlevelsup`, `varnullingrels`, `varnosyn`,
  `varattnosyn`, `varreturningtype`, `location`.
- `Const` `:327`
- `Param` `:391` — PARAM_EXTERN / PARAM_EXEC / PARAM_SUBLINK / PARAM_MULTIEXPR

Aggregates and windows:
- `Aggref` `:456`, `GroupingFunc` `:551`, `WindowFunc` `:586`,
  `WindowFuncRunCondition` `:621`, `MergeSupportFunc` `:653`

Function/operator calls:
- `SubscriptingRef` `:702`, `FuncExpr` `:766`, `NamedArgExpr` `:807`,
  `OpExpr` `:830`, `ScalarArrayOpExpr` `:907`, `BoolExpr` `:948`,
  `DistinctExpr`, `NullIfExpr` (typedefs of OpExpr)

Sub-selects:
- `SubLink` `:1022` — parsed form (EXISTS/ANY/ALL/expr/CTE/ROWCOMPARE)
- `SubPlan` `:1073` — planned form, with parameters and links to
  `subroot`
- `AlternativeSubPlan` `:1124`

Field/row manipulation:
- `FieldSelect` `:1141`, `FieldStore` `:1172`
- `RelabelType` `:1197`, `CoerceViaIO` `:1220`,
  `ArrayCoerceExpr` `:1246`, `ConvertRowtypeExpr` `:1274`,
  `CollateExpr` `:1292`

Case / row / array:
- `CaseExpr` `:1322`, `CaseWhen` `:1338`, `CaseTestExpr` `:1368`
- `ArrayExpr` `:1386`, `RowExpr` `:1428`, `RowCompareExpr` `:1471`
- `CoalesceExpr` `:1492`, `MinMaxExpr` `:1514`
- `SQLValueFunction` `:1561` (CURRENT_TIMESTAMP etc.)

XML and JSON:
- `XmlExpr` `:1604`, `JsonFormat` `:1656`, plus a large family of
  Json* expression nodes following.

Join tree / qual scaffolding:
- `FromExpr`, `JoinExpr`, `OnConflictExpr` (further down in the
  file).

## Why this is in primnodes.h, not parsenodes.h

These structs appear in `Query` (parse-tree), in `Path`/`Plan`
(planner), and in `ExprState`/`PlanState` (executor). Splitting them
into a separate header lets each of those layers depend only on
`primnodes.h` plus its own header — avoiding circular includes.

## Cross-references

- Sibling: `parsenodes.h` (parse-time-only nodes), `plannodes.h`
  (plan-time-only).
- Idiom: `knowledge/idioms/node-types-and-lists.md`.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/var-const-nodes.md](../../../../data-structures/var-const-nodes.md)
- [idioms/node-types.md](../../../../idioms/node-types.md)
- [idioms/portable-identifiers.md](../../../../idioms/portable-identifiers.md)
- [idioms/subplan-and-initplan.md](../../../../idioms/subplan-and-initplan.md)
