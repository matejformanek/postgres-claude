# btree_oid.c

## One-line summary

GiST opclass for `oid` — 8-byte key `[Oid|Oid]`, unsigned-int32 ordering.

## Public API

Standard 8 + sortsupport + KNN:
`gbt_oid_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_oid.c:18-26`. Plus `oid_dist`.

## Key invariants

- Key: `[lower:Oid|upper:Oid]`, size 8 (`gbtreekey8`)
  `source/contrib/btree_gist/btree_oid.c:85-97`.
- Raw C comparators on `Oid` (unsigned 32-bit).
- KNN `gbt_oid_dist` uses signed-safe subtraction (`if (aa < bb) bb - aa`)
  to avoid unsigned wraparound `:72-82`.

## Trust boundary / Phase D surface

- OIDs wrap around (32-bit unsigned). `gbt_oid_dist` returns `|a - b|`
  without considering wraparound — a near-zero and a near-2^32-1 OID are
  considered "far apart" by KNN, which matches the index ordering.
- EXCLUDE on oid: sound.

## Issues spotted

None significant.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
