---
path: src/common/md5_common.c
anchor_sha: 4b0bf0788b0
loc: 173
---

# md5_common.c

- **Source path:** `source/src/common/md5_common.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 173

## Purpose

Three convenience wrappers that take the generic `pg_cryptohash_*` API
and surface the historic MD5-shaped helpers used across the codebase:
`pg_md5_hash` (hex output), `pg_md5_binary` (raw 16 bytes), and
`pg_md5_encrypt` (the `md5...` `pg_authid.rolpassword` derivation).
[from-comment, md5_common.c:1-15]

## Role in PG

Linked into both frontend and backend libpgcommon. The three helpers
are the only sanctioned MD5 entry points outside the cryptohash
facade — `crypt.c::md5_crypt_verify`, `psql`'s MD5 prompt path,
`fe-auth.c`, `pg_authid` lookups, etc. all funnel through here.

## Key functions

- `pg_md5_hash(buff, len, hexsum, errstr)` (md5_common.c:73):
  - Creates a `pg_cryptohash_ctx` for `PG_MD5`, runs init/update/final
    into a stack `uint8 sum[16]`.
  - Hex-encodes via local `bytesToHex` (md5_common.c:27) into `hexsum`
    (33 chars).
  - Frees the ctx. **No explicit_bzero on `sum`** —
    `pg_cryptohash_free` scrubs the ctx but `sum` is on stack and
    survives until frame teardown.
  - Returns `false` on any cryptohash failure with `*errstr` set.
- `pg_md5_binary(buff, len, outbuf, errstr)` (md5_common.c:108): same
  flow but writes binary into the caller's `outbuf` (assumed 16
  bytes).
- `pg_md5_encrypt(passwd, salt, salt_len, buf, errstr)`
  (md5_common.c:145): builds the historic `md5` + MD5(passwd||salt)
  format.
  - **malloc(passwd_len + salt_len + 1)** for the concat buffer
    (md5_common.c:151).
  - Copies passwd then salt (salt at the end "because it may be known
    by users trying to crack the MD5 output" — md5_common.c:161-163).
  - `strcpy(buf, "md5")` then `pg_md5_hash` writes the hex into
    `buf+3`.
  - **`free(crypt_buf)` without `explicit_bzero`** (md5_common.c:170).
    `crypt_buf` carries the cleartext password concatenated with the
    salt. Plaintext + per-user salt freed unscrubbed onto the heap.

## OpenSSL vs fallback dispatch

This file is dispatch-agnostic; it uses `pg_cryptohash_*` directly.

## State / globals

- `bytesToHex`'s static `hex[]` lookup string (md5_common.c:30).
  Read-only.

## Concurrency

Reentrant.

## Phase D notes

- **`pg_md5_encrypt`'s `crypt_buf` is a clear leak of the cleartext
  password through `free()` without bzero** (md5_common.c:170). This
  is exactly the kind of site a `SecretBuf` would close: own
  malloc/scrub/free in one wrapper.
- **Stack `sum[16]` in `pg_md5_hash`** holds the MD5 of whatever was
  hashed — for the password path that's MD5(passwd||salt), the
  pre-image of a known-plaintext attack. Not scrubbed.
- Three calls deep:
  `crypt.c::md5_crypt_verify` → `pg_md5_encrypt` → `pg_md5_hash`. The
  password lifetime spans all three frames; only the final stage's
  ctx is scrubbed.

## Potential issues

- **[ISSUE-secret-scrub: `pg_md5_encrypt`'s `crypt_buf` holds the
  cleartext password and is freed unscrubbed]** `md5_common.c:151,
  170`. The exact `explicit_bzero`-before-free gap that motivated the
  A5 SecretBuf sweep. Severity: likely.
- **[ISSUE-secret-scrub: `pg_md5_hash`'s stack `sum[16]` is the
  MD5(password||salt) and is not explicit_bzero'd]**
  `md5_common.c:76, 96-98`. On stack but visible to subsequent stack
  frames until overwritten. Severity: maybe.
- **[ISSUE-stale-todo: salt "at the end because it may be known by
  users"]** `md5_common.c:161-163`. This is a 1990s-style mitigation
  against extending MD5 collisions; modernity says use a real KDF.
  Already deprecated. Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/md5.h.md`.
- Backend caller: `knowledge/files/src/backend/libpq/crypt.c.md`.
- Dispatch facade: `knowledge/files/src/common/cryptohash.c.md` /
  `cryptohash_openssl.c.md`.

## Tally

`[verified-by-code]=9 [from-comment]=2`
