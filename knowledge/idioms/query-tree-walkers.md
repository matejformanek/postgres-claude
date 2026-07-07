# Query / expression tree walkers — flag landscape

PG walks `Query` and expression trees through a tiny handful of helpers
in `src/backend/nodes/nodeFuncs.c`:

- `expression_tree_walker(node, walker, context)` — recurses through any
  expression-tree node, calling `walker(node, context)` at each step.
- `query_tree_walker(query, walker, context, flags)` — walks all
  expression subtrees of a `Query`, plus (optionally) its rangetable,
  CTEs, sortGroupClause.
- `range_table_walker(rtable, walker, context, flags)` — just the
  rangetable portion, separately callable.
- `expression_tree_mutator` / `query_tree_mutator` — same shape,
  produces a modified copy.

The `flags` argument is a bitmask of `QTW_*` constants in
`source/src/include/nodes/nodeFuncs.h:22-34`
[verified-by-code]. Most of the bugs in this area come from passing the
wrong flags, not from the walker callback itself. **Pass `0` unless you
specifically need what a flag enables**, and if you do enable a flag
that exposes a new node kind to your callback, the callback MUST handle
that kind.

Origin: sesvars F9 (2026-06-17). A walker speculatively passed
`QTW_EXAMINE_RTES_BEFORE` "to be thorough", which made
`range_table_walker` invoke the callback on every `T_RangeTblEntry`
node. The callback had no `T_RangeTblEntry` arm, so it fell through to
the default branch, which routed back into `expression_tree_walker`,
which has its own default branch that calls `elog(ERROR, "unrecognized
node type")`. 100+ regression failures, all from one speculative flag.

Anchors:
- `source/src/include/nodes/nodeFuncs.h:22-34` — `QTW_*` defines
- `source/src/backend/nodes/nodeFuncs.c:2862-2952` —
  `range_table_walker` / `range_table_entry_walker`
- `source/src/backend/nodes/nodeFuncs.c:2731-2734` — the
  `elog(ERROR, "unrecognized node type")` default arm
- `source/src/backend/nodes/README` — walker design

## The `QTW_*` flag table

[verified-by-code `source/src/include/nodes/nodeFuncs.h:22-34`]

| Flag | Hex | What it makes the walker do | Callback responsibility when set |
|---|---|---|---|
| `QTW_IGNORE_RT_SUBQUERIES` | `0x01` | **Skip** descending into `RangeTblEntry.subquery` (RTE_SUBQUERY) | none — fewer nodes visited |
| `QTW_IGNORE_CTE_SUBQUERIES` | `0x02` | **Skip** descending into `Query.cteList` | none — fewer nodes visited |
| `QTW_IGNORE_RC_SUBQUERIES` | `0x03` | Both of the above (it's `0x01 | 0x02`) | none |
| `QTW_IGNORE_JOINALIASES` | `0x04` | **Skip** `RangeTblEntry.joinaliasvars` (RTE_JOIN alias list) | none |
| `QTW_IGNORE_RANGE_TABLE` | `0x08` | **Skip** `Query.rtable` entirely | none |
| `QTW_EXAMINE_RTES_BEFORE` | `0x10` | **Visit** each `RangeTblEntry` **before** descending into its contents | **must handle `T_RangeTblEntry`** in callback |
| `QTW_EXAMINE_RTES_AFTER` | `0x20` | **Visit** each `RangeTblEntry` **after** descending into its contents | **must handle `T_RangeTblEntry`** in callback |
| `QTW_DONT_COPY_QUERY` | `0x40` | (mutator) do not copy the top `Query` node | none |
| `QTW_EXAMINE_SORTGROUP` | `0x80` | **Visit** `SortGroupClause` lists | **must handle `T_SortGroupClause`** |
| `QTW_IGNORE_GROUPEXPRS` | `0x100` | **Skip** `RTE_GROUP.groupexprs` | none |

The asymmetry between "IGNORE_*" (suppression — safe to add) and
"EXAMINE_*" (exposes new node tags — requires a callback arm) is the
main thing to internalize.

## What `range_table_walker` actually does

[verified-by-code `source/src/backend/nodes/nodeFuncs.c:2884-2952`]

For each RTE:

1. If `QTW_EXAMINE_RTES_BEFORE`: call `walker(rte, context)`. **This is
   where you hit `T_RangeTblEntry` in your callback.**
2. Switch on `rte->rtekind`:
   - `RTE_RELATION` → walk `rte->tablesample`.
   - `RTE_SUBQUERY` → walk `rte->subquery` (unless
     `QTW_IGNORE_RT_SUBQUERIES`).
   - `RTE_JOIN` → walk `rte->joinaliasvars` (unless
     `QTW_IGNORE_JOINALIASES`).
   - `RTE_FUNCTION` → walk `rte->functions`.
   - `RTE_TABLEFUNC` → walk `rte->tablefunc`.
   - `RTE_VALUES` → walk `rte->values_lists`.
   - `RTE_GRAPH_TABLE` → walk `graph_pattern`, `graph_table_columns`.
   - `RTE_CTE`, `RTE_NAMEDTUPLESTORE`, `RTE_RESULT` → nothing.
   - `RTE_GROUP` → walk `rte->groupexprs` (unless
     `QTW_IGNORE_GROUPEXPRS`).
3. Walk `rte->securityQuals`.
4. If `QTW_EXAMINE_RTES_AFTER`: call `walker(rte, context)`.

Both the `BEFORE` and `AFTER` hooks pass the RTE itself, not a node
inside it.

> "Walkers might need to examine the RTE node itself either before or
> after visiting its contents (or, conceivably, both). Note that if you
> specify neither flag, the walker won't be called on the RTE at all."
> [from-comment `source/src/backend/nodes/nodeFuncs.c:2889-2893`]

## Why the failure is "unrecognized node type"

When your callback returns `false` for a node it doesn't recognize,
control returns to `expression_tree_walker`, which then runs its own
switch on the same node. `expression_tree_walker` has cases for every
expression node but **no case for `T_RangeTblEntry`** (RTEs are parse-tree
nodes, not Expr nodes). It falls through to:

```c
default:
    elog(ERROR, "unrecognized node type: %d", (int) nodeTag(node));
    break;
```

[verified-by-code `source/src/backend/nodes/nodeFuncs.c:2731-2734`]

So a callback that doesn't recognize `T_RangeTblEntry` doesn't get a
clean "not my node, skip it" path — it gets a hard ERROR. Same pattern
applies to `T_SortGroupClause` when `QTW_EXAMINE_SORTGROUP` is set.

## Anti-pattern: speculative flags

The shape of the bug:

```c
/* WRONG — adds flags "to be thorough" without a matching callback arm */
query_tree_walker(query, my_walker, ctx,
                  QTW_EXAMINE_RTES_BEFORE | QTW_EXAMINE_SORTGROUP);

static bool
my_walker(Node *node, void *context)
{
    if (IsA(node, MyTargetExpr))
        ...do work...;
    return expression_tree_walker(node, my_walker, context);
    /* no case for T_RangeTblEntry → falls into expression_tree_walker's
       default → elog(ERROR) */
}
```

The fix is one of:

- **Drop the flag** if you don't need it (most common — the original
  question was usually answerable with `0`).
- **Add the callback arm**:

  ```c
  if (IsA(node, RangeTblEntry))
  {
      RangeTblEntry *rte = (RangeTblEntry *) node;
      ...inspect rte fields you care about...;
      return range_table_entry_walker(rte, my_walker, context, flags);
  }
  ```

  Note the recursive call into `range_table_entry_walker`, not back
  into `expression_tree_walker` — RTEs aren't expression nodes.

## Default starting flags by use case

| Use case | Flags | Callback must handle |
|---|---|---|
| Searching a Query for a specific Expr subtype anywhere | `0` | nothing extra |
| Same, but you also want to look at subquery and CTE bodies | `0` | nothing extra (subqueries / CTEs descend by default) |
| Same, but you DON'T want to descend into subqueries | `QTW_IGNORE_RT_SUBQUERIES \| QTW_IGNORE_CTE_SUBQUERIES` | nothing extra |
| Inspecting RTEs themselves (e.g. "which relations does this Query reference") | `QTW_EXAMINE_RTES_BEFORE` | `T_RangeTblEntry` arm |
| Same, but you want to act on post-content state of the RTE | `QTW_EXAMINE_RTES_AFTER` | `T_RangeTblEntry` arm |
| Walking `SortGroupClause` lists (rare) | `QTW_EXAMINE_SORTGROUP` | `T_SortGroupClause` arm |
| Modifying only the top-Query subexpressions without copying the Query node itself (mutator) | `QTW_DONT_COPY_QUERY` | nothing extra |

Most "find an Expr X anywhere in this Query" walkers want `0`. Reach
for flags only when you can name the field of the RTE / SortGroupClause
you need to inspect.

## Walker callback contract recap

```c
static bool my_walker(Node *node, void *context)
{
    if (node == NULL)
        return false;
    if (IsA(node, MyTarget))
    {
        ...handle...;
        /* return true to stop the walk early (found what we wanted),
           false to keep going */
        return false;
    }
    /* For Query nodes specifically, route through query_tree_walker
       (don't just recurse into expression_tree_walker — Query has
       subtrees that aren't Expr trees) */
    if (IsA(node, Query))
        return query_tree_walker((Query *) node, my_walker, context,
                                 0 /* or the flag you actually need */);
    /* For RTEs (only reached if QTW_EXAMINE_RTES_* was passed) */
    if (IsA(node, RangeTblEntry))
        return range_table_entry_walker((RangeTblEntry *) node,
                                        my_walker, context, flags);
    return expression_tree_walker(node, my_walker, context);
}
```

The recursive-self pattern is the convention; almost every walker in
PG is shaped this way.



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | 2731 | the elog(ERROR, "unrecognized node type") default arm |
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | 2862 | range_table_walker / range_table_entry_walker |
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | 2884 | [verified-by-code -2952] |
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | 2889 | > [from-comment -2893] |
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | 2891 | Whether passing both QTW_EXAMINE_RTES_BEFORE and QTW_EXAMINE_RTES_AFTER is ever useful — comment in... |
| [`src/backend/nodes/nodeFuncs.c`](../files/src/backend/nodes/nodeFuncs.c.md) | — | walkers |
| [`src/include/nodes/nodeFuncs.h`](../files/src/include/nodes/nodeFuncs.h.md) | 22 | QTW_ defines |
| [`src/include/nodes/nodeFuncs.h`](../files/src/include/nodes/nodeFuncs.h.md) | — | flag defines |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)
- [`add-new-node-type`](../scenarios/add-new-node-type.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/node-types-and-lists.md` — the NodeTag machinery
  the walker dispatches on
- `knowledge/idioms/node-types.md` — parse-tree vs Expr shape; RTEs
  are parse-tree nodes, which is why they need a flag to be visited
- `knowledge/idioms/expression-evaluator-flow.md` — executor-side
  expression handling (different from these walkers, which are
  parse/plan-time)
- `source/src/backend/nodes/nodeFuncs.c` — the walkers
- `source/src/include/nodes/nodeFuncs.h` — flag defines
- `source/src/backend/nodes/README` — design notes

## Open questions / unverified

- Whether `QTW_DONT_COPY_QUERY` has any subtle interaction with the
  copy of `targetList` in mutators [unverified] — not encountered in
  sesvars; usage is rare.
- Whether passing both `QTW_EXAMINE_RTES_BEFORE` and
  `QTW_EXAMINE_RTES_AFTER` is ever useful — comment in nodeFuncs.c
  says "conceivably both" but no in-tree caller does so [from-comment
  `source/src/backend/nodes/nodeFuncs.c:2891`].
