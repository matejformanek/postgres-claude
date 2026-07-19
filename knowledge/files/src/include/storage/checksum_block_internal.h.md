# `src/include/storage/checksum_block_internal.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~43
- **Source:** `source/src/include/storage/checksum_block_internal.h`

A bodyless, header-guard-less fragment of C that constitutes the inner
**body** of `pg_checksum_block()`. It is `#include`d twice: once into
`checksum_impl.h`'s static inline (for frontend/external programs) and
again into `src/backend/storage/page/checksum.c` where the backend
takes the address of the function for indirect dispatch through the
`pg_checksum_block` function pointer. The split exists so that the same
block-checksum algorithm body can be compiled both in a vectorizable
backend TU and in a generic frontend TU without duplicating the
algorithm. [verified-by-code] [from-comment]

## API / declarations

This file declares **no** prototypes. It is a textual macro-style
inclusion that expects the enclosing function to have declared a
parameter `const PGChecksummablePage *page` and to expect a `uint32`
return value. The body itself:

- Allocates a local `uint32 sums[N_SUMS]` (32 partial FNV states). [verified-by-code]
- `memcpy`s `checksumBaseOffsets` (defined in `checksum_impl.h`) into
  `sums` to seed each parallel hash with a different offset basis. [verified-by-code]
- Iterates the 32-column, `BLCKSZ/(4*32)`-row view of the page and
  feeds every column into its column-private FNV via the
  `CHECKSUM_COMP` macro. [verified-by-code]
- Performs two additional rounds with value 0 ("mixing" rounds). [verified-by-code]
- XOR-folds the 32 partial sums into a single `uint32 result` and
  returns. [verified-by-code]

## Notable invariants / details

- Line 15: the comment "*there is deliberately not an `#ifndef
  CHECKSUM_BLOCK_INTERNAL_H` here*" is load-bearing — the file is
  designed to be included multiple times in the same TU on x86 builds
  (`checksum.c` builds it at multiple ISA levels for runtime dispatch).
  A future contributor "fixing" this header by adding a guard would
  silently break the SIMD function-multiversioning. [from-comment]
  [ISSUE-undocumented-invariant: missing guard is intentional; only an
  inline comment protects against well-meaning header cleanup (nit)]
- `Assert(sizeof(PGChecksummablePage) == BLCKSZ)` at line 23 enforces
  that the union layout exactly fills a page; without it, the column
  iteration would silently under- or over-shoot. [verified-by-code]
- The body assumes `N_SUMS`, `BLCKSZ`, `CHECKSUM_COMP`,
  `PGChecksummablePage`, and `checksumBaseOffsets` are all visible at
  the include site — i.e. it implicitly depends on
  `checksum_impl.h` having been included first. [inferred]

## Potential issues

- File-wide. Re-using `#include` of a guard-less header as a textual
  macro is a niche pattern outside the project's usual style. The
  intent is clear from the head comment, but any tooling that
  auto-adds include guards (clang-tidy `llvm-header-guard`, IDE
  refactors) will break the build silently if pointed at this file.
  [ISSUE-style: guard-less header trips automatic-cleanup tooling (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-storage`](../../../../issues/include-storage.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)
