# `utils/ascii.h` — SIMD ASCII validation + safe strlcpy

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/ascii.h`)

## Role

Two utilities: `ascii_safe_strlcpy` (lossy copy that rejects non-ASCII /
NUL into a destination buffer) and `is_valid_ascii` (inline SIMD/SWAR
loop that checks a chunk of bytes for "pure 7-bit ASCII excluding NUL").
Used hot in COPY, JSON, encoding conversion, and parser scanners.

## Public API

- `void ascii_safe_strlcpy(char *dest, const char *src, size_t destsiz)`
  — `source/src/include/utils/ascii.h:16`. Out-of-line in `ascii.c`.
- `static inline bool is_valid_ascii(const unsigned char *s, int len)` —
  `:24-82`. Returns `false` if any zero byte or any high-bit-set byte
  appears in the chunk.

## Invariants

- `is_valid_ascii` requires `len % sizeof(Vector8) == 0` — the chunk size
  is 8 (SWAR) or 16 (SSE2/NEON) depending on platform.
  [verified-by-code, `:34`]
- The function returns `false` for any zero byte. The SWAR path adds 0x7F
  to each byte then ANDs into a "zero_cum" accumulator initialised to
  0x80; SIMD path uses `vector8_eq(chunk, 0)` directly.
  [verified-by-code, `:40-66`]
- The function returns `false` if any byte has the high bit set
  (i.e., is >= 0x80). [verified-by-code, `:65-66,72`]
- The SWAR comment explains why no carry-overflow concern: max byte after
  +0x7F is 0xFE, never carries. [from-comment, `:46-52`]

## Notable internals

The SWAR (no-SIMD) path is interesting: it uses the bit-arithmetic trick
`zero_cum &= (chunk + 0x7F)` to detect zeros without comparison. SIMD
path just uses `vector8_eq`. Both accumulate across chunks and check at
the end — branch-free per chunk.

## Trust-boundary / Phase D surface

- `len % sizeof(chunk) == 0` is enforced via `Assert` — in a release
  (non-cassert) build, callers passing a length that isn't a multiple
  of the chunk size will get **out-of-bounds reads** of up to 15 bytes
  past `s + len`. [ISSUE-correctness: `is_valid_ascii` reads past
  buffer end if `len % Vector8size != 0` and Assert is compiled out
  (likely)]
- The "tail" of a string of non-multiple length must be handled by the
  caller — the inline function makes no provision. Pretty common pattern
  in PG but easy to mis-call. [ISSUE-api-shape: caller-owned tail
  handling (nit)]
- `ascii_safe_strlcpy` is the only thing keeping non-ASCII bytes out of
  contexts that demand ASCII (log lines, system identifiers). Header
  doesn't document the rejection behaviour (does it stop at the first
  bad byte? substitute?). The .c file has the answer; header is silent.
  [ISSUE-documentation: `ascii_safe_strlcpy` semantics undocumented in
  header (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/pg_locale_c.h.md` — `pg_char_properties`
  is the byte-class lookup; this header is the bulk-validation
  counterpart.
- `source/src/include/port/simd.h` — `Vector8` typedef and operations.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-correctness: `is_valid_ascii` reads past `s + len` if `len % chunk
   != 0` and Assert is compiled out (likely)] —
   `source/src/include/utils/ascii.h:34`.
2. [ISSUE-api-shape: caller must handle the chunk-aligned tail (nit)] —
   `source/src/include/utils/ascii.h:24`.
3. [ISSUE-documentation: `ascii_safe_strlcpy` semantics undocumented in
   header (nit)] — `source/src/include/utils/ascii.h:16`.
