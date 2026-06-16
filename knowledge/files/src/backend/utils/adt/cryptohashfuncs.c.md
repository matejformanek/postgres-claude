# cryptohashfuncs.c — SQL-callable cryptographic hashes

## Purpose

Thin SQL wrappers around the `pg_cryptohash_*` API in `src/common/cryptohash*.c`. Exposes `md5(text)`, `md5(bytea)`, `sha224`, `sha256`, `sha384`, `sha512` to SQL. No SHA1 wrapper (deliberate omission).

Source: `source/src/backend/utils/adt/cryptohashfuncs.c` (169 lines).

## Key functions

- `md5_text` — MD5 over a `text` input, returns lower-case hex `text`. Uses `pg_md5_hash` (which itself can fail in FIPS mode). [verified-by-code cryptohashfuncs.c:33-53]
- `md5_bytea` — same for bytea. [verified-by-code:58-74]
- `cryptohash_internal(type, bytea)` — common SHA-2 routine. Creates a context via `pg_cryptohash_create`, init/update/final. Returns a bytea. Calls `elog(ERROR)` (not `ereport`) on any libcrypto failure — these are "should never happen" paths. [verified-by-code:79-133]
- `sha224_bytea` / `sha256_bytea` / `sha384_bytea` / `sha512_bytea` — one-line wrappers. [verified-by-code:140-169]

## Phase D notes

- **MD5 is deliberately retained for backward-compat** (used by `pg_authid` MD5 passwords, hash join salting). No SHA-1 SQL-level wrapper exists, which matches the policy that SHA-1 is gone for new use cases. [inferred from the switch/case that elog-errors on `PG_SHA1`]
- **FIPS mode**: when OpenSSL is in FIPS mode, MD5 is unavailable; `pg_md5_hash` returns false with an `errstr` and the SQL function errors with a clean message. [verified-by-code:46-48]
- **No secret-scrub surface**: hashes are deterministic and the input is application data, not a secret. The A5 finding about secret-scrub (`SecretBuf`) applies to ciphers/HMACs, not to plain hashes. There IS still a small concern that intermediate `pg_cryptohash_ctx` state could leak via heap inspection, but `pg_cryptohash_free` is called on every success path. There is no explicit scrub of the context memory. [verified-by-code:128]
- **No length/size validation needed**: cryptohash internals tolerate any input length, and the result buffer is sized from `PG_SHA*_DIGEST_LENGTH` constants.

## Potential issues

- `[ISSUE-secret-scrub: pg_cryptohash_free relies on whatever cryptohash backend (openssl vs in-tree) frees; the in-tree path may not zero context memory. Probably fine because hash inputs aren't secrets, but if pgcrypto adds HMAC over this file it would be a real gap (low)]`.
- `[ISSUE-error-handling: cryptohash_internal uses elog(ERROR) instead of ereport with SQLSTATE; if a user-facing failure mode emerges (e.g. FIPS toggle mid-session), the error won't carry a category. Current callers cannot trigger this, but it's a styled-as-internal-error path (low)]`.
- `[ISSUE-crypto-weakness: md5_text / md5_bytea remain unrestricted on FIPS-disabled builds — by design; documented in user docs (low)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
