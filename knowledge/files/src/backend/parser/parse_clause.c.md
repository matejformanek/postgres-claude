# parse_clause.c

- **Source:** `source/src/backend/parser/parse_clause.c` (4039 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entry points + static prototypes; per-clause bodies skim)

## Purpose

Handle the major SQL clauses inside a SELECT/UPDATE/DELETE: FROM (incl.
JOINs, sub-selects, function/values RTEs, TABLESAMPLE), WHERE, GROUP BY
(incl. ROLLUP/CUBE/GROUPING SETS), HAVING, ORDER BY, DISTINCT/DISTINCT ON,
WINDOW, LIMIT/OFFSET, FOR UPDATE/SHARE, and ON CONFLICT inference. Called
from `analyze.c` per-statement transformers.

## Public entry points (called from analyze.c)

The exported surface is the set of `transform*Clause` and helpers consumed
by `analyze.c`'s per-statement transformers. The static prototypes at
`:53-102` list the internal helpers.

| Symbol | Role |
|---|---|
| `transformFromClause` `:115` | walk FROM list, build RTEs, populate `pstate->p_rtable`, `p_joinlist`, `p_namespace` |
| `transformWhereClause` | type-check WHERE / ON / HAVING quals to boolean |
| `transformLimitClause` | type-check LIMIT/OFFSET, support `LIMIT ALL` |
| `transformGroupClause` | build `Query.groupClause`; handles GROUPING SETS via SQL92/SQL99 paths |
| `transformSortClause` / `transformDistinctClause` / `transformDistinctOnClause` | ORDER BY + DISTINCT(ON) sort-group setup |
| `transformWindowDefinitions` | build `Query.windowClause` |
| `transformOnConflictArbiter` | INSERT ON CONFLICT inference (unique index resolution) |

`transformFromClause` is the natural reading entry — it dispatches each FROM
item via `transformFromClauseItem` `:76-78` which itself fans out by node
kind:

- `RangeVar` → `transformTableEntry` `:63` → `addRangeTableEntry`
- `RangeSubselect` → `transformRangeSubselect` `:64` (recurses via
  `parse_sub_analyze`)
- `RangeFunction` → `transformRangeFunction` `:66`
- `RangeTableFunc` (XMLTABLE / JSON_TABLE shell) → `transformRangeTableFunc` `:68`
- `RangeGraphTable` → `transformRangeGraphTable` `:70`
- `RangeTableSample` → `transformRangeTableSample` `:72`
- `JoinExpr` → recursive walk; USING via `transformJoinUsingClause` `:59`,
  ON via `transformJoinOnClause` `:61`

## Joins and namespaces

The hardest concept in this file is the **namespace**: a list of
`ParseNamespaceItem` recording, for each visible RTE at this query level,
whether it's currently visible by alias, by columns, and whether LATERAL
status is on. Several helpers tune these flags:

- `setNamespaceColumnVisibility` `:84`
- `setNamespaceLateralState` `:85`
- `markRelsAsNulledBy` `:83` — record nullability under outer joins for the
  planner's null-propagation accounting

USING joins are merged in `buildMergedJoinVar` `:81`, producing the synthetic
merged column.

## ORDER BY / GROUP BY resolution

Two coexisting modes:

- `findTargetlistEntrySQL92` `:89` — match by output-column name / by integer
  position (`ORDER BY 1`).
- `findTargetlistEntrySQL99` `:91` — by expression equality against an
  already-in-target-list expression.

`addTargetToGroupList` `:97` inserts new sort-group refs as needed.

## Window frame bounds

`transformFrameOffset` `:100-102` handles RANGE/ROWS/GROUPS offsets,
including the `in_range` support function lookup the planner needs for
`RANGE BETWEEN N PRECEDING ...`.

## Locking clauses

`transformLockingClause` is in `analyze.c` (because it touches the whole
Query), but the per-RTE machinery for mark-as-locked lives here as a
helper. FOR UPDATE/SHARE locking propagates into subqueries
("pushed down"), explaining the `pushedDown` parameter.

## Dependencies into other parser files

Nearly every other `parse_*.c`: `parse_coerce` (clause-result coercion to
bool / to common type), `parse_collate` (re-run after building expressions),
`parse_expr` (for WHERE/ON), `parse_relation` (RTE construction),
`parse_target` (for ORDER BY items added to tlist), `parse_oper`
(equality opers for DISTINCT), and `rewrite/rewriteManip` (for vars
adjustments when expanding USING joins).

## Caveats / things easy to get wrong

- `transformFromClause` *appends to* whatever's already in `p_rtable` /
  `p_joinlist` / `p_namespace`. The comment at `:108-114` warns that this
  matters for rule processing and UPDATE/DELETE where the target rel was
  added before the FROM/USING.
- LATERAL visibility flips multiple times as we walk join trees; only
  `setNamespaceLateralState` should mutate it.
- `checkExprIsVarFree` `:87` enforces that LIMIT/OFFSET can't reference any
  Var — a frequent newbie patch failure point.
