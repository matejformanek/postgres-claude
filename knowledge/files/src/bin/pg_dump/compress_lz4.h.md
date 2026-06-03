---
path: src/bin/pg_dump/compress_lz4.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# compress_lz4.h

- **Source path:** `source/src/bin/pg_dump/compress_lz4.h`
- **Lines:** 24
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_lz4.c`, `compress_io.h`.

## Purpose

Declares the two LZ4 `Init*` entry points. Same shape as gzip and zstd siblings. [verified-by-code, compress_lz4.h:19-22]

## Public surface

- `InitCompressorLZ4(CompressorState *cs, const pg_compress_specification compression_spec)` [verified-by-code, compress_lz4.h:19-20]
- `InitCompressFileHandleLZ4(CompressFileHandle *CFH, const pg_compress_specification compression_spec)` [verified-by-code, compress_lz4.h:21-22]

## Invariants & gotchas

- No `USE_LZ4` guard in the header; the `#ifdef` is inside the `.c`. Stubs `pg_fatal` if invoked in a build without LZ4. Same convention as gzip. [verified-by-code, compress_lz4.h full file vs compress_lz4.c:790-803]
- Include guard `_COMPRESS_LZ4_H_`. [verified-by-code, compress_lz4.h:14-15]

## Cross-references

- `compress_lz4.c` — the implementation.

## Confidence tag tally
`[verified-by-code]=4`
