# btree_utils_num.c (+ btree_utils_num.h)

## One-line summary

Shared framework for every **fixed-size**, non-collation-aware `btree_gist`
opclass: defines the `gbtree_ninfo` vtable, the `[lower|upper]` packed key
representation, and one copy each of `compress`/`fetch`/`union`/`same`/
`consistent`/`distance`/`picksplit` parameterised by per-type comparator
callbacks.

## Public API

- Header types/macros (`btree_utils_num.h`):
  - `typedef char GBT_NUMKEY` — opaque byte storage; per-type keys are laid
    out as `[lower : tinfo->size][upper : tinfo->size]`
    `source/contrib/btree_gist/btree_utils_num.h:13`.
  - `GBT_NUMKEY_R { lower, upper }` — readable view of a key
    `source/contrib/btree_gist/btree_utils_num.h:16`.
  - `gbtree_ninfo` — per-type vtable: type tag `t`, datum `size`, index storage
    `indexsize` (must be `≥ 2*size`, asserted), 5 boolean comparators + one
    `int cmp` qsort comparator + an optional `float8 dist` for KNN
    `source/contrib/btree_gist/btree_utils_num.h:33`.
  - `Nsrt { i; GBT_NUMKEY *t; }` — sort vector entry for picksplit
    `source/contrib/btree_gist/btree_utils_num.h:25`.
  - `penalty_num(...)` macro — see "Notable internals" below
    `source/contrib/btree_gist/btree_utils_num.h:63`.
  - `INTERVAL_TO_SEC(ivp)` — approximate seconds-from-Interval (used in
    `btree_interval.c`, `btree_time.c`)
    `source/contrib/btree_gist/btree_utils_num.h:84`.
  - `GET_FLOAT_DISTANCE(t, a, b)` — `fabs((float8) *a - (float8) *b)` casting
    through `float8` `source/contrib/btree_gist/btree_utils_num.h:89`.

- Exported functions:
  - `gbt_num_compress(entry, tinfo)` — given a leaf datum, copy the scalar twice
    into a fresh `[v|v]` index key `source/contrib/btree_gist/btree_utils_num.c:13`.
  - `gbt_num_fetch(entry, tinfo)` — extract the original Datum from an
    `[lower|upper]` storage key for index-only scans
    `source/contrib/btree_gist/btree_utils_num.c:107`.
  - `gbt_num_union(out, entryvec, tinfo, flinfo)` — pairwise-min/pairwise-max
    over the entry vector `source/contrib/btree_gist/btree_utils_num.c:172`.
  - `gbt_num_same(a, b, tinfo, flinfo)` — lower == lower && upper == upper
    `source/contrib/btree_gist/btree_utils_num.c:212`.
  - `gbt_num_bin_union(u, e, tinfo, flinfo)` — fold one entry into a running
    union `source/contrib/btree_gist/btree_utils_num.c:228`.
  - `gbt_num_consistent(key, query, strategy, is_leaf, tinfo, flinfo)` — the
    big switch matching all 6 strategies (5 nbtree + `<>`)
    `source/contrib/btree_gist/btree_utils_num.c:263`.
  - `gbt_num_distance(key, query, is_leaf, tinfo, flinfo)` — KNN distance from
    point to range `source/contrib/btree_gist/btree_utils_num.c:316`.
  - `gbt_num_picksplit(entryvec, v, tinfo, flinfo)` — sort entries by
    `f_cmp`, split at the median `source/contrib/btree_gist/btree_utils_num.c:339`.

## Key invariants

- **Compressed key layout:** every fixed-size opclass stores keys as exactly
  `2 * tinfo->size` bytes (the local union inside `gbt_num_compress` is large
  enough for the biggest scalar type, then `memcpy`'d twice into the storage).
  The header `indexsize` constants like `8` for `gbtreekey8` MUST be `≥ 2 *
  tinfo->size`, enforced by `Assert(tinfo->indexsize >= 2 * tinfo->size)` in
  both compress and fetch `source/contrib/btree_gist/btree_utils_num.c:88,112`.
- **Leaf invariant:** on a leaf entry, `lower == upper`. `gbt_num_fetch` relies
  on this — it returns the lower bound only
  `source/contrib/btree_gist/btree_utils_num.c:115`.
- **Consistent / `is_leaf` distinction:** for `BTLessStrategy`,
  `BTGreaterStrategy`, and `BTEqualStrategy`, leaf entries use strict comparison
  while internal node entries widen to non-strict (the upper/lower bound MIGHT
  contain a match). This is the GiST "lossy on internal nodes, exact on leaves"
  contract. `*recheck = false` in callers means leaves are also exact, since
  fixed-size keys are not truncated `source/contrib/btree_gist/btree_utils_num.c:272-308`.
- **Not-equal strategy is true unless `key == [v,v]` and `v == query`** — i.e.
  it's only useful at leaves; on internal nodes it always returns true since
  any non-singleton range trivially contains a `v ≠ query`
  `source/contrib/btree_gist/btree_utils_num.c:299`.
- **`gbt_num_consistent` is collation-blind** — the header comment explicitly
  states "no datatypes that use this routine are collation-aware"
  `source/contrib/btree_gist/btree_utils_num.c:259`.

## Notable internals

### The `penalty_num` macro

`source/contrib/btree_gist/btree_utils_num.h:63`. Computes a GiST penalty
(cost of inserting a new key into an existing union):

- If neither side of the union grows (`nupper <= oupper` and `nlower >= olower`),
  penalty is 0.
- Otherwise: `tmp = expansion above + expansion below` (each scaled by 0.49
  to dodge overflow when computing the ratio); result is the ratio
  `tmp / (tmp + old_width)` plus `FLT_MIN`, then multiplied by
  `FLT_MAX / (natts+1)`.
- The `* (FLT_MAX / natts+1)` scaling means the absolute penalty is always
  huge — what matters is the *relative* penalty between candidate parents.
- The macro reads `((GISTENTRY *) PG_GETARG_POINTER(0))->rel->rd_att->natts`
  directly inside a macro — implicitly assumes the caller is a PG_FUNCTION_ARGS
  function with argument 0 a `GISTENTRY *`. Subtle coupling.

### `gbt_num_compress` — the union of scalar types

`source/contrib/btree_gist/btree_utils_num.c:20` — a single `union` of all
indexable scalar types (`bool, int16, int32, int64, float4, float8, DateADT,
TimeADT, Timestamp, Cash`) is used to materialise the scalar before
`memcpy`'ing twice. The `switch (tinfo->t)` selects the union member. Default
arm `leaf = DatumGetPointer(entry->key)` is taken for types not in the union
(macaddr, uuid, interval, inet, …) — those types are passed by reference and
the caller's pointer is already valid.

### `gbt_num_picksplit` — simple median split

`source/contrib/btree_gist/btree_utils_num.c:339`. Sorts entries via
`qsort_arg(..., tinfo->f_cmp, flinfo)` then splits at exactly the midpoint —
no rebalancing for skew. This is fine because GiST does not need a balanced
split for correctness; an unbalanced index just costs more page splits.

## Trust boundary / Phase D surface

- **`gbt_num_compress` switch arms and `Assert(indexsize >= 2*size)`** — the
  type tag `tinfo->t` is supplied by the per-type opclass's static `gbtree_ninfo
  tinfo` (read-only data), not by user input. A misconfigured per-type tinfo
  (e.g. `indexsize = 4` with `size = 8`) is caught only in assert builds; in
  release builds it would silently corrupt the index page.
- **`gbt_num_fetch` mirrors the switch** — if a per-type opclass adds a new
  `gbtree_type` enum value but forgets to extend the switch arm in *both*
  compress (line 37+) and fetch (line 119+), index-only scans on that type
  return the raw pointer Datum unmodified — usually harmless for fixed-size
  scalars but type-system-incorrect.
- **`gbt_num_consistent` collation policy** — the function deliberately does
  not pass `Oid collation` because none of its callers are collation-aware
  (int, float, date, oid, …). If a future type that *is* collation-aware were
  routed through `btree_utils_num.c` (which it shouldn't be — that's
  `btree_utils_var.c`'s job), comparison would silently use C-locale ordering.
- **`penalty_num` scaling factor 0.49** — the comment says "avoids floating
  point overflows" but this macro will still produce undefined results if
  `oupper / olower / nupper / nlower` are NaN. None of the integer types can
  produce NaN; `float4`/`float8` callers (`btree_float4.c`, `btree_float8.c`)
  rely on this macro and DO pass NaN through unchecked. See float4/float8 docs.
- **`gbt_num_consistent` BtreeGistNotEqualStrategyNumber on internal nodes**
  is the corner where EXCLUDE constraints can degrade: if a key range happens
  to collapse to a single point `[v,v]` on an internal node (rare but possible
  after many deletes), `<>` falsely returns "no match" for `query = v`,
  missing tuples below. Re-check via `*recheck` does NOT cover this since the
  callers all set `recheck = false`. The PG docs warn that EXCLUDE with `<>`
  on btree_gist is not a normal pattern, but the bound exists.
  See ISSUE below.
- **No NULL handling** — relies on GiST core's NULL screening before the
  consistent function is invoked. Per-type compress functions also rely on
  this: `DatumGetFloat4` of a NULL Datum is uninitialised memory.

## Cross-references

- `source/src/backend/access/gist/gistutil.c` — the GiST core that calls into
  every `gbt_*_consistent`/`union`/`penalty`/`picksplit`.
- `source/src/include/utils/cash.h`, `source/src/include/utils/date.h`,
  `source/src/include/utils/timestamp.h` — the type accessors used by the
  switch in `gbt_num_compress`.
- `knowledge/files/contrib/btree_gist/btree_gist.c.md` — the `gbtree_type`
  enum tag values.

## Issues spotted

- [ISSUE-CORRECTNESS-EDGE: `gbt_num_consistent` `BtreeGistNotEqualStrategyNumber`
  returns false on a singleton internal-node range `[v,v]` when `query == v`,
  even though the subtree below could still contain values other than `v` if a
  cascading union has not yet been recomputed. In practice GiST keeps internal
  ranges tight after splits, so this is theoretical, but the function does not
  set `*recheck = true` to cover it. (LOW)]
- [ISSUE-PERF: `gbt_num_picksplit` uses a simple median split with no
  consideration of overlap minimisation; for skewed inputs (e.g. monotonically
  increasing serial PKs) this produces highly overlapping internal-node ranges
  and degrades query selectivity. (LOW — design choice, but worth flagging
  vs core nbtree which has more sophisticated split heuristics)]
- [ISSUE-UNDEFINED-BEHAVIOR: `penalty_num` macro performs arithmetic on
  caller-provided `olower/oupper/nlower/nupper` without checking for NaN; for
  `float4`/`float8`, `NaN > X` is always false, which silently zeroes the
  penalty for NaN entries → NaN keys cluster pathologically in the index.
  (MED — affects index quality, not correctness, on NaN-heavy float data)]
- [ISSUE-MAINTAINABILITY: `penalty_num` references `((GISTENTRY *)
  PG_GETARG_POINTER(0))->rel->rd_att->natts` inside the macro, hardcoding the
  assumption that the calling function takes a GISTENTRY at arg position 0.
  This couples the macro to its caller signature; if any per-type penalty
  function ever reorders its args this silently breaks. (LOW)]
