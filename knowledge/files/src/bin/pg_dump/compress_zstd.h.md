---
path: src/bin/pg_dump/compress_zstd.h
anchor_sha: 4b0bf0788b0
loc: 25
depth: read
---

# compress_zstd.h

- **Source path:** `source/src/bin/pg_dump/compress_zstd.h`
- **Lines:** 25
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_zstd.c`, `compress_io.h`.

## Purpose

Declares the two Zstd `Init*` entry points. Same shape as gzip and lz4 siblings. [verified-by-code, compress_zstd.h:20-23]

## Public surface

- `InitCompressorZstd(CompressorState *cs, const pg_compress_specification compression_spec)` [verified-by-code, compress_zstd.h:20-21]
- `InitCompressFileHandleZstd(CompressFileHandle *CFH, const pg_compress_specification compression_spec)` [verified-by-code, compress_zstd.h:22-23]

## Invariants & gotchas

- Include guard `COMPRESS_ZSTD_H` — **no leading/trailing underscores**, unlike the sibling headers (`_COMPRESS_GZIP_H_`, `_COMPRESS_LZ4_H_`, `_COMPRESS_NONE_H_`). Cosmetic style-deviation, possibly because zstd was added later. [verified-by-code, compress_zstd.h:15-16 vs siblings]
- No `USE_ZSTD` guard in the header; `#ifndef USE_ZSTD` block in the `.c` provides stubs. Same convention as siblings. [verified-by-code, compress_zstd.h full file vs compress_zstd.c:21-37]

## Cross-references

- `compress_zstd.c` — the implementation.

## Confidence tag tally
`[verified-by-code]=4`
