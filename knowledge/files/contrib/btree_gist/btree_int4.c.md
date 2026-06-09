# btree_int4.c

## One-line summary

GiST opclass for `integer`. 8-byte key `[int32|int32]`. Identical structural
pattern to int2/int8.

## Public API

Standard 8 + sortsupport + KNN distance:
`gbt_int4_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_int4.c:18-26`. Plus exported
`int4_dist` for `<->`.

## Key invariants

- Key: `[lower:int32|upper:int32]`, size 8 (`gbtreekey8`)
  `source/contrib/btree_gist/btree_int4.c:78-90`.
- KNN `gbt_int4_dist` uses `GET_FLOAT_DISTANCE` (casts through float8 so no
  int overflow).

## Trust boundary / Phase D surface

- `int4_dist` (SQL function) uses overflow-checked subtraction from
  `common/int.h`.
- EXCLUDE on int4: sound integer equality.

## Issues spotted

None significant.
