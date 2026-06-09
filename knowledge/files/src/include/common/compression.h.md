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

## Issues

[ISSUE-trust-boundary: `pg_compress_specification` (`compression.h:32-40`)
fields `level` / `workers` / `long_distance` accept attacker-influenced
values through `parse_compress_specification` and only later go through
`validate_compress_specification` (`compression.h:53`). The header
does not document that validate must be called before use (medium)]
A caller that skips validate may push large `workers` or extreme
`level` values into zstd / lz4, exhausting CPU/RAM on the recipient.

[ISSUE-trust-boundary: enum order is persisted (`compression.h:17-20`
comment) — but the header has no static_assert or compile-time
guard against reordering. A future committer who alphabetises the
enum silently corrupts every existing pg_dump archive (low)]

[ISSUE-undocumented-invariant: `parse_error` field
(`compression.h:39`) is the only way to know if parsing succeeded;
NULL = OK, non-NULL = error message. No bool out-param, no return
code. Callers that forget to check this field see a half-initialised
struct (low)]

## Cross-refs

- A5 `common.md` — compression level abuse.
- A6 `pg_basebackup` — primary consumer.
- A14 `basebackup_to_shell` — compression-spec parsing echo.
- Companion: `src/common/compression.c.md`.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=4`
