# pg_tablespace.h

- **Source path:** `source/src/include/catalog/pg_tablespace.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'tablespace' system catalog (pg_tablespace)." Cluster-wide list of tablespaces. `[from-comment]`

## Catalog definition

- `CATALOG(pg_tablespace,1213,TableSpaceRelationId) BKI_SHARED_RELATION` `[verified-by-code]`
- `FormData_pg_tablespace` / `Form_pg_tablespace`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| spcname | NameData | — | — |
| spcowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| spcacl | aclitem[1] | — (varlena) | — |
| spcoptions | text[1] | — (varlena) | — |

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST_WITH_MACRO(pg_tablespace, 4185, 4186, PgTablespaceToastTable, PgTablespaceToastIndex)`; PK `pg_tablespace_oid_index`, unique `pg_tablespace_spcname_index`. Syscache: `TABLESPACEOID`. `[verified-by-code]`
- Function prototype: `get_tablespace_location(Oid tablespaceOid)`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_database.h.md` (dattablespace)
- `knowledge/files/src/include/catalog/pg_class.h.md` (reltablespace)

## Tally

`[verified-by-code]=3 [from-comment]=1`
