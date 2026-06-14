# RelOptInfo — per-relation planner state

`RelOptInfo` is the **planner's per-relation workspace** —
one per base RTE, one per join combination explored, plus
"other rels" (partition children, append-rel parents). It
holds the **pathlist** (candidate access paths), size /
cost estimates, base-restriction quals, join-info, and the
EC / lateral metadata that drives path generation. The
dynamic-programming join algorithm builds bigger
RelOptInfos from smaller ones by combining their pathlists.

Anchors:
- `source/src/include/nodes/pathnodes.h:1009-1080` —
  RelOptInfo struct head [verified-by-code]
- `source/src/include/nodes/pathnodes.h:1050-1056` —
  pathlist family [verified-by-code]
- `source/src/include/nodes/pathnodes.h:1142-1149` —
  baserestrictinfo + joininfo [verified-by-code]
- `source/src/include/nodes/pathnodes.h:803-906` — design
  commentary for fields [verified-by-code]
- `knowledge/data-structures/plannerinfo.md` — parent;
  PlannerInfo arrays hold these
- `knowledge/data-structures/restrictinfo.md` — companion;
  RelOptInfo's qual lists are RestrictInfo lists
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The shape (selected fields)

```c
typedef struct RelOptInfo
{
    pg_node_attr(no_copy_equal, no_read, no_query_jumble)
    NodeTag       type;
    RelOptKind    reloptkind;       /* base / join / other / upper */
    Relids        relids;            /* base + OJ relids in this rel */
    Cardinality   rows;              /* estimated row count */

    /* Per-rel planner controls */
    bool          consider_startup;
    bool          consider_param_startup;
    bool          consider_parallel;
    uint64        pgs_mask;

    PathTarget   *reltarget;         /* output targetlist + width */

    /* Path materialization */
    List         *pathlist;          /* candidate Paths */
    List         *ppilist;           /* ParamPathInfos */
    List         *partial_pathlist;  /* parallel-Partial Paths */
    Path         *cheapest_startup_path;
    Path         *cheapest_total_path;
    List         *cheapest_parameterized_paths;

    /* Lateral references */
    Relids        direct_lateral_relids;
    Relids        lateral_relids;

    /* Base-rel info (NOT set for join rels) */
    Index         relid;
    Oid           reltablespace;
    RTEKind       rtekind;
    AttrNumber    min_attr;
    AttrNumber    max_attr;
    /* ... attribute arrays */

    /* Quals + joins */
    List         *baserestrictinfo;  /* base-rel quals */
    QualCost      baserestrictcost;
    Index         baserestrict_min_security;
    List         *joininfo;          /* join clauses involving this rel */
    bool          has_eclass_joins;
    /* ... ~80 more fields */
} RelOptInfo;
```

[verified-by-code `pathnodes.h:1009-1170`]

## reloptkind — the 4 categories

[verified-by-code via `RelOptKind` enum]

| Kind | Meaning |
|---|---|
| `RELOPT_BASEREL` | One real base relation (table, index, function, etc.) |
| `RELOPT_JOINREL` | Two-or-more relations joined |
| `RELOPT_OTHER_MEMBER_REL` | Child of append-rel (partition / inherits) |
| `RELOPT_OTHER_JOINREL` | Join involving an otherrel |
| `RELOPT_UPPER_REL` | Upper-stage rel (GROUP, ORDER, LIMIT) |
| `RELOPT_OTHER_UPPER_REL` | Upper rel for partial paths |

The `OTHER_*` flavors are mirror RelOptInfos used during
**partitionwise join** / inheritance expansion. The
"upper" rels are added after base-rel and join planning,
for aggregation/grouping/limit stages.

## pathlist — the candidate Paths

[from-comment `pathnodes.h:803-810`]

> pathlist - List of Path nodes, one for each potentially
> useful method of producing this rel.
>
> cheapest_startup_path - the pathlist member with lowest
> startup cost (regardless of total cost)
>
> cheapest_total_path - the pathlist member with lowest
> total cost

Each Path is a candidate access method. For a base rel,
typical Paths: SeqScan, several IndexScans (one per usable
index), BitmapHeapScan, possibly TidScan. For a join rel:
NestLoop, MergeJoin, HashJoin paths in various
configurations.

`add_path` accepts a new candidate; the planner discards
strictly-dominated alternatives (worse on every cost
dimension).

## baserestrictinfo vs joininfo

[from-comment `pathnodes.h:896-918`]

> baserestrictinfo - List of RestrictInfo nodes, containing
> info about each non-join qualification clause in which
> this relation participates (only used for base rels)
>
> joininfo - List of RestrictInfo nodes, containing info
> about each join clause in which this relation
> participates

Two qual buckets:

- **`baserestrictinfo`** — single-rel quals (`WHERE
  t1.x > 5`). Pushed all the way down to the scan node.
- **`joininfo`** — multi-rel quals (`WHERE t1.id =
  t2.id`). Lives at the join level.

The split lets the planner cost scans without join quals
and choose join orderings with full qual visibility.

## relids — the rel-set identifier

```c
Relids        relids;
```

A `Relids` is a Bitmapset of range-table indices + outer-join
relids. For a base rel, just `{relid}`. For a join, the
union of constituent relids. Hashing on `relids` is how
the planner looks up "did we already build the RelOptInfo
for this combination?"

## reltarget — the output schema

```c
PathTarget   *reltarget;
```

`PathTarget` is a list of expressions + costs + width
estimates. For a base rel, just the columns referenced
above. For a join, the union of needed projections. The
planner threads PathTargets to track exactly which columns
to project at each level.

## Parallel-query fields

```c
bool          consider_parallel;
List         *partial_pathlist;
```

`partial_pathlist` carries **partial Paths** — those that
produce a fraction of the result per parallel worker.
A `Gather` node on top merges them. `consider_parallel = false`
suppresses partial path generation (e.g., for non-parallel-safe
predicates).

## Lateral references

```c
Relids        direct_lateral_relids;
Relids        lateral_relids;
```

For LATERAL subqueries: which RTEs are referenced from
this rel laterally. Affects valid join orderings (a rel
with lateral refs can't be joined until its referent is
on the inside).

## The has_clone qual machinery

[verified-by-code `pathnodes.h:2900` area]

When a qual must be evaluated above an outer join (to
preserve NULL semantics) AND below (for selectivity),
two RestrictInfo clones with same serial# but different
location flags get pushed into different lists. The
planner is careful to apply ≤ one of them per plan.

## Common review-time concerns

- **`relid` is invalid for join rels** — check
  `reloptkind != RELOPT_JOINREL` first.
- **`relids` is the canonical identifier** — not relid.
- **`pathlist` can be large** — dominated paths get
  pruned but the live set scales with index count.
- **`baserestrictinfo` only on base rels** — join rels
  collect quals in `joininfo`.
- **`reltarget` width drives memory estimates** — wrong
  width → bad hash-join sizing.
- **OTHER_MEMBER_REL vs BASEREL** — partition planning
  often needs the distinction.

## Invariants

- **[INV-1]** `reloptkind` classifies the rel; some fields
  unset for join/upper rels.
- **[INV-2]** `relids` is the canonical identifier for
  RelOptInfo lookup.
- **[INV-3]** `pathlist` holds undominated candidate
  Paths.
- **[INV-4]** `baserestrictinfo` for base rels only;
  joininfo for join clauses.
- **[INV-5]** `partial_pathlist` requires
  `consider_parallel = true`.

## Useful greps

- All RelOptInfo constructors:
  `grep -RIn 'build_simple_rel\|build_join_rel\|fetch_upper_rel' source/src/backend/optimizer | head -10`
- pathlist mutators:
  `grep -RIn 'add_path\|add_partial_path' source/src/backend/optimizer | head -10`
- reloptkind switches:
  `grep -RIn 'reloptkind ==\|reloptkind !=' source/src/backend/optimizer | head -10`

## Cross-references

- `knowledge/data-structures/plannerinfo.md` — parent;
  PlannerInfo holds simple_rel_array + join_rel_list of
  these.
- `knowledge/data-structures/restrictinfo.md` —
  baserestrictinfo + joininfo elements.
- `knowledge/idioms/partition-tuple-routing.md` —
  partitionwise planning produces OTHER_MEMBER_REL.
- `knowledge/subsystems/optimizer.md` — the planner.
- `.claude/skills/executor-and-planner/SKILL.md` —
  planner conventions.
- `source/src/include/nodes/pathnodes.h` — full struct.
- `source/src/backend/optimizer/util/relnode.c` —
  build_simple_rel, build_join_rel.
- `source/src/backend/optimizer/path/allpaths.c` —
  set_*_pathlist populates pathlist.
