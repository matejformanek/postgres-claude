# postgresql-hll — a self-promoting probabilistic type that poisons hash-aggregate path costs

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `citusdata/postgresql-hll` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-06 (see Sources footer).

## Domain & purpose

postgresql-hll adds a single SQL type, `hll`, implementing the **HyperLogLog**
probabilistic cardinality estimator: a fixed-size sketch (e.g. 1280 bytes) that
counts tens of billions of distinct values to within a few percent
(`README.md:6`). Its headline trick is *composability* — two `hll` sketches can
be unioned exactly, so distinct-count rollups across partitions/time-buckets
become cheap aggregate-of-aggregates. The interesting engineering is that `hll`
is not one data structure but a **hierarchy** of four, with automatic promotion
as a set grows: `EMPTY` → `EXPLICIT` (sorted exact id list) → `SPARSE` (lazy
register map) → `COMPRESSED`/`FULL` (the dense HyperLogLog register array)
(`README.md` "Algorithms"; `hll.c:110-114`). It is the worked answer to two
questions an anthropologist cares about: *how do you ship a varlena type that
silently changes its own internal encoding*, and *how does an extension force
the planner away from a join/aggregate strategy it knows will blow up*.

## How it hooks into PG

`PG_MODULE_MAGIC` (`hll.c:71-72`). Most of `hll` is conventional — a varlena
type with I/O functions, a pile of `PG_FUNCTION_INFO_V1` scalar functions, and
SQL-defined aggregates (`hll_add_agg`, `hll_union_agg`). The one
non-conventional thing `_PG_init` (`hll.c:156-165`) does is install a **planner
hook**: it chains `create_upper_paths_hook` to
`hll_aggregation_restriction_hook` (`hll.c:163-164`) `[verified-by-code]`. It is
*not* required to be in `shared_preload_libraries` for the type to work, but the
hook only takes effect cluster-wide if it is preloaded (the standard lazy-load
caveat). It also registers a GUC, `hll.force_groupagg` (`hll.c:434-435`), that
arms the hook.

## Where it diverges from core idioms

### 1. It maximizes the cost of unwanted planner paths instead of disabling a strategy

This is the standout divergence and worth studying. hll aggregates accumulate a
large transition state per group. `HashAggregate` keeps *all* groups' states
resident simultaneously, so a high-cardinality `GROUP BY` over hll can exhaust
memory; `GroupAggregate` streams one group at a time. Rather than ask users to
`SET enable_hashagg = off` (a blunt, session-wide instrument), hll reaches into
the planner's chosen paths and **poisons the cost of the hash-aggregate path**.
The `create_upper_paths_hook` callback `hll_aggregation_restriction_hook`
(`hll.c:175-230`), when `hll.force_groupagg` is set and `stage` is
`UPPERREL_GROUP_AGG`/`UPPERREL_FINAL`, walks `output_rel->pathlist`, finds any
`T_Agg` path with `aggstrategy == AGG_HASHED`, and calls
`MaximizeCostOfHashAggregate` (`hll.c:220-227`). That function pulls the
aggregate `Var`s out of the path target, and if any `Aggref->aggfnoid` is an hll
aggregate, it bluntly sets `path->total_cost = INT_MAX` (`hll.c:387-407`)
`[verified-by-code]`. So a path the planner already costed is *retroactively
made infinitely expensive* so `add_path`-style comparison rejects it. Mutating a
finished `Path`'s cost from a hook — as opposed to adding a path, or labeling a
function, or tuning a GUC — is an aggressive reach into planner internals that
core would never sanction. Cross-ref `[[knowledge/subsystems/optimizer]]`,
`.claude/skills/executor-and-planner/SKILL.md` (`create_upper_paths_hook`,
`UpperRelationKind`, `AggPath`).

### 2. A single varlena type that rewrites its own internal representation in place

Core types pick one on-disk layout. `hll` carries a 3-bit type tag
(`MST_EMPTY=0x1`, `MST_EXPLICIT=0x2`, `MST_SPARSE=0x3`, `MST_COMPRESSED=0x4`,
`hll.c:110-114`) in a `multiset_t` union (`ms_explicit_t` vs `ms_compressed_t`,
`hll.c:598-602`), and **promotes itself as data arrives**. `multiset_add`
(`hll.c:1221+`) is a state machine: an `EMPTY` set becomes `EXPLICIT` on first
insert (`:1241`), an `EXPLICIT` set that overflows its threshold is converted by
`explicit_to_compressed` which flips `ms_type = MST_COMPRESSED` (`:1009-1022,
1274`). One SQL type therefore has four serialization shapes, an upgrade
lattice between them, and per-shape branches in every I/O and operator function
(`hll.c:1085-1157` output switch). This adaptive-encoding design — trading exact
representation for the probabilistic one only once it pays off — is far richer
than the single-layout contract core's type system assumes. Cross-ref
`[[knowledge/idioms/varlena]]`, `.claude/skills/catalog-conventions/SKILL.md`.

### 3. It looks up and caches its *own* aggregate OIDs by name, at plan time

To recognize "is this Aggref one of mine?" inside the planner hook, hll resolves
its aggregate functions dynamically: `InitializeHllAggregateOids`
(`hll.c:234-259`) calls `FunctionOid(hllSchemaName, "hll_union_agg"/"hll_add_agg",
…)` and caches the OIDs in `hllAggregateArray`, guarded by the
`aggregateValuesInitialized` flag (`hll.c:128, 207, 259`). `HllAggregateOid`
(`hll.c:414-424`) then does a linear membership test against that array. Like
PostGIS, hll can't hardcode its own OIDs (they depend on install schema), so it
discovers them lazily and memoizes — a dynamic-OID pattern core builtins never
need. Cross-ref `[[knowledge/ideologies/postgis]]` (same dynamic-OID problem),
`[[knowledge/idioms/syscache]]`.

### 4. Version-forked hook signature inside one function body

The `create_upper_paths_hook` signature gained a `void *extra` argument in PG11.
hll keeps a single source that compiles across the boundary by `#if
(PG_VERSION_NUM >= 110000)` *inside* both the function definition and the
chained-call site (`hll.c:176-196`). Carrying core-version `#if`s through the
middle of a function — rather than behind a compat shim — is the portability
tax an extension spanning many PG majors pays, and a smell core code avoids.
Cross-ref `.claude/skills/extension-development/SKILL.md`.

## Notable design decisions (cited)

- **The hook always chains first.** `hll_aggregation_restriction_hook` invokes
  `previous_upper_path_hook` (if any) *before* doing its own work
  (`hll.c:189-196`) so it composes with other path-shaping extensions —
  textbook hook etiquette even while doing an untextbook thing with the result.
- **No-op unless the extension is actually installed.** The hook early-returns
  if `get_extension_oid(EXTENSION_NAME, true)` is invalid (`hll.c:200-205`), so
  merely loading the `.so` without `CREATE EXTENSION hll` costs nothing at plan
  time.
- **`force_groupagg` is off by default** (`hll.c:434-435`): the cost-poisoning
  is opt-in, a GUC the user flips when they hit the HashAggregate memory cliff.
- **Tunable precision packed into the type bits.** `REGWIDTH_BITS`,
  `EXPTHRESH_BITS`, `SPARSEON_BITS` (`hll.c:92-102, 473-474`) encode the
  log2(registers)/register-width/explicit-threshold parameters into the sketch
  header so each `hll` value is self-describing.
- **Conditional `PG_MODULE_MAGIC`** via `#ifdef` (`hll.c:71-72`) — compiles
  against very old PGs that lacked the macro.

## Links into corpus

- `[[knowledge/subsystems/optimizer]]` — `create_upper_paths_hook`,
  `UpperRelationKind`, `AggPath`/`AGG_HASHED`, and the `Path.total_cost` field
  hll overwrites.
- `[[knowledge/idioms/varlena]]` — the multi-representation varlena layout and
  in-place promotion.
- `[[knowledge/idioms/syscache]]` — dynamic OID resolution of the extension's
  own aggregates.
- `[[knowledge/ideologies/postgis]]` — the sibling dynamic-OID-caching pattern,
  and the other extension that leans on planner support/hooks.
- `.claude/skills/executor-and-planner/SKILL.md` — the upper-paths hook and the
  aggregate-strategy paths hll manipulates.
- `.claude/skills/catalog-conventions/SKILL.md` — why a custom aggregate's OID
  can't be hardcoded.

## Sources

Fetched 2026-06-06 (branch `master`). Manifest drift: the queue named
`README.markdown` (HTTP 404 — the real file is `README.md`, fetched) and
`src/hll.c`; the C file is actually at repo root `hll.c` not under `src/` (the
manifest path 404s for `src/hll.c`'s siblings, but `src/hll.c` itself resolved
to the root file via the raw host — fetched 3972 lines successfully). Added
`hll.control` for the control-field set.

- `https://raw.githubusercontent.com/citusdata/postgresql-hll/master/README.markdown`
  @ 2026-06-06 → HTTP 404 (manifest typo; real file is `README.md`).
- `https://raw.githubusercontent.com/citusdata/postgresql-hll/master/README.md`
  @ 2026-06-06 → HTTP 200 (26 KB).
- `https://raw.githubusercontent.com/citusdata/postgresql-hll/master/src/hll.c`
  @ 2026-06-06 → HTTP 200 (3972 lines).
- `https://raw.githubusercontent.com/citusdata/postgresql-hll/master/hll.control`
  @ 2026-06-06 → HTTP 200 (18 lines; `default_version = '2.21'`).
- Tree listing
  `https://api.github.com/repos/citusdata/postgresql-hll/git/trees/master?recursive=1`
  @ 2026-06-06 → HTTP 200 (123 paths; note the canonical C file is `hll.c` at
  root, and the `sql/` dir holds the regress fixtures).

All cites into `hll.c` — the `create_upper_paths_hook` install, the
`MaximizeCostOfHashAggregate` `total_cost = INT_MAX` poisoning, the `MST_*`
representation tags, the `multiset_add` promotion state machine, and the dynamic
aggregate-OID cache — are `[verified-by-code]` against the fetched file. The
exact register arithmetic of the HyperLogLog estimator itself was not derived
line-by-line; the algorithm hierarchy narrative is `[from-README]`.
</content>
