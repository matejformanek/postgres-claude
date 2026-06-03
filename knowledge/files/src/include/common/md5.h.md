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
- The three helpers do not accept a "context" or hold per-caller
  state; they wrap allocation+init+update+final around the
  `pg_cryptohash_ctx` opaque type. Each call pays an alloc/free pair.

## Cross-refs

- Impl of helpers: `knowledge/files/src/common/md5_common.c.md`.
- Fallback impl of primitive: `knowledge/files/src/common/md5.c.md`.
- Internal state: `knowledge/files/src/common/md5_int.h.md`.
- Caller: `knowledge/files/src/backend/libpq/crypt.c.md`.

## Tally

`[verified-by-code]=4 [from-comment]=1`
