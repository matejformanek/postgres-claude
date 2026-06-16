# pg_auth_members.h

- **Source path:** `source/src/include/catalog/pg_auth_members.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Authorization identifier membership: edges from members to roles, with grantor + admin/inherit/set flags. The catalog backing `GRANT role TO role` (role membership).

## Catalog definition

- `CATALOG(pg_auth_members, 1261, AuthMemRelationId) BKI_SHARED_RELATION BKI_ROWTYPE_OID(2843, AuthMemRelation_Rowtype_Id) BKI_SCHEMA_MACRO` — **shared catalog**, fixed rowtype OID, Schema_pg_auth_members[] emitted. [verified-by-code] `pg_auth_members.h:32`
- `FormData_pg_auth_members` typedef; pointer alias `Form_pg_auth_members`. [verified-by-code] `pg_auth_members.h:54,63`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — (needed for dependencies) |
| roleid | Oid | BKI_LOOKUP | `pg_authid` |
| member | Oid | BKI_LOOKUP | `pg_authid` |
| grantor | Oid | BKI_DEFAULT(POSTGRES), BKI_LOOKUP | `pg_authid` |
| admin_option | bool | BKI_DEFAULT(f) | — |
| inherit_option | bool | BKI_DEFAULT(t) | — |
| set_option | bool | BKI_DEFAULT(t) | — |

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_auth_members_oid_index, 6303, ...)` on (oid). [verified-by-code] `pg_auth_members.h:65`
- `DECLARE_UNIQUE_INDEX(pg_auth_members_role_member_index, 2694, ...)` on (roleid, member, grantor). [verified-by-code] `pg_auth_members.h:66`
- `DECLARE_UNIQUE_INDEX(pg_auth_members_member_role_index, 2695, ...)` on (member, roleid, grantor). [verified-by-code] `pg_auth_members.h:67`
- `DECLARE_INDEX(pg_auth_members_grantor_index, 6302, ...)` on (grantor). [verified-by-code] `pg_auth_members.h:68`
- `MAKE_SYSCACHE(AUTHMEMROLEMEM, ...)` and `MAKE_SYSCACHE(AUTHMEMMEMROLE, ...)`, both 8 buckets. [verified-by-code] `pg_auth_members.h:70-71`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_authid.h` (roles, also shared)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: grantor identifies the row uniquely with (roleid, member)]** `pg_auth_members.h:66-67` — the uniqueness keys both include `grantor`, meaning the same (roleid, member) pair can appear multiple times with different grantors. This is intentional (PG 16+ behavior) but the header doesn't note that revoking by a different grantor than the original is a SQL-spec edge case. Severity `nit`; semantics live in `aclchk.c`. Flag for the privilege-graph project.

## Tally

`[verified-by-code]=11 [inferred]=1`
