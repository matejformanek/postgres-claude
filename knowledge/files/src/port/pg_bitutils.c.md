---
path: src/port/pg_bitutils.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 194
depth: read
---

# src/port/pg_bitutils.c

## Purpose

Out-of-line backing for the bit-manipulation helpers declared inline in
`src/include/port/pg_bitutils.h`: the 256-entry lookup tables for
leftmost/rightmost set-bit and per-byte popcount, plus the **portable**
software popcount over a buffer. The CPU-feature-dispatched fast paths
(`pg_popcount_optimized` via x86-64 `POPCNTQ` or ARM NEON) live in sibling
files (`pg_popcount_avx512.c`, etc.); this file supplies both the tables and,
when no special instruction is available, the function-pointer targets resolve
to the portable code here. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `const uint8 pg_leftmost_one_pos[256]` | `pg_bitutils.c:27` | Position of MSB set bit per byte value (entry 0 unused) |
| `const uint8 pg_rightmost_one_pos[256]` | `pg_bitutils.c:55` | Position of LSB set bit per byte value |
| `const uint8 pg_number_of_ones[256]` | `pg_bitutils.c:80` | Popcount per byte value |
| `uint64 pg_popcount_portable(const char *buf, int bytes)` | `pg_bitutils.c:104` | Software popcount over a buffer |
| `uint64 pg_popcount_masked_portable(const char *buf, int bytes, uint8 mask)` | `pg_bitutils.c:136` | Popcount after masking each byte |
| `uint64 pg_popcount_optimized` / `pg_popcount_masked_optimized` | `:179` / `:189` | Defined here only when no SIMD/POPCNT path exists |

## Internal landmarks

- The three lookup tables are exported even when `HAVE__BUILTIN_CLZ`/`CTZ` makes
  them unused internally, "so that extensions possibly compiled with a different
  compiler can use it" (`pg_bitutils.c:23-25`, `:51-53`).
- `pg_popcount_portable` (`:104-129`) — processes 8-byte aligned chunks via
  `pg_popcount64` when the pointer is 8-aligned, then mops up trailing bytes
  through the table.
- The masked variant (`:136-163`) broadcasts the mask byte across a word with
  `maskv = ~UINT64CONST(0) / 0xFF * mask` (`:142`) — a neat single-byte-to-8-byte
  splat — then ANDs before counting.
- `#if !defined(HAVE_X86_64_POPCNTQ) && !defined(USE_NEON)` (`:165`) — only then
  does this file provide `pg_popcount_optimized` as a thin wrapper over the
  portable version; otherwise the optimized symbols live in the SIMD files.

## Invariants & gotchas

- **Entry 0 of the position tables must not be used** — there is no set bit in a
  zero byte; the comment flags this (`:21`, `:48`). Callers guard the zero case.
- The 8-byte fast path in the portable popcount is gated on pointer alignment
  (`buf == TYPEALIGN(8, buf)`); misaligned buffers fall straight to the
  byte-at-a-time loop, still correct, just slower.

## Cross-refs

- `knowledge/files/src/include/port/pg_bitutils.h.md` (if present) — the inline
  declarations and dispatch macros.
- `knowledge/files/src/backend/utils/adt/bit.c.md` — a popcount consumer.
