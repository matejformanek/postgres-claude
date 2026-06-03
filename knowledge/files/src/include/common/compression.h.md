---
path: src/include/common/compression.h
anchor_sha: 4b0bf0788b0
loc: 55
depth: skim
---

# compression.h

- **Source path:** `source/src/include/common/compression.h`
- **Lines:** 55
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/compression.c`.

## Purpose

Defines the `pg_compress_algorithm` enum (NONE/GZIP/LZ4/ZSTD) and the `pg_compress_specification` struct — the shared on-the-wire and on-disk way of describing "compress with X at level Y, workers Z". **The enum order is persisted** (e.g. inside pg_dump custom-format archives), so reordering would silently corrupt readers. [from-comment, compression.h:17-20]

## Public surface

- `enum pg_compress_algorithm`. [verified-by-code, compression.h:21-27]
- `PG_COMPRESSION_OPTION_WORKERS` / `PG_COMPRESSION_OPTION_LONG_DISTANCE` bit flags. [verified-by-code, compression.h:29-30]
- `struct pg_compress_specification { algorithm; options; level; workers; long_distance; parse_error; }` — `parse_error` is non-NULL iff parsing failed. [verified-by-code, compression.h:32-40]
- `parse_compress_options` (CLI → `algorithm` + `detail` strings), `parse_tar_compress_algorithm` (sniff by `.tar`/`.tgz`/`.tar.gz`/`.tar.lz4`/`.tar.zst` suffix), `parse_compress_algorithm` (name→enum), `get_compress_algorithm_name`, `parse_compress_specification`, `validate_compress_specification`. [verified-by-code, compression.h:42-53]

## Phase D notes

- See `compression.c.md` — the `algorithm` enum is persisted, the `level` int is unchecked at parse and only validated later.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=4`
