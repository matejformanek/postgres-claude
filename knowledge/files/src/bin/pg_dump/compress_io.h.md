---
path: src/bin/pg_dump/compress_io.h
anchor_sha: 4b0bf0788b0
loc: 208
depth: read
---

# compress_io.h

- **Source path:** `source/src/bin/pg_dump/compress_io.h`
- **Lines:** 208
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.c` (dispatcher), all four `compress_<algo>.c` (vtable implementers), `pg_backup_archiver.h` (`ArchiveHandle`).

## Purpose

Declares the two vtable structs (`CompressorState`, `CompressFileHandle`) that every compression backend fills in, plus the `ReadFunc`/`WriteFunc` callback typedefs that the Compressor API uses to talk to the underlying archive format. Also defines `DEFAULT_IO_BUFFER_SIZE` (128 KB), the unit of I/O for every backend. [verified-by-code, compress_io.h:27, 49-88, 98-193]

## Public surface

- `DEFAULT_IO_BUFFER_SIZE` (27) — `(128 * 1024)`. Comment warns: "When changing this value, it's necessary to check the relevant test cases still exercise all the branches." [from-comment, compress_io.h:20-26]
- `WriteFunc`, `ReadFunc` typedefs (34, 47) — the callback contract for the Compressor API. `ReadFunc` is permitted to `free()` and `malloc()` a larger `*buf` (returned via in/out params). [from-comment, compress_io.h:36-46]
- `CompressorState` struct (50-88) — the Compressor API vtable: `readData`, `writeData`, `end`, plus the `readF`/`writeF` callbacks, the `compression_spec`, and `private_data`. **The state is per-block, not per-archive** — pg_dump creates one per data block being read or written. [verified-by-code, compress_io.h:50-88]
- `CompressFileHandle` struct (100-193) — the Compress Stream API vtable: `open_func`, `open_write_func`, `read_func`, `write_func`, `gets_func`, `getc_func`, `eof_func`, `close_func`, `get_error_func`, plus `compression_spec` and `private_data`. Used for whole-file streams that an external utility can also decompress. [verified-by-code, compress_io.h:100-193]

## Vtable contract (from inline comments)

- `open_func` — accepts either `path` or `fd` (the other is sentinel `-1` / NULL). Modes: `'r'`, `'rb'`, `'w'`, `'wb'`, `'a'`, `'ab'`. Returns bool. [from-comment, compress_io.h:103-111]
- `open_write_func` — write modes only (`'w'`, `'wb'`, `'a'`, `'ab'`). Conventionally appends the algorithm suffix to the path (see each backend's `*_open_write`). [from-comment, compress_io.h:114-122]
- `read_func` — returns bytes read (< size on EOF). **Exits via `pg_fatal` for all error conditions.** [from-comment, compress_io.h:125-133]
- `write_func` — returns nothing; **exits via `pg_fatal` for all error conditions.** [from-comment, compress_io.h:136-141]
- `gets_func` — `fgets`-like; reads up to `size - 1` characters, null-terminates, includes the newline if encountered. Returns NULL on EOF-with-no-data or error. [from-comment, compress_io.h:143-153]
- `getc_func` — like `fgetc` but treats EOF as a fatal error (calls `pg_fatal`). [from-comment, compress_io.h:155-162]
- `eof_func` — bool, true at EOF. [from-comment, compress_io.h:164-169]
- `close_func` — bool, true on success. [from-comment, compress_io.h:171-176]
- `get_error_func` — returns a `const char *` describing the last error. **The lifetime is unspecified** in this header; each backend returns either a pointer into static library state (zlib's `gzerror`, zstd's `ZSTD_getErrorName`) or a thread-local `strerror`. Callers may not free it. [from-comment + verified-by-code, compress_io.h:178-182, compress_gzip.c:357-369, compress_zstd.c:567-573]

## Invariants & gotchas

- **`read_func` / `write_func` exit on error.** Callers do *not* receive error returns — `pg_fatal` is the contract. This means a single I/O error in any backend cannot be cleanly recovered; the whole pg_dump/pg_restore process dies. [from-comment, compress_io.h:131, 138]
- **`getc_func` even fatals on EOF** (per header doc) — but in practice none of the four backends does this for EOF; they only fatal on read error or the fgetc-returns-EOF-without-feof case. The comment overstates the contract. [verified-by-code, compress_none.c:185-201; compress_gzip.c:312-329; compress_lz4.c:575-590; compress_zstd.c:394-402] [maybe — header comment slightly inaccurate]
- **`private_data` ownership is per-backend.** No uniform invariant; each `Init*` chooses whether to populate it eagerly (none, lz4, zstd) or lazily on first open (gzip stores the `gzFile` only after `*_open`). [verified-by-code, compress_none.c:286, compress_gzip.c:446, compress_lz4.c:788, compress_zstd.c:591]
- **`DEFAULT_IO_BUFFER_SIZE = 128 KB`** is hardwired and shared across all backends as the unit of compressed-block-size and uncompressed-block-size sizing (lz4 actually uses `LZ4F_compressBound(128 KB) + 50%` for its buffer). Increasing it without verifying coverage on small inputs will silently disable some branches (see comment). [from-comment, compress_io.h:20-26]
- **No version field on either struct.** Adding a vtable function in a minor version would be an ABI break for any out-of-tree extender — but these structs are not exported outside pg_dump anyway. [inferred, compress_io.h:50-193]

## Cross-references

- `compress_io.c` — the dispatcher that allocates these structs.
- `compress_none.c`, `compress_gzip.c`, `compress_lz4.c`, `compress_zstd.c` — the implementers.

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=10 [inferred]=1 [maybe]=1`
