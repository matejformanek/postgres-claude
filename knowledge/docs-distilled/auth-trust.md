---
source_url: https://www.postgresql.org/docs/current/auth-trust.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.4 Trust Authentication"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/auth.c.md, knowledge/docs-distilled/auth-pg-hba-conf.md, knowledge/docs-distilled/runtime-config-connection.md]
---

# Trust authentication (§21.4)

No credential at all — the record match *is* the authorization. Correct only
when some *other* layer (OS socket perms, physical network isolation) is the
real gate.

## Non-obvious claims

- **Exact semantic:** "PostgreSQL assumes that anyone who can connect to the
  server is authorized to access the database with whatever database user name
  they specify (even superuser names)." No password check runs; the db/user
  column restrictions on the record still apply, but authentication is bypassed.
  `[from-docs]`
- **`trust` on TCP is almost always wrong.** "It is seldom reasonable to use
  `trust` for any TCP/IP connections other than those from localhost
  (127.0.0.1)" — filesystem permissions do **not** restrict TCP. `[from-docs]`
- **The safe pattern is socket-file permissions, not trust itself.** On a
  Unix-socket record, restrict who can reach the socket via
  `unix_socket_permissions`, `unix_socket_group`, and
  `unix_socket_directories` (§19.3) — then trust is delegating auth to the
  filesystem. But "setting file-system permissions only helps for Unix-socket
  connections. Local TCP/IP connections are not restricted by file-system
  permissions," so you must also drop/replace any `host … 127.0.0.1 … trust`
  line. `[from-docs]`
- **Appropriate uses:** single-user local workstation; a socket already fenced
  by OS permissions. On a multiuser machine it is "usually *not* appropriate by
  itself." `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/auth-pg-hba-conf.md]] — the record whose match
  grants trust access.
- [[knowledge/docs-distilled/runtime-config-connection.md]] —
  `unix_socket_permissions` / `unix_socket_group` / `unix_socket_directories`
  are the real gate behind a safe trust setup.
- [[knowledge/files/src/backend/libpq/auth.c.md]] — `ClientAuthentication()`
  short-circuits to success on `uaTrust`.
</content>
