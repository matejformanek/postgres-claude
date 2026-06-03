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

- This file deliberately has zero secret-buffer surface — it's purely
  version-string macros. No `EVP_*` ctx exposure, no key types.
- The `TLS1_3_VERSION` ladder hard-codes the macro names PG looks for;
  a future TLS 1.4 would silently be capped at 1.3 until someone
  added an `elif`.

## Cross-refs

- Backend SSL setup: `src/backend/libpq/be-secure-openssl.c`.
- Frontend SSL setup: `src/interfaces/libpq/fe-secure-openssl.c`.

## Tally

`[verified-by-code]=3`
