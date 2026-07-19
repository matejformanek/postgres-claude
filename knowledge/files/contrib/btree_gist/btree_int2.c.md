# btree_int2.c

## One-line summary

GiST opclass for `smallint`. 4-byte key `[int16|int16]`. Trivial fixed-width
type using `btree_utils_num.c` and raw C comparators.

## Public API

Standard 8 + sortsupport + KNN distance:
`gbt_int2_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_int2.c:18-27`. Plus exported
`int2_dist` for `<->`.

## Key invariants

- Key: `[lower:int16|upper:int16]`, size 4 (`gbtreekey4`)
  `source/contrib/btree_gist/btree_int2.c:80`.
- Raw C comparators; no NaN, no collation, no truncation.
- KNN distance via `GET_FLOAT_DISTANCE` macro (cast to float8 fabs).

## Trust boundary / Phase D surface

- `int2_dist` (the SQL function): subtraction overflow checked via the
  `common/int.h` helpers — see int4.c for the same pattern.
- EXCLUDE constraint on smallint: standard integer equality. Sound.
- No detoast; pass-by-value type.

## Cross-references

- `source/src/include/common/int.h` — overflow-aware integer ops.

## Issues spotted

None significant.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
