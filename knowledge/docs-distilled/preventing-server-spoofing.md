---
source_url: https://www.postgresql.org/docs/current/preventing-server-spoofing.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§19.6 Preventing Server Spoofing"
maps_to_skills: [error-handling, debugging]
maps_to_corpus: [knowledge/docs-distilled/auth-trust.md, knowledge/docs-distilled/auth-password.md, knowledge/docs-distilled/runtime-config-connection.md]
---

# Preventing server spoofing (§19.6)

The threat is a *local* impostor server started while the real one is down —
it can't read `PGDATA` (filesystem perms protect it) but it *can* harvest
passwords and queries from clients that connect to it.

## Non-obvious claims

- **The window is "server down".** "When the server is down, it is possible for a
  local user to spoof the normal server by starting their own server. The spoof
  server could read passwords and queries sent by clients, but could not return
  any data because the `PGDATA` directory would still be secure." `[from-docs]`
- **Local-socket defense = a write-protected socket directory.** Point
  `unix_socket_directories` at a directory writable only by the trusted PG user
  (i.e. *not* world-writable `/tmp`), so nobody else can drop a fake
  `.s.PGSQL.5432` socket. Optionally symlink `/tmp/.s.PGSQL.5432` to the real one
  for legacy clients (and protect it from tmp-cleaners). `[from-docs]`
- **Client-side local defense:** libpq `requirepeer=<owner>` makes the client
  demand the socket's server process be owned by the expected user — the mirror
  image of server-side peer auth. `[from-docs]`
- **TCP defense = the client must verify the server, not just encrypt.** SSL with
  `sslmode=verify-ca`/`verify-full` + a trusted root cert (or `sslrootcert=system`,
  which forces `verify-full`) defeats a MITM/impostor; or GSSAPI with server
  configured `hostgssenc` + client `gssencmode=require`. Encryption without
  server-identity verification does *not* stop spoofing. `[from-docs]`
- **SCRAM over plaintext TCP is spoofable.** libpq's SCRAM can't protect the
  whole exchange, so a captured handshake enables offline analysis; require SSL
  **and** `channel_binding=require` to bind the SCRAM exchange to the TLS channel.
  `[from-docs]` A subtle point: SCRAM's mutual-auth guarantee is only as strong
  as the channel binding.

## Links into corpus

- [[knowledge/docs-distilled/auth-password.md]] — why SCRAM still needs
  channel binding against a spoofed server.
- [[knowledge/docs-distilled/auth-trust.md]] — the socket-permission model this
  page hardens.
- [[knowledge/docs-distilled/runtime-config-connection.md]] —
  `unix_socket_directories` / `listen_addresses` knobs behind these defenses.
</content>
