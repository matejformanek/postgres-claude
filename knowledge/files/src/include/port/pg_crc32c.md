# `src/include/port/pg_crc32c.h`

## Role

CRC-32C checksum API — *Castagnoli* polynomial (0x1EDC6F41), the same
CRC used by iSCSI, SCTP, and Intel's hardware. **Not a cryptographic
hash.** Five hardware/software backends, picked by configure:

- `USE_SSE42_CRC32C` — direct Intel SSE 4.2 `_mm_crc32_*` intrinsics
  (constant-target build).
- `USE_SSE42_CRC32C_WITH_RUNTIME_CHECK` — same instructions, but
  guarded by CPUID dispatch.
- `USE_AVX512_CRC32C_WITH_RUNTIME_CHECK` — AVX-512 VPCLMULQDQ path
  (toggled within SSE 4.2 path).
- `USE_ARMV8_CRC32C` / `USE_ARMV8_CRC32C_WITH_RUNTIME_CHECK` — ARMv8
  CRC32 extension; optional PMULL crypto extension for wide-input.
- `USE_LOONGARCH_CRC32C` — LoongArch CRCC instructions.
- Default fallback — Slicing-by-8 lookup-table algorithm (Sarwate).

## Public API

`[verified-by-code]` `source/src/include/port/pg_crc32c.h:13-25`:

The "public interface consists of four macros":
- `INIT_CRC32C(crc)` — set crc = 0xFFFFFFFF.
- `COMP_CRC32C(crc, data, len)` — accumulate bytes.
- `FIN_CRC32C(crc)` — finalize: XOR 0xFFFFFFFF; on BE slicing-by-8,
  also byte-swap.
- `EQ_CRC32C(c1, c2)` — equality check (`==`).

`typedef uint32 pg_crc32c` `source/src/include/port/pg_crc32c.h:38`.

## Invariants

1. **INIT and EQ are identical across all backends.** `INIT` is
   always `crc = 0xFFFFFFFF`; `EQ` is always `c1 == c2`
   `[verified-by-code]` `source/src/include/port/pg_crc32c.h:40-42`.
2. **FIN XORs 0xFFFFFFFF.** This is part of the standard CRC-32C
   reflected output transform. On the slicing-by-8 fallback in
   big-endian builds, FIN additionally `pg_bswap32`s the result
   because the SB8 algorithm keeps the running value byte-swapped
   internally to avoid swapping per chunk `[from-comment]`
   `source/src/include/port/pg_crc32c.h:170-183`.
3. **NOT a cryptographic hash.** CRC-32C is linear in GF(2):
   collisions are trivial to construct, the function commutes with
   XOR, and it offers no preimage resistance. Used only for
   **corruption detection** (WAL record integrity, page checksums on
   data pages when `data_checksums=on`).
4. **Constant-length compile-time specialization.** For `USE_SSE42_CRC32C`
   without runtime check, if `pg_integer_constant_p(len) && len < 32`,
   the dispatch function inlines the SSE intrinsics directly to avoid
   a function call `[verified-by-code]`
   `source/src/include/port/pg_crc32c.h:73-91`. Same shortcut for
   ARMv8 `source/src/include/port/pg_crc32c.h:125-129`.
5. **`pg_attribute_no_sanitize_alignment` + `pg_attribute_target("sse4.2")`**
   are required on the inline dispatch even though the host compiler
   targets SSE 4.2 — comment notes "with-llvm" builds where gcc and
   clang disagree on built-in targets `[from-comment]`
   `source/src/include/port/pg_crc32c.h:63-66`.
6. **Function pointer for runtime-dispatch backends.**
   `extern pg_crc32c (*pg_comp_crc32c)(...)` lives in all the
   `_WITH_RUNTIME_CHECK` paths AND in the direct-SSE42 path (for
   AVX-512 fallback) `[verified-by-code]`
   `source/src/include/port/pg_crc32c.h:56,111,137,163`.

## Notable internals

The five `#elif` branches form a strict priority chain:

```
USE_SSE42_CRC32C
  > USE_SSE42_CRC32C_WITH_RUNTIME_CHECK
  > USE_ARMV8_CRC32C
  > USE_LOONGARCH_CRC32C
  > USE_ARMV8_CRC32C_WITH_RUNTIME_CHECK
  > [fallback: slicing-by-8]
```

The "constant-input inline" path uses 64-bit `_mm_crc32_u64`
(`SIZEOF_VOID_P >= 8`), then 32-bit chunks, then byte-at-a-time
`[verified-by-code]` `source/src/include/port/pg_crc32c.h:82-90`.
This is a real win for callsites like
`INIT_CRC32C(c); COMP_CRC32C(c, &xlrec, sizeof(xlrec)); FIN_CRC32C(c);`
where `sizeof(xlrec)` is a compile-time constant ≤ 32.

The function-pointer indirection in `pg_comp_crc32c` is populated by
a one-shot CPUID probe (`pg_comp_crc32c_choose.c` style) at backend
init. After the probe, every call is two loads + an indirect branch
— well-predicted on modern CPUs.

## Trust-boundary / Phase D surface

- **"Not a cryptographic hash" must be guarded against misuse.**
  Anyone using CRC32C for security purposes — auth tokens, integrity
  against an attacker, hash-table keying with adversarial input —
  has a critical flaw. The header docs do say "corruption detection
  only" but the type `pg_crc32c` and the name don't signal that. **A
  recurring corpus theme (A5/A11/A13/A14):** signature collisions in
  hash-based catalogs, dump filenames, bloomfilters. CRC32C is in
  the same bucket. **Phase-D-doc-issue:** every consumer of
  `pg_crc32c` should be inventoried; any one used cross a trust
  boundary (e.g. matching a hash from an untrusted submitter) needs
  flagging.
- **WAL record integrity boundary.** WAL records use CRC32C to
  detect torn writes and bit-rot. An attacker with WAL-injection
  capability (replication channel, archive-restore) can construct
  collisions trivially. PG's WAL trust model is "trusted
  shipper → trusted receiver" — but this is a known gap when archive
  storage is read-only-shared (S3 with permissive ACLs).
- **Data-page checksum (`data_checksums=on`)** uses FNV-1a, NOT
  CRC32C. Don't conflate the two. `pg_crc32c` is for WAL + 2PC +
  some replication frames.
- **Runtime-dispatch race window.** `pg_comp_crc32c` function pointer
  is set at backend init; same caveat as `pg_popcount_optimized` —
  extension `_PG_init` running before the probe would crash or use
  a non-initialized pointer.
- **AVX-512 VPCLMULQDQ availability is rare.** Only Ice Lake-server
  and newer Intel chips. The runtime check correctly falls back to
  SSE 4.2; verify by examining `pg_comp_crc32c_choose.c`.
- **LoongArch and ARMv8 paths have less CI exposure.** Bugs would
  surface only on those platforms.

## Cross-refs

- `source/src/port/pg_crc32c_sb8.c` — slicing-by-8 reference.
- `source/src/port/pg_crc32c_sse42.c`,
  `pg_crc32c_avx512.c`,
  `pg_crc32c_armv8.c`,
  `pg_crc32c_loongarch.c` — hardware implementations.
- `source/src/port/pg_crc32c_choose.c` (and arch-specific
  `pg_crc32c_*_choose.c`) — runtime probes.
- `source/src/include/access/xlog_internal.h` — WAL record header
  consumer.
- `source/src/include/access/twophase_rmgr.h` — 2PC state file CRC.
- A11/A13/A14 signature-collision cluster — CRC32C is hardware-CRC
  anchor (NOT crypto hash).
- A14 storage-AIO — WAL writeback path.

## Issues / unresolved

- **ISSUE-trust**: CRC32C is trivially collidable; cross-trust-
  boundary uses (WAL from untrusted archive, 2PC files from
  attacker-writable storage) are silent failures. Header says
  "corruption detection" but the type doesn't convey "untrusted-
  input-unsafe". (severity: medium, doc + audit; matches A11/A13/A14
  cluster pattern)
- **ISSUE-doc**: no inventory of "where CRC32C crosses a trust
  boundary" — a Phase-D follow-up should list every callsite and
  classify. (severity: medium, doc-only)
- **ISSUE-portability**: AVX-512 + LoongArch + ARMv8 PMULL paths
  have thin CI coverage. (severity: low, portability)
- **ISSUE-confusion**: PG has TWO checksum algorithms (CRC32C for
  WAL, FNV-1a for data pages). New contributors regularly conflate.
  Header could include a "see also: src/include/storage/checksum.h"
  cross-ref. (severity: low, doc)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
