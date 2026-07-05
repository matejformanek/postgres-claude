---
source_url: https://www.postgresql.org/docs/current/auth-peer.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.9 Peer Authentication"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/auth.c.md, knowledge/docs-distilled/auth-ident.md, knowledge/docs-distilled/auth-username-maps.md]
---

# Peer authentication (§21.9)

Kernel-vouched OS-user identity for local (Unix-domain socket) connections.

## Non-obvious claims

- **Local sockets only.** "This method is only supported on local connections" —
  it is meaningless for TCP records. `[from-docs]`
- **Identity comes from the kernel, not the client.** The client's OS user name
  is obtained via `getpeereid()` / the `SO_PEERCRED` socket option (or the
  platform equivalent), so — unlike ident — the *client cannot forge it*. That
  name is then used as the allowed database user. `[from-docs]`
- **Platform-limited:** Linux, most BSDs including macOS, and Solaris.
  **Not Windows** (no such socket-credential mechanism). `[from-docs]`
- **`map=` decouples OS-user from role.** With a user-name map, OS user `alice`
  can connect as role `app_ro`, etc.; without a map the two names must be
  identical. `[from-docs]`
- **Peer is the secure local twin of ident.** Ident asks a network service on
  the client host (forgeable); peer asks the local kernel (authoritative) — which
  is exactly why an hba `ident` line on a *local* connection silently runs peer
  instead. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/libpq/auth.c.md]] — `auth_peer()` /
  `ident_inet` dispatch.
- [[knowledge/docs-distilled/auth-ident.md]] — the forgeable network cousin.
- [[knowledge/docs-distilled/auth-username-maps.md]] — `map=` target.
</content>
