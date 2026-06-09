# btree_inet.c

## One-line summary

GiST opclass for `inet` and `cidr` — stores each inet value as a **single
`double` scalar** via `convert_network_to_scalar`, reuses the float8-style
fixed-width framework. Sets `*recheck = true` because the scalar is lossy.

## Public API

Standard 7-function GiST set + sortsupport:
`gbt_inet_{compress,union,picksplit,consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_inet.c:20-26`. No KNN (`f_dist = NULL`).

## Key invariants

- **Key:** `typedef struct { double lower, upper; } inetKEY` — 16 bytes
  (`gbtreekey16`). The actual inet value is **not stored** in the index — only
  a `double` scalar approximation.
- **Lossy compression:** `convert_network_to_scalar(inet, INETOID, &failure)`
  produces a double that orders consistent with inet ordering (IPv4 < IPv6,
  then by address). Multiple distinct inet values can collapse to the same
  scalar.
- **`*recheck = true`** in `gbt_inet_consistent`
  `source/contrib/btree_gist/btree_inet.c:136`. This is the *only* fixed-
  width btree_gist opclass that requires recheck — the per-tuple recheck
  pulls the original inet from the heap and re-applies the operator.
- **No `f_dist`, no `gbt_inet_distance`, no `gbt_inet_fetch`** — KNN and IOS
  are not supported because the scalar cannot reproduce the original inet.
- **Comparators are raw C `<`/`>`/`==`** on the double
  `source/contrib/btree_gist/btree_inet.c:30-53`.

## Notable internals

`gbt_inet_compress` `source/contrib/btree_gist/btree_inet.c:92`:
- `convert_network_to_scalar(entry->key, INETOID, &failure)` produces a
  finite double; `Assert(!failure)` — the inet type guarantees no failure.
- Stores `r->lower = r->upper = scalar` and constructs a fresh GISTENTRY.

`gbt_inet_consistent` `:117`:
- Converts query to scalar via the same function.
- Uses `gbt_num_consistent` on the scalar.
- Sets `*recheck = true` so heap-level filter rejects false positives.

## Trust boundary / Phase D surface

- **IPv4/IPv6 family mixing:** `convert_network_to_scalar` orders all IPv4
  addresses as smaller than all IPv6 addresses (the scalar function adds
  a large offset for IPv6). Range queries that mix families work correctly
  because the scalar preserves family ordering. EXCLUDE works.
- **Lossy comparison + recheck:** the recheck is mandatory. If a future
  patch changed `*recheck = false`, range queries would return incorrect
  results (matching scalars that don't match the actual inet). Verify by
  inspection that recheck stays.
- **`convert_network_to_scalar` failure mode:** the third arg `failure`
  is asserted, not handled. If the inet's family byte is corrupt, the
  function returns 0 and sets `*failure = true`. In assert builds this
  trips; in release builds, the corrupt entry gets scalar 0 and the index
  silently misorders it. The TOAST layer / type-input validation should
  prevent this, but the assert is the only defence in this file.
- **CIDR vs inet:** `gbt_inet_compress` passes `INETOID` unconditionally
  even for cidr values (which use a different type OID). The
  `convert_network_to_scalar` function dispatches internally on the actual
  data, so this works — but the OID arg is essentially ignored. Worth
  knowing: the scalar function does NOT validate that the bytes match the
  declared OID.
- **EXCLUDE constraint on inet:** `gbt_inet_same` uses the scalar `==`. Two
  distinct inets that happen to map to the same scalar would be considered
  "same" by GiST — but `*recheck = true` in `consistent` means the heap-
  level re-test catches this. EXCLUDE is sound.

## Cross-references

- `source/src/backend/utils/adt/network.c` — `convert_network_to_scalar`.
- `source/src/include/catalog/pg_type.h` — `INETOID`, `CIDROID`.
- `knowledge/files/contrib/btree_gist/btree_utils_num.c.md` — framework.

## Issues spotted

- [ISSUE-INTEGRITY: `Assert(!failure)` at `:105` and `:133` is the only
  defence against a corrupt inet datum. In release builds a malformed inet
  produces scalar 0 silently. The TOAST layer should prevent this, but it's
  worth a guard. (LOW — defence in depth)]
- [ISSUE-LOSSY-FETCH: No `gbt_inet_fetch` — IOS is implicitly disabled (the
  opclass doesn't advertise fetch support). If anyone added one, it would
  need to either restore the original inet (impossible from the scalar) or
  the IOS path would be silently wrong. The pattern matches `btree_macaddr.c`
  which also stores a scalar approximation but DOES have fetch. (LOW —
  trap for future contributors)]
- [ISSUE-OID-ARG-IGNORED: `gbt_inet_compress` and `gbt_inet_consistent` pass
  `INETOID` to `convert_network_to_scalar` but the function dispatches on
  the data. A `cidr` column with a `gist_inet_ops` opclass thus passes
  `INETOID` as a lie. Works by accident. (LOW — cosmetic)]
