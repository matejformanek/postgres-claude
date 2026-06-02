# Rewriting Var attnums in a Query parsetree

## Tool

Use `expression_tree_mutator` from `src/backend/nodes/nodeFuncs.c`. The mutator returns `Node *` so you can substitute new subtrees, which is what you want for a rewrite.

```c
static Node *
remap_var(Node *node, RemapCtx *ctx)
{
    if (node == NULL)
        return NULL;
    if (IsA(node, Var))
    {
        Var *v = (Var *) node;
        if (v->varno == ctx->rti && v->varattno == ctx->old_att)
        {
            Var *copy = copyObject(v);
            copy->varattno = ctx->new_att;
            return (Node *) copy;
        }
    }
    return expression_tree_mutator(node, remap_var, ctx);
}
```

Drive it over a whole Query with `query_tree_mutator(query, remap_var, &ctx, 0)`.

## Contract

- Walker returns `bool`. `true` typically means "stop walking".
- Mutator returns `Node *`. The callback returns the replacement, or recurses via `expression_tree_mutator(node, cb, ctx)` to copy-and-recurse children.
- Handle `node == NULL` at the top of your callback.

## Raw vs analyzed

- `raw_expression_tree_walker` walks the pre-analysis tree (`ColumnRef`, `A_Expr`, `FuncCall`, …).
- `expression_tree_walker` / `_mutator` walk the post-analysis tree (`Var`, `OpExpr`, `Aggref`, …).
- `ColumnRef` only exists pre-analysis; after `transform_expr` it becomes a `Var`.

Since the question says "post-parse-analysis", you're rewriting `Var`s — `expression_tree_mutator` is the right tool.

## Maintenance when adding a new expression node

If you add a new expression node, you need cases in `nodeFuncs.c` for `expression_tree_walker`, `expression_tree_mutator`, possibly `raw_expression_tree_walker` if the node appears in raw parsetrees, and the type/typmod/collation/location helpers (`exprType`, `exprTypmod`, `exprCollation`, `exprLocation`). Grep for an existing sibling node tag to find every site.
