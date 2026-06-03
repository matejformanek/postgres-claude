---
path: src/bin/pg_dump/compress_gzip.c
anchor_sha: 4b0bf0788b0
loc: 463
depth: read
---

# compress_gzip.c

- **Source path:** `source/src/bin/pg_dump/compress_gzip.c`
- **Lines:** 463
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.h` (vtable), `pg_backup_utils.h` (`pg_fatal`), zlib `<zlib.h>`.

## Purpose

zlib-based implementation of both APIs. **Compressor API** uses zlib's `deflate`/`inflate` low-level stream API (over the raw zlib format embedded in the custom archive's block layout). **Stream API** uses zlib's `gzopen`/`gzread`/`gzwrite` high-level wrappers — which write a gzip-formatted file the external `gunzip` utility can read. The whole file is `#ifdef HAVE_LIBZ`-gated; the `#else` arms provide stub `Init*` that `pg_fatal` immediately. [verified-by-code, compress_gzip.c:14-20, 448-462]

## Public surface

- `InitCompressorGzip(cs, spec)` (238) — fills the `CompressorState` vtable. If `cs->writeF` is set, calls `DeflateCompressorInit` to set up zlib state; the read-side does not pre-init (it's set up on first `ReadDataFromArchiveGzip` call). [verified-by-code, compress_gzip.c:238-255]
- `InitCompressFileHandleGzip(CFH, spec)` (430) — fills the stream vtable; `private_data` starts NULL, gets populated on `open_func`. [verified-by-code, compress_gzip.c:430-447]
- `#else` stubs (449, 456) — both `pg_fatal("this build does not support compression with %s", "gzip")`. [verified-by-code, compress_gzip.c:449-461]

## Internal landmarks (Compressor API — deflate/inflate)

- `GzipCompressorState` (36) — wraps a `z_streamp` plus an output buffer (`outbuf`, `outsize`). The `outbuf` is allocated 1 byte larger than `outsize` because "some routines want to append a trailing zero byte to the zlib output". [from-comment, compress_gzip.c:66-72]
- `DeflateCompressorInit` (54) — `pg_malloc0` the state, `pg_malloc(outsize+1)` the output buffer, `deflateInit(zp, level)`. Asserts `level != 0` because **level 0 is dispatched to the "None" compressor, not zlib-with-no-compression**. [verified-by-code, compress_gzip.c:54-86]
- `DeflateCompressorCommon` (110) — the deflate workhorse. Loops calling `deflate(zp, flush ? Z_FINISH : Z_NO_FLUSH)`, drains the output to `cs->writeF` whenever the output buffer has bytes, breaks on `Z_STREAM_END`. Explicitly avoids zero-length output chunks because "a zero length chunk is the EOF marker in the custom format". [from-comment + verified-by-code, compress_gzip.c:110-150]
- `DeflateCompressorEnd` (88) — sets `avail_in=0` then calls `DeflateCompressorCommon(.., flush=true)` to drain, then `deflateEnd`. [verified-by-code, compress_gzip.c:88-108]
- `EndCompressorGzip` (152) — guards on `cs->private_data != NULL` and forwards to `DeflateCompressorEnd`. [verified-by-code, compress_gzip.c:152-158]
- `WriteDataToArchiveGzip` (160) — sets `next_in`/`avail_in`, calls `DeflateCompressorCommon(.., flush=false)`. [verified-by-code, compress_gzip.c:160-169]
- `ReadDataFromArchiveGzip` (171) — sets up a fresh `z_stream` per call (no pre-init), loops `cs->readF` for compressed input and `inflate(zp, 0)` for output, NULL-terminates the output then `ahwrite`s it. Drains until `Z_STREAM_END`. **Per-call alloc/free of `z_stream`, `buf`, `out`.** [verified-by-code, compress_gzip.c:171-235]

## Internal landmarks (Stream API — gzopen-style)

- `Gzip_read` (263) — `gzread`; treats `<= 0` as either EOF (if `gzeof`) or fatal error. Distinguishes `Z_ERRNO` (use `strerror(errno)`) from other zlib errors (use `gzerror` message). [verified-by-code, compress_gzip.c:263-295]
- `Gzip_write` (297) — `gzwrite`; pg_fatal on short write with the same `Z_ERRNO` / `gzerror` discrimination. [verified-by-code, compress_gzip.c:297-310]
- `Gzip_getc` (312) — `gzgetc` (the function, **not** the macro — see file-top `#undef gzgetc` and the NetBSD bug citation). [verified-by-code + from-comment, compress_gzip.c:23-30, 312-329]
- `Gzip_gets`, `Gzip_close`, `Gzip_eof`, `Gzip_get_error` (331, 339, 349, 357) — direct shims over `gzgets`, `gzclose`, `gzeof`, `gzerror`. `Gzip_close` nulls `private_data` before forwarding to `gzclose`. [verified-by-code, compress_gzip.c:331-369]
- `Gzip_open` (371) — `gzopen` or `gzdopen(dup(fd))`. Appends the level digit to the mode string (e.g. `"wb9"`) if a non-default level is set. [verified-by-code, compress_gzip.c:371-411]
- `Gzip_open_write` (413) — `psprintf("%s.gz", path)` then forwards to `open_func`. [verified-by-code, compress_gzip.c:413-428]

## Invariants & gotchas

- **`#undef gzgetc` defends against a zlib macro/header skew.** The macro form would crash on platforms where the compiled-in struct layout differs from what the header says; the file-top comment cites NetBSD PR #59711. **Don't add back the macro.** [from-comment, compress_gzip.c:23-30]
- **Level 0 is rejected at this layer.** The dispatcher routes level-0 to the None backend in `pg_backup_archiver.c` / option parsing; the assert here is a backstop. Don't try to deflate with level 0 directly. [verified-by-code, compress_gzip.c:74-75]
- **Read-side state is per-call, not persistent.** `ReadDataFromArchiveGzip` mallocs and frees its own `z_stream` every call. There is no streamed read across data blocks — each block is a self-contained zlib stream. [verified-by-code, compress_gzip.c:171-235]
- **Zero-length output chunks are forbidden.** The "extra paranoia" guard at 132-141 (`if (zp->avail_out < gzipcs->outsize)`) prevents writing a zero-length compressed chunk, which would be interpreted as EOF by the custom archive's block format. Breaking this would corrupt the archive. [from-comment, compress_gzip.c:128-142]
- **`Gzip_open(fd)` `dup`s the fd.** Matches the none-backend convention; if `gzdopen` fails the duped fd is closed. [verified-by-code, compress_gzip.c:388-399]
- **`outbuf` is `outsize + 1` bytes.** The trailing byte permits `ahwrite` callers to use it as a C string. [from-comment + verified-by-code, compress_gzip.c:66-72, 189]
- **Decompression bomb.** `ReadDataFromArchiveGzip` has **no bound on output size vs input size.** A hostile archive with a high-ratio zlib stream can expand to arbitrary memory: each `inflate` call writes up to `DEFAULT_IO_BUFFER_SIZE` bytes to `ahwrite` per iteration, and the outer loop continues as long as `cs->readF` returns data. `ahwrite` (in pg_backup_archiver.c) ultimately writes to the restore destination (stdout / SQL connection / file), so the unbounded *output* lands wherever the restore is going. There is no in-memory amplification — output flows downstream — but a hostile archive can still consume unbounded restore-side resources (disk, server WAL, etc.). **See ISSUE-pg-dump-A3-compress_gzip-decompression-bomb.** [verified-by-code, compress_gzip.c:196-227] [maybe]
- **Error-message hygiene.** `pg_fatal("could not uncompress data: %s", zp->msg)` includes the zlib error text but no filename or env. [verified-by-code, compress_gzip.c:208, 223] OK.

## Phase D — hostile-archive surface

- **Decompression bomb** as above.
- **Malformed input.** `inflate()` returning anything outside `{Z_OK, Z_STREAM_END}` fatals; this includes `Z_DATA_ERROR` (corrupt input). The message contains `zp->msg` which zlib controls. No path-info leak. [verified-by-code, compress_gzip.c:206-208]
- **`Gzip_open_write` `psprintf("%s.gz", path)`.** The path is from the caller (pg_dump's `-f`); not hostile-archive-controlled. [verified-by-code, compress_gzip.c:420]

## Cross-references

- `compress_io.c` dispatches into `InitCompressorGzip` / `InitCompressFileHandleGzip`.
- Sibling backends `compress_lz4.c`, `compress_zstd.c` follow the same shape.

## Confidence tag tally
`[verified-by-code]=21 [from-comment]=5 [maybe]=1`
