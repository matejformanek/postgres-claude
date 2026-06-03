---
path: src/bin/pg_dump/compress_none.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# compress_none.h

- **Source path:** `source/src/bin/pg_dump/compress_none.h`
- **Lines:** 24
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_none.c`, `compress_io.h`.

## Purpose

Trivial header — declares the two `Init*None` entry points consumed by the `compress_io.c` dispatcher. [verified-by-code, compress_none.h:19-22]

## Public surface

- `InitCompressorNone(CompressorState *cs, const pg_compress_specification compression_spec)` [verified-by-code, compress_none.h:19-20]
- `InitCompressFileHandleNone(CompressFileHandle *CFH, const pg_compress_specification compression_spec)` [verified-by-code, compress_none.h:21-22]

## Invariants & gotchas

- No conditional compilation — the "none" backend is always built (it has no library dependency). The other three backends are all `#ifdef HAVE_LIBZ` / `#ifdef USE_LZ4` / `#ifdef USE_ZSTD` gated. [verified-by-code, compress_none.c full file vs e.g. compress_gzip.c:20]
- Header-include guard: `_COMPRESS_NONE_H_` (note the trailing underscore — matches lz4/gzip but not zstd which uses `COMPRESS_ZSTD_H`). Cosmetic. [verified-by-code, compress_none.h:14-15]

## Cross-references

- `compress_none.c` — the implementation.
- `compress_io.h` — the vtable types these functions populate.

## Confidence tag tally
`[verified-by-code]=4`
