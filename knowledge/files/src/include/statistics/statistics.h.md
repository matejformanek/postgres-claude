# `src/include/statistics/statistics.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~131
- **Source:** `source/src/include/statistics/statistics.h`

Public-ish header for extended statistics — defines the on-disk
representations (`MVNDistinct`, `MVDependencies`, `MCVList`) with
their magic/type constants, plus the planner-facing selectivity
entry points and the build-time entry from ANALYZE. [verified-by-code]

## API / declarations

### Tunables / constants

- `STATS_MAX_DIMENSIONS = 8` — hard cap on attributes per
  extended-stats object. [verified-by-code]
- `STATS_NDISTINCT_MAGIC = 0xA352BFA4`, `STATS_NDISTINCT_TYPE_BASIC = 1`.
- `STATS_DEPS_MAGIC = 0xB4549A2C`, `STATS_DEPS_TYPE_BASIC = 1`.
- `STATS_MCV_MAGIC = 0xE1A651C2`, `STATS_MCV_TYPE_BASIC = 1`.
- `STATS_MCVLIST_MAX_ITEMS = MAX_STATISTICS_TARGET` (the same cap
  as default_statistics_target).

### On-disk / in-memory structs

- `MVNDistinctItem { double ndistinct; int nattributes;
  AttrNumber *attributes }`.
- `MVNDistinct { magic, type, nitems; MVNDistinctItem items[FLEX] }`.
- `MVDependency { degree (0..1); AttrNumber nattributes;
  attributes[FLEX] }` — the LAST attribute in `attributes[]` is the
  determined column; earlier ones are the determining set. [inferred]
- `MVDependencies { magic, type, ndeps; MVDependency *deps[FLEX] }`
  — note the array of pointers (each MVDependency is variable size).
- `MCVItem { double frequency; double base_frequency (frequency if
  independent); bool *isnull; Datum *values }`.
- `MCVList { magic, type, nitems, ndimensions, Oid types[STATS_MAX_DIMENSIONS],
  MCVItem items[FLEX] }`.

### Loaders (catalog → struct)

- `statext_ndistinct_load(mvoid, inh)`,
- `statext_dependencies_load(mvoid, inh)`,
- `statext_mcv_load(mvoid, inh)`,
- `statext_expressions_load(stxoid, inh, idx)` → HeapTuple.

### Build hook from ANALYZE

- `BuildRelationExtStatistics(onerel, inh, totalrows, numrows, rows,
  natts, vacattrstats)` — invoked from analyze.c per-relation.
- `HasRelationExtStatistics(onerel)` — does the relation have any?
- `ComputeExtStatisticsRows(onerel, natts, vacattrstats)` — sample
  size needed.
- `statext_is_kind_built(htup, type)` — helper.

### Planner entry points

- `dependencies_clauselist_selectivity(root, clauses, varRelid,
  jointype, sjinfo, rel, **estimatedclauses)`,
- `statext_clauselist_selectivity(root, clauses, varRelid, jointype,
  sjinfo, rel, **estimatedclauses, is_or)` — unified entry over
  functional-deps and MCVs. Marks clauses it estimated by setting
  bits in `*estimatedclauses` so the caller's independent-clause
  fallback skips them.
- `has_stats_of_kind(stats, requiredkind)`,
- `choose_best_statistics(stats, requiredkind, inh, **clause_attnums,
  **clause_exprs, nclauses)` — picks a `StatisticExtInfo` that
  covers the most clause attnums.

## Notable invariants / details

- All three magics are 32-bit fingerprints written at the head of
  each serialized bytea — `_deserialize` validates against the
  magic and refuses unknown values. [inferred]
- `MVDependencies.deps` is an array OF POINTERS (each entry
  variable-size); ndistinct/MCV use flexible array members directly.
  The asymmetry shows up in (de)serialization. [from-comment]
- `MCVList.types[STATS_MAX_DIMENSIONS]` is fixed size — so MCV is
  bounded at 8 dims, consistent with `STATS_MAX_DIMENSIONS`.
- `base_frequency` in MCVItem = product of per-column frequencies
  (the "independent" estimate). The deviation from `frequency` is
  what makes a multivariate MCV entry useful.

## Potential issues

- `STATS_MAX_DIMENSIONS = 8` is hard-coded in multiple
  representations (`MCVList.types`, the `int2vector stxkeys`
  signature for validators, etc.). A hypothetical raise must touch
  all of them coherently. [ISSUE-undocumented-invariant:
  STATS_MAX_DIMENSIONS is structurally hard-coded (likely)]
- Magic numbers are not in a single registry table; any patch
  adding a fourth kind will pick a fresh magic by convention.
  [ISSUE-style: no central magic registry (nit)]
- `choose_best_statistics` picks "the most clauses covered" but the
  header doesn't say what the tie-breaker is — implementation uses
  first-found. [ISSUE-doc-drift: tie-break rule not in header (nit)]
- The planner-side `is_or` boolean is a recent addition; older
  external code calling the pre-`is_or` signature would silently
  miss the parameter. [ISSUE-undocumented-invariant: ABI break
  unflagged (maybe)]
