# `src/backend/storage/page/checksum.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 65
- **Source:** `source/src/backend/storage/page/checksum.c`

## Purpose

Thin shell over `storage/checksum_impl.h`. The actual algorithm
(FNV-1a-derived 16-bit page checksum) lives in the header so that
external programs (`pg_checksums`, etc.) can `#include` and reuse the
exact implementation. This file just compiles two instantiations
(fallback C and AVX2-accelerated) and chooses between them at runtime.
[from-comment] (`checksum.c:18-27`)

## Top of file

`#define PG_CHECKSUM_INTERNAL` then `#include "storage/checksum_impl.h"`
to pull in the in-tree implementation rather than the external-program
form.

## Public surface (checksum.h)

- `pg_checksum_page(char *page, BlockNumber blkno) → uint16` —
  declared via `checksum_impl.h`; the function pointer is dispatched
  through `pg_checksum_block`.

## Runtime dispatch

- `pg_checksum_block_fallback` (lines 31–34): the portable C version,
  body comes from `checksum_block_internal.h`.
- `pg_checksum_block_avx2` (lines 41–46, `#ifdef
  USE_AVX2_WITH_RUNTIME_CHECK`): AVX2-targeted via
  `pg_attribute_target("avx2")`.
- `pg_checksum_choose` (lines 51–62) sets the `pg_checksum_block`
  function pointer to the best available on first call
  (CPUID-gated), then jumps to it. Self-rewriting trampoline pattern.
  [verified-by-code]

## Invariants

- The checksum mixes the block number in so identical content at
  different positions produces different checksums (defeats simple
  swap-attack-style corruption). The mechanism is in
  `checksum_impl.h`, not this file. `[from-comment]` (page/README,
  storage/checksum_impl.h header)

## Cross-refs

- Called by `bufpage.c::PageIsVerified` and `PageSetChecksum`.

## Open questions

- I have not read `checksum_impl.h` in this pass; the polynomial /
  exact FNV variant is `[unverified]` here.

## Tag tally

`[verified-by-code]` 1 / `[from-comment]` 2 / `[unverified]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
