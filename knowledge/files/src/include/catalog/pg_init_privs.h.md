# pg_init_privs.h

- **Source path:** `source/src/include/catalog/pg_init_privs.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Snapshot of "initial privileges" on objects, captured either at initdb time (for system objects) or at `CREATE EXTENSION` time (for extension-owned objects). Used by pg_dump to emit only the *delta* between current ACLs and the initial ones, so dumps don't re-grant what was already granted by initdb/extension. [from-comment] `pg_init_privs.h:18-22`

## Catalog definition

- `CATALOG(pg_init_privs, 3394, InitPrivsRelationId)` — per-DB; no shared/bootstrap. [verified-by-code] `pg_init_privs.h:48`
- `FormData_pg_init_privs` typedef; pointer alias `Form_pg_init_privs`. [verified-by-code] `pg_init_privs.h:59,68`
- Object identity follows the (objoid, classoid, objsubid) convention shared with `pg_description`, `pg_seclabel`. [from-comment] `pg_init_privs.h:6-16`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| objoid | Oid | — | — (OID of the object) |
| classoid | Oid | BKI_LOOKUP | `pg_class` (catalog containing the object) |
| objsubid | int32 | — | — (column number, or 0; nonzero only for attribute privs) |
| privtype | char | — | — (see `InitPrivsType` below) |
| initprivs | aclitem[1] (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_init_privs, 4155, 4156)`. [verified-by-code] `pg_init_privs.h:70`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_init_privs_o_c_o_index, 3395, ...)` on (objoid, classoid, objsubid). [verified-by-code] `pg_init_privs.h:72`
- `typedef enum InitPrivsType { INITPRIVS_INITDB = 'i', INITPRIVS_EXTENSION = 'e' }` — **on-disk values** in `privtype`. Populated by initdb or by `recordExtensionInitPriv()` during `CREATE EXTENSION`. [verified-by-code] `pg_init_privs.h:81-85`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_default_acl.h` (template ACLs for new objects — different mechanism)
- Related: `pg_extension.h` (extension membership)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: InitPrivsType chars are on-disk, header doesn't say so]** `pg_init_privs.h:81-85` — `'i'`/`'e'` are persisted; renaming them silently corrupts dumps. Comment frames them as a runtime differentiation enum but doesn't warn. Severity `nit`, type `doc-drift`.

## Tally

`[verified-by-code]=8 [from-comment]=2`
