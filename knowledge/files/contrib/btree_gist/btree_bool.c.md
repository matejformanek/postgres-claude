# btree_bool.c

## One-line summary

GiST opclass for `boolean`. 2-byte key `[bool|bool]` — the smallest
`gbtree_ninfo` `indexsize` in the framework.

## Public API

Standard 8 + sortsupport: `gbt_bool_{compress,fetch,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_bool.c:18-25`. No KNN (`f_dist = NULL`,
default-initialised).

## Key invariants

- Key: `[lower:bool|upper:bool]`, size 2 (`gbtreekey2`)
  `source/contrib/btree_gist/btree_bool.c:75`.
- `gbt_bool_consistent` casts query to `bool` via `PG_GETARG_INT16` —
  works because `bool` in PG is stored in 1 byte but passed as int16
  `source/contrib/btree_gist/btree_bool.c:109`.

## Trust boundary / Phase D surface

- Three-state truth doesn't apply: NULLs are screened by GiST core.
- EXCLUDE on bool: trivially sound (only 2 possible values).

## Issues spotted

- [ISSUE-MINOR: `boolKEY` struct has implicit padding (`sizeof = 2` only
  on systems where bool is 1 byte). `Assert(indexsize >= 2*size)` in
  `gbt_num_compress` checks `2 >= 2*1 = 2` — exactly equal. Brittle if
  someone changed `sizeof(bool)`. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
