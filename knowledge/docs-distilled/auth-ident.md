---
source_url: https://www.postgresql.org/docs/current/auth-ident.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.8 Ident Authentication"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/auth.c.md, knowledge/docs-distilled/auth-peer.md]
---

# Ident authentication (§21.8)

Network-service OS-user identity for TCP connections — trust-the-client-host by
design; deprecated for anything but tightly-controlled networks.

## Non-obvious claims

- **TCP only, via an ident server on the *client* host, port 113 (RFC 1413).**
  PG asks the client's ident daemon "what user owns the connection out of your
  port X to my port Y?" and uses the answer as the database user name.
  `[from-docs]`
- **Silent fallback to peer for local records.** "When `ident` is specified for
  a local (non-TCP/IP) connection, peer authentication … will be used instead."
  A non-obvious substitution — a local `ident` line is really a `peer` line.
  `[from-docs]`
- **Trust model is the whole caveat.** The ident server is under the *client's*
  control; a compromised client can run any responder on port 113 and return any
  name. RFC 1413 itself says it "is not intended as an authorization or access
  control protocol." So ident is "only appropriate for closed networks where each
  client machine is under tight control." `[from-docs]`
- **Only option is `map=`.** Same user-name-map mechanism as peer/gss/cert.
  `[from-docs]`
- **Never use ident encryption.** Some ident servers can encrypt the returned
  name with a client-only key; PG cannot decrypt it and the docs explicitly warn
  it must not be used. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/libpq/auth.c.md]] — `ident_inet()` performs the
  RFC-1413 query.
- [[knowledge/docs-distilled/auth-peer.md]] — the local fallback and the secure
  kernel-based alternative.
</content>
