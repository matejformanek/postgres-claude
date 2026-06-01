# primnodes.h

- **Source:** `source/src/include/nodes/primnodes.h` (~2700 lines)
- **Last verified commit:** `ef6a95c7c64`
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
- `Const` `:324`
- `Param` `:391` — PARAM_EXTERN / PARAM_EXEC / PARAM_SUBLINK / PARAM_MULTIEXPR

Aggregates and windows:
- `Aggref` `:459`, `GroupingFunc` `:557`, `WindowFunc` `:594`,
  `WindowFuncRunCondition` `:629`, `MergeSupportFunc` `:661`

Function/operator calls:
- `SubscriptingRef` `:712`, `FuncExpr` `:779`, `NamedArgExpr` `:820`,
  `OpExpr` `:846`, `ScalarArrayOpExpr` `:926`, `BoolExpr` `:967`,
  `DistinctExpr`, `NullIfExpr` (typedefs of OpExpr)

Sub-selects:
- `SubLink` `:1041` — parsed form (EXISTS/ANY/ALL/expr/CTE/ROWCOMPARE)
- `SubPlan` `:1092` — planned form, with parameters and links to
  `subroot`
- `AlternativeSubPlan` `:1143`

Field/row manipulation:
- `FieldSelect` `:1160`, `FieldStore` `:1191`
- `RelabelType` `:1216`, `CoerceViaIO` `:1239`,
  `ArrayCoerceExpr` `:1265`, `ConvertRowtypeExpr` `:1293`,
  `CollateExpr` `:1311`

Case / row / array:
- `CaseExpr` `:1341`, `CaseWhen` `:1357`, `CaseTestExpr` `:1387`
- `ArrayExpr` `:1405`, `RowExpr` `:1447`, `RowCompareExpr` `:1490`
- `CoalesceExpr` `:1511`, `MinMaxExpr` `:1533`
- `SQLValueFunction` `:1580` (CURRENT_TIMESTAMP etc.)

XML and JSON:
- `XmlExpr` `:1623`, `JsonFormat` `:1675`, plus a large family of
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
