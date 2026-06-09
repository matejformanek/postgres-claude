---
path: src/include/common/openssl.h
anchor_sha: 4b0bf0788b0
loc: 43
---

# openssl.h

- **Source path:** `source/src/include/common/openssl.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 43

## Purpose

OpenSSL-specific helpers shared between frontend (`fe-secure-openssl.c`)
and backend (`be-secure-openssl.c`). The entire body is gated by
`#ifdef USE_OPENSSL` — when OpenSSL is absent this header is a no-op.
[verified-by-code, openssl.h:17-41]

## Key declarations

- `#include <openssl/ssl.h>` — only when `USE_OPENSSL`.
- `MIN_OPENSSL_TLS_VERSION "TLSv1"` (openssl.h:29).
- `MAX_OPENSSL_TLS_VERSION` — picked at compile time based on which
  `TLS1_*_VERSION` macros OpenSSL defines (openssl.h:31-39). LibreSSL
  lacks a runtime way to advertise its max version, so PG defines its
  own.

## Phase D notes

- **This file deliberately has zero secret-buffer surface** — purely
  version-string macros. No `EVP_*` ctx exposure, no key types. The
  A16 brief asked whether this is a future home for OpenSSL 3.0
  `EVP_CIPHER_fetch` / `EVP_MD_fetch` shims — **as of pin
  `4b0bf0788b0`, no such shims exist anywhere in
  `src/include/common/` or `src/common/`** (verified by grep for
  `EVP_CIPHER_fetch|EVP_MD_fetch` returning zero hits). The A11
  pgcrypto modernization candidate would either land here or
  introduce a new `common/evp.h`.
- **No ERR_get_error helper.** A11 finding (pgcrypto silently
  discards the OpenSSL error stack) is a candidate for a header-level
  helper here: `pg_openssl_consume_error_stack(const char **errstr)`.
  Currently every consumer hand-rolls (or doesn't bother).
- **No BN_FLG_CONSTTIME helper.** A11 finding (pgcrypto's BIGNUM
  ops run in variable-time — Brumley-Boneh 2003 timing attacks).
  A `pg_openssl_bn_set_consttime(BIGNUM *)` wrapper would centralize
  the discipline; absent today.
- **TLS version ladder hard-codes the macro names PG looks for** —
  a future TLS 1.4 would silently be capped at 1.3 until someone
  added an `elif`. The `LibreSSL` carve-out comment (line 22-25) is
  the historical reason this lives here at all.

## Cross-refs

- Backend SSL setup: `src/backend/libpq/be-secure-openssl.c`.
- Frontend SSL setup: `src/interfaces/libpq/fe-secure-openssl.c`.
- A11 pgcrypto modernization brief: `knowledge/issues/pgcrypto.md` —
  ERR_get_error / BN_FLG_CONSTTIME / px_memset / S2K-iter findings.
- OpenSSL-vs-fallback dispatch counterparts:
  `knowledge/files/src/include/common/cryptohash.h.md`,
  `knowledge/files/src/include/common/hmac.h.md`.

## Issues

1. `[ISSUE-audit-gap: no header-level helper to drain ERR_get_error()
   into an errstr; A11 finding "pgcrypto silently discards OpenSSL
   error stack" is unblocked by adding one (likely)]` —
   `source/src/include/common/openssl.h:17-41`.
2. `[ISSUE-audit-gap: no header-level pg_openssl_bn_set_consttime
   helper; A11 finding "non-constant-time RSA/Elgamal in pgcrypto"
   would benefit from a centralized BN_FLG_CONSTTIME wrapper (likely)]`
   — `source/src/include/common/openssl.h:17-41`.
3. `[ISSUE-api-shape: this header is OpenSSL-only (gated by
   USE_OPENSSL); LibreSSL and BoringSSL get the same code path
   because the public macros they expose mostly overlap, but no
   explicit feature-flag table documents which functions are safe
   on which library (nit)]` —
   `source/src/include/common/openssl.h:22-27`.
4. `[ISSUE-documentation: TLS1_3_VERSION ladder silently caps at the
   highest defined macro; no compile-time warning if OpenSSL gains
   TLS1_4_VERSION (nit)]` —
   `source/src/include/common/openssl.h:31-39`.

## Tally

`[verified-by-code]=4 [inferred]=2`
