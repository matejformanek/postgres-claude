---
path: src/common/hmac_openssl.c
anchor_sha: 4b0bf0788b0
loc: 373
---

# hmac_openssl.c

- **Source path:** `source/src/common/hmac_openssl.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 373

## Purpose

OpenSSL-backed implementation of `pg_hmac_*`. Wraps `HMAC_CTX_new /
_Init_ex / _Update / _Final / _free` (the legacy OpenSSL HMAC API
rather than `EVP_MAC_*`). Selected when `USE_OPENSSL` is set; peer of
`hmac.c`. [verified-by-code, hmac_openssl.c:1-14]

## Role in PG

Production HMAC path for OpenSSL builds. Same callers as the fallback
(`scram_SaltedPassword`, `scram_ClientKey`, `scram_ServerKey`).

## Key functions

- `pg_hmac_create(type)` (hmac_openssl.c:116):
  - Backend allocates in `TopMemoryContext` for resowner cleanup
    (hmac_openssl.c:43).
  - `ERR_clear_error()` before, then `ResourceOwnerEnlarge` before
    `HMAC_CTX_new` so OOM mid-enlarge can't leak the ctx
    (hmac_openssl.c:136-142).
  - On `HMAC_CTX_new` NULL: `explicit_bzero` + `FREE` +
    `ereport(ERROR)` in backend (hmac_openssl.c:144-154). Note the
    backend `ereport` is inside `#ifndef FRONTEND`, but the `return
    NULL` follows — in backend the `ereport` never returns so the
    return is dead code. [verified-by-code]
- `pg_hmac_init(ctx, key, len)` (hmac_openssl.c:171): `HMAC_Init_ex`
  with the right `EVP_<algo>()` selector. **Note OpenSSL copies `key`
  into its internal state** — caller can scrub their copy after the
  call.
- `pg_hmac_update / _final` (hmac_openssl.c:217-306): straightforward
  wrappers; `_final` bounds-checks `len`.
- `pg_hmac_free` (hmac_openssl.c:314): `HMAC_CTX_free` → resowner
  forget → `explicit_bzero` → `FREE`.
- `ResOwnerReleaseHMAC` callback (hmac_openssl.c:366): resowner
  cleans up after a longjmp.

## OpenSSL vs fallback dispatch

Build-time choice. Same opaque API as `hmac.c`.

## State / globals

- `hmac_resowner_desc` (hmac_openssl.c:75): `RELEASE_PRIO_HMAC_CONTEXTS`,
  `RESOURCE_RELEASE_BEFORE_LOCKS`. Backend only.

## Concurrency

Reentrant.

## Phase D notes

- **No `explicit_bzero` on the OpenSSL `HMAC_CTX` internal state — we
  trust `HMAC_CTX_free` to scrub.** Same trust-boundary as
  cryptohash_openssl.c.
- **Caller's `key` buffer:** OpenSSL `HMAC_Init_ex` internally copies
  the key. The PG wrapper does not retain a reference. Good — a
  caller can scrub their key after `_init` returns.
- **Resowner integration mirrors cryptohash_openssl.c** — same
  pattern, two file lookalikes. A `SecretBuf` in `src/common/` could
  share this resowner-desc skeleton.

## Potential issues

- **[ISSUE-trust-boundary: relying on `HMAC_CTX_free` to scrub key
  material]** (`hmac_openssl.c:319`). PG cannot reach into the
  opaque struct to `explicit_bzero` the ipad/opad blocks itself.
  Severity: maybe.
- **[ISSUE-dead-code: `return NULL` after `ereport(ERROR)` in
  backend]** (`hmac_openssl.c:148-153`). Cosmetic but unreachable in
  backend builds; the `#ifndef FRONTEND` brace placement makes the
  control flow harder to read than it needs to be. Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/hmac.h.md`.
- Fallback peer: `knowledge/files/src/common/hmac.c.md`.
- Resowner conventions: `src/include/utils/resowner.h`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Tally

`[verified-by-code]=9 [from-comment]=1 [inferred]=1`
