# `src/include/statistics/*.h` (combined)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/include/statistics/`

## `statistics.h`

Public surface used by `commands/analyze.c` and `optimizer/path/clausesel.c`:

- `StatisticExtInfo` — planner-side cached descriptor for one
  `pg_statistic_ext` row: oid, kind char (`d`,`f`,`m`,`e` =
  dependencies/ndistinct/mcv/exprs), `inherit`, `keys` (bitmapset),
  `exprs` (list). Built by `get_relation_statistics`.
- Kind chars: `STATS_EXT_DEPENDENCIES`, `STATS_EXT_NDISTINCT`,
  `STATS_EXT_MCV`, `STATS_EXT_EXPRESSIONS`.
- `STATS_MAX_DIMENSIONS = 8` — cap on columns per stats object.
- Public function declarations: `BuildRelationExtStatistics`,
  `ComputeExtStatisticsRows`, `statext_is_kind_built`,
  `statext_clauselist_selectivity`, `examine_opclause_args`,
  `mcv_combine_selectivities`.

## `extended_stats_internal.h`

Shared internal API between the kind-specific files:

- `StatsBuildData {numrows, nattnums, attnums, stats, values, nulls}` —
  the row-major sampled data block passed to each builder.
- `MVDependencies` / `MVDependency` — typed.
- `MVNDistinct` / `MVNDistinctItem` — typed.
- `MCVList` / `MCVItem` — typed (one MCVItem holds full per-column
  Datum/null arrays + frequency + base_frequency).
- `MultiSortSupport` — shared multi-column sort scaffolding used by
  builders. `multi_sort_init/compare`.
- Prototypes for `statext_dependencies_build/load/serialize/deserialize`
  and equivalents for ndistinct and mcv.

## `statistics_format.h`

On-disk binary layout constants (magic numbers, type ids) — kept
separate so frontend tools could parse without dragging in the build
code. Currently used internally only.

## `stat_utils.h`

Helpers for `pg_set_*_stats()` SQL functions (PG17+): validating user-
supplied stat arrays for `attribute_stats.c`/`relation_stats.c`.
