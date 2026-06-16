---
path: src/common/checksum_helper.c
anchor_sha: 4b0bf0788b0
loc: 232
depth: read
---

# checksum_helper.c

- **Source path:** `source/src/common/checksum_helper.c`
- **Lines:** 232
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/checksum_helper.h`, `common/cryptohash.c` (the underlying SHA-2 driver), `port/pg_crc32c.h`.

## Purpose

Thin façade over five checksum kernels (CRC-32C plus four SHA-2 widths). The five `switch` statements in `init`/`update`/`final` are the dispatch. NONE compiles to a no-op so a caller can write algorithm-agnostic loops without branching on "do I actually need a checksum?". [verified-by-code, checksum_helper.c:27-232]

## Role in PG

Both frontend and backend. Primary caller in this batch: `parse_manifest.c:verify_manifest_checksum`. Other callers: `pg_verifybackup`, `manifest.c` (backend backup manifest writer).

## Key functions

- `pg_checksum_parse_type(name, *type)` (27-50) — `pg_strcasecmp` against "none", "crc32c", "sha224", "sha256", "sha384", "sha512". Returns `false` and `CHECKSUM_TYPE_NONE` for unknown. [verified-by-code, checksum_helper.c:27-50]
- `pg_checksum_type_name(type)` (55-76) — string for log messages; `Assert(false)` + `"???"` fallback. [verified-by-code, checksum_helper.c:55-76]
- `pg_checksum_init(*ctx, type)` (82-138) — sets `ctx->type`, then per-algorithm: CRC32C uses inline `INIT_CRC32C`; each SHA variant calls `pg_cryptohash_create` then `pg_cryptohash_init`, freeing on init failure. Returns 0/-1. [verified-by-code, checksum_helper.c:82-138]
- `pg_checksum_update(*ctx, input, len)` (144-166) — `COMP_CRC32C` or `pg_cryptohash_update`. Returns 0/-1. [verified-by-code, checksum_helper.c:144-166]
- `pg_checksum_final(*ctx, *output)` (175-232) — five `StaticAssertDecl`s prove `PG_CHECKSUM_MAX_LENGTH` fits each digest. `FIN_CRC32C` + `memcpy` for CRC; `pg_cryptohash_final` + `pg_cryptohash_free` for SHA. Returns digest length (4 for CRC, 28/32/48/64 for SHAs) or -1. [verified-by-code, checksum_helper.c:175-232]

## State / globals

None. All state is in `*context`.

## Phase D notes

- **CRC-32C is not authentication.** A manifest's per-file CRC can be re-derived by the same actor that flipped the file contents. The header comment is explicit; documenting it here so future readers don't treat "checksum_type=crc32c" as tamper-evident. [from-comment, checksum_helper.h:20-27]
- **SHA failure path returns -1 without resetting `ctx->type`.** A caller that ignores the -1 and then calls `pg_checksum_update` will hit the SHA arm with a stale `c_sha2` pointer (NULL after `pg_cryptohash_free` in init). Calls to `pg_cryptohash_update(NULL, ...)` ultimately segfault or assert-fail. **The contract is "if init failed, do not call update/final"** — but the type isn't reset to NONE for caller convenience. [verified-by-code, checksum_helper.c:96-134] [ISSUE-undocumented-invariant: pg_checksum_init failure path leaves ctx->type set; caller MUST not call update/final after init returns -1 (maybe-low)]
- **`pg_checksum_final` frees the cryptohash ctx** (line 205, 212, 219, 226) but **only on the success path**. A `pg_cryptohash_final` failure returns -1 leaving `c_sha2` allocated — caller must remember to `pg_cryptohash_free` it. This is unintuitive for a "final" routine. [verified-by-code, checksum_helper.c:200-227] [ISSUE-undocumented-invariant: pg_checksum_final leaks c_sha2 on the -1 return path (maybe)]
- **No length-bound on `pg_checksum_update`'s `len`.** A 4 GiB+ input could overflow internal counters in the SHA-2 driver, but that's `cryptohash.c`'s problem. [inferred]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=9 [inferred]=1 [maybe]=2`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
