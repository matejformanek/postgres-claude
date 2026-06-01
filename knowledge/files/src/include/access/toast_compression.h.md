# toast_compression.h

- **Source path:** `source/src/include/access/toast_compression.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `toast_compression.c`, `detoast.h`, `toast_internals.h`.

## Purpose

Defines the on-disk compression-method identifiers (`'p'`, `'l'`, …) used in `pg_attribute.attcompression` and embedded in TOAST headers, plus the `ToastCompressionId` enum used for the 2-bit on-disk encoding. Declares the compress/decompress functions implemented in `toast_compression.c` and exposes the `default_toast_compression` GUC. [from-comment, toast_compression.h:1-13, 25-63]

## Key types and constants

- **`ToastCompressionId`** (37) — `TOAST_PGLZ_COMPRESSION_ID = 0`, `TOAST_LZ4_COMPRESSION_ID = 1`, `TOAST_INVALID_COMPRESSION_ID = 2`. Stored in 2 bits at the top of the raw-length field — so AT MOST 4 values ever, even if more compression methods are added. [from-comment, toast_compression.h:26-42]
- **char IDs (for `pg_attribute.attcompression`):** `TOAST_PGLZ_COMPRESSION = 'p'`, `TOAST_LZ4_COMPRESSION = 'l'`, `InvalidCompressionMethod = '\0'`.
- **Macro:** `CompressionMethodIsValid(cm)` — `cm != '\0'`.
- **`DEFAULT_TOAST_COMPRESSION`** — `TOAST_LZ4_COMPRESSION` if built with `USE_LZ4`, else `TOAST_PGLZ_COMPRESSION`.

## Public surface

- `pglz_compress_datum`, `pglz_decompress_datum`, `pglz_decompress_datum_slice`.
- `lz4_compress_datum`, `lz4_decompress_datum`, `lz4_decompress_datum_slice`.
- `toast_get_compression_id(varlena *attr)`, `CompressionNameToMethod(const char *)`, `GetCompressionMethodName(char)`.
- `extern PGDLLIMPORT int default_toast_compression`.

## Key invariants

- The on-disk 2-bit encoding caps total compression methods at 4 forever. [from-comment, toast_compression.h:30-36]
- `InvalidCompressionMethod = '\0'` in `attcompression` means "use the default" (i.e. defer to `default_toast_compression`).

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/toast_compression.c.md`.

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=0`
