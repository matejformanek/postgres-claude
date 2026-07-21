---
source_url: https://www.postgresql.org/docs/current/libpq-ssl.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.19 — SSL Support (sslmode threat ladder, verify-ca vs verify-full, client cert files, both-ends rule)"
maps_to_skill: wire-protocol
---

# libpq §34.19 — SSL Support

The client-side TLS story. The core mental model is a threat ladder:
`sslmode` buys you (nothing → encryption → CA trust → host identity) in four
steps, and the default stops one rung short of MITM protection.

## Non-obvious claims

- **The default `sslmode` is `prefer` — encryption if offered, but no MITM
  protection.** The ladder: `disable` (none), `allow` (encrypt only if server
  insists), `prefer` (default; encrypt if available), `require` (encrypted,
  trust routing), `verify-ca` (validate cert chain to a root CA), `verify-full`
  (chain **and** hostname). Encryption alone stops eavesdropping; only the
  `verify-*` levels stop an active man-in-the-middle. [from-docs]
- **`require` ≠ any certificate verification — except a quirky fallback.**
  `require` "provides no certificate verification"; but "for backward
  compatibility, if a root CA file exists, `require` behaves like `verify-ca`."
  So dropping a `root.crt` in place silently upgrades a `require` connection.
  [from-docs]
- **`verify-ca` vs `verify-full` is exactly the hostname check.** `verify-ca`
  validates the chain to `~/.postgresql/root.crt` but "does NOT verify the server
  hostname matches the certificate name" — so a server "registered by somebody
  else with the CA" passes. `verify-full` adds SAN/CN hostname matching:
  "I want to be sure that I connect to a server I trust, and that it's the one I
  specify." [from-docs]
- **Wildcard cert matching is one label deep.** In `verify-full`, `*` "matches
  all characters *except* dot (`.`)", so `*.example.com` does not match
  `a.b.example.com`. IP-address connections match `iPAddress` SANs, falling back
  to `dNSName` SANs / CN. [from-docs]
- **Default client credential files live in `~/.postgresql/`**:
  `postgresql.crt` (client cert sent to server), `postgresql.key` (private key —
  Unix perms must be `0600`, or `0640` for a root-owned key), `root.crt` (trusted
  CAs, verifies the *server*), `root.crl` (revocation list). Windows uses
  `%APPDATA%\postgresql\` with no permission check. Override each via
  `sslcert`/`sslkey`/`sslrootcert`/`sslcrl`(+`sslcrldir`) or their `PGSSL*`
  env vars. Format is PEM or DER; "the first certificate in `postgresql.crt` must
  be the client certificate." [from-docs]
- **SSL must be configured on *both* ends before connect, or you leak.** "For a
  connection to be known SSL-secured, SSL usage must be configured on both the
  client and the server before the connection is made. If it is only configured
  on the server, the client may end up sending sensitive information (e.g.,
  passwords) before it knows that the server requires high security." This is the
  argument for `require`+ over `prefer`. [from-docs]
- **Encrypted private keys are supported** (e.g. AES-128) — libpq will prompt or
  read the passphrase; a key with too-loose Unix permissions is rejected outright.
  [from-docs]
- **[unverified]** `sslnegotiation` (direct vs postgres TLS, PG17+) and
  `sslsni`/`channel_binding` (SCRAM binding) are documented on adjacent
  sub-pages; the fetched §34.19 body did not carry their prose, so they are left
  for a follow-up leaf (`libpq-connect` params page covers the option definitions).

## Links into corpus

- Runtime SSL introspection (was SSL used, which cipher):
  [[knowledge/docs-distilled/libpq-status.md]] (PQsslInUse / PQsslAttribute).
- SCRAM auth + channel binding over the encrypted channel: `wire-protocol` skill,
  [[knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md]].
- Connection option definitions (sslmode, sslcert, …):
  [[knowledge/docs-distilled/libpq-connect.md]].
- OpenSSL init ordering / thread locking: [[knowledge/docs-distilled/libpq-threading.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-secure-common.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-secure.c.md]].
