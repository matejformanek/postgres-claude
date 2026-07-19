# scram.h

- **Source path:** `source/src/include/libpq/scram.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Interface to libpq/scram.c" — exposes the SCRAM-SHA-256 mechanism
instance (`pg_be_scram_mech`), helpers to build and parse stored secrets,
and the legacy plaintext-verify path used when migrating passwords.

## Public API surface

- GUC: `scram_sha_256_iterations` (PBKDF2 iteration count for new secrets).
- `pg_be_scram_mech` — the `pg_be_sasl_mech` instance plugged into the
  SASL framework. SASL mechanism name (`"SCRAM-SHA-256"`,
  `"SCRAM-SHA-256-PLUS"` with channel binding) is **wire-protocol-visible**
  — defined in `scram.c` and `common/scram-common.h`, not in this header.
- `char *pg_be_scram_build_secret(const char *password)` — derive the
  storable secret from a plaintext password (the format that lands in
  `pg_authid.rolpassword`).
- `bool parse_scram_secret(secret, *iterations, *hash_type, *key_length,
  **salt, stored_key[], server_key[])` — split a stored secret into its
  fields.
- `bool scram_verify_plain_password(username, password, secret)` — used
  when the client sent a plaintext password (e.g. via `password` auth) but
  the server has only a SCRAM secret to compare against.

## Cross-refs

- Related backend: `src/backend/libpq/auth-scram.c`,
  `src/common/scram-common.c`.
- Related: `knowledge/files/src/include/libpq/sasl.h.md` (the framework
  this plugs into), `knowledge/files/src/include/libpq/crypt.h.md`
  (`PASSWORD_TYPE_SCRAM_SHA_256`), `knowledge/files/src/include/libpq/libpq-be.h.md`
  (Port carries `scram_ClientKey`/`scram_ServerKey`).
- Frontend: `src/interfaces/libpq/fe-auth-scram.c`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: stored_key / server_key buffer sizes implicit]**
  `scram.h:29-33` — `parse_scram_secret` writes into caller-supplied
  `uint8 stored_key[]` and `server_key[]` but the header gives no buffer
  size; the caller must know they need `SCRAM_MAX_KEY_LEN` (defined in
  `common/scram-common.h`). A short buffer silently overruns. Severity:
  maybe.
- **[ISSUE-leak: scram_verify_plain_password timing]** `scram.h:34-35` —
  doing a SCRAM verification of a plaintext password is by construction
  more expensive than a hash compare; whether the implementation
  constant-times the final equality (and whether failing-early on a bad
  base64-decoded salt leaks via timing) is not stated. Verify in
  `auth-scram.c`. Severity: maybe.
- **[ISSUE-undocumented-invariant: scram_sha_256_iterations lower bound]**
  `scram.h:22` — GUC has no documented floor in this header; a misconfigured
  cluster could set it to 1, weakening every newly created password.
  Defaulting to a safer floor would be a Phase D candidate. Severity:
  maybe.

## Tally

`[verified-by-code]=3 [from-comment]=1 [inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
