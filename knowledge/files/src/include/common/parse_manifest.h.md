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

## Issues

[ISSUE-trust-boundary: SHA-256 stored in `per_file_cb`'s
`checksum_payload` (`parse_manifest.h:29-32`) provides INTEGRITY,
not AUTHENTICITY — an attacker who controls the bytes of the
manifest also controls the SHA. A5's `common.md` finding: the
header presents `checksum_type`/`checksum_length`/`checksum_payload`
as if they were a security feature, but absent a signed manifest
or trusted distribution channel, they only detect accidental
corruption (high)] The header carries no warning. Cross-link to
checksum_helper.h's explicit "CRC-32C is not crypto" comment —
parse_manifest.h should echo the same statement for the whole
manifest.

[ISSUE-trust-boundary: `error_cb` is documented `pg_attribute_printf(2,3)`
and "must NOT return" by convention (`parse_manifest.h:36-37`) —
but the typedef has no `noreturn` annotation. A buggy registrant
returning normally leaves the parser in an inconsistent state
(medium)]

[ISSUE-trust-boundary: `json_parse_manifest_incremental_chunk`
(`parse_manifest.h:52-54`) — chunk-by-chunk parser; underlying
JSON parser is recursive. A5 + A8 jsonapi finding: deeply nested
JSON inputs from an attacker-controlled manifest could exhaust the
parser stack (high)] Cross-link: A8 jsonapi recursion echo.

[ISSUE-undocumented-invariant: `pathname` passed to `per_file_cb`
(`parse_manifest.h:30`) is consumer-trusted to be a relative,
non-traversing path — but the parser does NOT enforce this (low)]
A manifest containing `"path": "../../../etc/passwd"` reaches the
callback verbatim; pg_verifybackup callers must filter.

## Cross-refs

- A5 `common.md` — SHA-256 = integrity not authenticity.
- A8 `jsonapi.h` — recursion echo.
- A6 `pg_verifybackup` / `pg_combinebackup` — primary consumers.
- Companion: `src/common/parse_manifest.c.md`.

## Confidence tag tally
`[verified-by-code]=6`
