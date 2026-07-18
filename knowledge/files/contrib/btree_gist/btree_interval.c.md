# btree_interval.c

## One-line summary

GiST opclass for `interval`. 32-byte key `[Interval|Interval]` (16 bytes
each). Has custom decompress for legacy alignment, plus `abs_interval`
helper exported to other btree_gist files.

## Public API

`gbt_intv_{compress,fetch,decompress,union,picksplit,consistent,distance,
penalty,same,sortsupport}` `source/contrib/btree_gist/btree_interval.c:20-29`.
Note the explicit `gbt_intv_decompress` (most types use the generic
`gbt_decompress`).

Also exports `abs_interval(Interval *)` — used by time/timetz distance code.

## Key invariants

- Key: `[lower:Interval|upper:Interval]`, size 32 (`gbtreekey32`).
- `INTERVALSIZE 16` constant `source/contrib/btree_gist/btree_interval.c:96`
  — comment says this is for legacy alignment; "obsolete with the current
  definition of Interval, but was real before a separate 'day' field".
- Interval comparison uses fuzzy month/day → seconds conversion
  (`INTERVAL_TO_SEC` macro): months treated as 30 days, days as 24 hours.
  **This is approximate** — two intervals that are "equal" by
  `INTERVAL_TO_SEC` may still differ in their stored fields.

## Trust boundary / Phase D surface

- **Approximate equality vs `interval_eq`:** `interval_eq` (the SQL
  operator) compares all three fields (months, days, microseconds) exactly.
  `gbt_intv_dist` and `INTERVAL_TO_SEC`-based penalty use the approximate
  scalar. **The consistent function uses `interval_eq`, not the scalar**, so
  EXCLUDE constraints are sound; the scalar is only used for KNN ordering
  and penalty.
- EXCLUDE on interval: sound (uses exact `interval_eq`).
- `abs_interval` at `:113` uses a static const zero Interval — safe since
  the function doesn't mutate the static.

## Issues spotted

- [ISSUE-KNN-APPROX: KNN distance via `INTERVAL_TO_SEC` (30-day months) can
  produce surprising ordering: `'1 month'` and `'30 days'` have distance 0
  via the scalar, but `interval_cmp` treats them as different. KNN
  semantics are intentionally lossy here, but worth noting. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
