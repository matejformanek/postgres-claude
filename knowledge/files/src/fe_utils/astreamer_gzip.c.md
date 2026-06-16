# `src/fe_utils/astreamer_gzip.c`

- **File:** `source/src/fe_utils/astreamer_gzip.c` (397 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

gzip handling for the backup stream. Two streamers, intentionally asymmetric
with lz4/zstd: `astreamer_gzip_writer` is a *sink* — it gzip-compresses input
and writes it straight to a `gzFile` (no `bbs_next`), inherited from the older
pre-modular pg_basebackup code (`:10-18`). `astreamer_gzip_decompressor` is a
mid-chain streamer that inflates a gzip stream and forwards plaintext to its
successor (typically `astreamer_tar_parser`). The whole file is wrapped in
`#ifdef HAVE_LIBZ`; without zlib the `_new` constructors `pg_fatal` (`:140`,
`:275`). [verified-by-code]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer_gzip_writer_new` | :98 | Construct a gzip sink writing to `pathname` (via `gzopen`) or to a `dup`'d fd of the caller's `FILE` (via `gzdopen`). Sets level via `gzsetparams`. |
| `astreamer_gzip_decompressor_new` | :235 | Construct a gzip→plaintext streamer feeding `next`; `inflateInit2(zs, 15+16)` for gzip-wrapped inflate. |

## Internal landmarks

- **vtables:** `astreamer_gzip_writer_ops` (`:61`),
  `astreamer_gzip_decompressor_ops` (`:76`).
- **writer struct** (`:39-44`): `pathname` + a `gzFile`. **decompressor struct**
  (`:46-51`): a `z_stream` plus `bytes_written` (current fill of the output
  buffer).
- **writer fd duplication** (`:120-132`): when handed a caller `FILE`, it
  `dup(fileno(file))` and `gzdopen`s the copy, because `gzclose` would otherwise
  close the caller's underlying fd (`:120-123`, finalize comment `:172-181`). On
  `dup` failure → `pg_fatal("could not duplicate stdout")`. [verified-by-code]
- **writer content** (`:149-170`): no-op on `len==0`; `gzwrite(...) != len`
  triggers the standard `errno==0 ⇒ ENOSPC` then `pg_fatal` idiom.
- **writer finalize** (`:182-195`): `gzclose` (always closes the fd — that is
  why `_new` dup'd it) then NULLs `gzfile`. **writer free** (`:200-212`): asserts
  leaf (`bbs_next==NULL`) and `gzfile==NULL`, frees pathname + self.
- **decompressor buffer** (`:249-251`): `initStringInfo` then
  `enlargeStringInfo(..., 256*1024 - 1)` — a fixed ~256 KB plaintext output
  buffer, "comparable to the other decompressors" (`:250`). [from-comment]
- **zlib allocator hooks** (`:255-256`, `:382-396`): `zalloc=gzip_palloc`,
  `zfree=gzip_pfree` wrap `palloc(items*size)`/`pfree`, routing zlib's internal
  allocations through the frontend memory system. [verified-by-code]
- **decompressor content** (`:286-337`) — the bomb-relevant loop:
  - `next_in/avail_in` point at the input chunk (`:298-299`); loops
    `while (avail_in > 0)`.
  - Each iteration aims `next_out` at `bbs_buffer.data + bytes_written` with
    `avail_out = maxlen - bytes_written` (`:308-311`), then
    `inflate(zs, Z_NO_FLUSH)` (`:319`).
  - Non-`Z_OK`/`Z_STREAM_END`/`Z_BUF_ERROR` → `pg_fatal("could not decompress
    data")` (`:321-323`).
  - `bytes_written = maxlen - avail_out` (`:325-326`); when the output buffer is
    full it flushes the whole `maxlen` downstream as a `content` call of the
    *same* `context`, then resets `bytes_written = 0` (`:329-335`). [verified-by-code]
- **decompressor finalize** (`:342-360`): flushes any partial buffer as an
  `ASTREAMER_UNKNOWN` chunk, then finalizes the successor.
- **decompressor free** (`:365-376`): frees successor, `inflateEnd(&zstream)`,
  frees buffer + self.

## Invariants & gotchas

- **No unbounded output buffer — decompression bomb is bounded per flush.** The
  plaintext output buffer is a *fixed* ~256 KB (`:251`); the inflate loop fills
  it and drains downstream repeatedly. A high-ratio gzip bomb therefore does NOT
  cause a single huge allocation in this streamer — it produces many 256 KB
  chunks. The total work/output is still attacker-controlled (the stream can
  expand to any size and is written to disk downstream), but memory stays
  bounded. This is the key A5 datapoint: the *streaming* decompressors cap
  resident memory even though they place no cap on cumulative decompressed
  output. [verified-by-code]
- **Output `context` is preserved across flushes.** Each forwarded chunk carries
  the incoming `context` (`:333`) so the tar parser downstream still sees
  `ASTREAMER_UNKNOWN`. The finalize flush hardcodes `ASTREAMER_UNKNOWN` (`:357`).
  [verified-by-code]
- **`windowBits = 15+16`** selects max window + gzip header decoding (`:270`);
  comment notes it must be ≥ the compressor's windowBits, so the max is used for
  safety (`:260-269`). [from-comment]
- **Writer is a leaf**, decompressor is mid-chain. The writer's `gzFile`
  bypasses the `FILE` API and operates on a raw fd, so callers mixing other
  writes to the same `FILE` must beware (`:93-96`). [from-comment]
- **Frontend memory:** `palloc0_object`, `pstrdup`, `pfree`; even zlib-internal
  allocs go through `palloc` (`:255-256`). Errors via `pg_fatal`. [verified-by-code]

## Cross-references

- `knowledge/files/src/fe_utils/astreamer_lz4.c.md`,
  `knowledge/files/src/fe_utils/astreamer_zstd.c.md` — the symmetric
  compressor/decompressor pairs this file is contrasted with.
- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — the usual successor of the
  decompressor (plaintext → tar demux).
- `source/src/include/fe_utils/astreamer.h` — `astreamer`/`astreamer_ops`,
  `bbs_buffer`, `astreamer_content`/`_finalize`/`_free`.
- `source/src/common/compression.c` — `pg_compress_specification` (level, etc.).

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: no cumulative decompressed-size cap]**
  `astreamer_gzip.c:286` — the decompressor will inflate an arbitrarily large
  plaintext from a small gzip input; memory is bounded (256 KB) but the
  cumulative output forwarded downstream (and ultimately written to disk by the
  extractor) is unbounded and fully server-controlled. Consistent with the A5
  decompression-bomb theme: streaming bounds memory, not total output / disk
  use. For base backups the server is the trust root, so this is a
  defense-in-depth note, not a live bug. (nit)

## Confidence tag tally

- `[verified-by-code]` × 11
- `[from-comment]` × 4
