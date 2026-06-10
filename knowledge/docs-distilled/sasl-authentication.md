---
source_url: https://www.postgresql.org/docs/current/sasl-authentication.html
fetched_at: 2026-06-10T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# SASL Authentication (protocol ch. 54)

How PostgreSQL layers SASL (RFC 4422) over the FE/BE auth handshake. The two
password mechanisms in tree are SCRAM-SHA-256 / SCRAM-SHA-256-PLUS; PG18 also
ships OAUTHBEARER. Directly relevant to the A11 cleartext-password and D
data-leak threads — this is the wire-level contract those threats sit under.

## Non-obvious claims

- **Four-message envelope, mechanism-agnostic.** Server →
  `AuthenticationSASL` (lists mechanisms in *server* preference order); client →
  `SASLInitialResponse` (chosen mechanism + optional initial client response);
  then 1+ rounds of server `AuthenticationSASLContinue` ↔ client `SASLResponse`;
  finally optional `AuthenticationSASLFinal` immediately followed by
  `AuthenticationOk`. `ErrorResponse` may cut in at any stage. [from-docs]
- **SCRAM-SHA-256-PLUS is only advertised when the server was built with SSL.**
  Without SSL support only plain `SCRAM-SHA-256` is offered. The client picks one
  and names it inside `SASLInitialResponse`. [from-docs]
- **Channel binding type is `tls-server-end-point`.** The "-PLUS" variant mixes
  the *signature of the server's TLS certificate* into the transmitted hash, so a
  MITM that merely replays the real cert can't prove key ownership → SSL fails.
  Plain SCRAM's server-random defeats replay but **not** a pass-through fake
  server. [from-docs]
- **🔑 The username in SCRAM `client-first-message` is IGNORED.** The server uses
  the username already supplied in the startup packet. A mismatch is silently
  dropped, not an error — worth knowing for any auth-path audit. [from-docs]
- **SASLprep is best-effort, not mandatory.** Passwords are processed with
  SASLprep treating bytes as UTF-8 *even on non-UTF-8 servers*; but if the byte
  sequence is invalid UTF-8 or hits a SASLprep-prohibited sequence, PG falls back
  to the **raw** password rather than rejecting it. So two clients can disagree on
  normalization and still both authenticate. [from-docs]
- **OAUTHBEARER (RFC 7628) has no "-PLUS" / no channel binding** and sends no
  `AuthenticationSASLFinal` on success (server consumes no client-final data).
  The server only recognizes the `auth` key (the bearer token) in the GS2-framed
  initial response. [from-docs]
- **OAUTHBEARER discovery is a deliberate two-connection dance.** A tokenless
  client sends an empty `auth`; the server replies `AuthenticationSASLContinue`
  with an *error status + well-known URI + scopes*, the client kicks an empty
  `SASLResponse` (single `0x01` byte), the server fails the first exchange with
  `ErrorResponse`, the client runs the OAuth flow out-of-band, then *reconnects*
  with a populated `auth`. The first connection is throwaway. [from-docs]

## Links into corpus

- Companion to `knowledge/docs-distilled/protocol-flow.md` (where SASL slots into
  the startup `AuthenticationRequest` sequence) and
  `knowledge/docs-distilled/protocol-message-formats.md` (byte layout of the
  `AuthenticationSASL*` / `SASLInitialResponse` / `SASLResponse` messages).
- Threat-adjacent: A11 cleartext-password vector tags in
  `knowledge/issues/include-*.md` — SCRAM means the verifier (not the password)
  lives in `pg_authid.rolpassword`; this page is the matching wire story.
- Code: `source/src/backend/libpq/auth-scram.c` (server SCRAM state machine),
  `source/src/backend/libpq/auth-sasl.c` (the generic `CheckSASLAuth` loop),
  `source/src/common/scram-common.c`. [unverified — file paths not line-pinned
  this run]
