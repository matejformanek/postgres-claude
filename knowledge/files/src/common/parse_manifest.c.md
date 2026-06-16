---
path: src/common/parse_manifest.c
anchor_sha: 4b0bf0788b0
loc: 949
depth: read
---

# parse_manifest.c

- **Source path:** `source/src/common/parse_manifest.c`
- **Lines:** 949
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/parse_manifest.h`, `common/jsonapi.c` (the JSON tokenizer), `common/checksum_helper.c`.

## Purpose

JSON backup-manifest parser used by `pg_verifybackup` and `pg_combinebackup`. Drives `jsonapi.c` via semantic-action callbacks, accumulating per-file and per-WAL-range state, then invokes the caller's typed callbacks when each object closes. Verifies the trailing SHA-256 manifest checksum against everything before the last line. [verified-by-code, parse_manifest.c:222-272,800-878]

## Role in PG

Frontend-only (no backend caller; the backend `manifest.c` writes manifests but doesn't parse them).

## Key entry points

- `json_parse_manifest(*context, buffer, size)` (227-272) — one-shot path: `verify_manifest_checksum(...)` first, then `makeJsonLexContextCstringLen(buffer, size)`, then `pg_parse_json` driving the semantic-action callbacks. [verified-by-code, parse_manifest.c:227-272]
- `json_parse_manifest_incremental_init(*context)` (128-167) — palloc the incremental state + parse state, set up `JsonSemAction` callbacks, init a SHA-256 cryptohash (used to checksum the manifest stream as it arrives). [verified-by-code, parse_manifest.c:128-167]
- `json_parse_manifest_incremental_chunk(incstate, chunk, size, is_last)` (184-220) — feed `pg_parse_json_incremental`, update the manifest-checksum hash. On `is_last`: call `verify_manifest_checksum(parse, chunk, size, incstate->manifest_ctx)`. [verified-by-code, parse_manifest.c:184-220]
- `json_parse_manifest_incremental_shutdown(incstate)` (168-182) — pfree path. [verified-by-code, parse_manifest.c:168-182]

## Semantic callbacks (driven by jsonapi)

- `json_manifest_object_start/end` (275-348) — push/pop expected state across the FSM (`JM_EXPECT_TOPLEVEL_START`, `JM_EXPECT_THIS_FILE_FIELD`, …). [verified-by-code, parse_manifest.c:275-398]
- `json_manifest_array_start/end` (350-398) — handle Files[], WalRanges[]. [verified-by-code, parse_manifest.c:350-398]
- `json_manifest_object_field_start` (400-515) — match field name to enum (`JMFF_PATH`, `JMFF_SIZE`, `JMFF_CHECKSUM_ALGORITHM`, `JMFF_CHECKSUM`; `JMWRF_TIMELINE`, `JMWRF_START_LSN`, `JMWRF_END_LSN`). [verified-by-code, parse_manifest.c:400-515]
- `json_manifest_scalar` (516-…) — store the value at the FSM-dictated slot. [verified-by-code, parse_manifest.c:516-…]
- `json_manifest_finalize_file` (648-742) — required fields present; hex-decode the encoded pathname if used; `strtou64(parse->size)`; resolve checksum_type via `pg_checksum_parse_type`; hex-decode checksum payload; invoke `context->per_file_cb`. Frees the per-file scratch strings. [verified-by-code, parse_manifest.c:648-742]
- `json_manifest_finalize_wal_range` (750-…) — `strtoul(timeline)`, `parse_xlogrecptr` for start/end, invoke `per_wal_range_cb`. [verified-by-code, parse_manifest.c:750-…]
- `verify_manifest_checksum` (811-878) — find the last two newlines, hash everything up to the second-to-last newline with SHA-256, hex-decode the claimed checksum from the last line, `memcmp`. [verified-by-code, parse_manifest.c:811-878]

## State / globals

None. All state is in `JsonManifestParseState` / `JsonManifestParseIncrementalState`.

## Phase D notes — hostile-manifest surface

This is the other A3-shaped trust-boundary file in this batch. A manifest file is the caller's first sight of a backup; the parser's behavior on malformed input shapes whether `pg_verifybackup` errors clean or silently passes a bad backup.

- **Manifest checksum is SHA-256** (line 821, 850-863) — a hostile actor who can rewrite the manifest can recompute the SHA-256 and the verification trivially passes. **The SHA-256 is integrity, NOT authenticity.** The only authenticity comes from the per-file checksums, but those are themselves selected at backup time by `pg_basebackup --manifest-checksums=...` (and `crc32c` is the default). A user who chose `crc32c` for per-file checksums and gets a hostile manifest gets no authenticity at all. [verified-by-code, parse_manifest.c:811-878] [from-comment, checksum_helper.h:20-27] [ISSUE-trust-boundary: manifest SHA-256 is over the manifest bytes only; tampering with manifest+per-file CRCs together is not detected; matches the pg_dump archive trust model (maybe-high)]
- **`size = strtou64(parse->size, &ep, 10)`** at line 690 — accepts any uint64 size including huge ones; `*ep` check rejects garbage. Then `size` is passed to `per_file_cb` which (in `pg_verifybackup`) calls `stat()` and compares to actual file size. A hostile manifest can claim size=2^60 for a 1-byte file — verifybackup will report mismatch but not before doing the file stat. **No integer overflow possible** in the parser itself. [verified-by-code, parse_manifest.c:690-693]
- **`checksum_length = checksum_string_length / 2`** at line 712 — palloc of `checksum_length` bytes for the payload. `checksum_string_length` is `strlen(parse->checksum)` where `parse->checksum` is the raw token from jsonapi. **Token length is bounded by manifest size**, so this is bounded by available memory. No multiplicative blowup. [verified-by-code, parse_manifest.c:702-720]
- **`encoded_pathname`** (line 671-687) is hex-decoded into `raw_length = encoded_length / 2` bytes. Same bound — token-size-limited. [verified-by-code, parse_manifest.c:671-687]
- **`hexdecode_string`** (918-934) returns false on non-hex; finalize_file calls `json_manifest_parse_failure` which goes through `context->error_cb` (noreturn) — so a hostile pathname can't sneak in raw bytes via a malformed encoded form. [verified-by-code, parse_manifest.c:678-684,918-934]
- **`parse_xlogrecptr`** (939-948) uses `sscanf("%X/%08X", &hi, &lo)`. `%X` accepts any number of hex digits in glibc; in theory a 9+ digit `hi` overflows. **But** `uint32 hi` truncates silently and the resulting LSN is wrong but bounded — no out-of-range write. [verified-by-code, parse_manifest.c:939-948] [maybe — minor: could log "%X/%08X expected exactly 8 hex digits per side" but only the `lo` half is width-restricted]
- **No size cap on the manifest itself.** A 100 GiB manifest with one absurd `Files` array is parsed incrementally without total-size guard. SHA-256 streaming is fine; per-file callbacks fire one at a time. Memory steady-state is one file's worth of scratch (the per-file `pathname`/`size`/`checksum` strings, freed at line 727-741). Good. [verified-by-code, parse_manifest.c:184-220,727-741]
- **`json_manifest_parse_failure` is `pg_noreturn`** (line 117, 889-893) — the parser cannot continue after malformed input. The error_cb is the only place that decides exit code / message wording. [verified-by-code, parse_manifest.c:117,889-893]
- **`verify_manifest_checksum` requires `number_of_newlines >= 2`** (line 840-845) — minimum two lines means a one-line trivially-malformed manifest is rejected up front. [verified-by-code, parse_manifest.c:840-845]
- **The `incr_ctx` path frees the cryptohash inside `verify_manifest_checksum`** (line 877). If `incr_ctx` was supplied by the caller (incremental case), this is correct — line 184-220 passes `incstate->manifest_ctx` and after `verify_manifest_checksum` the incremental state expects the hash to be done. **But `json_parse_manifest_incremental_shutdown` should NOT then re-free it.** Read confirms shutdown only `pfree`s the `incstate` and `parse` structs. [verified-by-code, parse_manifest.c:168-182,877]

## Cross-references

- `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md` — sister "trust the archive header" pattern.
- pg_verifybackup driver: `src/bin/pg_verifybackup/pg_verifybackup.c`.
- Backend manifest writer: `src/backend/backup/basebackup_manifest.c`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=18 [from-comment]=1 [maybe]=2 [ISSUE]=1`
