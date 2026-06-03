---
path: src/bin/pg_dump/compress_gzip.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: read
---

# compress_gzip.h

- **Source path:** `source/src/bin/pg_dump/compress_gzip.h`
- **Lines:** 24
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `compress_gzip.c`, `compress_io.h`.

## Purpose

Header declaring the two `Init*Gzip` entry points. Same shape as the LZ4 and Zstd siblings. [verified-by-code, compress_gzip.h:19-22]

## Public surface

- `InitCompressorGzip(CompressorState *cs, const pg_compress_specification compression_spec)` [verified-by-code, compress_gzip.h:19-20]
- `InitCompressFileHandleGzip(CompressFileHandle *CFH, const pg_compress_specification compression_spec)` [verified-by-code, compress_gzip.h:21-22]

## Invariants & gotchas

- **No `HAVE_LIBZ` guard in the header.** The `#ifdef` is only inside `compress_gzip.c`; the prototypes are always visible. Callers must rely on the `#else` stubs (which `pg_fatal`) rather than conditional linking. This is intentional — the dispatcher in `compress_io.c` doesn't `#ifdef`-gate its calls either. [verified-by-code, compress_gzip.h full file vs compress_gzip.c:448-462]
- Include guard `_COMPRESS_GZIP_H_`. [verified-by-code, compress_gzip.h:14-15]

## Cross-references

- `compress_gzip.c` — the implementation.

## Confidence tag tally
`[verified-by-code]=4`
