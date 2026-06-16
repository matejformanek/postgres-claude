# `src/fe_utils/astreamer_lz4.c`

- **File:** `source/src/fe_utils/astreamer_lz4.c` (425 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

LZ4-frame handling for the backup stream. Unlike gzip (writer + decompressor),
lz4 provides a symmetric pair of mid-chain streamers: `astreamer_lz4_compressor`
compresses input and forwards lz4-frame bytes to its successor, and
`astreamer_lz4_decompressor` does the reverse. Both share one struct
(`astreamer_lz4_frame`) holding either a compression or decompression context.
The file is wrapped in `#ifdef USE_LZ4`; without liblz4 the constructors
`pg_fatal` (`:102`, `:302`). [verified-by-code]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer_lz4_compressor_new` | :71 | Construct an lz4 compressor feeding `next`; `LZ4F_max256KB` block size, level from `compress->level`. |
| `astreamer_lz4_decompressor_new` | :276 | Construct an lz4 decompressor feeding `next`; fixed ~256 KB output buffer. |

## Internal landmarks

- **shared struct** (`:28-38`): `cctx`/`dctx` (only one is live), `prefs`,
  `bytes_written` (output-buffer fill), `header_written` (compressor only).
- **vtables:** `astreamer_lz4_compressor_ops` (`:47`),
  `astreamer_lz4_decompressor_ops` (`:60`).
- **compressor setup** (`:71-105`): `initStringInfo` (no pre-enlarge — the
  buffer grows on demand, see below), `prefs.frameInfo.blockSizeID =
  LZ4F_max256KB`, `LZ4F_createCompressionContext`.
- **compressor content** (`:117-195`):
  - Writes the lz4 frame header lazily on the first chunk via
    `LZ4F_compressBegin` into `bbs_buffer.data`, recording `bytes_written`
    (`:133-147`).
  - Computes `out_bound = LZ4F_compressBound(len, &prefs)` and, if the remaining
    buffer space `avail_out < out_bound`, **flushes** the buffer downstream and
    then **`enlargeStringInfo(&bbs_buffer, out_bound)` if the whole buffer is
    smaller than `out_bound`** (`:161-176`). So the compressor's output buffer
    can grow to whatever a single input chunk's bound demands.
  - `LZ4F_compressUpdate(cctx, next_out, avail_out, next_in, len, NULL)`
    (`:186-188`), error → `pg_fatal`. [verified-by-code]
- **compressor finalize** (`:200-254`): same bound/flush/enlarge dance for the
  footer (`LZ4F_compressBound(0)`), `LZ4F_compressEnd` to flush the frame,
  forwards remaining bytes, finalizes successor. [verified-by-code]
- **decompressor setup** (`:276-305`): `initStringInfo` then
  `enlargeStringInfo(..., 256*1024 - 1)` — a *fixed* ~256 KB output buffer
  "comparable to the compressor's" (`:291-292`); `LZ4F_createDecompressionContext`.
- **decompressor content** (`:313-386`) — the bomb-relevant loop:
  - `next_in/avail_in` = input chunk; `next_out` at `bbs_buffer.data +
    bytes_written`, `avail_out = maxlen - bytes_written` (`:325-329`).
  - `while (avail_in > 0)`: `read_size`/`out_size` are dual in/out params to
    `LZ4F_decompress` reporting bytes consumed/produced (`:337-355`); error →
    `pg_fatal`.
  - Advances input/output cursors (`:362-368`); when the fixed output buffer
    fills (`bytes_written >= maxlen`) it flushes `maxlen` downstream with the
    incoming `context` and resets (`:374-384`). **The output buffer is never
    enlarged on the decompress path.** [verified-by-code]
- **decompressor finalize** (`:391-409`): flushes any partial buffer as
  `ASTREAMER_UNKNOWN`, finalizes successor.
- **free** (`:259-269`, `:414-424`): free successor, free the lz4 context
  (`LZ4F_freeCompressionContext` / `LZ4F_freeDecompressionContext`), free buffer
  + self.

## Invariants & gotchas

- **Asymmetric buffer sizing — only the COMPRESSOR enlarges.** The compressor
  grows `bbs_buffer` to satisfy `LZ4F_compressBound` for the current chunk
  (`:170-171`, `:222-223`); the **decompressor uses a fixed ~256 KB output
  buffer and flushes in a loop** (`:374`). A decompression bomb therefore stays
  memory-bounded at ~256 KB resident, like gzip — it does not over-allocate on
  the decompress side. This is the A5 datapoint for lz4. [verified-by-code]
- **Output `context` preserved across flushes** on both paths (`:167`, `:379`);
  finalize flushes hardcode `ASTREAMER_UNKNOWN` (`:219`, `:251`, `:406`).
  [verified-by-code]
- **One context per struct.** `cctx` and `dctx` coexist in the struct but only
  the one matching the chosen ops is created/freed; the other stays NULL.
  [verified-by-code]
- **Frontend memory:** `palloc0_object`, `initStringInfo`/`enlargeStringInfo`,
  `pfree`; errors via `pg_fatal` carrying `LZ4F_getErrorName`. [verified-by-code]
- **Buffer ownership:** the streamer owns `bbs_buffer`; `bytes_written` is the
  logical fill, reset to 0 after every downstream flush. [verified-by-code]

## Cross-references

- `knowledge/files/src/fe_utils/astreamer_gzip.c.md`,
  `knowledge/files/src/fe_utils/astreamer_zstd.c.md` — sibling
  compressor/decompressor streamers; gzip is the asymmetric writer/decompressor
  outlier.
- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — typical successor of the
  decompressor.
- `source/src/include/fe_utils/astreamer.h` — `astreamer`/`astreamer_ops`,
  `astreamer_content`/`_finalize`/`_free`.
- `source/src/common/compression.c` — `pg_compress_specification`.

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: no cumulative decompressed-size cap]**
  `astreamer_lz4.c:313` — the decompressor emits an arbitrarily large plaintext
  from a small lz4 frame; resident memory is bounded (~256 KB) but total output
  forwarded downstream (and written to disk) is unbounded and server-controlled.
  Same A5 streaming-bounds-memory-not-output caveat as gzip/zstd; server is the
  base-backup trust root, so defense-in-depth note rather than a live bug. (nit)

## Confidence tag tally

- `[verified-by-code]` × 12
