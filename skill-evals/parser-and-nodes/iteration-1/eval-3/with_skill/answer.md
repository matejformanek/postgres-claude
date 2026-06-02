# Walking and rewriting a Query parsetree

## The right infrastructure: `expression_tree_mutator`

Since you want to *rewrite* (return new nodes), you need a **mutator**, not a walker. Walkers return `bool` (true/false to stop); mutators return `Node *` (possibly new).

Both live in `source/src/backend/nodes/nodeFuncs.c` (~4900 lines, see `knowledge/files/src/backend/nodes/nodeFuncs.c.md`). Public entry points:

- `expression_tree_walker(node, walker, context)` → `bool`
- `expression_tree_mutator(node, mutator, context)` → `Node *`
- `query_tree_walker` / `query_tree_mutator` — wrap the expression versions for `Query` trees, with flags to control recursion into `rtable` subqueries, the rangetable itself, CTEs, JOIN aliases (see `nodeFuncs.h:21-34`).

The public names are macros that wrap the `_impl` functions to silence callback-type warnings (`nodeFuncs.h:155-183`). That's why your callback can be declared as `Node *fn(Node *node, MyCtx *ctx)` rather than `void *`.

## Skeleton for your rewrite

```c
typedef struct {
    int    target_attno;
    int    new_attno;
    Index  rt_index;
} RewriteCtx;

static Node *
rewrite_var_mutator(Node *node, RewriteCtx *ctx)
{
    if (node == NULL)
        return NULL;
    if (IsA(node, Var))
    {
        Var *v = (Var *) node;
        if (v->varno == ctx->rt_index && v->varattno == ctx->target_attno)
        {
            Var *newv = copyObject(v);
            newv->varattno = ctx->new_attno;
            return (Node *) newv;
        }
        /* fall through to default recursion */
    }
    /* Query: descend into subqueries too */
    if (IsA(node, Query))
        return (Node *) query_tree_mutator((Query *) node,
                                           rewrite_var_mutator, ctx, 0);
    return expression_tree_mutator(node, rewrite_var_mutator, ctx);
}

/* call: */
Query *out = (Query *) query_tree_mutator(query, rewrite_var_mutator, &ctx,
                                          QTW_EXAMINE_RTES_BEFORE);
```

## Contract

### Walker (`expression_tree_walker`)

- Callback signature: `bool walker(Node *node, void *ctx)`.
- Return `true` to short-circuit the entire walk; `false` to keep going.
- Implementation handles `NULL`, common Expr subtypes, and **list-of-Node recursion** itself. The callback only needs to switch on `nodeTag` for types it cares about, then fall through to `return expression_tree_walker(node, walker, context);` to recurse.

### Mutator (`expression_tree_mutator`)

- Callback signature: `Node *mutator(Node *node, void *ctx)`.
- Returns a (possibly new) Node — **NULL is allowed and means "delete this subtree"**.
- Helpers know how to rebuild common container nodes — list elements get individually mutated, the container is rebuilt around the mutated cells.
- Must handle `NULL` input → return `NULL`.

(See `nodeFuncs.c.md` "Walker contract" / "Mutator contract".)

## Post-analysis vs raw — which to use

The pipeline (`knowledge/idioms/parser-pipeline.md`):
- **Raw parse tree** (output of `raw_parser`, before analyze) — contains shapes like `A_Expr`, `ColumnRef`, `A_Const`, `ResTarget`. Catalog-unresolved.
- **Analyzed Query tree** — contains `Var`, `OpExpr`, `Const`, `TargetEntry`, `RangeTblEntry`. Catalog-resolved, typed.

These are **different node shapes**, so they need different walkers:

| Stage | What you'd walk | Use |
|---|---|---|
| Pre-analyze (raw) | `A_Expr`, `ColumnRef`, … | `raw_expression_tree_walker` |
| Post-analyze (Query) | `Var`, `OpExpr`, … | `expression_tree_walker` / `_mutator` |
| Executor time | `PlanState` | `planstate_tree_walker` |

`raw_expression_tree_walker_impl` exists for early hooks (e.g. some `analyze.c`-time security/audit walks). The **post**-analysis walker does NOT know about raw shapes — if you hand it an `A_Expr` it'll fall off the switch.

For "rewrite ColumnRef" the answer is: if you're working pre-analyze, use `raw_expression_tree_walker` (no mutator exists — you'd have to walk + edit in place, awkward); if post-analyze (which is far more common — that's what plan rewriters do), you'll be matching `Var` nodes via `expression_tree_mutator`. Your prompt mentions both — they're different stages. Pick the right one based on whether you have a raw parsetree or an analyzed Query.

## What to update if you add a new expression node type

This is the maintenance tax that bites everyone who skips it. Every one of these switches in `nodeFuncs.c` must learn the new tag, otherwise its result type / collation / location / walker recursion silently misbehaves:

1. **`exprType`** (`nodeFuncs.c:42-300+`) — what type does this expression return?
2. **`exprTypmod`** (`:304+`) — what's its typmod?
3. **`exprCollation`** (`:826+`) and `exprSetCollation`, `exprInputCollation`.
4. **`exprLocation`** (`:1403+`) — for error reporting.
5. **`expression_tree_walker_impl`** — must recurse into the new node's children.
6. **`expression_tree_mutator_impl`** — ditto, but rebuilds.
7. **`raw_expression_tree_walker_impl`** — if the node can appear in raw parsetrees.
8. **`set_opfuncid`** family — only if the new node holds an operator OID needing resolution.

The README lists this under "step 3: add cases to the functions in nodeFuncs.c" — grep `T_<SiblingNode>` (e.g. `T_OpExpr`) to find every site. Five-to-eight maintenance points per node, and the file is ~5000 lines precisely because each of these is its own giant switch.

Also: `pg_stat_statements` query-id uses `queryjumblefuncs.c` (mostly generated), and any node holding child expressions needs the autogenerated jumble logic to be correct — verify per-field `query_jumble_ignore` / `query_jumble_location` annotations after the first build.

## Files to know

- `source/src/backend/nodes/nodeFuncs.c` — all walkers/mutators
- `source/src/include/nodes/nodeFuncs.h:21-34` — `QTW_*` flag bits for `query_tree_walker`
- `source/src/include/nodes/nodeFuncs.h:155-183` — public macro wrappers
- `source/src/backend/nodes/README` step 3 — the maintenance contract
