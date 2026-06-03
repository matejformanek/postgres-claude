---
path: src/bin/pg_dump/compress_io.c
anchor_sha: 4b0bf0788b0
loc: 301
depth: read
---

# compress_io.c

- **Source path:** `source/src/bin/pg_dump/compress_io.c`
- **Lines:** 301
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_io.h` (vtable), `compress_none.c`/`compress_gzip.c`/`compress_lz4.c`/`compress_zstd.c` (backends), `pg_backup_archiver.h` (`ArchiveHandle`), `common/compression.h` (`pg_compress_specification`).

## Purpose

Dispatcher across the four compression backends pg_dump/pg_restore know about: `none`, `gzip` (zlib), `lz4`, `zstd`. Exposes two parallel APIs: a **Compressor API** (callback-driven, used for embedded data blocks inside the custom/directory archive formats) and a **Compress Stream API** (fopen-like wrapper used when the resulting file should be readable by an external `gunzip`/`unlz4`/`unzstd`). Also probes which algorithms this build was compiled with. [from-comment, compress_io.c:1-62]

## Public surface

- `supports_compression(spec)` (86) — returns `NULL` if the requested algorithm is compiled-in, else a `psprintf`'d error string. Gated on `HAVE_LIBZ` / `USE_LZ4` / `USE_ZSTD`. [verified-by-code, compress_io.c:86-112]
- `AllocateCompressor(spec, readF, writeF)` (122) — allocate `CompressorState`, dispatch to `InitCompressor{None,Gzip,LZ4,Zstd}`. [verified-by-code, compress_io.c:122-142]
- `EndCompressor(AH, cs)` (147) — calls `cs->end(AH, cs)` then frees the state struct itself. [verified-by-code, compress_io.c:147-152]
- `InitCompressFileHandle(spec)` (193) — allocate `CompressFileHandle`, dispatch to `InitCompressFileHandle{None,Gzip,LZ4,Zstd}`. [verified-by-code, compress_io.c:193-210]
- `InitDiscoverCompressFileHandle(path, mode)` (239) — for reads; infer algorithm from filename suffix first, else stat the bare path, else try `path.gz`/`path.lz4`/`path.zst` in that order. Asserts `mode == PG_BINARY_R`. [verified-by-code, compress_io.c:239-281]
- `EndCompressFileHandle(CFH)` (288) — call `close_func` if `private_data` is non-NULL (i.e. an open file), free the handle. Preserves `errno`. [verified-by-code, compress_io.c:288-300]

## Internal landmarks

- `hasSuffix(filename, suffix)` (162) — trailing-`memcmp` check; pure. [verified-by-code, compress_io.c:162-174]
- `free_keep_errno(p)` (177) — `free()` wrapper that saves/restores `errno`. Used everywhere a temp string is freed between an I/O syscall and the caller's `errno` read. [verified-by-code, compress_io.c:176-184]
- `check_compressed_file(path, fname, ext)` (218) — `psprintf("%s.%s", path, ext)` into `*fname`, `access(F_OK)`. Used only by the discovery routine. [verified-by-code, compress_io.c:218-224]

## Dispatch table (which backend handles which algorithm)

The four `if/else if` ladders in `supports_compression`, `AllocateCompressor`, `InitCompressFileHandle` are the **only** place algorithm → backend is wired. There is **no vtable lookup at archive-read time** — the archive header carries an algorithm tag (`PG_COMPRESSION_*` enum), `AllocateCompressor` dispatches off it, and a missing `else` branch leaves `cs->readData`/`writeData`/`end` as NULL. [verified-by-code, compress_io.c:132-140] [Phase D concern, see ISSUE register]

## Invariants & gotchas

- **Compile-time vs runtime mismatch.** If the source dump was made with e.g. zstd but the *restoring* build lacks `USE_ZSTD`, `AllocateCompressor` silently leaves the `CompressorState` callbacks NULL — there is no `else { pg_fatal(...); }` arm. The fatal is delivered later when the per-backend `InitCompressor*` stub fires (each backend's `#else` arm contains `pg_fatal("this build does not support compression with ...")`). So the error surfaces, but only because every backend's stub fires unconditionally. [verified-by-code, compress_io.c:132-140; compress_gzip.c:449-461; compress_lz4.c:790-803; compress_zstd.c:22-33] Removing a backend stub would create a NULL-deref. [maybe — Phase D]
- **Discovery probes are silent.** `InitDiscoverCompressFileHandle` may stat-then-open-then-probe up to 4 candidate paths; partial errors (e.g. `path.gz` exists but is unreadable) are ignored by the probe loop. The final `open_func` failure is what surfaces. [verified-by-code, compress_io.c:259-273]
- **Suffix sniffing trusts the filename.** `hasSuffix(".gz")` → gzip backend is chosen unconditionally. An attacker who controls the filename can force a specific decompressor (e.g. zstd skip-frame handling). The archive's own format header is not consulted at this layer. [verified-by-code, compress_io.c:253-258] [Phase D concern]
- **`mode` is asserted to `PG_BINARY_R`** (line 249) — discovery is read-only by contract. Production builds with `-DNDEBUG` will silently accept other modes; the discovery logic uses `stat`/`access` so write modes would fail at `open_func` anyway. [verified-by-code, compress_io.c:249]
- **`free_keep_errno` discipline is consistent.** Every code path that frees a temp string between `errno`-setting syscalls uses it. [verified-by-code, compress_io.c:221, 275, 278]
- **No NULL check on dispatched `Init*` functions.** `pg_malloc0_object` cannot return NULL (pg_fatal on OOM), so the state struct is always non-NULL — but the dispatch ladders leave callbacks NULL for unknown algorithms. The caller is expected to have already validated via `supports_compression`. [inferred, compress_io.c:122-142]

## Phase D — hostile-archive surface

- **Backend-tag from archive header.** The `pg_compress_specification.algorithm` for `AllocateCompressor` is set by the format-specific reader (pg_backup_custom.c / pg_backup_directory.c) from bytes inside the archive. A hostile archive that claims `PG_COMPRESSION_*` with a value outside the enum range falls through all four `if/else if` ladders → all callbacks remain NULL → next `cs->readData(...)` is a NULL-fn-pointer call. There is no enum-range guard in `AllocateCompressor`. **See ISSUE-pg-dump-A3-compress_io-unknown-algo.** [verified-by-code, compress_io.c:132-140] [maybe]
- **Discovery via filename suffix.** Restoring `pg_restore foo` where `foo.gz` is a symlink the attacker controls is the standard concern. Mitigated by the OS access checks. [verified-by-code, compress_io.c:253-269]

## Cross-references

- Callers: `pg_backup_custom.c` (custom format embedded blocks), `pg_backup_directory.c` (per-TOC-entry files), `pg_dump.c` (TOC file).
- Per-backend implementations: `compress_none.c`, `compress_gzip.c`, `compress_lz4.c`, `compress_zstd.c`.
- See also `knowledge/files/src/bin/pg_dump/compress_io.h.md` for the vtable contract.

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=1 [inferred]=1 [maybe]=2`
