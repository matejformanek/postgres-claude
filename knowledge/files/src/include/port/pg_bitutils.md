# `src/include/port/pg_bitutils.h`

## Role

Bit-manipulation primitives — leading-zero / trailing-zero / popcount /
next-power-of-2 / log2 / rotate. Three-tier implementation:

1. GCC/Clang builtins (`__builtin_ctz`, `__builtin_clz`).
2. MSVC intrinsics (`_BitScanForward`, `_BitScanReverse`, `intrin.h`).
3. Lookup-table fallback (`pg_leftmost_one_pos[256]`,
   `pg_rightmost_one_pos[256]`, `pg_number_of_ones[256]`).

For `popcount` over buffers, a function-pointer dispatch routes to
hardware-POPCNT (x86) or SVE (ARM) implementations at runtime
`[verified-by-code]` `source/src/include/port/pg_bitutils.h:282-295`.

## Public API

`[verified-by-code]` `source/src/include/port/pg_bitutils.h:31-417`:

**Lookup tables** (extern PGDLLIMPORT, 256-entry):
- `pg_leftmost_one_pos[256]` — MSB position 0-7 for each byte.
- `pg_rightmost_one_pos[256]` — LSB position 0-7.
- `pg_number_of_ones[256]` — popcount of each byte.

**Single-word bit-scan**:
- `pg_leftmost_one_pos32(word)` / `_64` — MSB position, word > 0.
- `pg_rightmost_one_pos32(word)` / `_64` — LSB position, word > 0.

**Power-of-2 helpers**:
- `pg_nextpower2_32/64(num)` — round up; preconditions
  `num > 0 && num <= MAX/2 + 1`.
- `pg_prevpower2_32/64(num)` — round down; precondition `num > 0`.
- `pg_ceil_log2_32/64(num)` — ceil(log2).

**Popcount**:
- `pg_popcount32/64(word)` — single-word, Hacker's Delight algorithm.
- `pg_popcount(buf, bytes)` — buffer popcount; inlines a 1-byte loop
  for `bytes < 8`, dispatches to function pointer otherwise.
- `pg_popcount_masked(buf, bytes, mask)` — same with per-byte AND.

**Rotate**:
- `pg_rotate_right32(word, n)`, `pg_rotate_left32(word, n)`.

**Size-t aliases** (auto-pick 32 vs 64):
- `pg_leftmost_one_pos_size_t`, `pg_nextpower2_size_t`,
  `pg_prevpower2_size_t`.

## Invariants

1. **All bit-scan functions require `word != 0`.** Asserted on every
   path `[verified-by-code]` `source/src/include/port/pg_bitutils.h:44,75,114,148`.
   `__builtin_clz(0)` is undefined behavior, and the LUT loop would
   under-shift forever.
2. **`pg_nextpower2_32` rejects `num > UINT32_MAX/2 + 1`.** Asserted
   `[verified-by-code]` `source/src/include/port/pg_bitutils.h:191`.
   Beyond that the result would overflow.
3. **`pg_popcount32/64` is *not* the hardware-POPCNT path** despite
   the name — it's the parallel-bit-sum bithack
   `[verified-by-code]` `source/src/include/port/pg_bitutils.h:308-335`.
   Comment notes: "newer versions of popular compilers will
   automatically replace this with a special popcount instruction if
   possible, so we don't bother using builtin functions"
   `source/src/include/port/pg_bitutils.h:302-307`.
4. **Buffer-`pg_popcount` has an 8-byte threshold.** Below 8 bytes,
   inline LUT loop; at/above 8, function-pointer call to optimized
   `pg_popcount_optimized` `[verified-by-code]`
   `source/src/include/port/pg_bitutils.h:346-388`. The 8 is "the
   point at which we'll first use special instructions in the
   optimized version".
5. **Function-pointer dispatch lives behind two configure macros**:
   `HAVE_X86_64_POPCNTQ` and `USE_SVE_POPCNT_WITH_RUNTIME_CHECK`. If
   neither is set, `pg_popcount_optimized` is a normal function (no
   pointer), and the dispatch overhead disappears `[verified-by-code]`
   `source/src/include/port/pg_bitutils.h:282-295`.
6. **`pg_rotate_left/right32` with `n == 0` or `n == 32` is undefined
   behavior** in C (shift by ≥ width). Not asserted here; caller's
   responsibility `[verified-by-code]`
   `source/src/include/port/pg_bitutils.h:392-403`.

## Notable internals

The 256-entry LUTs are referenced by `pg_leftmost_one_pos32` only on
the no-builtin path: the algorithm walks 8 bits at a time from MSB
(`shift = 32 - 8; while (word >> shift) == 0; shift -= 8`) and then
indexes the LUT for the remaining byte
`[verified-by-code]` `source/src/include/port/pg_bitutils.h:56-63`.

Popcount-buffer dispatch is the canonical PG runtime-feature-detection
pattern: a function-pointer global, populated by `pg_popcount_optimized`
initially pointing at a probe function that examines CPUID/HWCAP and
swaps itself for `pg_popcount_avx512` / `_sve` / `_sse42` accordingly.
The actual probe lives in `src/port/pg_popcount_*.c` (out of scope here).

## Trust-boundary / Phase D surface

- **The `Assert(word != 0)` discipline.** In release builds, the
  assert vanishes; passing `0` to `pg_leftmost_one_pos32` returns
  garbage (the high-zero LUT entry, which is 0, so result is `0 + 0
  = 0` — but morally undefined). New callers must prove `word != 0`.
  **Phase-D-review-pattern:** grep new `pg_leftmost_one_pos*` /
  `pg_rightmost_one_pos*` / `pg_nextpower2*` callers for an obvious
  null-check pattern; flag any reading from caller-controlled input.
- **`pg_nextpower2_*` overflow on max input.** If a caller passes
  exactly `UINT32_MAX / 2 + 2`, the next power of 2 is `2^32` which
  doesn't fit in uint32. Asserted-only check. **Phase-D-review-
  pattern:** size-related callsites (e.g. hash-table sizing from a
  GUC) must clamp before calling.
- **Buffer popcount function-pointer race window.** The
  `pg_popcount_optimized` pointer is initialized at backend startup
  (in `pg_popcount_*_choose.c` style code, called by `BackendStartup`
  or similar). Before that init, the pointer is null/probe. Bgworkers
  that call popcount during their own `_PG_init` MIGHT race the
  initialization. **Phase-D-review-pattern:** extension code calling
  `pg_popcount(...)` during `_PG_init` before PG's startup hooks
  fire. Likely safe (init in `BackendInit`) but worth verifying.
- **POPCNT-availability vs binary-shipped baseline.** If the binary
  is built with `-mpopcnt` but runs on a CPU without POPCNT, behavior
  is undefined at the instruction level (not pg_bitutils's fault, but
  the runtime check exists specifically to avoid this). Document that
  the runtime-check version (`HAVE_X86_64_POPCNTQ` set) is the safe
  default for distributed builds.
- **No SIMD popcount in this header.** The optimized buffer popcount
  uses AVX-512 / SVE in separate .c files; this header just exposes
  the function pointer.

## Cross-refs

- `source/src/port/pg_popcount.c`, `pg_popcount_avx512.c`,
  `pg_popcount_sve.c` — the optimized implementations behind the
  function pointer.
- `source/src/port/pg_bitutils.c` — provides the three 256-byte LUTs.
- `source/src/backend/lib/bloomfilter.c`,
  `source/src/backend/access/heap/visibilitymap.c` — heavy popcount
  consumers.
- `source/src/backend/utils/hash/dynahash.c` — `pg_nextpower2_32` for
  bucket sizing.

## Issues / unresolved

- **ISSUE-trust**: `Assert(word != 0)` is the only `word == 0` guard;
  release builds silently return wrong (0). (severity: low — UB is
  scoped to "garbage in, garbage out")
- **ISSUE-doc**: `pg_popcount32` vs `pg_popcount` confusion — the
  word-form does NOT use hardware POPCNT; the buffer-form does (via
  the pointer). A caller wanting hardware POPCNT on a single u64
  should NOT use `pg_popcount64`. (severity: medium, doc-only)
- **ISSUE-trust**: function-pointer dispatch init order vs.
  `_PG_init` of preloaded extensions — undocumented. (severity: low)
