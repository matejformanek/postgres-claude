---
path: src/include/common/hmac.h
anchor_sha: 4b0bf0788b0
loc: 30
---

# hmac.h

- **Source path:** `source/src/include/common/hmac.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 30

## Purpose

Public API for the multi-algorithm HMAC facade. Lives in
`src/common/` so both backend and libpq can keyed-MAC with any
`pg_cryptohash_type`. The mechanism that consumes it is SCRAM
(`scram_ClientKey`, `scram_ServerKey`, `scram_SaltedPassword` — all in
`scram-common.c`). [verified-by-code, hmac.h:14-29]

## Key declarations

- `struct pg_hmac_ctx` — opaque, private to each impl
  (hmac.h:21).
- `pg_hmac_create / _init / _update / _final / _free / _error`
  (hmac.h:23-28). `_init` takes the key+length; the hash type is
  pinned by `_create`. `_final(dest, len)` checks `len >=
  digest_size_for(type)`.

## OpenSSL vs fallback dispatch

Same link-time pattern as cryptohash: one of `hmac.c` (RFC-2104
fallback built on top of `pg_cryptohash_*`) or `hmac_openssl.c`
(OpenSSL `HMAC_CTX_*`) is compiled. They cannot coexist.

## Phase D notes

- Key bytes are passed by `_init(key, len)` — the callee copies into
  the ipad/opad. No documented constraint on the caller to scrub `key`
  after `_init`. Both `hmac.c` and `hmac_openssl.c` `explicit_bzero`
  the entire context in `_free`. [verified-by-code, hmac.c:295,
  hmac_openssl.c:325]
- No constant-time compare helper — SCRAM hand-rolls
  `timingsafe_bcmp` against the result.

## Cross-refs

- Fallback impl: `knowledge/files/src/common/hmac.c.md`.
- OpenSSL impl: `knowledge/files/src/common/hmac_openssl.c.md`.
- Primary consumer: `src/common/scram-common.c`.

## Tally

`[verified-by-code]=3`
