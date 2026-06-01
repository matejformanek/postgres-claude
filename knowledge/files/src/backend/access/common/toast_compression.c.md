# toast_compression.c

- **Source path:** `source/src/backend/access/common/toast_compression.c`
- **Lines:** 316
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `toast_compression.h`, `detoast.c` (consumer), `toast_internals.c` (storage path), `common/pg_lzcompress.c`, `lz4.h`.

## Purpose

The compression algorithms supported for TOAST: PGLZ (always built in) and LZ4 (optional, gated on `USE_LZ4`). Provides compress/decompress/decompress-slice routines for each, plus the `default_toast_compression` GUC and the algorithm-id ↔ name mapping (`'p'`, `'l'`, …) recorded in `pg_attribute.attcompression`. [from-comment, toast_compression.c:1-13]

## Top-of-file comment

> "Functions for toast compression." [from-comment, toast_compression.c:3-4]

## Public surface

- `pglz_compress_datum` (40) — Compress an entire varlena with PGLZ. Returns NULL if the result wouldn't be smaller than the input.
- `pglz_decompress_datum` (82), `pglz_decompress_datum_slice` (109).
- `lz4_compress_datum` (139), `lz4_decompress_datum` (182), `lz4_decompress_datum_slice` (215). All three `ereport(ERROR, ERRCODE_FEATURE_NOT_SUPPORTED)` if the backend was built without `USE_LZ4`.
- `toast_get_compression_id` (254) — extract the algorithm id from a compressed varlena's header.
- `CompressionNameToMethod` (285), `GetCompressionMethodName` (304) — name ↔ char-id (`pglz` ↔ `'p'`, `lz4` ↔ `'l'`).

## Key invariants

- `pglz_compress_datum` returns NULL if compression doesn't shrink the value — caller MUST handle NULL (i.e. give up on compression). [verified-by-code, toast_compression.c:40-80]
- LZ4 functions throw at runtime (not at compile time) when LZ4 isn't available — gives a clean error path for backups/dumps that reference LZ4-compressed values on a non-LZ4 build. [verified-by-code, toast_compression.c:139-250]
- The compression-method id char (`'p'` / `'l'`) is stored both in `pg_attribute.attcompression` and in the toast header (`VARATT_EXTERNAL_GET_COMPRESSION_METHOD`); the two MUST agree for newly-written values but reads must tolerate older values written with a different attcompression. [verified-by-code, toast_compression.c:254-283]

## Functions of note

- **`pglz_compress_datum`** (40) — Allocate `PGLZ_MAX_OUTPUT(rawsize)`, call `pglz_compress`. If output length ≥ raw length, free and return NULL. Otherwise write the `toast_compress_header` (raw size + algorithm id encoded in the high bits of va_tcinfo). [verified-by-code]
- **`lz4_compress_datum`** (139) — `LZ4_compressBound`, then `LZ4_compress_default`. Same header convention as PGLZ. [verified-by-code]
- **`pglz_decompress_datum_slice`** (109) — Streaming decompress with a stop-length, used by `detoast_attr_slice` for slicing into compressed-external values. [verified-by-code]

## Cross-references

- Compress side called from: `heaptoast.c::heap_toast_insert_or_update`, `indextuple.c::index_form_tuple_context` (when an index value needs recompression).
- Decompress side called from: `detoast.c`.

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
