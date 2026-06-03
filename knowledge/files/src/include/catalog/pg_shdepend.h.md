# pg_shdepend.h

- **Source path:** `source/src/include/catalog/pg_shdepend.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Cross-database dependency edges, primarily tracking dependencies on shared objects (roles, tablespaces, databases). Header comment: "Currently, only dependencies on roles are explicitly stored in pg_shdepend." Loaded during initdb; no `.dat` file. [from-comment] `pg_shdepend.h:13-14`

## Catalog definition

- `CATALOG(pg_shdepend, 1214, SharedDependRelationId) BKI_SHARED_RELATION` — **shared catalog** (lives in `global/`). [verified-by-code] `pg_shdepend.h:40`
- `FormData_pg_shdepend` typedef; pointer alias `Form_pg_shdepend`. [verified-by-code] `pg_shdepend.h:68,77`
- No `oid` column; identified by composite key.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| dbid | Oid | BKI_LOOKUP_OPT | `pg_database` (0 = shared object) |
| classid | Oid | BKI_LOOKUP | `pg_class` |
| objid | Oid | — | — |
| objsubid | int32 | — | — (column number, or 0) |
| refclassid | Oid | BKI_LOOKUP | `pg_class` |
| refobjid | Oid | — | — (always a shared object) |
| deptype | char | — | — (see `SharedDependencyType` in `dependency.h`) |

Note: no `refobjsubid` — comment says "We don't bother with a sub-object ID either" for the referenced (always shared) object. [from-comment] `pg_shdepend.h:54-57`

## Key declarations beyond FormData

- `DECLARE_INDEX(pg_shdepend_depender_index, 1232, ...)` on (dbid, classid, objid, objsubid). [verified-by-code] `pg_shdepend.h:79`
- `DECLARE_INDEX(pg_shdepend_reference_index, 1233, ...)` on (refclassid, refobjid). [verified-by-code] `pg_shdepend.h:80`
- `deptype` semantics: `SharedDependencyType` in `dependency.h` — codes 'o' OWNER, 'a' ACL, 'i' INITACL, 'r' POLICY, 't' TABLESPACE. **On-disk values.** [from-comment]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `knowledge/files/src/include/catalog/dependency.h.md` (SharedDependencyType char codes)
- Related: `knowledge/files/src/include/catalog/pg_depend.h.md` (per-DB sibling)

## Tally

`[verified-by-code]=6 [from-comment]=3`
