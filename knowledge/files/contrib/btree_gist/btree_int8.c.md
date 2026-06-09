# btree_int8.c

## One-line summary

GiST opclass for `bigint`. 16-byte key `[int64|int64]`. Identical structural
pattern to int2/int4.

## Public API

Standard 8 + sortsupport + KNN:
`gbt_int8_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_int8.c:18-26`. Plus exported
`int8_dist`.

## Key invariants

- Key: `[lower:int64|upper:int64]`, size 16 (`gbtreekey16`)
  `source/contrib/btree_gist/btree_int8.c:80-92`.

## Trust boundary / Phase D surface

- `gbt_int8_dist` (`GET_FLOAT_DISTANCE`) casts int64 → float8 before
  subtraction. **Lossy** for int64 values above 2^53. The KNN distance
  ordering becomes coarse-grained for huge bigints — same value class
  collapses. Operational, not correctness (the recheck path is exact).
- EXCLUDE on bigint: sound.

## Issues spotted

- [ISSUE-PERF: KNN `gbt_int8_dist` via `GET_FLOAT_DISTANCE` loses precision
  for bigints exceeding double's 53-bit mantissa. KNN ordering of two
  bigints differing only in low bits is non-deterministic. (LOW)]
