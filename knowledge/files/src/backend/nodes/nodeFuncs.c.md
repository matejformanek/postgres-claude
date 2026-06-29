# nodeFuncs.c

- **Source:** `source/src/backend/nodes/nodeFuncs.c` (~4900 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read (top-level dispatchers + walker/mutator infrastructure)

## Purpose

Hand-written tree introspection and traversal utilities — the things
that have to know about every expression node type but don't fit the
auto-generated copy/equal/out/read scheme. The file has four major
sections:

1. **Type/typmod/collation introspection** of arbitrary expression
   trees (`exprType`, `exprTypmod`, `exprCollation`,
   `exprInputCollation`, `exprSetCollation`).
2. **Location tracking** (`exprLocation`, `leftmostLoc`).
3. **OpExpr funcid resolution** (`set_opfuncid`, `set_sa_opfuncid`,
   `fix_opfuncids`).
4. **Tree walkers and mutators** — the polymorphic recursion
   engines.

## Public entry points (line numbers)

| Line | Function | Returns |
|---|---|---|
| 42 | `exprType(const Node *)` | `Oid` |
| 304 | `exprTypmod(const Node *)` | `int32` |
| 561 | `exprIsLengthCoercion` | `bool` |
| 640 | `applyRelabelType` | `Node *` |
| 693 | `relabel_to_typmod` | `Node *` |
| 826 | `exprCollation(const Node *)` | `Oid` |
| 1403 | `exprLocation(const Node *)` | `int` |
| (later) | `expression_returns_set` | `bool` |
| (later) | `expression_tree_walker_impl` | `bool` |
| (later) | `expression_tree_mutator_impl` | `Node *` |
| (later) | `query_tree_walker_impl` / `mutator_impl` | |
| (later) | `range_table_walker_impl` / `mutator_impl` | |
| (later) | `raw_expression_tree_walker_impl` | `bool` |
| (later) | `planstate_tree_walker_impl` | `bool` |

## Dispatch idiom

Each function is a giant `switch (nodeTag(expr))` over expression
node types. For example, `exprType` `:49-300` maps each `T_*`
expression tag to the field that holds its result type
(`Var.vartype`, `Const.consttype`, `FuncExpr.funcresulttype`, etc.).
`[verified-by-code]`

When a new expression node is added, **every one of these switches
must be taught about it** — otherwise its result type / collation /
walker recursion silently misbehaves. The README lists this under
"step 3: add cases to the functions in nodeFuncs.c".
`[from-README:95-98]`

## Walkers and mutators

The public API is **macro-wrapped** to silence callback-type
warnings:

```c
#define expression_tree_walker(n, w, c) \
    expression_tree_walker_impl(n, (tree_walker_callback) (w), c)
```

`nodeFuncs.h:155-183` `[verified-by-code]`. This lets the callback be
declared as `bool walker(Node *node, MyContext *ctx)` rather than
`void *` — pretty much every walker in the planner does this.

### Walker contract

- Callback returns `true` to short-circuit (stop the whole walk),
  `false` to keep going.
- Implementation handles list-of-Node recursion, NULL, and the
  common Expr subtypes itself; the callback need only switch on
  `nodeTag` for the types it cares about, falling through to
  `return expression_tree_walker(node, walker, context);` for
  recursion.

### Mutator contract

- Callback returns a (possibly new) Node tree. NULL is an allowed
  return (means "delete this subtree").
- Helpers like `expression_tree_mutator(node, ...)` know how to
  rebuild common container nodes (list elements get individually
  mutated, container is rebuilt).

### query_tree_walker flags (`nodeFuncs.h:21-34`)

Control whether subqueries in `rtable` / `cteList`, JOIN aliases, the
range table itself, etc. are descended into. Used heavily in the
optimizer to avoid double-walking subqueries.

### raw_expression_tree_walker

Walks **pre-analysis** parse-tree nodes (A_Expr, ColumnRef, etc.).
The post-analysis walker doesn't know about those raw shapes.

### planstate_tree_walker

Walks `PlanState` trees (executor-time). Has its own helpers for
SubPlan, ModifyTable's per-resultrel substates, MergeAppend's array
of subplans, etc. Static helpers `planstate_walk_subplans` /
`planstate_walk_members` `:29-34` `[verified-by-code]`.

## Why this file is huge

Every expression-node type produces a case-clause in `exprType`,
`exprTypmod`, `exprCollation`, `exprLocation`, the walker, and the
mutator — five maintenance points per node. The file is essentially
five parallel switch-statements stacked end to end.

## Cross-references

- Header: `source/src/include/nodes/nodeFuncs.h`
- Most callers: every file under `src/backend/optimizer/` and
  `src/backend/rewrite/`; `src/backend/parser/parse_*.c`.
- `set_opfuncid` is called from planner before plan finalization so
  the executor doesn't have to resolve operator → function lookup at
  exec time.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/query-tree-walkers.md](../../../../idioms/query-tree-walkers.md)

