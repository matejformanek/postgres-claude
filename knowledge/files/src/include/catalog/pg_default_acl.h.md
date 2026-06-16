# pg_default_acl.h

- **Source path:** `source/src/include/catalog/pg_default_acl.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Default ACLs of new objects — backs `ALTER DEFAULT PRIVILEGES`. Each row says: for objects of type X created by role Y in namespace Z (or all namespaces), apply this aclitem[] to the new object's permissions.

## Catalog definition

- `CATALOG(pg_default_acl, 826, DefaultAclRelationId)` — per-DB; no shared/bootstrap flags. [verified-by-code] `pg_default_acl.h:32`
- `FormData_pg_default_acl` typedef; pointer alias `Form_pg_default_acl`. [verified-by-code] `pg_default_acl.h:45,54`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| defaclrole | Oid | BKI_LOOKUP | `pg_authid` (owner of the ACL) |
| defaclnamespace | Oid | BKI_LOOKUP_OPT | `pg_namespace` (0 = all namespaces) |
| defaclobjtype | char | — | — (see DEFACLOBJ_* below) |
| defaclacl | aclitem[1] (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_default_acl, 4143, 4144)`. [verified-by-code] `pg_default_acl.h:56`
- `DECLARE_UNIQUE_INDEX(pg_default_acl_role_nsp_obj_index, 827, ...)` on (defaclrole, defaclnamespace, defaclobjtype). [verified-by-code] `pg_default_acl.h:58`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_default_acl_oid_index, 828, ...)`. [verified-by-code] `pg_default_acl.h:59`
- `MAKE_SYSCACHE(DEFACLROLENSPOBJ, ...)`. [verified-by-code] `pg_default_acl.h:61`
- `DEFACLOBJ_*` char constants (under `#ifdef EXPOSE_TO_CLIENT_CODE`), used in `defaclobjtype`. **These are on-disk values.** [verified-by-code] `pg_default_acl.h:63-77`
  - `DEFACLOBJ_RELATION 'r'` (table/view), `DEFACLOBJ_SEQUENCE 'S'`, `DEFACLOBJ_FUNCTION 'f'`, `DEFACLOBJ_TYPE 'T'`, `DEFACLOBJ_NAMESPACE 'n'`, `DEFACLOBJ_LARGEOBJECT 'L'`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_init_privs.h` (extension-installed initial privs, separate concept)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: DEFACLOBJ_* chars are on-disk, header doesn't say so]** `pg_default_acl.h:65-77` — comment says "These codes are used in the defaclobjtype column" but doesn't flag that they are persisted on disk and a renumbering breaks pg_upgrade. Compare `dependency.h`'s explicit on-disk warning for `DependencyType`. Severity `nit`, type `doc-drift`.

## Tally

`[verified-by-code]=10 [inferred]=1`
