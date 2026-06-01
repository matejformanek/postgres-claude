# `src/backend/utils/adt/array_userfuncs.c`

- **File:** `source/src/backend/utils/adt/array_userfuncs.c` (2047 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

User-visible array support functions — the SQL-callable layer over
`arrayfuncs.c`'s lower-level primitives. (`array_userfuncs.c:1-4`
[from-comment])

## What lives here

### Element/array combining
- `array_append(arr, elem)` (`:140`) — `arr || elem`.
- `array_prepend(elem, arr)` (`:223`) — `elem || arr`.
- `array_cat(arr1, arr2)` (`:317`) — `arr1 || arr2`. Has its own
  dimension-matching rules: appending a 1-D to another 1-D produces
  1-D; concatenating with a higher-D respects shape.
- `array_append_support` / `array_prepend_support` (`:193`, `:286`) —
  planner support functions (`SUPPORT_REQUEST_SIMPLIFY`) that fold
  constant-folded array concatenation at plan time.

### `array_agg` family — the SUM-shape aggregate over elements
- `array_agg_transfn` (`:556`) — single-D variant. Accumulates into
  an `ArrayBuildState` (in `arrayfuncs.c`).
- `array_agg_combine` (`:602`) — parallel-aggregate combine.
- `array_agg_serialize` / `_deserialize` (`:699`, `:788`) — for
  parallel transit through DSM.
- `array_agg_finalfn` (`:899`) — emit final array.
- `array_agg_array_*` (`:934-1277`) — the multi-D variant (`array_agg` of
  arrays), which preserves inner shape and concatenates outer dim.

### Search
- `array_position(arr, elem)` / `array_position_start(arr, elem, start)`
  (`:1310`, `:1316`) — first index of `elem` (or NULL).
- `array_positions(arr, elem)` (`:1484`) — all indexes.
- Shared core `array_position_common` (`:1329`) — uses the element
  type's default btree opclass equality.

### Sampling / reordering
- `array_shuffle(arr)` (`:1711`), `array_shuffle_n(arr, n, keep_lb, ...)`
  (`:1622`) — Fisher-Yates using `pg_prng` (note: `common/pg_prng.h`
  imported at top, not the legacy `random()`).
- `array_sample(arr, n)` (`:1745`) — random subset.
- `array_reverse(arr)` (`:1859`), `array_reverse_n` (`:1784`) — reverse
  along outer dim.

### Misc
- `fetch_array_arg_replace_nulls` (`:81`) — coerce a possibly-NULL
  array arg into a valid empty array, so callers needn't special-case
  the NULL input. Used by append/prepend/cat.

## Notable design notes

- All combining operations check that the element type matches the
  array's `elemtype` OID exactly (not a runtime cast — the SQL coercion
  must happen earlier).
- `array_agg`'s parallel-aggregate variants (`combine/serialize/
  deserialize`) are non-trivial because the accumulator state holds
  Datum + isnull arrays plus the element type's typlen/byval/align that
  must be re-discovered after DSM transit.
- The `_support` planner functions for append/prepend are notable —
  they let `'{1,2}'::int[] || 3` collapse at plan time, which matters
  for prepared statements that build arrays via repeated concatenation.

## Cross-references

- `source/src/backend/utils/adt/arrayfuncs.c` — primitives this file
  composes (`construct_md_array`, `array_iterate`, `deconstruct_array`,
  `accumArrayResult`/`makeArrayResult` for the agg path, etc.).
- `source/src/include/utils/array.h` — declarations.
- `source/src/include/common/pg_prng.h` — RNG for shuffle/sample.

## Confidence tag tally

- `[verified-by-code]` × ~4
- `[from-comment]` × ~2
