---
path: src/common/cryptohash_openssl.c
anchor_sha: 4b0bf0788b0
loc: 390
---

# cryptohash_openssl.c

- **Source path:** `source/src/common/cryptohash_openssl.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 390

## Purpose

OpenSSL-backed implementation of `pg_cryptohash_*`. Wraps
`EVP_MD_CTX` and the per-algorithm `EVP_md5/sha1/sha224/256/384/512`
selectors behind the same opaque-context API as `cryptohash.c`.
Selected at build time when `USE_OPENSSL` is defined.
[verified-by-code, cryptohash_openssl.c:1-15]

## Role in PG

When OpenSSL is enabled — which is the default for production PG
packages — this file defines `pg_cryptohash_*`. Same callers as the
fallback: SCRAM, MD5 password helpers, WAL summarisation, anything
linking `libpgcommon`.

## Key functions

- `pg_cryptohash_create(type)` (cryptohash_openssl.c:121):
  - Calls `ResourceOwnerEnlarge(CurrentResourceOwner)` *first* in the
    backend so that "out of memory" while sizing the resowner can't
    leak the about-to-be-allocated context (cryptohash_openssl.c:127-133).
  - Backend allocates in `TopMemoryContext` so the resowner can clean
    up across query boundaries (cryptohash_openssl.c:42).
  - `ERR_clear_error()` before `EVP_MD_CTX_create()` to keep error
    queue clean for later `ERR_get_error()` calls.
  - On `EVP_MD_CTX_create()` failure: `explicit_bzero` + `FREE` +
    `ereport(ERROR)` in backend / `return NULL` in frontend
    (cryptohash_openssl.c:151-162).
- `pg_cryptohash_init` (cryptohash_openssl.c:177): switches on type,
  calls `EVP_DigestInit_ex(ctx, EVP_<algo>(), NULL)`. Negative status
  pulls a reason string from `ERR_get_error` →
  `ERR_reason_error_string` (cryptohash_openssl.c:210). Also
  `ERR_clear_error()` again to drain the second-error case FIPS
  builds emit (cryptohash_openssl.c:213-218). [verified-by-code]
- `pg_cryptohash_update` (cryptohash_openssl.c:229): single
  `EVP_DigestUpdate`.
- `pg_cryptohash_final` (cryptohash_openssl.c:254): bounds-checks
  `len >= digest_size_for(type)`, then `EVP_DigestFinal_ex`.
- `pg_cryptohash_free` (cryptohash_openssl.c:325):
  `EVP_MD_CTX_destroy` → resowner forget → `explicit_bzero` → `FREE`.
- `pg_cryptohash_error(ctx)` (cryptohash_openssl.c:348): prefers the
  cached `errreason` string, else maps the enum, else `"success"`.
- `ResOwnerReleaseCryptoHash` (cryptohash_openssl.c:382): resowner
  callback that calls `pg_cryptohash_free` if the user forgot to.

## OpenSSL vs fallback dispatch

Build-time choice. Both files export the identical six-symbol API.

## State / globals

- `cryptohash_resowner_desc` (cryptohash_openssl.c:80) — static
  `ResourceOwnerDesc` with `release_phase = RESOURCE_RELEASE_BEFORE_LOCKS`
  and `release_priority = RELEASE_PRIO_CRYPTOHASH_CONTEXTS`. Backend
  only.

## Concurrency

Reentrant. Per-call context. Backend uses `CurrentResourceOwner`
which is per-backend (no cross-process sharing).

## Phase D notes

- **`EVP_MD_CTX` leak protection.** The resource-owner integration
  guarantees that even a longjmp'd `ereport(ERROR)` mid-hash will
  trigger `EVP_MD_CTX_destroy` via `ResOwnerReleaseCryptoHash`.
  Mirror this design in any `SecretBuf` that holds a libcrypto handle.
- **`explicit_bzero` on close** (cryptohash_openssl.c:153, 338):
  scrubs the *PG* wrapper. Note that `EVP_MD_CTX_destroy` is OpenSSL's
  responsibility for the inner state — and the OpenSSL docs say it
  *does* zeroise, but we're trusting that.
- **`ERR_clear_error` discipline** before and after each OpenSSL call
  is correct but easy to skip in new code; documented.

## Potential issues

- **[ISSUE-trust-boundary: relying on OpenSSL `EVP_MD_CTX_destroy` to
  scrub]** (`cryptohash_openssl.c:331`). If a future OpenSSL/LibreSSL
  defect skips zeroing, the underlying `EVP_MD_CTX` heap area is
  leaked-with-key-material. PG can't `explicit_bzero` it directly
  because the inner layout is opaque. Severity: maybe.
- **[ISSUE-secret-scrub: `dest` buffer in `_final` is caller-owned and
  unscrubbed]** Same as fallback impl — the caller's output buffer is
  not the context's job. Severity: maybe.
- **[ISSUE-correctness: `EVP_DigestFinal_ex(... 0)` uses a `NULL` /
  zero out-length pointer]** (cryptohash_openssl.c:308). OpenSSL
  accepts NULL but the literal `0` is non-idiomatic; relies on the
  spec saying it's a no-op pointer. Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/cryptohash.h.md`.
- Fallback peer: `knowledge/files/src/common/cryptohash.c.md`.
- Resowner conventions: `src/include/utils/resowner.h`.

## Tally

`[verified-by-code]=11 [from-comment]=2 [inferred]=1`
