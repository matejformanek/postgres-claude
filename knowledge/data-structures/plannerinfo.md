# PlannerInfo — the per-Query planner workspace

`PlannerInfo` (alias `root`) is the **planner's per-Query
state machine**. Every planner function takes a
`PlannerInfo *root` argument; it threads the Query tree,
range table, RelOptInfo arrays, equivalence classes,
PlaceHolderVars, and outer-Param context through every
recursive call. One PlannerInfo exists per query level
(top-level Query + each subquery). Understanding its core
fields is the cost of admission for planner work.

Anchors:
- `source/src/include/nodes/pathnodes.h:300-302` —
  PlannerInfo forward + struct header [verified-by-code]
- `source/src/include/nodes/pathnodes.h:346-354` —
  simple_rel_array [verified-by-code]
- `source/src/include/nodes/pathnodes.h:394-402` —
  join_rel_list comment + field [verified-by-code]
- `source/src/include/nodes/pathnodes.h:436` —
  eq_classes [verified-by-code]
- `knowledge/data-structures/reloptinfo.md` — companion;
  PlannerInfo holds arrays of these
- `knowledge/data-structures/restrictinfo.md` — companion;
  RestrictInfo nodes live in PlannerInfo's lists
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion

## The shape (selected fields)

```c
struct PlannerInfo
{
    pg_node_attr(no_copy_equal, no_read, no_query_jumble)
    NodeTag type;

    Query          *parse;            /* the Query being planned */
    PlannerGlobal  *glob;             /* cross-Query state */
    Index           query_level;      /* 1 at outermost */
    PlannerInfo    *parent_root;      /* NULL at outermost */

    char           *plan_name;        /* EXPLAIN label */
    char           *alternative_plan_name;

    List           *plan_params;      /* PARAM_EXEC handed down */
    Bitmapset      *outer_params;     /* PARAM_EXEC available from outer */

    /* The big arrays */
    struct RelOptInfo **simple_rel_array;  /* base + other RTEs */
    int                 simple_rel_array_size;
    RangeTblEntry     **simple_rte_array;  /* mirror RTE array */

    /* Join planning */
    List           *join_rel_list;    /* all join RelOptInfos seen */
    int             join_cur_level;
    List          **join_rel_level;   /* per-level join lists */

    /* Equivalence + placeholders */
    List           *eq_classes;       /* EquivalenceClass list */
    List           *placeholder_list; /* PlaceHolderInfo list */

    /* ... ~80 more fields */
};
```

[verified-by-code `pathnodes.h:300-500`]

## The four big arrays

[verified-by-code `pathnodes.h:346-372`]

PlannerInfo holds two parallel arrays indexed by **range
table index** (1-based; entry 0 wasted):

- **`simple_rel_array[rti]`** — pointer to base/other-rel
  RelOptInfo for RTE at index rti, or NULL if no relation
  (e.g., join RTE, or RTE not yet referenced).
- **`simple_rte_array[rti]`** — the RangeTblEntry pointer,
  cached to avoid `rt_fetch()` indirection on hot paths.

[from-comment `pathnodes.h:347-353`]

> simple_rel_array holds pointers to "base rels" and "other
> rels" (see comments for RelOptInfo for more info). It is
> indexed by rangetable index (so entry 0 is always
> wasted). Entries can be NULL when an RTE does not
> correspond to a base relation, such as a join RTE or an
> unreferenced view RTE; or if the RelOptInfo hasn't been
> made yet.

The size grows to match RTE additions during query rewrite
+ subquery pullup.

## join_rel_list — the join-relation pool

[verified-by-code `pathnodes.h:394-402`]

```c
/*
 * join_rel_list is a list of all join-relation RelOptInfos we have
 * considered in this planning run.  For small problems we just scan
 * the list to do lookups, but when there are many join relations
 * we build a hash table for faster lookups.
 */
List           *join_rel_list;
```

Each entry: a RelOptInfo whose `relids` is a **superset of
one RTE** — i.e., a join of two or more base rels.
`make_join_rel` adds entries as the dynamic-programming
join algorithm builds bigger joins from smaller ones.

The complementary `join_rel_level[N]` array (when used)
groups joins by # of base rels — level 2 is two-rel joins,
level 3 is three-rel joins, etc. Standard bottom-up
DP-style join search consults level N-1 to build level N.

## eq_classes — the equivalence class machinery

[verified-by-code `pathnodes.h:436`]

```c
List       *eq_classes;     /* list of active EquivalenceClasses */
```

Each `EquivalenceClass` represents a set of expressions
known to be equal — typically via equijoin (`a = b`) or
sort-key derivation. The planner uses ECs to:

- Generate redundant join conditions (`a = b AND b = c → a = c`).
- Push qual conditions through joins (if `a` and `b` are in
  same EC, condition on `a` applies to `b`'s relation).
- Recognize compatible sort orders for merge joins.

ECs are constructed early (`initsplan.c`) and consulted
throughout path generation.

## placeholder_list — for outer joins + lateral

```c
List       *placeholder_list;    /* list of PlaceHolderInfos */
```

[from-comment `pathnodes.h:496` area]

`PlaceHolderVar` wraps an expression that needs to be
evaluated **after** a specific outer join — to preserve
NULL semantics. The list records the PHV → output-level
mapping. Without placeholders, expressions referencing
outer-join nullable columns could be evaluated below the
join, producing wrong results.

## Subquery nesting — parent_root + query_level

```c
Index           query_level;      /* 1 at outermost */
PlannerInfo    *parent_root;      /* NULL at outermost */
```

`(SELECT ... FROM (SELECT ...))` — outer PlannerInfo has
`query_level = 1, parent_root = NULL`. Inner subquery has
`query_level = 2, parent_root = outer`. Correlated
references (Vars with `varlevelsup > 0`) resolve up the
chain.

## plan_params + outer_params — the parameter handshake

[from-comment `pathnodes.h:338-343`]

> plan_params contains the expressions that this query
> level needs to make available to a lower query level that
> is currently being planned. outer_params contains the
> paramIds of PARAM_EXEC Params that outer query levels
> will make available to this query level.

For correlated subplans: outer query records what it
provides; inner query records what it needs. The
`PlannerParamItem` entries get turned into PARAM_EXEC slots
at execution time.

## The PlannerGlobal — cross-Query state

```c
PlannerGlobal  *glob;
```

One `PlannerGlobal` per top-level planner invocation,
shared across all PlannerInfos. Holds:
- The cumulative `subplans` list (final Plan nodes for
  subqueries).
- `paramExecTypes` (PARAM_EXEC slot types).
- `relationOids` and `invalItems` (for plan-cache
  invalidation).
- `boundParams` (PARAM_EXTERN values).

A subquery's PlannerInfo points to the same glob as its
parent — so they share the subplan numbering, the param
type list, etc.

## Common review-time concerns

- **`root` is the convention** — virtually every planner
  function takes `PlannerInfo *root`.
- **simple_rel_array is sparse** — NULL entries are
  expected; check before deref.
- **join_rel_list grows during DP search** — don't cache
  list length across `make_join_rel` calls.
- **eq_classes are NOT immutable** — `add_eq_member` may
  add to existing classes during planning.
- **parent_root for correlated lookups** — Vars with
  varlevelsup > 0 resolve via parent_root chain.
- **PlannerGlobal subplans is the source of truth** —
  Plan tree's `initPlan` / `subPlan` Var indices reference
  it.

## Invariants

- **[INV-1]** `query_level = 1` at outermost; > 1 in
  subqueries.
- **[INV-2]** `simple_rel_array[0]` is always wasted (RTE
  indexing is 1-based).
- **[INV-3]** `parent_root == NULL` at outermost; subquery
  roots chain to parent.
- **[INV-4]** A join-rel's RelOptInfo lives in
  `join_rel_list`, not in `simple_rel_array`.
- **[INV-5]** `glob` is shared across the entire planner
  invocation (parent + children).

## Useful greps

- All PlannerInfo field references:
  `grep -n 'root->' source/src/backend/optimizer/plan/planner.c | head -20`
- simple_rel_array users:
  `grep -RIn 'simple_rel_array\[' source/src/backend/optimizer | head -10`
- join_rel_list users:
  `grep -RIn 'join_rel_list' source/src/backend/optimizer | head -10`
- eq_classes users:
  `grep -RIn 'eq_classes' source/src/backend/optimizer/path | head -10`

## Cross-references

- `knowledge/data-structures/reloptinfo.md` —
  per-relation planner state, arrayed in PlannerInfo.
- `knowledge/data-structures/restrictinfo.md` — qual
  clauses; held in RelOptInfo lists owned via PlannerInfo.
- `knowledge/data-structures/var-const-nodes.md` — Var's
  varlevelsup resolves via parent_root chain.
- `knowledge/subsystems/optimizer.md` — the planner
  subsystem this struct centers.
- `.claude/skills/executor-and-planner/SKILL.md` — planner
  conventions.
- `source/src/include/nodes/pathnodes.h` — full struct.
- `source/src/backend/optimizer/plan/planmain.c` —
  `query_planner` entry.
- `source/src/backend/optimizer/path/allpaths.c` —
  set_*_pathlist functions that populate simple_rel_array.
