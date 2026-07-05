---
source_url: https://www.postgresql.org/docs/current/auth-username-maps.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.2 User Name Maps (pg_ident.conf)"
maps_to_skills: [error-handling]
maps_to_corpus: [knowledge/files/src/backend/libpq/hba.c.md, knowledge/docs-distilled/auth-pg-hba-conf.md, knowledge/docs-distilled/auth-cert.md]
---

# User name maps — pg_ident.conf (§21.2)

Translate an **external** (OS / Kerberos / certificate) user name into a
PostgreSQL role. Activated per-hba-line via the `map=map-name` option.

## Non-obvious claims

- **Three-field format:** `map-name  system-username  database-username`. A map
  is referenced from `pg_hba.conf` with `map=map-name`, and the option "is
  supported for all authentication methods that receive external user names"
  (peer, ident, gss, sspi, cert, pam, ldap-search+bind, radius, …). `[from-docs]`
- **Not equivalence — permission.** Each entry means "this operating-system
  user *is allowed to* connect as this database user", a one-way grant. The
  connection is allowed "if there is any map entry that pairs" the external name
  with the requested role. `[from-docs]`
- **Regex on the system-username field** when it starts with `/`: the remainder
  is a regex allowing **exactly one** capture group, whose match is substituted
  into the database-username field as `\1` (backslash-one). Example:
  `mymap  /^(.*)@mydomain\.com$  \1`. `[from-docs]`
- **`\1` cannot cross into a regex database-username.** If the *database*-user
  field is itself a regex (leading `/`), "it is not possible to use `\1` within
  it to refer to a capture from the system-username field." `[from-docs]`
- **Anchor your regexes.** A regex matches a *substring* by default; the docs
  advise `^…$` to force a whole-string match of the system user name — an
  un-anchored map is a real misconfiguration footgun. `[from-docs]`
- **Keyword quoting asymmetry.** On the database-username field: `all` (login as
  any existing role) and a leading `+` (login as any role that is a
  direct-or-indirect member of that role) both **lose** their special meaning
  when quoted — but quoting a value **containing `\1` does *not*** disable the
  backreference. `[from-docs]`
- **Diagnostics:** the `pg_ident_file_mappings` system view flags bad lines via
  a non-null `error` column, same pre-test pattern as `pg_hba_file_rules`.
  `[from-docs]`
- **Reload:** read at start-up and on SIGHUP, identical lifecycle to
  `pg_hba.conf`. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/auth-pg-hba-conf.md]] — the `map=` option lives on
  the hba record that dispatches to a map.
- [[knowledge/files/src/backend/libpq/hba.c.md]] — hba.c also parses
  `pg_ident.conf` and applies the map (`check_ident_usermap`).
- [[knowledge/docs-distilled/auth-cert.md]] — cert auth's canonical map use case
  (CN → role).
</content>
