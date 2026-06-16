# pg_database.h

- **Source path:** `source/src/include/catalog/pg_database.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'database' system catalog (pg_database)." One row per database in the cluster. Cluster-wide (`BKI_SHARED_RELATION`). `[from-comment]`

## Catalog definition

- `CATALOG(pg_database,1262,DatabaseRelationId) BKI_SHARED_RELATION BKI_ROWTYPE_OID(1248,DatabaseRelation_Rowtype_Id) BKI_SCHEMA_MACRO` `[verified-by-code]`
- `FormData_pg_database` / `Form_pg_database`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| datname | NameData | — | — |
| datdba | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| encoding | int32 | — | — |
| datlocprovider | char | — | — (matches pg_collation.collprovider) |
| datistemplate | bool | — | — |
| datallowconn | bool | — | — |
| dathasloginevt | bool | — | — |
| datconnlimit | int32 | — | — (see DATCONNLIMIT_*) |
| datfrozenxid | TransactionId | — | — |
| datminmxid | TransactionId | — | — |
| dattablespace | Oid | — | `pg_tablespace` |
| datcollate | text | `BKI_FORCE_NOT_NULL` (varlena) | — (LC_COLLATE) |
| datctype | text | `BKI_FORCE_NOT_NULL` (varlena) | — (LC_CTYPE) |
| datlocale | text | — (varlena) | — (ICU locale ID) |
| daticurules | text | — (varlena) | — (ICU rules) |
| datcollversion | text | `BKI_DEFAULT(_null_)` (varlena) | — |
| datacl | aclitem[1] | — (varlena) | — |

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST_WITH_MACRO(pg_database, 4177, 4178, PgDatabaseToastTable, PgDatabaseToastIndex)`; unique `pg_database_datname_index`, PK `pg_database_oid_index`. Syscache: `DATABASEOID`. `[verified-by-code]`
- Fixed OIDs reserved for databases created later in initdb: `DECLARE_OID_DEFINING_MACRO(Template0DbOid, 4)`, `DECLARE_OID_DEFINING_MACRO(PostgresDbOid, 5)`. (Only template1 is in `pg_database.dat`; template0 and postgres are made later but get pinned OIDs here.) `[from-comment]`
- Special datconnlimit values (NOT in `EXPOSE_TO_CLIENT_CODE` block — backend only): `DATCONNLIMIT_UNLIMITED = -1`, `DATCONNLIMIT_INVALID_DB = -2`. Header comments that overloading -2 for "in the middle of being dropped" "isn't particularly clean, but is backpatchable." `[verified-by-code]`
- Function prototypes: `get_database_oid`, `database_is_invalid_form`, `database_is_invalid_oid`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_tablespace.h.md` (dattablespace)
- `knowledge/files/src/include/catalog/pg_authid.h.md` (datdba)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-stale-todo: DATCONNLIMIT_INVALID_DB sentinel overload]** `pg_database.h:123-128` — comment explicitly acknowledges this is "not particularly clean" but was the backpatchable choice. A separate `datisinvalid` bool would be cleaner; flag for triage in case a major-version cycle wants to clean it up.

## Tally

`[verified-by-code]=4 [from-comment]=2`
