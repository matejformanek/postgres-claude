---
path: src/include/common/parse_manifest.h
anchor_sha: 4b0bf0788b0
loc: 57
depth: skim
---

# parse_manifest.h

- **Source path:** `source/src/include/common/parse_manifest.h`
- **Lines:** 57
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/parse_manifest.c`.

## Purpose

Callback-driven JSON backup-manifest parser. `pg_verifybackup` and `pg_combinebackup` register four callbacks (`version_cb`, `system_identifier_cb`, `per_file_cb`, `per_wal_range_cb`) and one error callback; the parser invokes them as it walks the JSON. Supports both single-shot (`json_parse_manifest`) and incremental (`json_parse_manifest_incremental_*`) modes for handling large manifests without buffering the whole file. [verified-by-code, parse_manifest.h:24-55]

## Public surface

- `struct JsonManifestParseContext { private_data; version_cb; system_identifier_cb; per_file_cb; per_wal_range_cb; error_cb; }`. [verified-by-code, parse_manifest.h:39-47]
- Callback typedefs with payloads:
  - `version_cb(ctx, int manifest_version)`
  - `system_identifier_cb(ctx, uint64)`
  - `per_file_cb(ctx, pathname, uint64 size, checksum_type, checksum_length, *checksum_payload)`
  - `per_wal_range_cb(ctx, TimeLineID, XLogRecPtr start, XLogRecPtr end)`
  - `error_cb(ctx, fmt, …)` — `pg_attribute_printf` and must NOT return. [verified-by-code, parse_manifest.h:25-37]
- `json_parse_manifest(*context, buffer, size)` — one-shot. [verified-by-code, parse_manifest.h:49-50]
- `json_parse_manifest_incremental_init/_chunk/_shutdown` — chunk-by-chunk. [verified-by-code, parse_manifest.h:51-55]

## Phase D notes

See `parse_manifest.c.md` — every field that becomes a callback argument crosses the trust boundary.

## Confidence tag tally
`[verified-by-code]=6`
