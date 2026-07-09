---
source_url: https://www.postgresql.org/docs/current/role-membership.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§22.3 Role Membership"
maps_to_skills: [catalog-conventions, row-level-security]
maps_to_corpus: [knowledge/docs-distilled/role-attributes.md, knowledge/docs-distilled/predefined-roles.md, knowledge/docs-distilled/ddl-priv.md]
---

# Role membership — INHERIT vs SET ROLE, and the pg_auth_members graph (§22.3)

The role-to-role membership graph in `pg_auth_members`
(`src/include/catalog/pg_auth_members.h`) and the two independent axes — passive
privilege inheritance vs explicit identity switch — that trip people up.

## Non-obvious claims

- **Membership is a row in `pg_auth_members` with three boolean options**,
  verifiable at `pg_auth_members.h`: `roleid` (the group) + `member` + `grantor`
  (`:38`/`:44`), plus `admin_option` (default `f`, `:47`), `inherit_option`
  (default `t`, `:50`), `set_option` (default `t`, `:53`) `[verified-by-code]`.
  So each *grant* of membership carries its own INHERIT/SET/ADMIN flags — the
  same member can inherit one group but not another. `[from-docs]`
- **INHERIT and SET ROLE are orthogonal and map to two different C predicates.**
  `has_privs_of_role()` (`acl.c:5053`) answers "does this role passively hold
  that role's privileges?" — the INHERIT axis. `is_member_of_role()`
  (`acl.c:5048`) answers "may this role `SET ROLE` to it?" — the SET axis.
  `[verified-by-code]` A member with `INHERIT TRUE, SET FALSE` uses the
  privileges automatically but can never assume the identity. `[from-docs]`
- **`SET ROLE` changes object ownership; INHERIT does not.** Objects created
  after `SET ROLE admin` are owned by `admin`, not the login role — whereas
  inherited privileges leave you acting as yourself. `[from-docs]`
- **Role *attributes* are never inherited, full stop.** `LOGIN`, `SUPERUSER`,
  `CREATEDB`, `CREATEROLE` cannot flow through membership even with
  `INHERIT TRUE` — you must actually `SET ROLE` to a role that *has* the
  attribute to use it. This is the single most common membership gotcha.
  `[from-docs]`
- **`INHERIT TRUE` is the PG default for backward compat (pre-8.1),** which
  diverges from the SQL standard (where roles inherit but users don't). Use
  `NOINHERIT` / per-grant `WITH INHERIT FALSE` for standard behavior. `[from-docs]`
- **The graph is a DAG:** circular membership is rejected, and you cannot grant
  membership to `PUBLIC`. `SET ROLE` can walk any unbroken chain of
  `SET TRUE` grants; `RESET ROLE` / `SET ROLE NONE` returns to the login role.
  `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/role-attributes.md]] — the attributes that stay
  un-inherited across this graph.
- [[knowledge/docs-distilled/predefined-roles.md]] — capability roles you join
  via exactly this membership mechanism.
- [[knowledge/docs-distilled/ddl-priv.md]] — object ACLs, which INHERIT *does*
  propagate (unlike attributes).
