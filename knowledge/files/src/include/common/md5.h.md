---
path: src/include/common/md5.h
anchor_sha: 4b0bf0788b0
loc: 37
---

# md5.h

- **Source path:** `source/src/include/common/md5.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 37

## Purpose

Public MD5 constants and three convenience helpers that wrap the
generic `pg_cryptohash_*` API. Both frontend and backend pull this in
to work with MD5-encrypted passwords (the `md5...` rolpassword
prefix). [from-comment, md5.h:6-8]

## Key declarations

- **Constants:**
  - `MD5_DIGEST_LENGTH = 16`, `MD5_BLOCK_SIZE = 64` (md5.h:20-22).
  - `MD5_PASSWD_CHARSET "0123456789abcdef"` — used by `crypt.c` to
    classify a stored secret as `PASSWORD_TYPE_MD5`.
  - `MD5_PASSWD_LEN = 35` — the `"md5" + 32 hex` shape stored in
    `pg_authid.rolpassword`.
- **Helpers (all live in `md5_common.c`):**
  - `pg_md5_hash(buff, len, hexsum, errstr)` — one-shot MD5 → hex
    string (33 chars incl. NUL).
  - `pg_md5_binary(buff, len, outbuf, errstr)` — same, but raw 16 bytes.
  - `pg_md5_encrypt(passwd, salt, salt_len, buf, errstr)` — the
    "md5"+MD5(passwd||salt) password derivation. Output buffer must be
    ≥ 36 bytes.

## Phase D notes

- **MD5 is deprecated but still wired up.** `crypt.c::encrypt_password`
  emits a WARNING when storing an MD5 secret (gated by
  `md5_password_warnings` GUC). The fallback impl
  (`src/common/md5.c`) is preserved because some platforms still
  build PG without OpenSSL.
- **Header lacks deprecation comment.** Nothing in `md5.h:1-37` warns
  the reader "MD5 is for legacy auth only — do NOT use this for
  password hashing or message authentication in new code." A
  reader who searches for "MD5 PostgreSQL" lands here and finds
  `pg_md5_encrypt` with no caveats.
- **`pg_md5_encrypt` parameter validation.** Takes `salt_len` but the
  impl in `md5_common.c` allows any salt length up to internal
  buffer; the header doesn't document min/max. Same for `passwd`
  length.
- **SecretBuf candidate sites.** A5's common.md flags
  `md5_common.c:151,170` (the `crypt_buf` hex digest staging and the
  intermediate `*outbuf`) as secret-scrub gaps — the header-level
  fix is for `pg_md5_encrypt`'s `buf` parameter to become a
  `SecretBuf` so the caller can't accidentally leave the derived
  hash on the stack.
- **No constant-time compare helper for MD5 hex digests.** Password
  verification in `crypt.c::md5_crypt_verify` uses `strcmp` against
  the stored hash — A5 finding (#likely). Header-level `pg_md5_equal`
  would have steered them right.

## Cross-refs

- Impl of helpers: `knowledge/files/src/common/md5_common.c.md`.
- Fallback impl of primitive: `knowledge/files/src/common/md5.c.md`.
- Internal state: `knowledge/files/src/common/md5_int.h.md`.
- Caller: `knowledge/files/src/backend/libpq/crypt.c.md`.
- A5 SecretBuf cluster: `knowledge/issues/common.md`.

## Issues

1. `[ISSUE-documentation: no deprecation/use-only-for-legacy-SCRAM
   note in header — discoverability hazard for new contributors
   (likely)]` — `source/src/include/common/md5.h:1-38`.
2. `[ISSUE-api-shape: pg_md5_encrypt's output buf is caller-owned
   plain char[]; A5 SecretBuf candidate site (likely)]` —
   `source/src/include/common/md5.h:33-35`.
3. `[ISSUE-documentation: pg_md5_encrypt's salt_len constraints
   (range, why salt is uint8* but passed by uint8 type) are not in
   header (nit)]` — `source/src/include/common/md5.h:33`.
4. `[ISSUE-api-shape: no constant-time pg_md5_equal helper — every
   caller uses strcmp on hex digests, leaking timing (maybe)]` —
   `source/src/include/common/md5.h:29-32`.

## Tally

`[verified-by-code]=4 [from-comment]=2`
