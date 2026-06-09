# btree_uuid.c

## One-line summary

GiST opclass for `uuid` — 32-byte key `[lower:pg_uuid_t|upper:pg_uuid_t]`
(16 + 16 bytes). Has its own compress (doesn't use the
`gbt_num_compress` switch since `pg_uuid_t` isn't in the union), uses memcmp
for ordering, and a custom `uuid_2_double` for penalty.

## Public API

Standard 8 GiST + sortsupport: `gbt_uuid_{compress,fetch,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_uuid.c:21-28`.

## Key invariants

- **Key:** `typedef struct { pg_uuid_t lower, upper; } uuidKEY` — 32 bytes
  (`gbtreekey32`).
- **Comparison:** `uuid_internal_cmp` = `memcmp(arg1->data, arg2->data,
  UUID_LEN)` `source/contrib/btree_gist/btree_uuid.c:32`. UUIDs are
  big-endian-comparable byte arrays.
- **Custom compress** at `source/contrib/btree_gist/btree_uuid.c:100`: bypasses
  `gbt_num_compress` because `pg_uuid_t` is not in the union (it's a
  16-byte by-reference type). Allocates `2 * UUID_LEN` and `memcpy`s twice.
- **`gbt_uuid_fetch` uses `gbt_num_fetch`** even though compress doesn't use
  `gbt_num_compress` — works because `gbt_num_fetch`'s default arm
  (`datum = entry->key`) handles pointer types. The lower bound at offset 0
  IS the original `pg_uuid_t`.

## Notable internals

### `uuid_2_double` — penalty scalar

`source/contrib/btree_gist/btree_uuid.c:170`:
- Treats the UUID as a 128-bit big-endian integer.
- On little-endian hosts, byte-swaps each 64-bit half before native arithmetic.
- Returns `(double) uu[0] + (double) uu[1] / 2^64` — i.e. uses double's 53-bit
  mantissa for the high half, and a fractional part for the low half. This
  side-steps 128-bit overflow (`2^128 ≈ 3.4e38` could exceed POSIX-min double
  range of `1e37`).
- This double is then fed into `penalty_num`.

The big-endian handling is the only place in btree_gist where byte order
matters for correctness.

## Trust boundary / Phase D surface

- **UUID random-distribution stress:** UUIDv4 is high-entropy random. The
  internal-node ranges for a UUID GiST index will cover near-full UUID space
  after a few thousand inserts, making the index nearly useless for range
  selectivity. Index ordering remains correct, but operational performance
  is bad for random UUIDs. UUIDv7 (time-ordered) would behave better.
- **`uuid_2_double` precision loss:** the conversion preserves only ~53 high
  bits → near-leaf inserts in dense areas may all get penalty 0. This is
  benign: GiST falls back on first-fit when all penalties tie.
- **Endianness:** `pg_bswap64` on little-endian is critical for correctness.
  If `WORDS_BIGENDIAN` were ever mis-defined on a particular build, the
  penalty would order UUIDs by *byte-swapped* value — internal-node bounds
  would be wildly off but `gbt_uuid_same`/`consistent` (which use raw memcmp)
  would still work. **Index would have correct query results but pathological
  performance.**
- **EXCLUDE constraint:** `gbt_uuid_same` uses memcmp — exact byte equality.
  Sound.
- **Lossless fetch:** `gbt_uuid_fetch` returns the original UUID bytes from
  the lower bound. Sound IOS support.

## Cross-references

- `source/src/backend/utils/adt/uuid.c` — the built-in uuid type's
  `uuid_cmp` (also memcmp-based).
- `source/src/include/port/pg_bswap.h` — `pg_bswap64`.
- `knowledge/files/contrib/btree_gist/btree_utils_num.c.md` — framework.

## Issues spotted

- [ISSUE-PERF: For UUIDv4 (random) inserts, internal-node ranges cover
  almost the full UUID space after a small number of inserts → GiST index
  scans degenerate to full-index reads. Operational. (LOW)]
- [ISSUE-PORTABILITY-LATENT: `uuid_2_double` correctness depends on
  `WORDS_BIGENDIAN` being set correctly at compile time. Misconfigured
  cross-compiles silently produce broken indexes (correct results, broken
  performance). (LOW)]
- [ISSUE-DESIGN: Custom compress at `:100` instead of extending the
  `gbt_num_compress` switch — diverges from the framework. Future
  maintainers must remember that UUID has its own compress path. (LOW —
  documented by the explicit `PG_FUNCTION_INFO_V1`)]
