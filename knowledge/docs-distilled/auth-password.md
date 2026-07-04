---
source_url: https://www.postgresql.org/docs/current/auth-password.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.5 Password Authentication"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/crypt.c.md, knowledge/files/src/backend/libpq/auth-scram.c.md, knowledge/docs-distilled/sasl-authentication.md]
---

# Password authentication — scram-sha-256 / md5 / password (§21.5)

Three `pg_hba.conf` methods, all reading the verifier stored in
`pg_authid.rolpassword`. The method the server actually runs is decided by the
**stored verifier type**, not only by the hba keyword.

## Non-obvious claims

- **The stored-verifier type drives the exchange.** `get_password_type()`
  classifies `rolpassword` by prefix: an `md5`-prefixed string →
  `PASSWORD_TYPE_MD5`, a `SCRAM-SHA-256$…` string → `PASSWORD_TYPE_SCRAM_SHA_256`.
  `[verified-by-code]` `source/src/backend/libpq/crypt.c:153` (`get_password_type`),
  `:165` (MD5), `:168` (SCRAM). This is why the hba `md5` method **auto-upgrades
  to SCRAM** when the password happens to be stored as SCRAM. `[from-docs]`
- **`md5` in hba is a superset.** If the hba line says `md5` but the verifier is
  SCRAM, the server transparently performs SCRAM-SHA-256 instead — so `md5`
  lines keep working after a SCRAM migration. `[from-docs]`
- **`password` sends cleartext.** The `password` method transmits the password
  in clear over the wire (safe only under SSL/GSSAPI encryption) but can verify
  against *either* a SCRAM or an MD5 stored verifier. `[from-docs]`
- **SCRAM verifier format** (what lands in `rolpassword`):
  `SCRAM-SHA-256$<iterations>:<salt>$<StoredKey>:<ServerKey>`. `[from-docs]`
  The challenge-response is RFC 7677 (SCRAM-SHA-256); see the SASL exchange doc.
- **`password_encryption` picks the on-write format.** The GUC (values
  `scram-sha-256` or `md5`) decides how `CREATE ROLE … PASSWORD` / `ALTER ROLE`
  / psql `\password` store the verifier. `encrypt_password()` re-encodes a
  plaintext to the target type, but will keep an already-hashed input as-is.
  `[verified-by-code]` `source/src/backend/libpq/crypt.c:180` (`encrypt_password`).
- **NULL verifier always fails.** A role with no password (`rolpassword` NULL)
  can never satisfy a password method — password auth "always fails" for it.
  `[from-docs]`
- **md5 is deprecated.** MD5 is cryptographically broken and a stolen MD5
  verifier is directly usable; support "will be removed in a future release".
  The migration path is: confirm clients speak SCRAM → set
  `password_encryption='scram-sha-256'` → have every role re-set its password →
  flip hba lines to `scram-sha-256`. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/libpq/crypt.c.md]] — `get_password_type` /
  `encrypt_password` / `plain_crypt_verify`, the verifier classifier this page
  turns on.
- [[knowledge/files/src/backend/libpq/auth-scram.c.md]] — the backend SCRAM
  state machine that a `scram-sha-256` (or upgraded `md5`) line drives.
- [[knowledge/docs-distilled/sasl-authentication.md]] — protocol-level SCRAM
  message flow + channel binding.
</content>
