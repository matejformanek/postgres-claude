---
source_url: https://www.postgresql.org/docs/current/encryption-options.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§19.8 Encryption Options"
maps_to_skills: [row-level-security, wire-protocol, collation-provider]
maps_to_corpus: [knowledge/docs-distilled/auth-password.md, knowledge/docs-distilled/ssl-tcp.md, knowledge/docs-distilled/gssapi-enc.md, knowledge/subsystems/libpq-backend.md]
---

# Encryption options — the threat-model map (§19.8)

A single short chapter that indexes every encryption surface PG offers, each
against a *different* trust boundary. The value is the boundary matrix, not the
mechanisms (those live in the pages this one links to).

## Non-obvious claims

- **Each option assumes a different untrusted party.** Password-storage
  encryption defends against a leaked catalog; column encryption (`pgcrypto`)
  against a nosy DBA reading rows; partition/filesystem encryption against a
  *stolen drive*; SSL/GSSAPI against a *network eavesdropper*; client-side
  encryption against an *untrusted server admin*. No single option covers all
  four; picking one means naming the adversary. `[from-docs]`
- **Password-storage encryption never sends the cleartext password to the
  server** under SCRAM or MD5 — the client transforms it first, so a
  compromised server (or its logs) never sees it. SCRAM is the standard,
  MD5 is the deprecated PG-specific scheme. `password_encryption` GUC picks
  which verifier is stored. `[from-docs]` (Mechanism: `auth-password.md`.)
- **`pgcrypto` column encryption has an unavoidable cleartext window on the
  server**: the key is supplied by the client, but decryption happens
  server-side, so a privileged attacker with full DB-server access (or a core
  dump) can still catch the key + plaintext in memory. It defends storage, not
  a compromised live server. `[from-docs]`
- **Filesystem/partition encryption (dm-crypt+LUKS, eCryptfs, geli/gbde)
  protects only data *at rest*** — once the FS is mounted for the running
  cluster, everything is cleartext to any process, and the mount key itself
  becomes an attack surface (where is it stored to allow unattended boot?).
  `[from-docs]`
- **SSL host authentication is the MITM defense, distinct from SSL encryption.**
  Encryption alone (client not verifying the server cert) still lets an
  impersonator terminate the TLS and harvest the password; only server-cert
  verification (`sslmode=verify-full`) closes it. Encryption ≠ authentication.
  `[from-docs]`
- **Client-side encryption is the only option that assumes the DBA is hostile** —
  cleartext never exists on the server at all, at the cost of moving all key
  management (and the loss of server-side WHERE/index on the ciphertext) to the
  client. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/auth-password.md]] — SCRAM vs MD5 verifier storage,
  the `password_encryption` mechanism this page summarizes.
- [[knowledge/docs-distilled/ssl-tcp.md]] — the SSL network-encryption +
  host-authentication surface.
- [[knowledge/docs-distilled/gssapi-enc.md]] — the GSSAPI network-encryption
  alternative (password never transmitted at all).
- [[knowledge/subsystems/libpq-backend.md]] — `be-secure*.c`, where the network
  options are implemented.
