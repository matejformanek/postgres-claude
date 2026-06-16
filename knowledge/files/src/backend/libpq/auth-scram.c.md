---
path: src/backend/libpq/auth-scram.c
anchor_sha: 4b0bf0788b0
loc: 1503
depth: deep
---

# auth-scram.c

- **Source path:** `source/src/backend/libpq/auth-scram.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1503

## Purpose

Server-side implementation of `SCRAM-SHA-256` and
`SCRAM-SHA-256-PLUS` (RFC 5802 / 5803 / 7677), the SASL mechanism
PostgreSQL has used as its primary password method since v10.
Plumbed into `CheckSASLAuth` as the `pg_be_sasl_mech` named
`pg_be_scram_mech` (auth-scram.c:114). Also exports
`pg_be_scram_build_secret` (called from `crypt.c::encrypt_password`)
and `scram_verify_plain_password` (called when a plaintext password
arrives over the wire but the catalog stores a SCRAM secret).
[verified-by-code, auth-scram.c:114-120, 480-583]

The header comment is the canonical statement of PG's deliberate
deviations from the spec — empty username on the wire (real username
flows in the startup packet), `tls-server-end-point` as the only
channel-binding type (not `tls-unique`), SASLprep best-effort because
the password's encoding isn't yet pinned, and the "mock secret +
doomed flag" pattern that makes user-doesn't-exist
indistinguishable-by-timing from wrong-password. [from-comment,
auth-scram.c:6-81]

## Public API surface

- `const pg_be_sasl_mech pg_be_scram_mech` — `auth-scram.c:114`. The
  vtable wired into `CheckSASLAuth(&pg_be_scram_mech, ...)` from
  `auth.c:867`. `max_message_length = PG_MAX_SASL_MESSAGE_LENGTH`.
- `char *pg_be_scram_build_secret(const char *password)` —
  `auth-scram.c:481`. Generates a fresh `SCRAM-SHA-256$<iter>:<salt>$<storedkey>:<serverkey>`
  secret string. Best-effort SASLprep on the input; random
  `SCRAM_DEFAULT_SALT_LEN` salt from `pg_strong_random`.
  [verified-by-code, auth-scram.c:480-513]
- `bool scram_verify_plain_password(const char *username, const char *password, const char *secret)`
  — `auth-scram.c:521`. Used when HBA method is plain `password` but
  pg_authid stores a SCRAM secret: recompute the ServerKey from the
  plaintext and compare via `timingsafe_bcmp`. [verified-by-code,
  auth-scram.c:520-583]
- `bool parse_scram_secret(const char *secret, int *iterations, pg_cryptohash_type *hash_type, int *key_length, char **salt, uint8 *stored_key, uint8 *server_key)`
  — `auth-scram.c:598`. Parses the `$`-delimited stored secret;
  returns false (not ereports) on malformed. Used both by SCRAM
  handshake init and by `crypt.c::get_password_type`. [verified-by-code]
- GUC: `int scram_sha_256_iterations` — `auth-scram.c:194`, default
  `SCRAM_SHA_256_DEFAULT_ITERATIONS` (4096).

## Internal landmarks

- **State machine.** `scram_state.state` ∈ {`SCRAM_AUTH_INIT`,
  `SCRAM_AUTH_SALT_SENT`, `SCRAM_AUTH_FINISHED`}
  (auth-scram.c:126-131). Driven by `scram_exchange` (auth-scram.c:350):
  INIT consumes `client-first-message`, builds server-first, transitions
  to `SALT_SENT`; SALT_SENT consumes `client-final-message`, verifies
  proof, transitions to FINISHED.
- **Per-exchange state struct.** `scram_state` (auth-scram.c:133-173) —
  carries port pointer, channel-binding flag, hash type, iteration
  count, salt, three keys (ClientKey/StoredKey/ServerKey of
  `SCRAM_MAX_KEY_LEN` bytes), all parsed client message fields, server
  nonce, the `doomed` flag, and `logdetail`. The `doomed` flag is the
  single bit that distinguishes mock auth from real auth.
- **Mock secret machinery** — `mock_scram_secret` (auth-scram.c:695)
  builds a plausible-looking salt + zero keys when the user is
  unknown; `scram_mock_salt` (auth-scram.c:1469) makes the salt a
  SHA-256 of `username || GetMockAuthenticationNonce()` so the same
  username always produces the same salt on the same cluster (the
  cluster's nonce lives in pg_control and is set at initdb).
  [verified-by-code, auth-scram.c:684-735, 1463-1503]
- **Message parsers** — `read_client_first_message` (auth-scram.c:911,
  the GS2 header + cbind flag + ignored authzid + ignored username
  + nonce) and `read_client_final_message` (auth-scram.c:1264, the
  cbind echo + final nonce + proof). Both stamp errors with
  `ERRCODE_PROTOCOL_VIOLATION` and use `sanitize_char` / `sanitize_str`
  (auth-scram.c:805, 825) to truncate / hex-escape attacker-supplied
  bytes before they hit the log.
- **Channel binding.** Only `tls-server-end-point` is supported
  (auth-scram.c:1050-1057). The server computes its own
  `tls-server-end-point` value via `be_tls_get_certificate_hash`
  (auth-scram.c:1325) and *string-compares* the base64 forms
  (auth-scram.c:1351 — `strcmp`, not `timingsafe_bcmp`; both sides are
  base64 of the server's own cert hash, no user secret involved, so
  the leak is "did the client know our cert").
- **Verification primitives** — `verify_final_nonce` (auth-scram.c:1125)
  uses `timingsafe_bcmp` for both halves; `verify_client_proof`
  (auth-scram.c:1147) computes ClientSignature = HMAC(StoredKey,
  AuthMessage), XORs into ClientProof to recover ClientKey, hashes it
  with `scram_H`, and `timingsafe_bcmp`s against StoredKey. Returns
  false (not ereport) on mismatch so the caller can fail uniformly.
- **MyProcPort secret stash.** On success, both `ClientKey` and
  `ServerKey` are copied into `MyProcPort->scram_*` and
  `has_scram_keys = true` is set (auth-scram.c:467-470). Used later by
  postgres_fdw / dblink for SCRAM passthrough.

## Invariants & gotchas

- **Mock authentication uses the full code path.** Even when
  `doomed = true`, `verify_client_proof` is still called
  (auth-scram.c:440); the explicit comment at auth-scram.c:435-438:
  "the order of these checks is intentional. We calculate the client
  proof even in a mock authentication, even though it's bound to
  fail, to thwart timing attacks." [verified-by-code]
- **`timingsafe_bcmp` is mandatory** at every comparison of a
  secret-derived value: nonce halves (auth-scram.c:1133-1135),
  client proof vs StoredKey (auth-scram.c:1189), ServerKey from
  plaintext (auth-scram.c:582). A future patch that swaps in `memcmp`
  is a security regression.
- **PG's `n=user` field is ignored** (auth-scram.c:1097-1101) — only
  the startup-packet username is trusted; this prevents a SCRAM-level
  username swap. libpq always sends `n=` empty. A custom client that
  sends a non-empty `n=` is silently accepted because the field is
  used for nothing.
- **`tls-server-end-point` is the only channel binding.** The
  client-side flag `'p='` MUST be followed by exactly
  `tls-server-end-point` or the exchange errors (auth-scram.c:1053-1057).
  This is on-wire and unchangeable without a new mechanism name.
- **SCRAM mechanism string `SCRAM-SHA-256` (and `-PLUS`) is part of
  the wire protocol** — exposed in `scram_get_mechanisms`
  (auth-scram.c:204-220) and consumed verbatim from the client in
  `init`. Renaming breaks every libpq in the world.
- **Channel-binding *PLUS* offered iff `port->ssl_in_use`**, gated by
  `#ifdef USE_SSL`. A GSS-encrypted connection therefore cannot get
  channel binding (correct per spec — only TLS provides
  tls-server-end-point).
- **SASLprep failure is benign**: if `pg_saslprep` returns anything
  but `SASLPREP_SUCCESS` we just use the raw bytes (auth-scram.c:494-496,
  561-563). The header comment explains why: `client_encoding` isn't
  pinned yet, so being strict would lock out non-UTF8 sites.
- **Mock secret zero keys** (auth-scram.c:733-734) — the StoredKey /
  ServerKey are zeroed because the doomed path never actually
  compares against them; but mock_scram_salt *is* deterministic, so a
  passive observer can't tell from the wire whether the user is mock
  or real until the proof check fails identically in both cases.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/scram.h.md` (planned).
- SASL framework: `knowledge/files/src/backend/libpq/auth-sasl.c.md`.
- Frontend counterpart: `src/interfaces/libpq/fe-auth-scram.c`.
- Common SCRAM primitives: `src/common/scram-common.c`, `src/common/saslprep.c`.
- Cert hash for channel binding: `be-secure-openssl.c::be_tls_get_certificate_hash`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: parsed client proof / nonce not scrubbed]**
  `auth-scram.c:1392-1393` — `client_proof` is `pfree`'d after
  `memcpy` into `state->ClientProof`, but no `explicit_bzero`. The
  client proof is HMAC-derived from the user's password; combined
  with a recorded server-first-message it enables offline brute force.
  Same for `state->ClientKey/StoredKey/ServerKey/ClientProof` — the
  whole `scram_state` is `palloc0_object`'d (auth-scram.c:243) and
  never explicit-bzero'd at exchange end. Severity: maybe.
- **[ISSUE-style: `sanitize_char` returns pointer to static buffer]**
  `auth-scram.c:804-814` — two simultaneous `errdetail("%s ... %s",
  sanitize_char(a), sanitize_char(b))` in one error report would
  smash the buffer; the codebase happens to never do this but it's a
  trap. Severity: nit.
- **[ISSUE-doc-drift: header comment claims `tls-unique` not specified
  for TLS 1.3]** `auth-scram.c:25-26` — this was true in 2017; as of
  2026 there is RFC 9266 (`tls-exporter`) which would be the
  TLS-1.3-compatible replacement. Flag for follow-up: are we missing
  a chance to add a TLS-1.3-clean binding? Severity: nit.
- **[ISSUE-correctness: mock_scram_salt is deterministic per
  (username, cluster_nonce)]** `auth-scram.c:1469-1503` — an attacker
  who can probe with arbitrary usernames can learn whether two
  usernames are the same (same salt = same user). Probably acceptable
  (they could send the same name anyway) but document. Severity: nit.
- **[ISSUE-question: GUC `scram_sha_256_iterations` default 4096 is
  RFC-minimum]** `auth-scram.c:194` — OWASP recommends ≥ 600k for
  PBKDF2-HMAC-SHA256 in 2026. PG's choice is *iteration count for
  every new ALTER USER*; bumping affects every CREATE USER thereafter.
  Worth a planning note. Severity: maybe.

## Tally

`[verified-by-code]=20 [from-comment]=10 [inferred]=1`
