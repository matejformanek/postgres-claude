# `contrib/btree_gist/btree_utils_num.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 117
- **Source:** `source/contrib/btree_gist/btree_utils_num.h`

Header that defines the *numeric-key* abstraction layer for
`btree_gist`. Declares: the key-storage typedefs (`GBT_NUMKEY`,
`GBT_NUMKEY_R`), the per-type info struct `gbtree_ninfo` (a vtable),
two cross-cutting macros (`penalty_num`, `INTERVAL_TO_SEC`), and the
function prototypes that every numeric-type opclass body in
`btree_int4.c`/`btree_float8.c`/`btree_ts.c`/etc. calls back into in
`btree_utils_num.c`. [verified-by-code]

## API / entry points (types)

- `typedef char GBT_NUMKEY` `:13` — a raw byte buffer holding
  `[lower][upper]` packed back-to-back. Size = `2 *
  tinfo->indexsize`. [verified-by-code]
- `typedef struct { const GBT_NUMKEY *lower, *upper; } GBT_NUMKEY_R`
  `:16-20` — the "readable" form, just pointers into the packed
  buffer for `lower` and `upper`. [verified-by-code]
- `typedef struct { int i; GBT_NUMKEY *t; } Nsrt` `:24-28` — sort
  entry used by `gbt_num_picksplit`. [verified-by-code]
- `typedef struct { enum gbtree_type t; int32 size; int32 indexsize;
  bool (*f_gt)(const void *, const void *, FmgrInfo *); ...; float8
  (*f_dist)(...); } gbtree_ninfo` `:33-51` — the per-type vtable.
  - `size` = sizeof input value, 0 means variable.
  - `indexsize` = size of the value as stored in the index.
  - Six comparison methods (`f_gt/ge/eq/le/lt/cmp`) all
    `(const void *, const void *, FmgrInfo *) -> bool/int`.
  - One distance method `f_dist` for kNN support, `float8`-valued.
  [verified-by-code]

## API / entry points (functions)

All declared `extern`, defined in `btree_utils_num.c`:

- `abs_interval(Interval *)` `:92` — `INTERVAL_TO_SEC` uses, plus
  some opclass-specific callers. [verified-by-code]
- `gbt_num_consistent(key, query, strategy, is_leaf, tinfo, flinfo)`
  `:94-96` — implements the GiST `consistent` support function for
  all numeric types. Delegates per-strategy to one of the `f_*`
  callbacks. [verified-by-code]
- `gbt_num_distance(key, query, is_leaf, tinfo, flinfo)` `:98-99` —
  kNN ordering distance via `f_dist`. [verified-by-code]
- `gbt_num_picksplit(entryvec, v, tinfo, flinfo)` `:101-102` —
  splitting heuristic for index pages. Uses `Nsrt` sort. [verified-by-code]
- `gbt_num_compress(entry, tinfo)` `:104` — produce a packed
  `GBT_NUMKEY` from an input value. [verified-by-code]
- `gbt_num_fetch(entry, tinfo)` `:106` — inverse for index-only
  scans: extract the lower bound from a leaf key. [verified-by-code]
- `gbt_num_union(out, entryvec, tinfo, flinfo)` `:108-109` — compute
  the bounding interval of a set of keys. [verified-by-code]
- `gbt_num_same(a, b, tinfo, flinfo)` `:111-112` — exact-equality
  test on packed keys. [verified-by-code]
- `gbt_num_bin_union(u, e, tinfo, flinfo)` `:114-115` — binary union
  helper used by `gbt_num_union`. [verified-by-code]

## Macros worth noting

- **`penalty_num(result, olower, oupper, nlower, nupper)` `:63-76`**
  — the standard GiST page-split penalty for numeric ranges.
  Uses 0.49 scale factors to avoid overflow when computing
  `FLT_MAX`-bounded penalties. Final scale by `FLT_MAX /
  (entry->rel->rd_att->natts + 1)`. [verified-by-code]
- **`INTERVAL_TO_SEC(ivp) :84-87`** — approximate Interval-to-seconds
  used by `time`, `timetz`, and `interval` opclasses for a unified
  distance metric. Uses 30-day months and 24-hour days — APPROXIMATE.
  [verified-by-code + from-comment]
- **`GET_FLOAT_DISTANCE(t, arg1, arg2) :89`** — `fabs(a - b)` cast
  through `float8`. Used by `btree_int*` and `btree_float*` for kNN.
  [verified-by-code]

## Notable invariants / details

- **INV-1: A `GBT_NUMKEY` is exactly `2 * tinfo->indexsize` bytes**
  of `[lower-bytes][upper-bytes]`. All `gbt_num_*` functions in
  `btree_utils_num.c` rely on this packing. [verified-by-code]
- **INV-2: `f_cmp` returns int (sortable), `f_eq/gt/...` return
  bool.** Different vtable entries for different result types
  because the existing PG comparison functions vary in return
  conventions. [verified-by-code]
- **INV-3: `INTERVAL_TO_SEC` is an APPROXIMATION**: it treats months
  as 30 days and ignores leap-year/DST detail. Used only for kNN
  ordering, not for correctness of consistent-checks. [from-comment]
  **[ISSUE-undocumented-invariant: 30-day-month approximation could
  surprise distance-by-interval users (nit)]**
- **INV-4: `penalty_num` returns FLT-scaled penalty so GiST's
  `add_path`-style comparison stays in `float4` range without
  overflow.** Each factor of 0.49 caps the partial penalty at half
  of FLT_MAX. [verified-by-code]

## Potential issues

- `:74` `PG_GETARG_POINTER(0)` is referenced inside the
  `penalty_num` macro — coupling the macro to its expansion site
  (must be called from a function with `fcinfo` and arg 0 being a
  `GISTENTRY *`). Macro expansion makes this implicit; no way to
  reuse `penalty_num` from a non-fmgr context. [verified-by-code]
  **[ISSUE-style: penalty_num macro hardcodes PG_GETARG_POINTER(0)
  (nit)]**
- `:31` Comment `/* type description */` is sparse for a 19-field
  struct. Per-field docs would help maintainers. [verified-by-code]
  **[ISSUE-doc-drift: gbtree_ninfo field semantics under-documented
  (nit)]**
- `:38-40` `enum gbtree_type t` in the struct is unused for some
  consumers — most call paths know their type at compile time. Dead
  field for those, but kept for uniformity. [inferred]
- `:71-75` `penalty_num` rescales by `(natts + 1)` to handle
  multi-column GiST. For natts very large (e.g. multi-column index
  with many columns), the scale becomes small. Unlikely in practice.
  [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `btree_gist`](../../../issues/btree_gist.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
