# btree_macaddr.c

## One-line summary

GiST opclass for `macaddr` (6-byte IEEE-802 MAC address). 16-byte key
`[macaddr|macaddr|pad[4]]` — pad bytes round struct size up to
`gbtreekey16`.

## Public API

Standard 7 + sortsupport: `gbt_macad_{compress,fetch,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_macaddr.c:21-28`. No KNN.

## Key invariants

- Key: `[lower:macaddr|upper:macaddr|pad[4]]`, size 16 (`gbtreekey16`)
  `source/contrib/btree_gist/btree_macaddr.c:13-18`. The `pad[4]` is
  explicitly named in the struct to make the size match `gbtreekey16`.
- Internal `mac_2_uint64` converts MAC to uint64 for penalty arithmetic
  `source/contrib/btree_gist/btree_macaddr.c:95`.

## Trust boundary / Phase D surface

- MAC address byte order: PG's macaddr is stored in network byte order. The
  comparators delegate to `macaddr_cmp` which does the right memcmp-style
  comparison. Sound.
- The 4 pad bytes are zeroed by `palloc0` in `gbt_num_compress`; any leaked
  pad bytes from index pages are zero. No information leak.
- EXCLUDE on macaddr: sound.

## Issues spotted

None significant.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
