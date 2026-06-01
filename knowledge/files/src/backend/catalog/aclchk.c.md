# aclchk.c

- **Source path:** `source/src/backend/catalog/aclchk.c`
- **Lines:** ~5 050
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `utils/adt/acl.c` (the Acl datatype + `aclmask`), `include/utils/acl.h` (AclMode bits), `catalog/pg_init_privs.h`.

## Purpose

"Routines to check access control permissions." Two halves: (1) the GRANT/REVOKE backend (`ExecuteGrantStmt`, `ExecGrant_<Class>`), and (2) the per-object-type ACL check wrappers (`<class>_aclmask`, `<class>_aclcheck`, plus `_ext` and string variants). All sit on top of `aclmask()` in acl.c, adding catalog lookup of the relevant ACL column. [from-comment, aclchk.c:13-36]

## Public surface — GRANT/REVOKE side

- `ExecuteGrantStmt` (395) — parse-tree entry. Builds an `InternalGrant` struct from the GrantStmt and dispatches to `ExecGrantStmt_oids`.
- `ExecGrantStmt_oids` (594) — per-object-type dispatch: ACL_KIND_COLUMN → `ExecGrant_Attribute`, ACL_KIND_LARGEOBJECT → `ExecGrant_Largeobject`, ACL_KIND_PARAMETER → `ExecGrant_Parameter`, otherwise `ExecGrant_common`. Relation case has its own `ExecGrant_Relation` because of column ACLs.
- `objectNamesToOids` (671), `objectsInSchemaToOids` (784), `getRelationsInNamespace` (877) — resolve grant target lists.
- `ExecAlterDefaultPrivilegesStmt` (915), `SetDefaultACLsInSchemas` (1109), `SetDefaultACL` (1151) — ALTER DEFAULT PRIVILEGES backend; populates pg_default_acl.
- `RemoveRoleFromObjectACL` (1426) — used by `DROP OWNED BY` / role cleanup.
- `expand_col_privileges` (1566), `expand_all_col_privileges` (1599) — column-list → per-attnum AclItem expansion.
- `ExecGrant_Attribute` (1645), `ExecGrant_Relation` (1790) — relation/column ACL writers (pg_attribute.attacl + pg_class.relacl).
- `ExecGrant_common` (2133) — generic GRANT/REVOKE for catalogs that have a single ACL column with default privileges from `get_user_default_acl`.
- `ExecGrant_Language_check`, `ExecGrant_Type_check`, `ExecGrant_Largeobject`, `ExecGrant_Parameter` — class-specific validators (PROCEDURAL languages must be trusted; type must not be a domain over a polymorphic; large object must exist; parameter must be GUC).
- `merge_acl_with_grant` (182), `restrict_and_check_grant` (241) — combine current ACL + grant deltas into a new AclItem array, then write back via inplace or normal update.
- `updateAclDependencies` (in pg_shdepend.c, called from here) — keep pg_shdepend in sync with grantees mentioned in the ACL.

## Public surface — ACL check side

The `pg_<class>_aclmask(objid, roleid, mask, how)` family returns the subset of `mask` actually held; `pg_<class>_aclcheck` returns ACLCHECK_OK/NO_PRIV. `_ext` variants set `*is_missing = true` instead of erroring when the object is gone. Examples in this file: `pg_class_aclmask`, `pg_attribute_aclmask`, `pg_database_aclcheck`, `pg_proc_aclcheck`, `pg_language_aclcheck`, `pg_largeobject_aclcheck`, `pg_namespace_aclcheck`, `pg_tablespace_aclcheck`, `pg_type_aclcheck`, `pg_foreign_data_wrapper_aclcheck`, `pg_foreign_server_aclcheck`, `pg_parameter_aclcheck`. All sit on top of `aclmask` and follow the same pattern: SearchSysCache → extract ACL → call aclmask.

## Default ACLs

When `<class>.relacl` (or equivalent) is NULL, the **default ACL** computed by `acldefault(OBJECT_TABLE, owner)` applies (defined in utils/adt/acl.c): owner gets all privileges; PUBLIC gets nothing on tables/sequences/functions but USAGE on languages and types. ALTER DEFAULT PRIVILEGES *overrides* this default per (granter, schema, object-type) — stored in pg_default_acl, fetched at object-create time by `get_user_default_acl`.

## Init privileges (extension members)

When an extension is installed, the privileges of its member objects at install time are snapshotted into pg_init_privs. This lets `ALTER EXTENSION ... UPDATE` and pg_dump correctly emit "extra" GRANTs that the user added on top of the extension defaults. `RemoveRoleFromObjectACL` walks pg_init_privs as well as pg_class/pg_proc/etc. ACLs.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=1`
