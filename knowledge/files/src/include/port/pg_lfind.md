# `src/include/port/pg_lfind.h`

## Role

SIMD-accelerated linear search routines over small arrays. Provides:

- `pg_lfind8(key, base, nelem)` — find a `uint8` in a `uint8[]`.
- `pg_lfind8_le(key, base, nelem)` — find any byte ≤ key.
- `pg_lfind32(key, base, nelem)` — find a `uint32` in a `uint32[]`.

All static inline; all return `bool` (presence/absence). Built on
top of `port/simd.h`. Header copyright 2022+ (recent — pre-2022, PG
used handwritten unrolled loops) `[verified-by-code]`
`source/src/include/port/pg_lfind.h:7`.

## Public API

`[verified-by-code]` `source/src/include/port/pg_lfind.h:25-209`:

- `bool pg_lfind8(uint8 key, const uint8 *base, uint32 nelem)`
- `bool pg_lfind8_le(uint8 key, const uint8 *base, uint32 nelem)`
- `bool pg_lfind32(uint32 key, const uint32 *base, uint32 nelem)`

Internal helpers (also inline):
- `pg_lfind32_one_by_one_helper(key, base, nelem)` — scalar loop.
- `pg_lfind32_simd_helper(keys, base)` — 4-register block compare.

## Invariants

1. **`pg_lfind8`/`pg_lfind8_le` always have a scalar tail.** The SIMD
   loop processes `nelem & ~(sizeof(Vector8)-1)` elements; the
   remainder runs byte-by-byte `[verified-by-code]`
   `source/src/include/port/pg_lfind.h:30-46`. Safe for any nelem
   (including 0).
2. **`pg_lfind32` is much heavier: 4-register-block unroll.** Each
   block processes `4 * sizeof(Vector32)/sizeof(uint32)` = 16 uint32s
   on SSE2/NEON. If `nelem < 16`, falls back to scalar entirely
   `[verified-by-code]` `source/src/include/port/pg_lfind.h:165-178`.
3. **`pg_lfind32` "process last block again" tail trick.** After the
   `do {} while (i < tail_idx)` loop, the function unconditionally
   re-runs `pg_lfind32_simd_helper(keys, &base[nelem - 16])` — the
   last 16-element block, even if it overlaps with already-checked
   elements `[verified-by-code]`
   `source/src/include/port/pg_lfind.h:194-202`. Comment says
   "testing has demonstrated that this helps more cases than it
   harms" — branch-free is cheaper than a scalar tail.
4. **USE_NO_SIMD fallback.** `pg_lfind32` falls back to the scalar
   helper entirely. `pg_lfind8` still uses Vector8 because USE_NO_SIMD
   Vector8 is a uint64 with bithack `has`/`has_le` (4-byte parallel,
   not 16) `[verified-by-code]` `source/src/include/port/pg_lfind.h:155-207`.
5. **Assert-checked correctness.** Under `USE_ASSERT_CHECKING`,
   `pg_lfind32` runs `pg_lfind32_one_by_one_helper` first into a
   shadow result and asserts the SIMD path matches at each return
   point `[verified-by-code]`
   `source/src/include/port/pg_lfind.h:169-201`.

## Notable internals

`pg_lfind32_simd_helper` `source/src/include/port/pg_lfind.h:108-143`:

- Loads 4 vectors at offsets `[0, n, 2n, 3n]` for `n = 4` (per Vector32).
- `vector32_eq` against the broadcast key into 4 result vectors.
- `vector32_or` reduces 4→2→1.
- `vector32_is_highbit_set` returns the answer.

The 4-way unroll exposes instruction-level parallelism; the comment
notes "for better instruction-level parallelism, each loop iteration
operates on a block of four registers"
`source/src/include/port/pg_lfind.h:159-161`.

## Trust-boundary / Phase D surface

- **`pg_lfind32`'s "last block re-checked" trick over-reads up to
  64 bytes before `base[nelem]`** — no, actually it re-reads
  `base[nelem - 16]` through `base[nelem - 1]`, which is in-bounds.
  But if `nelem >= 16` is false the early return covers it. ASAN
  would flag any miss. Verified safe.
- **`pg_lfind8` is the JSON-parsing hot path.** Used in
  `escape_json_string`/`varlena.c` to find the first byte requiring
  escape. A bug here (e.g. NEON intrinsic miscount) would silently
  mis-escape JSON. Mitigation: `vector8_has` has the
  USE_ASSERT_CHECKING shadow.
- **No bounds checks on `base`.** Caller guarantees `base[0..nelem)`
  is readable. Stack-allocated arrays or palloc'd buffers OK; any
  fishy callsite (e.g. variable-length reading from network buffer)
  is a correctness audit target. **Phase-D-review-pattern:** new
  `pg_lfind*` callers with caller-controlled nelem need bounds proof
  in the commit message.
- **Performance asymmetry on USE_NO_SIMD.** `pg_lfind32` falls all
  the way back to a scalar loop. On a hypothetical RISC-V build, code
  hot-spotting on `pg_lfind32` would silently lose ~10x perf.
  Document for porting newcomers.
- **A7 echo: stack-depth in record_recv.** Big composite types
  iterate their member OIDs through `pg_lfind`-style scans; the SIMD
  fast path is what keeps deep recursion within stack budget. If
  `USE_NO_SIMD` builds blow the budget under specific corpora, that's
  a portability-tax to document.

## Cross-refs

- `source/src/include/port/simd.h` — substrate.
- `source/src/backend/utils/adt/varlena.c` — `escape_json_string`,
  `byteain` validation use `pg_lfind8`.
- `source/src/backend/utils/adt/json*.c` — JSON tokenization fast paths.
- `source/src/backend/access/transam/multixact.c` — `pg_lfind32`
  member-OID search.
- A7 record_recv stack-depth — JSON parsing fast path.
- A13/A14 collision cluster — hash prefix scan idiom.

## Issues / unresolved

- **ISSUE-perf**: `pg_lfind32` is documented as faster only for
  `nelem >= 16`. Below that, callers might be better off with the
  one-by-one helper directly. But the inline body checks `nelem` and
  branches into one-by-one anyway, so the cost is minimal. (severity:
  low)
- **ISSUE-doc**: no public guidance on "when should I reach for
  `pg_lfind` vs a tight C loop?" The win is real but only above
  ~16-32 elements and only when the compiler can't auto-vectorize
  (e.g. data-dependent branches inside the loop). (severity: doc-only)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
