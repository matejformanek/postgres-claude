---
path: src/bin/pg_dump/compress_lz4.c
anchor_sha: 4b0bf0788b0
loc: 805
depth: read
---

# compress_lz4.c

- **Source path:** `source/src/bin/pg_dump/compress_lz4.c`
- **Lines:** 805
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.h`, `pg_backup_utils.h`, LZ4 library `<lz4frame.h>`.

## Purpose

LZ4-frame-format implementation of both APIs. Uses the LZ4 frame format (not the raw block format), making the resulting `.lz4` files readable by the external `unlz4` utility. **Single `LZ4State` struct serves both compressor- and stream- API roles** (with lazy init via `LZ4Stream_init` in the stream case). The whole file is `#ifdef USE_LZ4`-gated; `#else` arms `pg_fatal`. [verified-by-code, compress_lz4.c:20-21, 39-79, 790-803]

## Public surface

- `InitCompressorLZ4(cs, spec)` (290) — fills the Compressor API vtable. Read-side returns immediately without allocating state ("Read operations have access to the whole input. No state needs to be carried between calls."); write-side allocates `LZ4State`, sets `prefs.compressionLevel` if `level >= 0`, calls `LZ4State_compression_init`. [from-comment + verified-by-code, compress_lz4.c:290-317]
- `InitCompressFileHandleLZ4(CFH, spec)` (767) — fills the stream vtable, allocates `LZ4State`, sets level if `>= 0`. **State is eagerly allocated but library context is lazy** via `LZ4Stream_init`. [verified-by-code, compress_lz4.c:767-789]
- `#else` stubs (791, 798) — `pg_fatal("this build does not support compression with %s", "LZ4")`. [verified-by-code, compress_lz4.c:790-803]

## Internal landmarks (shared)

- `LZ4State` (39) — the omnibus struct: `fp` (stream-API only), `prefs`, `ctx` (compress), `dtx` (decompress), `inited` lazy flag, `compressing` direction flag, three buffer regions (`buffer`/`outbuf`/`bufnext`/`outbufnext` etc.), `errcode`. [verified-by-code, compress_lz4.c:39-79]
- `LZ4State_compression_init` (91) — allocates the compression buffer sized to `LZ4F_compressBound(DEFAULT_IO_BUFFER_SIZE, prefs) + 50%`, but never smaller than `LZ4F_HEADER_SIZE_MAX` (32 bytes, fallback-defined if missing). Creates compression context, calls `LZ4F_compressBegin` to emit the frame header into the buffer. [verified-by-code, compress_lz4.c:91-143]
- `LZ4F_HEADER_SIZE_MAX` fallback (28) — defined locally to 32 if the installed library is older than v1.7.5. [verified-by-code, compress_lz4.c:27-29]

## Internal landmarks (Compressor API)

- `ReadDataFromArchiveLZ4` (152) — allocates `outbuf` and `readbuf` (both `DEFAULT_IO_BUFFER_SIZE`), creates a fresh decompression context, loops `cs->readF` then nested `LZ4F_decompress` calls until input is consumed, `ahwrite`s each chunk. [verified-by-code, compress_lz4.c:152-203]
- `WriteDataToArchiveLZ4` (205) — chunks input into ≤ `DEFAULT_IO_BUFFER_SIZE`, flushes the output buffer to `cs->writeF` when `LZ4F_compressBound(chunk) > free space`, calls `LZ4F_compressUpdate`. [verified-by-code, compress_lz4.c:205-243]
- `EndCompressorLZ4` (245) — flush + `LZ4F_compressEnd` to emit the frame footer; final `cs->writeF` of the buffered tail; `LZ4F_freeCompressionContext`; free buffers. [verified-by-code, compress_lz4.c:245-285]

## Internal landmarks (Stream API)

- `LZ4Stream_eof` (329) — true iff `outbufnext >= outbufdata && bufnext >= bufdata && feof(state->fp)`. The double-buffer EOF requires draining both stages. [verified-by-code, compress_lz4.c:329-337]
- `LZ4Stream_init(state, compressing)` (365) — lazy library setup; compressing path forwards to `LZ4State_compression_init`; decompressing path creates `dtx`, allocates `buffer` and `outbuf` at `DEFAULT_IO_BUFFER_SIZE` each. Idempotent on `state->inited`. [verified-by-code, compress_lz4.c:365-397]
- `LZ4Stream_read_internal` (409) — the workhorse for stream-API reads. Optional `eol_flag` for `gets_func`. Loops: drain `outbuf`; if empty, fread into `buffer`; `LZ4F_decompress` from `buffer` into `outbuf`. Returns -1 on error (errcode in state). [verified-by-code, compress_lz4.c:409-506]
- `LZ4Stream_write` (511) — lazy `LZ4Stream_init`, chunks input, flushes via `fwrite(state->fp)`, calls `LZ4F_compressUpdate`. ENOSPC synthesis on short fwrite. [verified-by-code, compress_lz4.c:511-555]
- `LZ4Stream_read`, `LZ4Stream_getc`, `LZ4Stream_gets` (560, 575, 595) — shims over `_read_internal`. `_gets` decrements `size - 1` and stuffs `'\0'`; passes `eol_flag=true`. [verified-by-code, compress_lz4.c:560-618]
- `LZ4Stream_close` (624) — compressing branch: drain + `LZ4F_compressEnd` + write footer + `LZ4F_freeCompressionContext`; decompressing branch: `LZ4F_freeDecompressionContext` + free `outbuf`; both: free `buffer`, free state, `fclose(fp)`. Returns success bool. [verified-by-code, compress_lz4.c:624-709]
- `LZ4Stream_open`, `LZ4Stream_open_write` (711, 747) — `fopen`/`fdopen(dup(fd))`; `_open_write` appends `.lz4` via `psprintf`. [verified-by-code, compress_lz4.c:711-762]

## Invariants & gotchas

- **Compressor-API read path has no persistent state.** `InitCompressorLZ4` returns immediately when `cs->readF` is set; `ReadDataFromArchiveLZ4` builds its own `dtx` on every invocation. [from-comment, compress_lz4.c:302-306]
- **Buffer sizing math.** `state->buflen = LZ4F_compressBound(DEFAULT_IO_BUFFER_SIZE) * 1.5`, floor at `LZ4F_HEADER_SIZE_MAX`. The "50% slop" comment explains: "the typical output block size is about 128K when DEFAULT_IO_BUFFER_SIZE = 128K." Changing `DEFAULT_IO_BUFFER_SIZE` may break this equivalence. [from-comment, compress_lz4.c:102-110]
- **`LZ4F_HEADER_SIZE_MAX` fallback.** Pre-v1.7.5 LZ4 libs lack the macro; local fallback to 32. If LZ4 ever increased the header above 32 in a future version we'd undercount, but the buffer also gets the `compressBound + 50%` upper bound which dominates for realistic inputs. [verified-by-code, compress_lz4.c:27-29]
- **`compressionLevel < 0` not propagated.** The check `if (cs->compression_spec.level >= 0)` (309, 785) leaves `prefs.compressionLevel` zero-initialized (LZ4 default) when `level < 0`. The corollary: `--compress=lz4:-3` is silently treated as "default" rather than "fast mode" (LZ4 supports negative levels for fast acceleration). [verified-by-code, compress_lz4.c:309-310, 785-786] [maybe — feature gap]
- **Lazy stream init.** `LZ4Stream_init` is idempotent (`state->inited` short-circuits). Important for `LZ4Stream_write` and `_read_internal` both calling it; the second call is a no-op. [verified-by-code, compress_lz4.c:370-371]
- **fread loop uses `< state->buflen && !feof()` as the error signal** (468). A short read with neither error nor EOF is treated as an error (`could not read from input file`). This is conservative — POSIX permits short reads on regular files in some edge cases — but pg_dump only deals with regular files. [verified-by-code, compress_lz4.c:467-472]
- **`LZ4F_decompress` failure → `pg_log_error` then `return -1`.** In the stream API. The compressor-API path `pg_fatal`s instead (186-189). Inconsistent severity for the same library error. [verified-by-code, compress_lz4.c:186-189, 492-498]
- **`LZ4Stream_close` releases `outbuf` only in the decompressing branch** (691). In the compressing branch the buffer (`state->buffer`) is freed at 694; `outbuf` is never allocated for compression. Symmetric and correct. [verified-by-code, compress_lz4.c:681-695]
- **Error-message hygiene.** All error messages use `LZ4F_getErrorName(status)` (LZ4-internal text) or `%m`. No filename/env leak. [verified-by-code, full file]

## Phase D — hostile-archive surface

- **Decompression bomb.** `ReadDataFromArchiveLZ4` and `_read_internal` both let `LZ4F_decompress` write up to `DEFAULT_IO_BUFFER_SIZE` per call; the outer loop continues until input EOF. No output-size bound. Same DoS shape as the gzip backend. [verified-by-code, compress_lz4.c:185-194, 487-502]
- **Frame-format error handling.** `LZ4F_isError(status)` covers malformed frame headers, bad block checksums, truncated frames — they all fatal (or `return -1` in the stream API). The library's own size checks defend against integer-overflow on block-size headers (since LZ4 v1.9.x); we rely on that. **See ISSUE-pg-dump-A3-compress_lz4-trusts-library-size-checks.** [verified-by-code, compress_lz4.c:186-189, 492-498] [maybe]
- **`fread` reads up to `buflen = DEFAULT_IO_BUFFER_SIZE` into `state->buffer`.** No per-frame size header consumed by us — we hand bytes to `LZ4F_decompress` which interprets the frame internally. So a hostile size header inside an LZ4 block doesn't reach our integer math; the LZ4 library handles it. [verified-by-code, compress_lz4.c:467, 487-491]
- **`Assert(input->size <= input_allocated_size)`** (292-293 in zstd; here at `Assert` in `_read_internal`'s loop, 292-293 in the zstd file rather than this one). The lz4 path has no analogous assert, but it constrains via `fread(.., state->buflen, ..)` which can't overflow. [verified-by-code, compress_lz4.c:467]
- **No "skip frame" handling.** LZ4 has skippable frames; the standard `LZ4F_decompress` handles them silently per its docs. Nothing in this file inspects frame contents. [inferred, compress_lz4.c]

## Cross-references

- `compress_io.c` dispatches.
- Sibling backends `compress_gzip.c`, `compress_zstd.c`.

## Confidence tag tally
`[verified-by-code]=22 [from-comment]=4 [inferred]=1 [maybe]=2`
