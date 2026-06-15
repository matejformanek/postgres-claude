---
path: src/test/modules/test_int128/test_int128.c
anchor_sha: e18b0cb7344
loc: 285
depth: read
---

# src/test/modules/test_int128/test_int128.c

## Purpose

Standalone test binary (not a backend extension) that diffs the portable
roll-our-own 128-bit integer routines in `src/include/common/int128.h`
against the compiler's native `__int128`. Used to validate the fallback path
on platforms where PG can't rely on `__int128` (e.g. some MSVC builds).
Generates random 64-bit operands with `pg_prng` and checks add/sub/multiply/
divide and three-way compare. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `test_int128.c:79` (HAVE_INT128) / `:278` (else) | Iterates a default 1B random ops; argv[1] overrides count |
| `my_int128_compare` (static inline) | `:62` | Reference three-way compare on native `int128` |

## Internal landmarks

- `test128` union (`:40`) overlays native `int128`, the `INT128` struct from
  `common/int128.h`, and a `(hi, lo)` pair — letting the test read out
  either representation with byte-identical bit layout.
- Predefining `USE_NATIVE_INT128=1` flips the header to its native variant so
  you can sanity-check the test framework itself.
- The seven operations covered: unsigned add, signed add, 128-bit add,
  unsigned sub, signed sub, 64×64 multiply-add, 64×64 multiply-sub,
  128/32 divide-mod, and signed compare.
- Division test guards against `z32==0` (`:104-106`) — a divide-by-zero
  would trap before reaching the comparison.

## Invariants & gotchas

- **Standalone client-side binary** — uses `postgres_fe.h`, runs without a
  backend.
- Requires `HAVE_INT128` at compile time; otherwise the program just prints
  "skipping tests" and exits 0 (`:278-283`). On platforms without native
  int128, the fallback in `int128.h` is exercised only indirectly via
  consumers like `numeric.c`.
- A failure prints both the native and computed results in hex and returns 1
  — the test harness diffs against expected (empty) output.
- The PRNG is seeded from `time(NULL)` (`:84`) — the comment about
  "reproducible since we use a fixed seed" predates a switch and is now
  slightly misleading.

## Cross-refs

- `source/src/include/common/int128.h` — the implementation under test.
- `source/src/backend/utils/adt/numeric.c` — primary consumer of these
  routines (sum/avg accumulators for `int8`).
