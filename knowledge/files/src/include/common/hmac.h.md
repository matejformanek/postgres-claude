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

- **Same SecretBuf-template story as cryptohash.h.** `_free` does
  `explicit_bzero(ctx, sizeof(pg_hmac_ctx))` then `free` —
  `[verified-by-code, source/src/common/hmac.c:295]`. But the
  header itself never tells the caller this.
- **Key lifetime gap.** `_init(key, len)` copies the key into the
  ctx's `k_ipad`/`k_opad`, but the caller's `key` buffer remains live
  with the secret bytes — no scrub contract documented at header
  level. The caller MUST `explicit_bzero(key, len)` after init if
  they care.
- **`shrinkbuf` and `h` not scrubbed in fallback.** A5 finding noted
  the fallback HMAC's intermediate buffers (`shrinkbuf` for
  key-too-long path at hmac.c:165-169 and intermediate digest `h` at
  hmac.c:253-257) use `memset` not `explicit_bzero`
  (`source/src/common/hmac.c:169` and `:257`). The header doesn't
  expose these but A11 / A5 link them as candidates for an internal
  `SecretBuf`.
- **No constant-time compare helper.** SCRAM
  (`auth-scram.c::verify_client_proof`) hand-rolls a `timingsafe_bcmp`
  loop against `_final`'s output. Any new consumer must remember to
  do the same. pgcrypto does not (A11).
- **`_init` takes raw `(key, len)` not opaque `SecretBuf`** — A5
  proposed adding `_init_secret(SecretBuf *key)` variants. The
  current API forces the caller to manage the key's memory hygiene.

## Cross-refs

- Fallback impl: `knowledge/files/src/common/hmac.c.md`.
- OpenSSL impl: `knowledge/files/src/common/hmac_openssl.c.md`.
- Primary consumer: `src/common/scram-common.c`.
- A5 SecretBuf hosting site: `knowledge/issues/common.md`.
- A11 pgcrypto adoption candidate: `knowledge/issues/pgcrypto.md`.

## Issues

1. `[ISSUE-documentation: _free's explicit_bzero scrubbing contract
   is not documented at header level (likely)]` —
   `source/src/include/common/hmac.h:27`.
2. `[ISSUE-api-shape: _init takes raw (key, len); no SecretBuf-aware
   variant; caller must scrub their own key buffer (likely)]` —
   `source/src/include/common/hmac.h:24`.
3. `[ISSUE-api-shape: no constant-time tag-compare helper; every
   HMAC consumer reinvents timingsafe_bcmp (maybe)]` —
   `source/src/include/common/hmac.h:26`.
4. `[ISSUE-documentation: no header note that pg_hmac_final's dest
   buffer holds a verification tag that callers must compare in
   constant time (maybe)]` — `source/src/include/common/hmac.h:26`.

## Tally

`[verified-by-code]=4 [inferred]=1`
