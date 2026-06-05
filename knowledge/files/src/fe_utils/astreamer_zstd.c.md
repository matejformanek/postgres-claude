# `src/fe_utils/astreamer_zstd.c`

- **File:** `source/src/fe_utils/astreamer_zstd.c` (369 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

zstd handling for the backup stream. Like lz4 (and unlike gzip) it is a
symmetric pair of mid-chain streamers: `astreamer_zstd_compressor` compresses
input and forwards zstd-frame bytes to its successor;
`astreamer_zstd_decompressor` reverses it. Both share `astreamer_zstd_frame`,
holding a `ZSTD_CCtx`/`ZSTD_DCtx` and a libzstd `ZSTD_outBuffer` view onto the
base `bbs_buffer`. The file is wrapped in `#ifdef USE_ZSTD`; without libzstd the
constructors `pg_fatal` (`:130`, `:285`). [verified-by-code]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer_zstd_compressor_new` | :69 | Construct a zstd compressor feeding `next`; sets level and optional `nbWorkers` / long-distance matching from `compress`. Output buffer = `ZSTD_CStreamOutSize()`. |
| `astreamer_zstd_decompressor_new` | :258 | Construct a zstd decompressor feeding `next`; output buffer = `ZSTD_DStreamOutSize()`. |

## Internal landmarks

- **shared struct** (`:29-36`): `cctx`/`dctx` (one live), plus a
  `ZSTD_outBuffer zstd_outBuf` whose `.dst` aliases `bbs_buffer.data`, `.size =
  maxlen`, `.pos` = current fill.
- **vtables:** `astreamer_zstd_compressor_ops` (`:45`),
  `astreamer_zstd_decompressor_ops` (`:58`).
- **compressor setup** (`:69-133`): buffer sized to `ZSTD_CStreamOutSize()`
  (`:85`); `ZSTD_createCCtx`; sets `ZSTD_c_compressionLevel` (`:92-96`), and,
  gated on `compress->options` flags, `ZSTD_c_nbWorkers` (`:99-111`) and
  `ZSTD_c_enableLongDistanceMatching` (`:113-121`) — each a `pg_fatal` on error.
  Initializes `zstd_outBuf` over the buffer (`:124-126`). [verified-by-code]
- **compressor content** (`:145-185`): `ZSTD_inBuffer inBuf = {data, len, 0}`;
  `while (inBuf.pos < inBuf.size)`: if remaining out space `< ZSTD_compressBound(...)`
  it flushes `zstd_outBuf.pos` bytes downstream and resets the out buffer
  (`:163-175`), then `ZSTD_compressStream2(..., ZSTD_e_continue)` (`:177-179`),
  error → `pg_fatal`. [verified-by-code]
- **compressor finalize** (`:190-237`): `do { ... ZSTD_compressStream2(...,
  ZSTD_e_end) } while (yet_to_flush > 0)`, flushing/resetting the out buffer as
  needed, then forwards any final bytes and finalizes the successor (`:196-236`).
- **decompressor setup** (`:258-288`): buffer sized to `ZSTD_DStreamOutSize()`
  (`:272`) — a *fixed* libzstd-recommended output block; `ZSTD_createDCtx`;
  initializes `zstd_outBuf` (`:279-281`).
- **decompressor content** (`:296-333`) — the bomb-relevant loop:
  - `ZSTD_inBuffer inBuf = {data, len, 0}`; `while (inBuf.pos < inBuf.size)`.
  - If `zstd_outBuf.pos >= zstd_outBuf.size` (output full), flush `pos` bytes
    downstream with the incoming `context` and reset the out buffer to the start
    of `bbs_buffer` (`:313-324`).
  - `ZSTD_decompressStream(dctx, &zstd_outBuf, &inBuf)` (`:326-327`), error →
    `pg_fatal`. **The output buffer is fixed and never enlarged.** [verified-by-code]
- **decompressor finalize** (`:338-354`): flushes any partial buffer as
  `ASTREAMER_UNKNOWN`, finalizes successor.
- **free** (`:242-251`, `:359-368`): free successor, `ZSTD_freeCCtx` /
  `ZSTD_freeDCtx`, free buffer + self.

## Invariants & gotchas

- **Decompressor output buffer is fixed (`ZSTD_DStreamOutSize()`), never
  enlarged.** As with gzip/lz4, a zstd bomb is **memory-bounded**: the decode
  loop fills one libzstd-recommended output block and drains downstream
  repeatedly (`:313-324`). The compressor's buffer (`ZSTD_CStreamOutSize()`) is
  likewise fixed and only flushed, not grown (contrast lz4's compressor, which
  *does* enlarge). This is the A5 datapoint for zstd. [verified-by-code]
- **`zstd_outBuf` aliases `bbs_buffer.data`.** The libzstd out-buffer view is set
  up once and re-pointed at `bbs_buffer.data` after every flush (`:172-174`,
  `:321-323`); the StringInfo data is never reallocated on the hot path, so the
  alias stays valid. [verified-by-code]
- **Output `context` preserved across flushes** (`:169`, `:318`); finalize
  flushes hardcode `ASTREAMER_UNKNOWN` (`:211`, `:233`, `:351`). [verified-by-code]
- **Multithreaded compression is optional** and silently feature-gated: setting
  `nbWorkers` is attempted only when `PG_COMPRESSION_OPTION_WORKERS` is set, and
  is expected to fail on old/non-threaded libzstd (comment `:101-105`).
  [from-comment]
- **Frontend memory:** `palloc0_object`, `initStringInfo`/`enlargeStringInfo`,
  `pfree`; errors via `pg_fatal` carrying `ZSTD_getErrorName`. [verified-by-code]

## Cross-references

- `knowledge/files/src/fe_utils/astreamer_lz4.c.md` — the closely parallel
  symmetric streamer (note the compressor buffer-enlarge difference).
- `knowledge/files/src/fe_utils/astreamer_gzip.c.md` — the asymmetric outlier.
- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — typical successor of the
  decompressor.
- `source/src/include/fe_utils/astreamer.h` — `astreamer`/`astreamer_ops`.
- `source/src/common/compression.c` — `pg_compress_specification`,
  `PG_COMPRESSION_OPTION_*` flags.

## Potential issues

- **[ISSUE-question: no cumulative decompressed-size cap]**
  `astreamer_zstd.c:296` — arbitrarily large plaintext from a small zstd frame;
  resident memory bounded (`ZSTD_DStreamOutSize()`) but total decompressed
  output forwarded/written is unbounded and server-controlled. Same A5
  streaming-bounds-memory-not-output caveat as gzip/lz4; defense-in-depth note,
  not a live bug (server is the base-backup trust root). (nit)

## Confidence tag tally

- `[verified-by-code]` × 11
- `[from-comment]` × 1
