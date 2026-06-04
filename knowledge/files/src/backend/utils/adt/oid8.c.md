---
path: src/backend/utils/adt/oid8.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 168
depth: read
---

# oid8.c

- **Source path:** `source/src/backend/utils/adt/oid8.c`
- **Lines:** 168
- **Depth:** read
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/catalog/pg_type.h`, `src/include/utils/builtins.h` (`PG_GETARG_OID8`/`PG_RETURN_OID8`, `uint64in_subr`, `pg_ulltoa_n`, `Oid8` typedef), `src/include/libpq/pqformat.h`, `src/include/catalog/pg_proc.dat`

> Note: at this anchor SHA `oid8.c` is the **scalar 8-byte OID type (`Oid8`)** — an unsigned 64-bit OID, analogous to `xid8` — NOT the `oidvector` helper. The `oidvector` code lives in `oid.c`. (The task's context blurb describing this as "oidvector helpers" is stale.)

## Purpose
SQL type I/O, comparison, hashing, and min/max-aggregate support for the `oid8` type, an unsigned 64-bit object identifier [from-comment `oid8.c:3-4`, verified-by-code `oid8.c:27-168`]. `Oid8` is an unsigned integer, so all comparisons are plain unsigned C operators on the underlying 64-bit value — there is no wraparound semantics here (unlike `xid`) [verified-by-code `oid8.c:86-138`].

## Public symbols
| Symbol | file:line | Role |
|---|---|---|
| `oid8in` | `oid8.c:27` | cstring → oid8 via `uint64in_subr` |
| `oid8out` | `oid8.c:37` | oid8 → cstring via `pg_ulltoa_n` + manual palloc/memcpy |
| `oid8recv` | `oid8.c:60` | binary recv (`pq_getmsgint64`) |
| `oid8send` | `oid8.c:71` | binary send (`pq_sendint64`) |
| `oid8eq`/`oid8ne` | `oid8.c:86`/`95` | (in)equality, plain `==`/`!=` |
| `oid8lt`/`oid8le`/`oid8ge`/`oid8gt` | `oid8.c:104`/`113`/`122`/`131` | ordering, plain unsigned compares |
| `hashoid8`/`hashoid8extended` | `oid8.c:140`/`146` | delegate to `hashint8`/`hashint8extended` |
| `oid8larger`/`oid8smaller` | `oid8.c:152`/`161` | min/max aggregate support |

## Internal landmarks
- `MAXOID8LEN` (=20) sizes the output stack buffer for a 64-bit decimal value [verified-by-code `oid8.c:21`, `oid8.c:41`].
- `oid8out` avoids `pstrdup`'s `strlen` by computing the length from `pg_ulltoa_n` and doing a manual `palloc`+`memcpy` [from-comment `oid8.c:48-53`].
- `hashoid8`/`hashoid8extended` pass `fcinfo` straight through to `hashint8`/`hashint8extended` [verified-by-code `oid8.c:140-150`].

## Invariants & gotchas
- **Plain unsigned ordering, no wraparound.** Unlike `xid`, `oid8` comparisons (`<`, `<=`, etc.) are direct unsigned comparisons on the 64-bit value; sorting is a true total order [verified-by-code `oid8.c:104-138`].
- **oid8 hashes identically to int8.** Because hashing delegates to `hashint8[extended]`, an `oid8` and the bit-identical `int8`/`bigint` produce the same hash — relevant for any cross-type hash assumptions [verified-by-code `oid8.c:140-150`].
- **Output buffer is exact.** `MAXOID8LEN + 1` (=21) bytes holds the largest 64-bit decimal plus NUL; the `+ 1` from `pg_ulltoa_n` then the `buf[len-1] = '\0'` is the standard numutils idiom [verified-by-code `oid8.c:41-46`].

## Cross-references
- [[knowledge/files/src/backend/utils/adt/oid.c.md]] — the 32-bit `oid` type and `oidvector`.
- [[knowledge/files/src/backend/utils/adt/xid.c.md]] — `xid8` is the analogous 64-bit transaction-id type and likewise delegates hashing to int8.
- [[knowledge/files/src/backend/utils/adt/int8.c.md]] — `hashint8`/`hashint8extended` targets.
- [[knowledge/files/src/backend/utils/adt/numutils.c.md]] — `uint64in_subr`, `pg_ulltoa_n`.
- [[knowledge/idioms/fmgr.md]] — V1 calling convention.

## Potential issues
None surfaced. Trivial type-support file; all idioms match siblings.

## Confidence tag tally
- [verified-by-code]: 9
- [from-comment]: 3
- [inferred]: 0
- [unverified]: 0
