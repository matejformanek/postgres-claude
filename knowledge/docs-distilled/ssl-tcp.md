---
source_url: https://www.postgresql.org/docs/current/ssl-tcp.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§19.9 Secure TCP/IP Connections with SSL"
maps_to_skills: [wire-protocol, extension-development]
maps_to_corpus: [knowledge/subsystems/libpq-backend.md, knowledge/docs-distilled/auth-cert.md, knowledge/docs-distilled/protocol-flow.md, knowledge/docs-distilled/runtime-config-connection.md]
---

# Secure TCP/IP connections with SSL — the backend TLS surface (§19.9)

How `ssl=on` wires the OpenSSL server context, and the file/permission/verify
rules a backend hacker touching `be-secure-openssl.c` needs. Implemented in
`src/backend/libpq/be-secure-openssl.c` (context built in `be_tls_init`, per-
connection handshake in `be_tls_open_server`).

## Non-obvious claims

- **SSL rides the *same* TCP port, chosen per-connection by a pre-startup
  negotiation.** With `ssl=on` the client sends an `SSLRequest`
  (`NEGOTIATE_SSL_CODE = PG_PROTOCOL(1234,5679)`, `pqcomm.h:128`
  `[verified-by-code]`); the backend answers a single byte `'S'` (start TLS) or
  `'N'` (plaintext) before any StartupMessage — see `backend_startup.c:582`
  where `NEGOTIATE_SSL_CODE` sets `SSLok = 'S'`/`'N'` `[verified-by-code]`.
  There is no separate SSL port. `[from-docs]`
- **Four files, all default-relative to `$PGDATA`:** `ssl_cert_file`
  (`server.crt`, sent to client), `ssl_key_file` (`server.key`, proves
  ownership — loaded via `SSL_CTX_use_PrivateKey_file`, `be-secure-openssl.c:712`
  `[verified-by-code]`), `ssl_ca_file` (trusted CAs for *client*-cert checking),
  and `ssl_crl_file`/`ssl_crl_dir` (revocation). The cert chain is loaded by
  `SSL_CTX_use_certificate_chain_file`, `be-secure-openssl.c:691`
  `[verified-by-code]`. `[from-docs]`
- **`server.key` permission rule is enforced, not advisory:** must be `0600`
  (owner-only) *or* `0640` **only if owned by root/a system cert manager** and PG
  runs as a group member; a group-readable key owned by the DB user is rejected.
  If the data dir itself is group-readable, keys must live *outside* `$PGDATA`.
  Windows does not support passphrase-protected keys. `[from-docs]`
- **`clientcert` in a `hostssl` line has two strengths:** `verify-ca` (cert
  merely signed by a trusted CA) vs `verify-full` (CA *and* the cert CN must
  match the DB username / ident map). The `cert` auth *method* always implies
  full chain validation. Without `clientcert`, a client cert is verified only if
  the client volunteers one. `[from-docs]`
- **`NULL-SHA`/`NULL-MD5` ciphers are a footgun:** they authenticate but do NOT
  encrypt, so an `ssl_ciphers` list that admits them gives a false sense of a
  protected channel. `[from-docs]`
- **Passphrase reload without restart** needs
  `ssl_passphrase_command_supports_reload = on`; otherwise a passphrase-protected
  key blocks `SIGHUP` config reload (the prompt can't be answered
  non-interactively). `[from-docs]`
- **OpenSSL system config (`openssl.cnf`, located via `openssl version -d`, or
  `OPENSSL_CONF`) is read at server start and reload** — but on Windows each new
  backend re-reads it per connection (fork-vs-exec difference). `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/libpq-backend.md]] — `be-secure.c` `secure_open_server`
  (`be-secure.c:116`) dispatches to `be_tls_open_server`.
- [[knowledge/docs-distilled/auth-cert.md]] — the `cert` auth method that builds
  on client-cert verification.
- [[knowledge/docs-distilled/protocol-flow.md]] — where the `SSLRequest`
  negotiation sits in the connection handshake.
- [[knowledge/docs-distilled/runtime-config-connection.md]] — the `ssl_*` GUC
  reference (min-protocol, ciphers, ECDH curve, DH params).
