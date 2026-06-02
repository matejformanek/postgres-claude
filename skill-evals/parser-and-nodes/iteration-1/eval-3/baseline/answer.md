# Walking and rewriting a Query parsetree — baseline

## What to use

Since you're *rewriting*, you want a mutator. PostgreSQL provides:

- `expression_tree_walker(node, walker_fn, ctx)` — walks, callback returns bool (true to stop).
- `expression_tree_mutator(node, mutator_fn, ctx)` — rewrites, callback returns `Node *`.
- `query_tree_walker` / `query_tree_mutator` — wrappers for Query trees that handle the rangetable, CTEs, subqueries, etc.

These live in `src/backend/nodes/nodeFuncs.c`.

## Skeleton

```c
static Node *
my_mutator(Node *node, MyCtx *ctx)
{
    if (node == NULL)
        return NULL;
    if (IsA(node, Var))
    {
        /* rewrite logic */
        ...
    }
    if (IsA(node, Query))
        return (Node *) query_tree_mutator((Query *) node, my_mutator, ctx, 0);
    return expression_tree_mutator(node, my_mutator, ctx);
}
```

## Contract

- Walker callback returns `bool` — `true` to stop the walk early.
- Mutator callback returns a Node — usually you call `expression_tree_mutator(node, ...)` at the bottom to handle the default recursion.
- Both must handle NULL.

## Post-analysis vs raw

- After parse-analysis, column references are `Var` nodes (with `varno`, `varattno` referencing a rangetable entry). Use `expression_tree_walker`/`_mutator`.
- Before parse-analysis (raw parse tree from `raw_parser`), column references are `ColumnRef` nodes wrapping a string. Use `raw_expression_tree_walker` for these. (I don't recall if there's a `raw_expression_tree_mutator` — possibly not, in which case you'd walk + edit in place.)

For "rewrite all ColumnRefs to point at a different attribute" — `ColumnRef` only exists pre-analysis, so you'd be in `raw_expression_tree_walker` territory. If you actually mean `Var` (post-analysis), use `expression_tree_mutator`.

## Maintenance when adding a new expression node

You'd need to add a case to every switch in nodeFuncs.c that switches on `nodeTag` for expressions — including:

- `exprType` (what type does this expression return)
- `exprTypmod`
- `exprCollation`
- `exprLocation`
- The walker and mutator (so recursion descends into the new node's children)
- The raw walker if the node appears in raw trees

If you forget one, walkers silently skip your node and downstream code (planner, rewriter) may misbehave. The general advice: grep for an existing similar node type (e.g. `T_OpExpr`) and add a parallel case wherever it appears.

I don't have exact line numbers in nodeFuncs.c memorized.
