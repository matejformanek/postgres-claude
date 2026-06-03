---
path: src/bin/pg_dump/compress_none.c
anchor_sha: 4b0bf0788b0
loc: 288
depth: read
---

# compress_none.c

- **Source path:** `source/src/bin/pg_dump/compress_none.c`
- **Lines:** 288
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.h` (vtable), `pg_backup_utils.h` (`pg_fatal`).

## Purpose

Pass-through "no compression" implementation of both the Compressor API and the Compress Stream API. The Compressor API path buffers small writes into a 128 KB chunk to keep archive block sizes reasonable; the Stream API path is a thin shim over `fopen`/`fread`/`fwrite`/`fclose`. [from-comment, compress_none.c:25-29]

## Public surface

- `InitCompressorNone(cs, spec)` (109) — fills the `CompressorState` vtable with `ReadDataFromArchiveNone` / `WriteDataToArchiveNone` / `EndCompressorNone`; if a `writeF` is set, allocates a 128 KB `NoneCompressorState` write buffer. [verified-by-code, compress_none.c:109-134]
- `InitCompressFileHandleNone(CFH, spec)` (272) — fills the `CompressFileHandle` vtable with all the `*_none` shims; leaves `private_data` NULL until `open_func` runs. [verified-by-code, compress_none.c:272-287]

## Internal landmarks (Compressor API)

- `NoneCompressorState` (30) — `{ buffer, buflen, bufdata }`. Only used in the write direction; reads pass straight through. [verified-by-code, compress_none.c:30-35]
- `ReadDataFromArchiveNone` (42) — loops `cs->readF(AH, &buf, &buflen)` until 0, calls `ahwrite(buf, 1, cnt, AH)`. Allocates a 128 KB buffer the `readF` may grow. [verified-by-code, compress_none.c:42-57]
- `WriteDataToArchiveNone` (61) — accumulates into `nonecs->buffer`; when full, calls `cs->writeF(AH, buffer, bufdata)` and resets. [verified-by-code, compress_none.c:61-86]
- `EndCompressorNone` (89) — flushes any tail bytes, frees state. Idempotent guard on `nonecs != NULL`. [verified-by-code, compress_none.c:89-103]

## Internal landmarks (Stream API)

- `read_none`, `write_none` (147, 160) — `fread`/`fwrite` direct over the `FILE *` in `private_data`. `write_none` synthesizes `ENOSPC` when `fwrite` returned a short count but `errno == 0`. [verified-by-code, compress_none.c:146-171]
- `get_error_none` (174) — `strerror(errno)`. [verified-by-code, compress_none.c:173-177]
- `gets_none`, `getc_none` (180, 186) — `fgets` / `fgetc`. `getc_none` distinguishes "read error" from "EOF" via `feof` and calls `pg_fatal` for either; this *does* match the header comment that `getc_func` treats EOF as an error. [verified-by-code, compress_none.c:179-201]
- `close_none`, `eof_none` (204, 223) — `fclose` / `feof`. `close_none` clears `private_data` before calling `fclose` (so a double-close cannot reuse the pointer). [verified-by-code, compress_none.c:203-226]
- `open_none`, `open_write_none` (229, 257) — `fopen(path, mode)` or `fdopen(dup(fd), mode)`. The `fd` branch `dup`s the fd to keep ownership clean; if `fdopen` fails, the dup is `close()`d. [verified-by-code, compress_none.c:228-266]

## Invariants & gotchas

- **The "pass-through" is not truly trivial.** The write-side Compressor API buffers up to 128 KB before flushing; the buffer's purpose is to keep archive block sizes large enough to not fragment the custom-archive format. [from-comment, compress_none.c:25-29]
- **The read-side Compressor API has no buffer of its own** but the loop still allocates a 128 KB `buf` and may pass it to `cs->readF` which is permitted to `realloc()` it. The trailing `free(buf)` is the original pointer; if `readF` realloc'd-and-replaced, `buf` was updated in-place. [verified-by-code, compress_none.c:42-57; contract per compress_io.h:36-46]
- **`open_write_none` does NOT append a suffix.** Unlike the gzip/lz4/zstd `*_open_write` which append `.gz`/`.lz4`/`.zst`, the none variant uses the literal `path`. [verified-by-code, compress_none.c:256-266]
- **`write_none` ENOSPC synthesis.** When `fwrite` short-counts but `errno == 0` (a glibc quirk on some platforms), it injects `ENOSPC` so the `%m` in the `pg_fatal` message is meaningful. [verified-by-code, compress_none.c:164-170]
- **`fd` ownership via `dup`.** The `open_none(fd)` path `dup`s the caller's fd before `fdopen`; the caller retains its own fd. If `fdopen` fails, `close(dup_fd)` is called explicitly. [verified-by-code, compress_none.c:233-244]
- **`close_none` clears `private_data` first.** This is a minor double-close defense — if `fclose` longjmps via a hostile fdopen impl, the handle won't dangle. [verified-by-code, compress_none.c:204-219]
- **`EndCompressorNone` is idempotent on `private_data == NULL`** — important because `InitCompressorNone` may leave it NULL when neither `writeF` was supplied (read-only path). [verified-by-code, compress_none.c:91-103]

## Phase D — is it really trivial?

- The pass-through has a 128 KB write buffer and a single ENOSPC synthesis. No content inspection, no checksum, no length-prefixing. Nothing that would parse hostile bytes. The only attack surface is filename in `open_none(path, ...)` which is `fopen()` — TOCTOU between discovery `stat` and `fopen` exists at the `compress_io.c` level, not here.
- **No issue surfaced.** [verified-by-code, full file]

## Cross-references

- `compress_io.c` dispatches into `InitCompressorNone` / `InitCompressFileHandleNone`.
- Vtable contract: `compress_io.h`.

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=2`
