# `src/include/port/pg_bswap.h`

## Role

Byte-order conversion — 16/32/64-bit byte-swap (`pg_bswap16/32/64`) and
host-to-network / network-to-host wrappers (`pg_hton16/32/64`,
`pg_ntoh16/32/64`). On big-endian hosts, hton/ntoh are no-ops; on
little-endian (everything PG supports today besides POWER/S390 in BE
mode), they call `pg_bswap*`.

Plus `DatumBigEndianToNative(x)` — a Datum-level helper used to make
bitwise sort comparisons cheap (compare a big-endian-stored Datum as a
native uint64 == memcmp result).

Implementation tiers:
1. GCC/Clang `__builtin_bswap{16,32,64}` (`HAVE__BUILTIN_BSWAP*`).
2. MSVC `_byteswap_{ushort,ulong,uint64}` (via `<stdlib.h>` already in
   c.h, per the prologue comment line 25-27).
3. Handwritten shift-and-mask fallback `[verified-by-code]`
   `source/src/include/port/pg_bswap.h:41-100`.

## Public API

`[verified-by-code]` `source/src/include/port/pg_bswap.h:30-146`:

- `uint16 pg_bswap16(uint16 x)`
- `uint32 pg_bswap32(uint32 x)`
- `uint64 pg_bswap64(uint64 x)`
- `pg_hton16/32/64(x)` — host→network (big-endian on the wire).
- `pg_ntoh16/32/64(x)` — network→host.
- `DatumBigEndianToNative(x)` — uses pg_bswap64 on LE, no-op on BE.

All take and return **unsigned**. Comment warns against passing signed
ints (sign-extension on shift can corrupt the result)
`[from-comment]` `source/src/include/port/pg_bswap.h:10-13`.

## Invariants

1. **Unsigned-only.** The fallback shift-and-mask
   (`((x << 24) & 0xff000000) | ...`) is correctness-sensitive on
   signed inputs because `<<` on negative signed ints is UB
   `[from-comment]` `source/src/include/port/pg_bswap.h:10-13`.
2. **Builtin preferred over MSVC intrinsic preferred over fallback.**
   `__builtin_bswap*` is tested first; if absent, `_byteswap_*`; if
   neither, the fallback `[verified-by-code]`
   `source/src/include/port/pg_bswap.h:30-101`. PG's c.h includes
   `<stdlib.h>` so MSVC's `_byteswap_*` is always available without
   re-include here.
3. **`pg_hton/ntoh` macros key off `WORDS_BIGENDIAN`** (set by
   configure for BE platforms like SPARC BE, S390x BE, POWER BE)
   `[verified-by-code]` `source/src/include/port/pg_bswap.h:108-128`.
   PG still supports BE platforms officially but they're rare in
   production.
4. **`DatumBigEndianToNative` chains through `UInt64GetDatum` /
   `DatumGetUInt64`** to stay type-safe across the swap
   `[verified-by-code]` `source/src/include/port/pg_bswap.h:145`.

## Notable internals

The fallback `pg_bswap64` is a textbook 8-shift / 8-mask /
7-OR formula `[verified-by-code]`
`source/src/include/port/pg_bswap.h:88-100`. The compiler can usually
recognize this pattern and turn it into `bswap` even without the
builtin — but PG doesn't trust that across all supported compilers,
so it tests the macro explicitly.

`DatumBigEndianToNative` is used by abbreviated-key sorting (B-tree,
sort routines): an abbreviated key is stored big-endian inside the
Datum so that a single integer comparison gives the same answer as a
byte-by-byte strcmp. On LE machines this needs a one-shot byte swap
before comparison; on BE machines it's a no-op.

## Trust-boundary / Phase D surface

- **Signed-input footgun.** The header carefully says "use caution
  with signed integers" but the cast at call sites is the caller's
  responsibility. A new caller doing `pg_bswap32(some_int32)` would
  compile with no warning and produce wrong results on negative
  inputs in the fallback path. **Phase-D-review-pattern:** grep new
  `pg_bswap*` callers; flag any non-unsigned argument.
- **A2 libpq wire protocol echo.** Every `int32` / `int16` field in
  PostgreSQL's frontend/backend protocol uses `pg_hton/ntoh*`.
  Endianness bugs here would silently corrupt every wire message.
  No issue today but the entire wire-protocol correctness rests on
  this 50-line header.
- **`DatumBigEndianToNative` correctness depends on Datum being 8
  bytes.** PG's Datum is uint64 on 64-bit, uint32 on 32-bit. The
  macro uses `pg_bswap64`/`DatumGetUInt64` unconditionally — so on
  32-bit, calling this with a 4-byte Datum is wrong. Looking at line
  145: `UInt64GetDatum(pg_bswap64(DatumGetUInt64(x)))` — yes, it
  assumes Datum is 64-bit. 32-bit support of PG is being phased out
  per ongoing CommitFest discussion. **Phase-D-doc-issue:**
  explicitly state "requires SIZEOF_DATUM == 8".
- **Big-endian platforms get a fast path** but they're CI-poor; bugs
  in the BE branch (e.g. forgetting a `pg_hton32` on a new wire
  field) would silently corrupt only on BE installs.

## Cross-refs

- `source/src/backend/libpq/pqformat.c` — heaviest hton/ntoh consumer.
- `source/src/backend/utils/sort/sortsupport.c` —
  `DatumBigEndianToNative` for abbreviated keys.
- `source/src/include/port/pg_crc32c.h` — `#include`s this header
  for the slicing-by-8 BE-mode FIN.
- A2 libpq wire — every length, OID, integer field travels through
  these macros.

## Issues / unresolved

- **ISSUE-doc**: `DatumBigEndianToNative` assumes 8-byte Datum
  without comment or `StaticAssertDecl`. (severity: medium on the
  32-bit-build path, currently fading)
- **ISSUE-trust**: signed-int input warning is comment-only; a
  type-check `StaticAssertStmt(__builtin_types_compatible_p(...))`
  would catch real footguns. Out of scope for portable C, but worth
  flagging. (severity: low)
