---
source_url: https://www.postgresql.org/docs/current/role-attributes.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§22.2 Role Attributes"
maps_to_skills: [row-level-security, catalog-conventions, physical-replication]
maps_to_corpus: [knowledge/docs-distilled/role-membership.md, knowledge/docs-distilled/ddl-priv.md, knowledge/docs-distilled/predefined-roles.md]
---

# Role attributes — the pg_authid flag bits (§22.2)

The per-role capability flags that live as boolean columns in `pg_authid`
(`src/include/catalog/pg_authid.h`), distinct from object ACLs and NOT
inheritable through membership.

## Non-obvious claims

- **Six attributes are boolean columns in `pg_authid`**, verifiable one-to-one
  at `pg_authid.h:37-43` `[verified-by-code]`: `rolsuper` (SUPERUSER — commented
  "read this field via `superuser()` only!"), `rolcreaterole` (CREATEROLE),
  `rolcreatedb` (CREATEDB), `rolcanlogin` (LOGIN), `rolreplication`
  (REPLICATION), `rolbypassrls` (BYPASSRLS). CONNECTION LIMIT / PASSWORD /
  VALID UNTIL are separate columns, not capability bits. `[from-docs]`
- **SUPERUSER bypasses *every* permission check except LOGIN.** That single
  exception is why a superuser role still needs `LOGIN` (or a `SET ROLE`) to
  actually connect. Only a superuser can create another superuser. `[from-docs]`
- **LOGIN is the only line between a "user" and a "group".** `CREATE USER` sets
  it by default; `CREATE ROLE` does not — but internally they are the same
  `pg_authid` row, so the group/user split is pure convention. `[from-docs]`
- **CREATEROLE is powerful and historically escalation-prone.** A CREATEROLE
  role auto-grants itself `ADMIN TRUE, SET FALSE, INHERIT FALSE` on roles it
  creates; it can then re-grant those roles back to itself *with* INHERIT/SET to
  regain their privileges. The docs call this "a safeguard against accidents,
  not a security feature." CREATEROLE explicitly *cannot* create/alter SUPERUSER
  roles, create REPLICATION roles, or grant REPLICATION/BYPASSRLS. `[from-docs]`
- **BYPASSRLS is not the same as SUPERUSER-skips-RLS.** It's a dedicated flag so
  you can hand out RLS-exemption without full superuser; CREATEROLE cannot grant
  it (closes an escalation path). `[from-docs]` (See `row-level-security` skill.)
- **REPLICATION requires LOGIN** and lets the role open a replication connection
  (walsender) — the attribute a physical/logical standby's connection role
  needs. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/role-membership.md]] — why these attributes are
  NOT inherited via membership even under INHERIT TRUE.
- [[knowledge/docs-distilled/ddl-priv.md]] — the object-ACL model these
  role-level flags sit above.
- [[knowledge/docs-distilled/predefined-roles.md]] — the modern alternative to
  handing out these raw attributes.
