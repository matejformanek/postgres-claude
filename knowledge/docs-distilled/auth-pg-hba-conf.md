---
source_url: https://www.postgresql.org/docs/current/auth-pg-hba-conf.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§21.1 The pg_hba.conf File (Client Authentication)"
maps_to_skills: [error-handling, extension-development]
maps_to_corpus: [knowledge/files/src/backend/libpq/hba.c.md, knowledge/subsystems/libpq-backend.md, knowledge/docs-distilled/sasl-authentication.md]
---

# pg_hba.conf — host-based authentication records (§21.1)

The per-connection access-control file. Read at postmaster start and on SIGHUP;
each record is one line `conn-type  database  user  [address]  auth-method [options]`.

## Non-obvious claims

- **First-match-wins, no fall-through.** "The first record with a matching
  connection type, client address, requested database, and user name is used…
  There is no 'fall-through' or 'backup': if one record is chosen and the
  authentication fails, subsequent records are not considered." `[from-docs]`
  Verified in code: `check_hba()` walks `parsed_hba_lines` with `foreach`, and
  on the first line that matches conntype+address+db+user it does
  `port->hba = hba; return;` immediately — no continue past a match.
  `[verified-by-code]` `source/src/backend/libpq/hba.c:2347` (foreach loop),
  `:2430` (`port->hba = hba; return;`). Record **order is significant**.
- **Six connection types.** `local` (unix socket only), `host` (TCP, SSL or
  not), `hostssl` (TCP + mandatory SSL), `hostnossl` (TCP, no SSL),
  `hostgssenc` (TCP + mandatory GSSAPI encryption), `hostnogssenc`. Hostname
  and CIDR address matching does **not** apply to `local` records. `[from-docs]`
- **Database-field keywords lose meaning when quoted.** `all` (any db);
  `sameuser` (db name == role name); `samerole` (role is member of a role named
  like the db — superusers match only if *explicitly* members); `replication`
  matches **physical** replication connections only, **not logical**. Quoting
  (`"replication"`) forces a literal database-name match. `[from-docs]`
- **User field:** `all`; `+rolename` = any role directly-or-indirectly a member
  of `rolename` (superusers count only if explicit members); leading `/` = regex;
  leading `@` = include a file of names; comma-separated lists mix all forms.
  `[from-docs]`
- **Address field:** CIDR (`10.6.0.0/16`, `::1/128`, `0.0.0.0/0`), or a separate
  netmask column, or keywords `all` / `samehost` (server's own IPs) / `samenet`
  (server's directly-connected subnets). **Hostname matching does reverse-then-
  forward DNS** and is case-insensitive; a leading-dot suffix like `.example.com`
  matches sub-domains but not the bare domain. `[from-docs]`
- **Two cross-method options usable on any `hostssl` record:**
  `clientcert=verify-ca` (require a valid client cert) and
  `clientcert=verify-full` (cert required *and* its CN/DN must equal the db user
  or its mapped name). `clientname=CN` (default) vs `clientname=DN` (match the
  whole RFC-2253 Distinguished Name). `[from-docs]`
- **Include directives:** `include`, `include_if_exists` (log-and-skip if
  absent), `include_dir` (all `[!.]*.conf` in C-locale order — digits before
  letters, upper before lower). `@file` constructs allow nesting; relative paths
  resolve against the referencing file's directory. `[from-docs]`
- **Diagnostics without a reload:** the `pg_hba_file_rules` system view shows
  each parsed line with a non-null `error` column on bad lines — pre-test edits
  before SIGHUP. `[from-docs]`
- **Reload semantics:** SIGHUP (`pg_ctl reload` / `pg_reload_conf()` /
  `kill -HUP`) on every platform except Windows, where new connections pick up
  changes immediately. `[from-docs]` The dispatch that reads the chosen method
  is `hba_getauthmethod()` `[verified-by-code]`
  `source/src/backend/libpq/hba.c:2935`.

## Links into corpus

- [[knowledge/files/src/backend/libpq/hba.c.md]] — the parser + `check_hba()`
  matcher this page describes.
- [[knowledge/subsystems/libpq-backend.md]] — where hba lookup sits in the
  backend connection-establishment path.
- [[knowledge/docs-distilled/sasl-authentication.md]] — the SCRAM exchange a
  `scram-sha-256` record triggers.
- [[knowledge/docs-distilled/auth-username-maps.md]] — the `map=` option target.
</content>
</invoke>
