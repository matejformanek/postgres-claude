# btree_ts.c

## One-line summary

GiST opclass for `timestamp` and `timestamptz`. 16-byte key
`[Timestamp|Timestamp]` (Timestamp is int64 microseconds-since-epoch).

## Public API

`gbt_ts_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` plus `gbt_tstz_compress`, `gbt_tstz_consistent`,
`gbt_tstz_distance` `source/contrib/btree_gist/btree_ts.c:23-34`.

## Key invariants

- Key: `[lower:Timestamp|upper:Timestamp]`, size 16 (`gbtreekey16`).
- timestamptz is stored as UTC microseconds — same representation as
  timestamp; the type discrimination is purely semantic.
- KNN dist returns `+infinity` if either operand is `TIMESTAMP_NOT_FINITE`
  `source/contrib/btree_gist/btree_ts.c:115-116`.

## Trust boundary / Phase D surface

- **Timestamp infinity** is explicitly handled in `gbt_ts_dist` (returns
  `get_float8_infinity()` for not-finite operands). Penalty/union do NOT
  special-case infinity — they rely on `timestamp_cmp` (which orders
  -infinity < everything < +infinity) producing consistent results.
- EXCLUDE on timestamp: sound via `timestamp_eq`.

## Issues spotted

None significant for security/correctness; standard fixed-width pattern.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
