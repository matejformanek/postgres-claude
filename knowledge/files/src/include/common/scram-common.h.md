---
path: src/include/common/scram-common.h
anchor_sha: 4b0bf0788b0
loc: 70
---

# scram-common.h

- **Source path:** `source/src/include/common/scram-common.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 70

## Purpose

Public constants + primitives shared by the SCRAM server
(`src/backend/libpq/auth-scram.c`) and client
(`src/interfaces/libpq/fe-auth-scram.c`). Declares the SCRAM-SHA-256
mechanism names, key/salt/nonce sizes, default iteration count, and
the five low-level helpers that implement RFC 5802 §3 derivations.
[verified-by-code, scram-common.h:13-68]

## Key declarations

- **Mechanism names (wire-protocol strings):**
  - `SCRAM_SHA_256_NAME "SCRAM-SHA-256"` (scram-common.h:20)
  - `SCRAM_SHA_256_PLUS_NAME "SCRAM-SHA-256-PLUS"` (scram-common.h:21)
  Renaming either is an on-wire break.
- **Size constants:**
  - `SCRAM_SHA_256_KEY_LEN = PG_SHA256_DIGEST_LENGTH` (32 bytes,
    scram-common.h:24).
  - `SCRAM_MAX_KEY_LEN = SCRAM_SHA_256_KEY_LEN` (scram-common.h:30) —
    sized for the *largest* SCRAM hash supported; today only
    SHA-256 is wired. Adding SCRAM-SHA-512 would require bumping
    this and re-sizing fixed-buffer call sites.
  - `SCRAM_RAW_NONCE_LEN = 18` (scram-common.h:37) — raw bytes from
    `pg_strong_random`; gets base64-encoded for the wire.
  - `SCRAM_DEFAULT_SALT_LEN = 16` (scram-common.h:44) — per RFC 7677
    example.
  - `SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096` (scram-common.h:50) —
    RFC minimum. See `auth-scram.c` notes for the OWASP-2026
    discrepancy.
- **Primitives** (all return 0/-1 with `*errstr` set on failure):
  - `scram_SaltedPassword` — PBKDF2-HMAC-`hash_type`.
  - `scram_H` — bare hash (one shot).
  - `scram_ClientKey` — HMAC(SaltedPassword, "Client Key").
  - `scram_ServerKey` — HMAC(SaltedPassword, "Server Key").
  - `scram_build_secret` — composes the full
    `SCRAM-SHA-256$iter:salt$stored:server` string for
    pg_authid.rolpassword.

## Phase D notes

- All five primitives take `const char *password` / `const uint8
  *salted_password` — secret material lives in the caller's frame.
  `scram_build_secret` is the only one that allocates output
  (palloc/malloc); its three intermediate `uint8 [SCRAM_MAX_KEY_LEN]`
  stack arrays in the impl carry derived key material. See
  scram-common.c notes.

## Cross-refs

- Impl: `knowledge/files/src/common/scram-common.c.md`.
- Backend caller: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Frontend caller: `src/interfaces/libpq/fe-auth-scram.c`.

## Tally

`[verified-by-code]=5 [inferred]=1`
