---
source_url: https://www.postgresql.org/docs/current/gssapi-enc.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§19.10 GSSAPI Encryption Support"
maps_to_skills: [wire-protocol]
maps_to_corpus: [knowledge/subsystems/libpq-backend.md, knowledge/docs-distilled/ssl-tcp.md, knowledge/docs-distilled/protocol-replication.md]
---

# GSSAPI encryption support — the Kerberos transport wrap (§19.10)

The second in-transit encryption option, orthogonal to SSL. Implemented in
`src/backend/libpq/be-secure-gssapi.c` (`be_gssapi_write`,
`be-secure-gssapi.c:105` `[verified-by-code]`; the encrypted-send staging buffer
`PqGSSSendBuffer` at `:69` `[verified-by-code]`).

## Non-obvious claims

- **Encryption and authentication are decided by the *same* GSSAPI exchange but
  are not the same decision.** The mechanism always establishes both client and
  server identities per the GSSAPI impl, yet you may still layer a *different* PG
  auth method on top for extra verification — i.e. you can use GSSAPI purely as
  an encrypted transport and authenticate some other way. `[from-docs]`
- **Same TCP port as plaintext and SSL**, selected by a pre-startup
  `GSSENCRequest` (`NEGOTIATE_GSS_CODE = PG_PROTOCOL(1234,5680)`, `pqcomm.h:129`
  `[verified-by-code]`), the GSS twin of the `SSLRequest` byte-negotiation.
  `[from-docs]`
- **Client picks by default → downgrade-attackable.** Left to the client
  (`gssencmode=prefer`), a MITM can strip the request; the server must *require*
  GSSAPI encryption with a `hostgssenc` line in `pg_hba.conf` (and refuse with
  `hostnogssenc`) to close it. `[from-docs]`
- **Zero extra setup beyond GSSAPI *authentication*.** If Kerberos auth already
  works (keytab via `krb_server_keyfile`, principal established), encryption is
  free — no separate certs/keys as SSL needs. This is its main operational
  advantage over TLS in Kerberos shops. `[from-docs]`
- **Packet framing is bounded:** each GSSAPI-wrapped message is length-prefixed
  and capped at `PQ_GSS_MAX_PACKET_SIZE = 16384` bytes including the uint32
  header (`be-secure-gssapi.c:54`, enforced at `:222`/`:358`)
  `[verified-by-code]` — larger payloads are split, so the wrap is a stream
  frame, not a per-query blob.

## Links into corpus

- [[knowledge/subsystems/libpq-backend.md]] — `secure_open_server`
  (`be-secure.c:116`) dispatches to the GSS path just as it does to TLS.
- [[knowledge/docs-distilled/ssl-tcp.md]] — the sibling in-transit option; same
  single-port negotiation shape, different key material.
- [[knowledge/docs-distilled/protocol-replication.md]] — GSSAPI also wraps the
  replication protocol stream.
