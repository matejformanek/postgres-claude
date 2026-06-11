# `src/include/statistics/extended_stats_internal.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~144
- **Source:** `source/src/include/statistics/extended_stats_internal.h`

Internal helpers for building, serializing and applying extended
statistics (ndistinct / functional dependencies / multi-column MCV).
Consumed by `backend/statistics/{mvdistinct,dependencies,mcv,extended_stats}.c`.
Not part of the public extension API; consumers must include this
through the backend-only header chain. [verified-by-code]

## API / declarations

### Helpers

- `StdAnalyzeData { eqopr, eqfunc, ltopr }` — lookup result for a
  column's `=`/`<` operator info from analyze.c.
- `ScalarItem { Datum value; int tupno }` — per-value reference back
  to the source tuple.
- `DimensionInfo { nvalues, nbytes, nbytes_aligned, typlen,
  typbyval }` — (de)serialization metadata per attribute.
- `MultiSortSupportData { ndims; SortSupportData ssup[FLEX] }` —
  variable-length sort support for multi-column sorts.
- `MultiSortSupport` (typedef of pointer).
- `SortItem { Datum *values; bool *isnull; int count }` — multi-col
  sort key + frequency.
- `StatsBuildData { numrows, nattnums, attnums, stats (per-att
  VacAttrStats), values (numrows × nattnums), nulls (same) }` —
  unified input format to all extended-stats builders.

### ndistinct API

- `statext_ndistinct_build(totalrows, *data)` → `MVNDistinct*`.
- `_serialize` / `_deserialize` (bytea ↔ struct).
- `_validate(ndistinct, stxkeys, numexprs, elevel)` — for the new
  `pg_set_attribute_stats`-style import paths.
- `_free`.

### Functional-dependencies API (same shape)

- `statext_dependencies_build` / `_serialize` / `_deserialize` /
  `_validate` / `_free`.

### MCV API

- `statext_mcv_build(data, totalrows, stattarget)`.
- `_serialize(mcvlist, stats)` — needs typlen/typbyval per dim,
  hence `VacAttrStats**` arg.
- `_deserialize` / `_free`.
- `statext_mcv_import(elevel, numattrs, atttypids, atttypmods,
  atttypcolls, nitems, mcv_elems, mcv_nulls, freqs, base_freqs)`
  → Datum bytea — used by user-facing pg_*_stats import functions.

### Multi-sort helpers

- `multi_sort_init(ndims)`, `multi_sort_add_dimension`,
  `multi_sort_compare`, `multi_sort_compare_dim`,
  `multi_sort_compare_dims`.
- `compare_scalars_simple`, `compare_datums_simple`.
- `build_attnums_array(attrs Bitmapset, nexprs, *numattrs)`,
- `build_sorted_items(data, *nitems, mss, numattrs, attnums)`.

### Estimation helpers

- `examine_opclause_args(args, **expr, **cst, *expronleft)` —
  decompose a `Var op Const` pattern.
- `mcv_combine_selectivities(simple, mcv_sel, mcv_basesel,
  mcv_totalsel)` — combines a non-MCV simple selectivity with the
  MCV-derived overlap selectivity. The signature is the key formula
  for the planner's combine path.
- `mcv_clauselist_selectivity(root, stat, clauses, varRelid,
  jointype, sjinfo, rel, *basesel, *totalsel)`,
- `mcv_clause_selectivity_or(root, stat, mcv, clause, **or_matches,
  *basesel, *overlap_mcvsel, *overlap_basesel, *totalsel)` — OR
  variant.

## Notable invariants / details

- All four extended-stat kinds (ndistinct, deps, MCV) share the
  identical (build / serialize / deserialize / validate / free)
  shape — easy template for a new kind. [inferred]
- `StatsBuildData.values` is `Datum**`: outer index is attribute
  number into `attnums[]`, inner is tuple index. The two-level
  layout simplifies builder code that iterates by attribute.
  [inferred]
- `multi_sort_compare` is the standard qsort-style `void *`
  callback; `arg` carries the `MultiSortSupport`.

## Potential issues

- `mcv_combine_selectivities` and `mcv_clause_selectivity_or`
  signatures encode the MCV/non-MCV split formula by parameter
  list. A change to the formula must update both signatures or
  drift silently. [ISSUE-undocumented-invariant: combine formula
  is encoded in signature (likely)]
- `_validate` functions take `int elevel` (so caller picks ERROR
  vs WARNING) but the header doesn't say which levels are
  expected. [ISSUE-doc-drift: elevel contract on _validate (nit)]
- `examine_opclause_args` doesn't say how it signals a non-matching
  clause — the implementation returns false; callers must check.
  [ISSUE-doc-drift: examine_opclause_args false-return path (nit)]
- The header has no `_PG_EXTENDED_STATS_INTERNAL_H_` style include
  guard cookie — uses `EXTENDED_STATS_INTERNAL_H`, consistent with
  the rest of `src/include/statistics/`. None.
