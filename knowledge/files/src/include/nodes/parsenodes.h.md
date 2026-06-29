# parsenodes.h

- **Source:** `source/src/include/nodes/parsenodes.h` (4599 lines)
- **Last verified commit:** `f0a4f280b4d3` (2026-06-25; clean re-pin — struct cites hold within ±3, doc convention cites the struct's leading comment line)
- **Depth:** skim (top comment + struct inventory)

## Purpose

Definitions of every node that appears in a **parse tree** — the
output of the gram.y grammar, refined by `parser/analyze.c`. Two
shapes coexist:

1. **Raw** parse-tree nodes (prefix `A_`, `Range*`, plus statement
   nodes for utility commands): produced directly by the bison
   grammar.
2. **Analyzed** parse-tree nodes wrapped in a `Query` (the
   parser's final output).

`location` fields are byte offsets into the source SQL text; the
top-of-file comment explains they're needed for error-cursor
positioning. `:5-13` `[from-comment]`

## Major struct families

### Top-level

- `Query` `:117` — the analyzed parse tree of a DML/SELECT statement.
  Contains `commandType`, `querySource`, `queryId`, `canSetTag`,
  `utilityStmt`, `resultRelation`, `hasAggs`, `hasWindowFuncs`,
  `hasTargetSRFs`, `hasSubLinks`, `hasDistinctOn`, `hasRecursive`,
  `hasModifyingCTE`, `hasForUpdate`, `hasRowSecurity`, `isReturn`,
  `cteList`, `rtable`, `rteperminfos`, `jointree`, `mergeActionList`,
  `mergeTargetRelation`, `mergeJoinCondition`, `targetList`,
  `override`, `onConflict`, `returningList`, `groupClause`,
  `groupDistinct`, `groupingSets`, `havingQual`, `windowClause`,
  `distinctClause`, `sortClause`, `limitOffset`, `limitCount`,
  `limitOption`, `rowMarks`, `setOperations`, `constraintDeps`,
  `withCheckOptions`, `stmt_location`, `stmt_len`.

### Raw expressions / references (parser-only)

- `TypeName` `:285`, `ColumnRef` `:311`, `ParamRef` `:321`,
  `A_Expr` `:349`, `A_Const` `:385`, `TypeCast` `:398`,
  `CollateClause` `:409`, `RoleSpec` `:429`, `FuncCall` `:451`,
  `A_Star` `:474`, `A_Indices` `:485`, `A_Indirection` `:508`,
  `A_ArrayExpr` `:518`, `ResTarget` `:545`, `MultiAssignRef` `:563`,
  `SortBy` `:574`, `WindowDef` `:592`
- Range items: `RangeSubselect` `:646`, `RangeFunction` `:668`,
  `RangeTableFunc` `:686`, `RangeTableFuncCol` `:704`,
  `RangeGraphTable` `:719`, `RangeTableSample` `:739`
- `ColumnDef` `:767`, `TableLikeClause` `:795`, `IndexElem` `:824`,
  `DefElem` `:856`, `LockingClause` `:876`, `XmlSerialize` `:887`
- Partitioning: `PartitionElem` `:905`, `PartitionSpec` `:927`,
  `PartitionRangeDatum` `:974`, `SinglePartitionSpec` `:989`,
  `PartitionCmd` `:1001`
- Graph (SQL/PGQ): `GraphPattern` `:1026`, `GraphElementPattern` `:1046`

### Range table

- `RangeTblEntry` `:1137` — the workhorse. Holds `rtekind`
  (RELATION/SUBQUERY/JOIN/FUNCTION/TABLEFUNC/VALUES/CTE/
  NAMEDTUPLESTORE/RESULT/GROUP/GRAPH_TABLE), and per-kind specific
  fields. The single most-touched struct in the planner.
- `RTEPermissionInfo` `:1402` — per-relation permission tracking
  (split out of RangeTblEntry).
- `RangeTblFunction` `:1433` — function-scan info.
- Many subordinate structs follow: `TableSampleClause`,
  `WithCheckOption`, `SortGroupClause`, `GroupingSet`, `WindowClause`,
  `RowMarkClause`, `WithClause`, `InferClause`, `OnConflictClause`,
  `CTESearchClause`, `CTECycleClause`, `CommonTableExpr`,
  `TriggerTransition`, `MergeWhenClause`, `ReturningOption`,
  `ReturningClause`.

### Utility statements

All `*Stmt` nodes (after the analyzed-query block in the file):
`InsertStmt`, `UpdateStmt`, `DeleteStmt`, `MergeStmt`, `SelectStmt`,
`SetOperationStmt`, plus every DDL: `CreateStmt`, `AlterTableStmt`,
`DropStmt`, `CreateIndexStmt`, `CreateFunctionStmt`,
`CreateRoleStmt`, `GrantStmt`, `VacuumStmt`, `ExplainStmt`,
`CreateExtensionStmt`, `CreateTrigStmt`, … and many more (full list
runs ~150 statement types).

## When to come back here

- Adding a SQL syntactic construct: extend the relevant raw/analyzed
  structs here, plus the grammar (`gram.y`) and parse-analysis
  (`parser/analyze.c`, `parser/parse_*.c`).
- Reading planner code: many planner functions take pieces of these
  structs (`fromlist`, `quals`, `rtable`, `targetList`) — this header
  defines them.

## Cross-references

- Sibling: `primnodes.h` (cross-stage executable expressions).
- Downstream: `pathnodes.h` (planner views these), `plannodes.h`
  (plan-time outputs that contain some parse-tree fragments).
- Idiom: `knowledge/idioms/node-types-and-lists.md`.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/parser-pipeline.md](../../../../idioms/parser-pipeline.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
- [idioms/node-types.md](../../../../idioms/node-types.md)
- [idioms/security-barrier-views.md](../../../../idioms/security-barrier-views.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new SQL keyword](../../../../scenarios/add-new-sql-keyword.md)
- [Scenario — Add a new utility statement](../../../../scenarios/add-new-utility-statement.md)

<!-- scenarios:auto:end -->

