---
source_url: https://www.postgresql.org/docs/current/auth-cert.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.12 Certificate Authentication"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/be-secure-openssl.c.md, knowledge/docs-distilled/auth-username-maps.md, knowledge/docs-distilled/auth-pg-hba-conf.md]
---

# Certificate authentication — the `cert` method (§21.12)

TLS client-certificate auth: the client's cert identity *is* the credential;
no password crosses the wire.

## Non-obvious claims

- **`hostssl`-only.** Cert auth is available for SSL/TLS connections only, so it
  can appear only on `hostssl` records. The server "will require that the client
  provide a valid, trusted certificate" (chained to the server's root CA).
  `[from-docs]`
- **CN → database user by default.** The certificate `cn` (Common Name) is
  compared to the requested database user name; a match allows login. Use a
  `map=` user-name map to let the CN differ from the role name (the canonical
  pg_ident.conf use case). `[from-docs]`
- **`cert` == trust + verify-full.** "It is redundant to use the `clientcert`
  option with `cert` authentication because `cert` authentication is effectively
  `trust` authentication with `clientcert=verify-full`." So `cert` implicitly
  demands a valid cert whose CN/DN matches the (mapped) user — no separate
  `clientcert=` needed. `[from-docs]`
- **DN matching for finer identity:** `clientname=DN` matches against the whole
  RFC-2253 Distinguished Name instead of just the CN — useful when CNs collide
  or you need OU/O components. (`clientname=CN` is the default.) `[from-docs]`
- **No password transmitted.** Authentication is purely the TLS handshake +
  cert-chain validation; there is no secret exchanged after the cert is
  presented. `[from-docs]`
- **Distinction from `clientcert` on other methods.** `clientcert=verify-ca` /
  `verify-full` can *augment* a password/scram line on any `hostssl` record
  (cert required *in addition to* the password); the `cert` method makes the
  cert the *sole* credential. `[from-docs]` (see auth-pg-hba-conf.md options.)

## Links into corpus

- [[knowledge/docs-distilled/auth-username-maps.md]] — the `map=` mechanism cert
  auth leans on to decouple CN from role.
- [[knowledge/docs-distilled/auth-pg-hba-conf.md]] — the `clientcert=` /
  `clientname=` option semantics live on the hba record.
- [[knowledge/files/src/backend/libpq/be-secure-openssl.c.md]] — the backend TLS
  handshake + peer-cert extraction that feeds the CN/DN comparison.
</content>
