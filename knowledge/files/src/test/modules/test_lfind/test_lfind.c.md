---
path: src/test/modules/test_lfind/test_lfind.c
anchor_sha: e18b0cb7344
loc: 148
depth: read
---

# src/test/modules/test_lfind/test_lfind.c

## Purpose

Verifies correctness of the SIMD-accelerated linear-search helpers in
`port/pg_lfind.h` (`pg_lfind8`, `pg_lfind8_le`, `pg_lfind32`). The interesting
property of these helpers is they have a vector fast path plus a scalar tail
for the last `len % VECTORWIDTH` bytes; bugs typically hide at the boundary
between the two. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_lfind8` | `test_lfind.c:57` | Exhaustive sweep over interesting byte values (0, 1, 0x7F, 0x80, 0x81, 0xFD, 0xFE, 0xFF) |
| `test_lfind8_le` | `:102` | Same sweep, less-than-or-equal variant |
| `test_lfind32` | `:118` | Searches a 135-element uint32 array with sentinel values at positions 8, 64, and 134 |

## Internal landmarks

- `LEN_NO_TAIL(Vector8)` = `2 * sizeof(Vector8)`, `LEN_WITH_TAIL` adds 3
  (`:23-24`) — the 2x factor exercises iteration through more than one
  vector, the +3 forces a non-aligned scalar tail.
- Each `test_lfind8_internal` call runs both a "key in the tail" placement
  and a "key in the vector body" placement, so both code paths are hit.
- `test_lfind32` deliberately uses a length (135) that's not a multiple of
  any plausible vector width.

## Invariants & gotchas

- The helpers under test are header-inline (`port/pg_lfind.h`) and conditional
  on the build's SIMD capability — buildfarm coverage of CPUs without SSE2/NEON
  ensures the scalar fallback is also exercised.
- Failure mode is `elog(ERROR, ...)` — a hit/miss disagreement aborts the
  containing SQL statement; the regression test sees the ERROR.

## Cross-refs

- `source/src/include/port/pg_lfind.h` — the implementation under test.
- `source/src/include/port/simd.h` — `Vector8`, `Vector32` typedefs and the
  per-arch intrinsics.
