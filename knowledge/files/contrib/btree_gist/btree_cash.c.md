# btree_cash.c

## One-line summary

GiST opclass for `money`. 16-byte key `[Cash|Cash]` (Cash is int64).
Identical structural pattern to int8 but with the `Cash` typedef and
`gbt_t_cash` type tag.

## Public API

Standard 8 + sortsupport + KNN:
`gbt_cash_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_cash.c:20-28`. Plus
`cash_dist`.

## Key invariants

- Key: `[lower:Cash|upper:Cash]` (Cash = int64), size 16 (`gbtreekey16`)
  `source/contrib/btree_gist/btree_cash.c:80-92`.
- Raw C int64 comparators.
- `gbt_cash_dist` uses `GET_FLOAT_DISTANCE(Cash, ...)` — same int64-to-double
  precision-loss caveat as int8.

## Trust boundary / Phase D surface

- Cash is locale-aware at the I/O level (`utils/cash.c`) but the in-memory
  representation is plain int64 — comparisons are locale-INVARIANT. Sound.
- EXCLUDE on money: sound integer-style equality.

## Issues spotted

- [ISSUE-PERF: KNN distance precision loss for huge cash values
  (> 2^53 cents ≈ $90 quadrillion). Theoretical. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
