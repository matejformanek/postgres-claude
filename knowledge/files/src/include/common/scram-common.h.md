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

- **All five primitives take raw `const char *password` / `const uint8
  *salted_password`** — secret material lives in the caller's frame
  and the header imposes no scrub contract. `scram_build_secret` is
  the only one that allocates output (palloc/malloc); its three
  intermediate `uint8 [SCRAM_MAX_KEY_LEN]` stack arrays in the impl
  carry derived key material. See scram-common.c notes.
- **Iteration-count clamping is absent at header level.** The
  `SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096` is per RFC 7677 minimum
  (line 50). But `scram_SaltedPassword`'s `int iterations` param is
  unbounded above — a malicious server can send a huge iteration
  count in `SCRAM-SHA-256$<iter>:...` to force the client through
  PBKDF2 for minutes; OWASP-2026 advisory is 600k as the *default*,
  not the floor. Header offers no `SCRAM_SHA_256_MAX_ITERATIONS` cap
  for callers to gate on. A8 / A11-related DoS surface.
- **Hash type is parameterized** (`pg_cryptohash_type hash_type`) but
  the impl only validates `PG_SHA256`; passing `PG_MD5` would silently
  produce 32-byte truncated output that nothing in the wire format
  accepts. Header doesn't constrain.
- **Wire-protocol stability.** `SCRAM_SHA_256_NAME` and
  `SCRAM_SHA_256_PLUS_NAME` are on-wire IANA names — renaming
  breaks every SCRAM client. `SCRAM_RAW_NONCE_LEN = 18` and
  `SCRAM_DEFAULT_SALT_LEN = 16` are wire-derived defaults; raising
  them is a compat issue with old clients.
- **`scram_build_secret` returns palloc'd / malloc'd string with the
  full secret** in `pg_authid.rolpassword` shape — caller must
  `pfree` (backend) or `free` (frontend). Output contains the
  base64-encoded stored key (a SecretBuf candidate, technically, but
  this one is meant to be persisted).
- **`*errstr` opacity.** Every primitive returns `int` 0/-1 with
  `const char **errstr`. The string is statically allocated and
  reaches `ereport(ERROR)` callsites verbatim — same OpenSSL-leakage
  concern as cryptohash_error.

## Cross-refs

- Impl: `knowledge/files/src/common/scram-common.c.md`.
- Backend caller: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Frontend caller: `src/interfaces/libpq/fe-auth-scram.c`.
- HMAC dep: `knowledge/files/src/include/common/hmac.h.md`.
- SHA-2 sizing: `knowledge/files/src/include/common/sha2.h.md`.

## Issues

1. `[ISSUE-defense-in-depth: no SCRAM_SHA_256_MAX_ITERATIONS upper
   bound; client-side parse can be coerced into expensive PBKDF2
   loops by a malicious server (likely)]` —
   `source/src/include/common/scram-common.h:50`.
2. `[ISSUE-documentation: SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096 is
   the RFC minimum; OWASP-2026 recommends ≥ 600 000. Header offers
   no MIN/MAX guidance (likely)]` —
   `source/src/include/common/scram-common.h:50`.
3. `[ISSUE-api-shape: scram_SaltedPassword takes pg_cryptohash_type
   hash_type but impl only accepts PG_SHA256; header doesn't
   constrain (nit)]` — `source/src/include/common/scram-common.h:52`.
4. `[ISSUE-defense-in-depth: password / salted_password params are
   raw const char *; no SecretBuf-aware variant — caller must scrub
   their own frame (likely)]` —
   `source/src/include/common/scram-common.h:52-64`.
5. `[ISSUE-documentation: SCRAM_MAX_KEY_LEN ties statically to
   SCRAM_SHA_256_KEY_LEN; adding SCRAM-SHA-512 requires coordinated
   bumps the header doesn't flag (nit)]` —
   `source/src/include/common/scram-common.h:30`.

## Tally

`[verified-by-code]=6 [inferred]=2`
