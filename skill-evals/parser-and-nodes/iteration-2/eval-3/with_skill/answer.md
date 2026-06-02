# Rewriting Var attnums in a Query parsetree

## Tool: `expression_tree_mutator`

You're rewriting, not just inspecting, so you want the **mutator**, not the walker — mutators return `Node *` and let you substitute new subtrees.

```c
static Node *
remap_var_walker(Node *node, RemapCtx *ctx)
{
    if (node == NULL)
        return NULL;
    if (IsA(node, Var))
    {
        Var *v = (Var *) node;
        if (v->varno == ctx->target_rti && v->varattno == ctx->old_attno)
        {
            Var *copy = copyObject(v);
            copy->varattno = ctx->new_attno;
            return (Node *) copy;
        }
    }
    return expression_tree_mutator(node, remap_var_walker, ctx);
}
```

Drive it over the whole `Query` with `query_tree_mutator(query, remap_var_walker, &ctx, 0)` — that wrapper recurses through `targetList`, `jointree->quals`, `havingQual`, the rtable's subquery RTEs, the CTE list, etc.

## Contracts

- **Mutator** (`expression_tree_mutator_impl` in `nodeFuncs.c:3018+`): callback receives a `Node *`, returns a `Node *`. **Return `NULL` to delete a subtree.** Return a fresh node to substitute, or recurse via `expression_tree_mutator(node, cb, ctx)` to copy-and-recurse children. The mutator allocates a copy of every node it descends into (it never mutates the input in place).
- **Walker** (`expression_tree_walker_impl` in `nodeFuncs.c:2111+`): callback returns `bool`. `true` short-circuits the entire traversal (the walker treats it as "found what I wanted, stop"); `false` keeps walking siblings.
- The macros at `nodeFuncs.h:155-183` (`expression_tree_walker` → `expression_tree_walker_impl` with a `(tree_walker_callback)` cast) suppress the otherwise-noisy `-Wincompatible-pointer-types` warnings so your callback can be typed `(Node *, RemapCtx *)` instead of `(Node *, void *)`.

## `expression_tree_mutator` vs `raw_expression_tree_walker`

These operate on different shapes:

| Stage | Walker | Typical nodes |
| --- | --- | --- |
| **Raw parse tree** (before parse analysis) | `raw_expression_tree_walker` (`nodeFuncs.c:4115+`) | `A_Expr`, `ColumnRef`, `A_Const`, `FuncCall`, `SelectStmt` |
| **Post-analysis Query / plan tree** | `expression_tree_walker` / `_mutator` | `Var`, `OpExpr`, `Const`, `FuncExpr`, `Aggref` |

`ColumnRef` only exists pre-analysis; after `transformExpr`/`transformColumnRef`, it has been resolved to a `Var` (or `Param`, `FieldSelect`, etc.) with a definite `varno`/`varattno`. Since your task says "post-parse-analysis" and "attribute number", you're rewriting `Var`s, so it's `expression_tree_mutator`. If you ever need to rewrite `ColumnRef`s (e.g. in a pre-analysis hook), use `raw_expression_tree_walker` — but note there is no `raw_expression_tree_mutator`: the raw shape is rewrite-via-walker-with-side-effects-on-context, not in-place transform.

There's also `planstate_tree_walker` (`nodeFuncs.h:181`) — the executor-time analogue, walking a `PlanState` tree at run time (used by EXPLAIN ANALYZE accumulation, parallel-worker stats, etc.).

## `QTW_*` flags

When using `query_tree_walker` / `_mutator`, the fourth argument is a bitmask from `nodeFuncs.h:22-34`:

- `QTW_IGNORE_RT_SUBQUERIES` — don't descend into subquery RTEs.
- `QTW_IGNORE_CTE_SUBQUERIES` — skip CTE definitions.
- `QTW_IGNORE_RC_SUBQUERIES` — both of the above.
- `QTW_IGNORE_JOINALIASES` — skip JOIN alias var lists.
- `QTW_IGNORE_RANGE_TABLE` — skip the rtable entirely.
- `QTW_EXAMINE_RTES_BEFORE` / `_AFTER` — examine RTE nodes themselves.
- `QTW_DONT_COPY_QUERY` — for the mutator, don't deep-copy the top Query (mutate-in-place semantics).
- `QTW_EXAMINE_SORTGROUP` — include SortGroupClause lists.
- `QTW_IGNORE_GROUPEXPRS` — skip GROUP expressions list.

For attnum remapping you probably want `0` (descend everything) or `QTW_EXAMINE_RTES_BEFORE` if subqueries also reference your target relation.

## Adding a new expression node — walker maintenance

If you ever add a new expression node type, you must add cases to **every** giant switch in `src/backend/nodes/nodeFuncs.c` or walkers/mutators will silently skip your node:

- `exprType` (`:42+`), `exprTypmod` (`:304+`), `exprCollation` (`:826+`), `exprSetCollation` (`:1140+`), `exprInputCollation` (`:1092+`), `exprLocation` (`:1403+`) — type/typmod/collation/location introspection.
- `expression_tree_walker_impl` (`:2111+`) and `expression_tree_mutator_impl` (`:3018+`) — recursion into children.
- `raw_expression_tree_walker_impl` (`:4115+`) — only if the node can also appear in raw parsetrees.
- `set_opfuncid` family (`:1890+`) — only if the node carries an unresolved operator OID.

Five-to-eight maintenance points total. Grep `T_OpExpr` (or another sibling) to enumerate every site mechanically.
