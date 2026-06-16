# `src/backend/utils/adt/arrayutils.c`

- **File:** `source/src/backend/utils/adt/arrayutils.c` (264 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Small utility kit shared by `arrayfuncs.c`, `array_expanded.c`,
`arraysubs.c`, and ranges/typanalyze code. Subscript-to-offset math,
overflow-checked `ndim × dim[]` reduction, sub-array iteration helpers,
and the `typmod[]` string-array decoder.

## Key functions

- `ArrayGetOffset(n, dim, lb, indx)` (`:32-44`) — row-major linearizer.
  No overflow check: comment at `:27-30` asserts caller has already
  validated. [verified-by-code]
- `ArrayGetNItems(ndim, dims)` (`:57-60`) → calls
  `ArrayGetNItemsSafe(ndim, dims, NULL)`. [verified-by-code]
- `ArrayGetNItemsSafe(ndim, dims, escontext)` (`:67-102`) — multiplies
  `dims[]` with explicit `int64`-widened product and round-trip
  comparison to detect overflow (`:86-93`). Final guard against
  `MaxArraySize` (`:96-100`). Returns -1 + soft error on overflow when
  `escontext` provided. Negative dim treated as overflow indicator
  (`:79-84`). [verified-by-code]
- `ArrayCheckBounds(ndim, dims, lb)` (`:117-120`) /
  `ArrayCheckBoundsSafe(…, escontext)` (`:127-145`) — `pg_add_s32_overflow`
  on each `dims[i] + lb[i]` pair. Rejects arrays whose last subscript
  would reach `INT_MAX` (`:107-115` [from-comment]). [verified-by-code]
- `mda_get_range`/`mda_get_prod`/`mda_get_offset_values` (`:153-195`) —
  sub-array slice iteration helpers. All assume caller validated, no
  overflow checks. [from-comment]
- `mda_next_tuple(n, curr, span)` (`:208-225`) — lexicographic
  next-tuple bump used by `array_fill`/`array_set_slice` loops.
  [verified-by-code]
- `ArrayGetIntegerTypmods(arr, *n)` (`:233-263`) — extracts integer
  typmods from a `cstring[]` `ArrayType`. Rejects non-`cstring[]`,
  multi-D, or null-containing inputs (`:239-253`). Calls
  `pg_strtoint32` per element, which throws on overflow.
  [verified-by-code]

## Phase D notes

- **ArrayGetNItems** is the chokepoint for "untrusted dim[] from
  ArrayType header" — used by `array_in`, `array_recv`,
  `deconstruct_array`, etc. The int64-prod check at `:86-93` is the
  defense against malicious binary-format arrays claiming huge
  dimensions. [verified-by-code]
- `ArrayCheckBoundsSafe` complements this for the lower-bound side: an
  attacker sending `lb=INT_MAX, dim=10` would have `lb+dim` overflow
  caught at `:137`. [verified-by-code]
- `mda_*` helpers explicitly skip checks — relies on caller having run
  `ArrayGetNItems`/`ArrayCheckBounds` first.

## Potential issues

- [ISSUE-undocumented-invariant: `mda_*` helpers' "caller has
  validated" contract is comment-only; a future caller that forgets to
  run `ArrayGetNItems` first could overflow `prod[]` silently (low)]
- [ISSUE-correctness: `ArrayGetIntegerTypmods` does `palloc(*n *
  sizeof(int32))` where `*n` is the deconstructed array length — bounded
  by `MaxArraySize` via the upstream `ArrayGetNItems`, so safe in
  practice (info)]

## Cross-references

- `source/src/include/utils/array.h` — `MaxArraySize`, `MAXDIM`,
  `ArrayType` layout, function decls.
- `source/src/include/common/int.h` — `pg_add_s32_overflow`.
- `source/src/backend/utils/adt/arrayfuncs.c` — the heavy consumer.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[verified-by-code]` × 6
- `[from-comment]` × 2
