---
source_url: https://www.postgresql.org/docs/current/ddl-priv.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§5.7 Privileges"
maps_to_skills: [row-level-security, catalog-conventions]
maps_to_corpus: [knowledge/docs-distilled/role-attributes.md, knowledge/docs-distilled/predefined-roles.md, knowledge/subsystems/access-heap.md]
---

# Privileges — the aclitem/ACL model (§5.7)

How object access is represented on disk (`aclitem[]` arrays) and checked. The
privilege bits + AclItem struct live in `src/include/utils/acl.h`; the check
logic in `src/backend/utils/adt/acl.c` + `catalog/aclchk.c`.

## Non-obvious claims

- **Fifteen privilege types**, keyword-for-keyword: `SELECT INSERT UPDATE DELETE
  TRUNCATE REFERENCES TRIGGER CREATE CONNECT TEMPORARY EXECUTE USAGE SET
  ALTER SYSTEM MAINTAIN`. `MAINTAIN` (VACUUM/ANALYZE/CLUSTER/REINDEX/REFRESH/LOCK)
  is the newest. `ACL_MAINTAIN_CHR = 'm'` (`acl.h:151`); the relation bundle
  `ACL_ALL_RIGHTS_RELATION` enumerates the full set at `acl.h:160`
  `[verified-by-code]`. `[from-docs]`
- **Ownership is not a privilege and can't be granted.** The right to
  DROP/ALTER is inherent in being owner; owners are *always treated as holding
  every grant option*, so they can re-grant even privileges they explicitly
  revoked from themselves. `[from-docs]`
- **ACLs are `aclitem` arrays with a compact text form**
  `grantee=privs[*].../grantor` — empty grantee = `PUBLIC`, `*` suffix = WITH
  GRANT OPTION. Each entry is an `AclItem { ai_grantee, ai_privs, ai_grantor }`
  (`acl.h:54`, `:56-57`) `[verified-by-code]`; privilege abbreviations are the
  `ACL_*_CHR` chars (`SELECT` = `'r'`, `acl.h:138`) `[verified-by-code]`.
  Example: `calvin=r*w/hobbes` = SELECT-with-grant + UPDATE, both from hobbes.
  `[from-docs]`
- **A NULL acl column ≠ an empty ACL.** NULL means "default privileges apply"
  (owner-all, plus PUBLIC's built-in defaults: `CONNECT`+`TEMPORARY` on DBs,
  `EXECUTE` on functions, `USAGE` on languages/types). The *first* GRANT/REVOKE
  instantiates the defaults explicitly; only then does `(none)` (non-null but
  empty) become visible. This is why `\dp` shows blank vs `(none)`. `[from-docs]`
- **Grant-option revoke cascades.** Revoking a grant option from X transitively
  strips the privilege from everyone who received it through X's grant chain.
  `[from-docs]`
- **`ALTER DEFAULT PRIVILEGES`** rewrites what *future* objects get at creation
  (per creating-role, per schema) — it does not touch existing objects.
  `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/role-attributes.md]] — SUPERUSER bypasses all these
  checks; BYPASSRLS/etc. are role flags, not ACL bits.
- [[knowledge/docs-distilled/predefined-roles.md]] — capability roles that grant
  bundles of these privileges without SUPERUSER.
- [[knowledge/subsystems/access-heap.md]] — where the per-relation ACL column
  (`pg_class.relacl`) is read during permission checks.
