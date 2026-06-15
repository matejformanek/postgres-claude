---
path: src/port/pg_crc32c_sb8.c
anchor_sha: e18b0cb7344
loc: 1169
depth: read
---

# src/port/pg_crc32c_sb8.c

## Purpose

Pure-software CRC32C using the Kounavis/Berry "slicing-by-8" table-lookup
algorithm. This is the universal fallback on any platform that lacks
SSE4.2/ARMv8-CRC/LoongArch-CRC hardware, and the baseline against which
SIMD arms are tested. The bulk of the file is the eight 256-entry lookup
tables (`pg_crc32c_table[8][256]`) for the Castagnoli polynomial — ~1000
lines of constants. The runtime is ~100 lines of code at the top.
`[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `pg_crc32c pg_comp_crc32c_sb8(pg_crc32c crc, const void *data, size_t len)` | `pg_crc32c_sb8.c:35` | Slicing-by-8 software CRC32C |
| `static const uint32 pg_crc32c_table[8][256]` | `:109` | 8 × 256 lookup tables; little-endian stored even on big-endian builds |

## Internal landmarks

- `CRC8(x)` macro (`:28-32`) — byte-at-a-time variant with two arms:
  big-endian shifts the high byte of `crc` out, little-endian the low byte.
  Used for the alignment preamble and the trailing residue.
- Alignment preamble (`:44-48`) — chews 0-3 bytes one at a time so the main
  loop starts on a 4-byte boundary (the loop reads two `uint32`s = 8 bytes
  but the table lookups want byte access via shift; 4-byte alignment is
  sufficient on every platform we care about).
- Main slicing-by-8 loop (`:54-86`) — reads two `uint32` words, XORs the
  first with the running CRC, then splits both into eight bytes via shifts,
  one byte per slice table. Final CRC is the XOR of all eight table lookups.
  This is exactly the algorithm from Kounavis & Berry 2008 (cited in the
  file header).
- Big-endian byte split (`:60-67`) vs little-endian (`:69-76`) — different
  shift directions; the tables themselves are stored in little-endian byte
  order even on big-endian builds, per the comment block at `:101-108`.
  `[from-comment]`
- Trailing residue (`:91-96`) — byte-at-a-time `CRC8` over the last 0-7
  bytes.

## Invariants & gotchas

- **Tables are byte-reversed on big-endian builds.** The comment at `:101-108`
  flags this: tables store little-endian regardless of host endianness, with
  the endian-specific shift logic in the loop accounting for the difference.
  Bit-exact agreement with the SSE4.2/ARMv8 hardware variants is the
  invariant — any mismatch would corrupt cross-platform replication. `[from-comment]`
- **This is the dispatch-fallback floor.** When neither SSE4.2 nor ARMv8 CRC
  is detected at runtime, this is what runs. WAL/page checksums on ancient
  x86_64-without-SSE4.2, or 32-bit i386, fall here. Performance is roughly
  1 GB/s per core vs ~10 GB/s for SSE4.2 — but the correctness invariant
  is what matters.
- The table polynomial is **Castagnoli (0x1EDC6F41)** — same as iSCSI CRC32C,
  not zlib's CRC32. Identical polynomial to what hardware CRC32 instructions
  on Intel/ARM compute. `[from-comment]`

## Cross-refs

- `knowledge/files/src/port/pg_crc32c_sse42.c.md` — x86 hardware accelerator.
- `knowledge/files/src/port/pg_crc32c_armv8.c.md` — ARM hardware accelerator.
- `knowledge/files/src/port/pg_crc32c_loongarch.c.md` — LoongArch hardware
  accelerator.
- Kounavis & Berry, "Novel Table Lookup-Based Algorithms for High-Performance
  CRC Generation", IEEE TC 2008, doi:10.1109/TC.2008.85 (cited in file
  header).
