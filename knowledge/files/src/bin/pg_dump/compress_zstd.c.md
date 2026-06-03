---
path: src/bin/pg_dump/compress_zstd.c
anchor_sha: 4b0bf0788b0
loc: 595
depth: read
---

# compress_zstd.c

- **Source path:** `source/src/bin/pg_dump/compress_zstd.c`
- **Lines:** 595
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.h`, `pg_backup_utils.h`, zstd library `<zstd.h>`.

## Purpose

Zstandard implementation of both APIs. Uses zstd's high-level `ZSTD_CStream`/`ZSTD_DStream` streaming API with `ZSTD_compressStream2` / `ZSTD_decompressStream`. Exposes the `long_distance_matching` knob (`ZSTD_c_enableLongDistanceMatching`) via `PG_COMPRESSION_OPTION_LONG_DISTANCE`. The whole file body is `#ifndef USE_ZSTD`/`#else` — note this is inverted from gzip/lz4 which put `#ifdef USE_*` around the body and stubs `#else`. Same effect. [verified-by-code, compress_zstd.c:21-37, 21-33 stubs]

## Public surface

- `InitCompressorZstd(cs, spec)` (210) — fills the Compressor API vtable, asserts exactly one of `readF`/`writeF` is set, eagerly allocates the appropriate context (`ZSTD_createDStream` or `ZSTD_createCStream`) and its I/O buffers. **Output buffer is allocated 1 byte larger than `ZSTD_DStreamOutSize()`** so `ReadDataFromArchiveZstd` can stuff `'\0'` for the `ExecuteSqlCommandBuf` optimization. [from-comment, compress_zstd.c:236-244]
- `InitCompressFileHandleZstd(CFH, spec)` (575) — fills the stream vtable; `private_data` starts NULL and gets the `ZstdCompressorState` (containing `fp`) on `Zstd_open`. The compress/decompress context itself is lazily created on first `Zstd_write`/`Zstd_read_internal`. [verified-by-code, compress_zstd.c:274-284, 362-370, 575-592]
- `#ifndef USE_ZSTD` stubs (23, 30) — `pg_fatal("this build does not support compression with %s", "ZSTD")`. [verified-by-code, compress_zstd.c:22-33]

## Internal landmarks

- `ZstdCompressorState` (39) — `{ fp, cstream, dstream, output, input, zstderror }`. Single struct for both directions; one of `cstream`/`dstream` is non-NULL. [verified-by-code, compress_zstd.c:39-51]
- `_Zstd_CCtx_setParam_or_die` (60) — wrapper around `ZSTD_CCtx_setParameter` that `pg_fatal`s on `ZSTD_isError`. Used only on writes. [verified-by-code, compress_zstd.c:59-69]
- `_ZstdCStreamParams(compress)` (72) — `ZSTD_createCStream`, set level, conditionally set `ZSTD_c_enableLongDistanceMatching` if `PG_COMPRESSION_OPTION_LONG_DISTANCE` bit is set in `compress.options`. [verified-by-code, compress_zstd.c:71-90]
- `_ZstdWriteCommon(AH, cs, flush)` (93) — the compressor-API write loop: `ZSTD_compressStream2(.., flush ? ZSTD_e_end : ZSTD_e_continue)`, dump output buffer when full or when flushing, break on `res == 0` (frame end). [verified-by-code, compress_zstd.c:92-121]
- `EndCompressorZstd` (123) — dispatches based on `cs->readF`/`cs->writeF`: free the corresponding context + its src/dst buffer. [verified-by-code, compress_zstd.c:123-145]
- `WriteDataToArchiveZstd`, `ReadDataFromArchiveZstd` (147, 160) — the Compressor API directional entry points. `Read` uses `unconstify` because `ZSTD_inBuffer.src` is `const void *` but `readF` is allowed to realloc it (cast away const, then track new size). [verified-by-code, compress_zstd.c:147-207]

## Internal landmarks (Stream API)

- `Zstd_read_internal(ptr, size, CFH, exit_on_error)` (261) — workhorse: lazy `dstream` creation on first call; loop until output buffer is full or input EOF; `fread` into `input.src` when consumed; `ZSTD_decompressStream` into caller's `ptr`. Returns bytes produced; `-1` on error if `exit_on_error == false`. [verified-by-code, compress_zstd.c:260-347]
- `Zstd_write` (350) — lazy `cstream` creation, loop `ZSTD_compressStream2(ZSTD_e_continue)`, flush via `fwrite` when output full, ENOSPC synthesis on short write. [verified-by-code, compress_zstd.c:349-392]
- `Zstd_getc`, `Zstd_gets`, `Zstd_read` (394, 404, 429) — shims. `Zstd_gets` reads one byte at a time via `Zstd_read_internal(.., exit_on_error=false)` until newline or EOF — "only used to read the list of LOs, and the I/O is buffered anyway." [from-comment, compress_zstd.c:411-414]
- `Zstd_close` (435) — compressing branch: drain via `ZSTD_compressStream2(ZSTD_e_end)` loop with fwrite per output dump, free `cstream`, free output buffer; decompressing branch: free `dstream`, free input buffer; both: `fclose(fp)`. **Captures error text into `zstdcs->zstderror` rather than fatal-ing,** so `get_error_func` can return it. Then frees the state and returns success bool. [verified-by-code, compress_zstd.c:435-494]
- `Zstd_open` (504) — uses `pg_malloc_extended(... | MCXT_ALLOC_NO_OOM | MCXT_ALLOC_ZERO)`. **The only place in this file that does soft-OOM** — returns false on alloc failure rather than fatal. The dup-fd path closes the dup on `fdopen` failure. [verified-by-code, compress_zstd.c:504-556]
- `Zstd_open_write` (558) — `sprintf(fname, "%s.zst", path)` into a stack `char[MAXPGPATH]`. **Uses raw `sprintf`, not `snprintf`** — see gotchas. [verified-by-code, compress_zstd.c:558-565]
- `Zstd_get_error` (567) — returns `zstdcs->zstderror`, which is set by `Zstd_close` only. Other code paths leave it NULL. [verified-by-code, compress_zstd.c:567-573]
- `Zstd_eof` (496) — `feof(zstdcs->fp)`. Note this does **not** consult whether internal zstd buffers are drained, unlike `LZ4Stream_eof`. [verified-by-code, compress_zstd.c:496-502] [maybe — see gotchas]

## Invariants & gotchas

- **`PG_COMPRESSION_OPTION_LONG_DISTANCE` is the only sub-option exposed.** Setting it adds memory cost; the parameter value is read from `compress.long_distance`. [verified-by-code, compress_zstd.c:84-87]
- **`Assert((readF == NULL) != (writeF == NULL))`** in `InitCompressorZstd` (226). The Compressor API requires exactly one direction. [verified-by-code, compress_zstd.c:226]
- **Output buffer is `ZSTD_DStreamOutSize() + 1` bytes** in the read-side init (244) so `ahwrite` can null-terminate. Matches the gzip convention. [from-comment, compress_zstd.c:236-244]
- **`unconstify(void *, zstdcs->input.src)` cast.** `ZSTD_inBuffer.src` is typed `const void *` but the buffer is owned by us; the cast is needed for `pg_free` and `readF` realloc. Sound, but a minor C-pedantry trap. [verified-by-code, compress_zstd.c:132, 178, 309, 481]
- **`Zstd_eof` may return false when no more decompressed bytes are available.** Specifically, if `fp` has not yet hit EOF but `dstream` has consumed all input it's ever going to produce output from. A `_read_internal` returning 0 followed by an `eof_func` check would be a more reliable EOF signal — `Zstd_getc` already does this. Callers using `eof_func` directly may get stuck. [verified-by-code, compress_zstd.c:496-502 vs LZ4Stream_eof:329-337] [maybe]
- **`Zstd_open_write` uses `sprintf` to a `char[MAXPGPATH]` stack buffer.** `path` comes from pg_dump command-line args. If `path` length + 4 (`".zst"`) exceeds `MAXPGPATH = 1024`, this writes past the buffer. Caller-side validation may or may not exist; the other backends use `psprintf` (heap) so this is the outlier. **See ISSUE-pg-dump-A3-compress_zstd-sprintf-MAXPGPATH.** [verified-by-code, compress_zstd.c:561-564] [maybe]
- **`Zstd_close` swallows errors into `zstderror`,** unlike gzip/lz4 which `pg_log_error` and continue with a success bool. Net effect is similar (caller gets the bool) but Zstd's err text is sourced from `ZSTD_getErrorName` (library-controlled string) or `strerror`. No path/env leak. [verified-by-code, compress_zstd.c:435-494]
- **Lazy stream init has two sites.** `Zstd_open` creates the state struct + fp; `Zstd_read_internal`/`Zstd_write` create the dstream/cstream + buffers on first call. **`Zstd_open` does NOT create them,** so a caller that opens-and-immediately-closes a zstd file (no read or write) skips dstream/cstream allocation; `Zstd_close`'s `if (zstdcs->cstream)` / `if (zstdcs->dstream)` guards make this safe. [verified-by-code, compress_zstd.c:274-284, 362-370, 441, 478]

## Phase D — hostile-archive surface

- **Decompression bomb.** `Zstd_read_internal` and `ReadDataFromArchiveZstd` let `ZSTD_decompressStream` produce up to the caller-supplied `size` (or `ZSTD_DStreamOutSize()`) per call, then loop. No total output bound. Same shape as gzip/lz4. [verified-by-code, compress_zstd.c:329, 193]
- **Skippable frames.** Zstd's skippable frames (magic `0x184D2A5n`) are silently consumed by `ZSTD_decompressStream`. A hostile archive could pad with arbitrary skippable-frame contents; the library skips them (no content reaches us), so no decode-time issue. However, the **compressed size** of skippable frames is not bounded by output → an attacker could inflate the on-disk archive without affecting decompressed output (low-severity DoS — bandwidth). [inferred from zstd docs, compress_zstd.c:329] [maybe]
- **`MAXPGPATH` overflow** in `Zstd_open_write` (above). [maybe]
- **Error-message hygiene.** All errors use `ZSTD_getErrorName(res)` or `%m`. No filename injection. [verified-by-code, full file]
- **Input/output buffer sizes from library calls** (`ZSTD_DStreamInSize`, `ZSTD_DStreamOutSize`, `ZSTD_CStreamOutSize`). These are library-controlled positive constants, not attacker-influenced. [verified-by-code, compress_zstd.c:166, 234, 243, 250]

## Cross-references

- `compress_io.c` dispatches.
- Sibling backends `compress_gzip.c`, `compress_lz4.c`.

## Confidence tag tally
`[verified-by-code]=24 [from-comment]=2 [inferred]=1 [maybe]=4`
