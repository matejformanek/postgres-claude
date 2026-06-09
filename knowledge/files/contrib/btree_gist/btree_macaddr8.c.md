# btree_macaddr8.c

## One-line summary

GiST opclass for `macaddr8` (8-byte EUI-64 MAC address). 16-byte key
`[macaddr8|macaddr8]` — no padding needed since 2*8 = 16.

## Public API

Standard 7 + sortsupport: `gbt_macad8_{compress,fetch,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_macaddr8.c:21-28`. No KNN.

## Key invariants

- Key: `[lower:macaddr8|upper:macaddr8]`, size 16 (`gbtreekey16`)
  `source/contrib/btree_gist/btree_macaddr8.c:13-18`.
- Internal `mac8_2_uint64` converts to uint64 for penalty (same pattern as
  macaddr).

## Trust boundary / Phase D surface

- EUI-64 → uint64 is a lossless conversion (8 bytes fit). Sound.
- EXCLUDE on macaddr8: sound.

## Issues spotted

None significant.
