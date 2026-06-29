# nodeFuncs.h

- **Source:** `source/src/include/nodes/nodeFuncs.h` (224 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Prototypes + inline predicates for the introspection / walker /
mutator engine in `nodeFuncs.c`.

## query_tree_walker flag bits `:21-34`

```
QTW_IGNORE_RT_SUBQUERIES    0x01
QTW_IGNORE_CTE_SUBQUERIES   0x02
QTW_IGNORE_RC_SUBQUERIES    0x03  (= both of above)
QTW_IGNORE_JOINALIASES      0x04
QTW_IGNORE_RANGE_TABLE      0x08
QTW_EXAMINE_RTES_BEFORE     0x10
QTW_EXAMINE_RTES_AFTER      0x20
QTW_DONT_COPY_QUERY         0x40
QTW_EXAMINE_SORTGROUP       0x80
QTW_IGNORE_GROUPEXPRS       0x100
```

Used by callers to control descent into substructures.

## Callback typedefs `:36-46`

```c
typedef bool (*check_function_callback)  (Oid, void *);
typedef bool (*tree_walker_callback)     (Node *, void *);
typedef bool (*planstate_tree_walker_callback) (PlanState *, void *);
typedef Node *(*tree_mutator_callback)   (Node *, void *);
```

## Macro wrappers `:154-183`

To allow callers to declare callbacks like `bool walker(Node *,
MyCtx *)` instead of `bool walker(Node *, void *)`, every public
walker/mutator is a macro that casts to the canonical signature
before calling `_impl`. This deliberately violates strict C aliasing
but is documented as intentional `:145-153` `[from-comment]`.

Public wrappers: `expression_tree_walker`, `expression_tree_mutator`,
`query_tree_walker`, `query_tree_mutator`, `range_table_walker`,
`range_table_mutator`, `range_table_entry_walker`,
`query_or_expression_tree_walker`, `query_or_expression_tree_mutator`,
`raw_expression_tree_walker`, `planstate_tree_walker`.

## Introspection

- `exprType`, `exprTypmod`, `exprIsLengthCoercion`,
  `applyRelabelType`, `relabel_to_typmod`, `strip_implicit_coercions`,
  `expression_returns_set`
- `exprCollation`, `exprInputCollation`, `exprSetCollation`,
  `exprSetInputCollation`
- `exprLocation`
- `fix_opfuncids`, `set_opfuncid`, `set_sa_opfuncid` — resolve
  operator → support-function OIDs before exec
- `check_functions_in_node` — run a predicate over every called
  function in an expr tree

## Inline predicates `:70-139`

- `is_funcclause(c)` — `IsA(c, FuncExpr)`
- `is_opclause(c)` — `IsA(c, OpExpr)`
- `get_leftop(c)` / `get_rightop(c)` — extract OpExpr args
- `is_andclause(c)` / `is_orclause(c)` / `is_notclause(c)`
- `get_notclausearg(c)` — extract the single child of a NOT clause

## Cross-references

- Implementation: `source/src/backend/nodes/nodeFuncs.c`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/query-tree-walkers.md](../../../../idioms/query-tree-walkers.md)
