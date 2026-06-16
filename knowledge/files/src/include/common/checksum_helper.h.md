---
path: src/include/common/checksum_helper.h
anchor_sha: 4b0bf0788b0
loc: 72
depth: skim
---

# checksum_helper.h

- **Source path:** `source/src/include/common/checksum_helper.h`
- **Lines:** 72
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/checksum_helper.c`, `common/cryptohash.c`, `port/pg_crc32c.h`.

## Purpose

Algorithm-agnostic checksum API: `pg_checksum_init` / `update` / `final`, dispatching on a `pg_checksum_type` enum. Supports `NONE`, `CRC32C`, `SHA224/256/384/512`. Used by backup manifests (`parse_manifest.c`, `manifest.c`) where the algorithm is configurable per file. [from-comment, checksum_helper.h:20-27]

## Public surface

- `enum pg_checksum_type { CHECKSUM_TYPE_NONE, _CRC32C, _SHA224, _SHA256, _SHA384, _SHA512 }`. **MD5 deliberately omitted** — comment at line 24-27 notes that anything needing crypto should pick something better. [verified-by-code, checksum_helper.h:29-37]
- `union pg_checksum_raw_context { pg_crc32c c_crc32c; pg_cryptohash_ctx *c_sha2; }`. [verified-by-code, checksum_helper.h:42-46]
- `struct pg_checksum_context { type; raw_context; }`. [verified-by-code, checksum_helper.h:52-56]
- `#define PG_CHECKSUM_MAX_LENGTH PG_SHA512_DIGEST_LENGTH` (64). [verified-by-code, checksum_helper.h:62]
- `pg_checksum_parse_type`, `pg_checksum_type_name`, `pg_checksum_init/update/final`. [verified-by-code, checksum_helper.h:64-70]

## Phase D notes

- CRC-32C is **not crypto** — it is collision-trivial and an attacker who can modify a manifest can also rewrite the CRC. CRC-32C is included only as a faster integrity check for accidental damage. The header comment is explicit. [from-comment, checksum_helper.h:20-27]

## Issues

[ISSUE-trust-boundary: enum `pg_checksum_type` (`checksum_helper.h:29-37`)
puts `CHECKSUM_TYPE_CRC32C` and `CHECKSUM_TYPE_SHA512` in the same
namespace; the API forces no distinction between "fast integrity" and
"crypto-strong" choices at compile time. A5 finding: callers that
parameterize on user input (e.g. `pg_basebackup --manifest-checksums=`)
can be talked into the weakest acceptable option (medium)] The
header notes MD5 was deliberately omitted but does not warn that
CRC32C is similarly weak for adversarial settings.

[ISSUE-stale-todo: comment at `checksum_helper.h:20-27` says "we
include CRC-32C because it's much faster" — true but loaded; an
explicit "DO NOT USE FOR AUTHENTICITY" warning would make the
header self-documenting (low)]

[ISSUE-trust-boundary: `pg_checksum_parse_type` (`checksum_helper.h:64`)
takes a `char *name` — parser for CLI/manifest input. Lower-case
matching, locale-dependent? Header says nothing (low)]

## Cross-refs

- A5 `common.md` — CRC32C-vs-SHA misuse.
- A6 `pg_verifybackup` — primary consumer.
- Companion: `src/common/checksum_helper.c.md`, `parse_manifest.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=5`
