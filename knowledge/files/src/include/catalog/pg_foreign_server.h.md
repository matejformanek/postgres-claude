# pg_foreign_server.h

- **Source path:** `source/src/include/catalog/pg_foreign_server.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'foreign server' system catalog (pg_foreign_server)." `[from-comment]` One row per CREATE SERVER — binds a name (with optional `srvtype` / `srvversion`) and FDW-specific options to a wrapper.

## Catalog definition

- `CATALOG(pg_foreign_server,1417,ForeignServerRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_foreign_server.h:30`
- `FormData_pg_foreign_server` typedef. Pointer alias: `Form_pg_foreign_server`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| srvname | NameData | — | — |
| srvowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| srvfdw | Oid | `BKI_LOOKUP` | `pg_foreign_data_wrapper` |
| srvtype | text | (varlena) | — |
| srvversion | text | (varlena) | — |
| srvacl | aclitem[1] | (varlena) | — |
| srvoptions | text[1] | (varlena) | — |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_foreign_server, 4151, 4152)`. `[verified-by-code]`
- Indexes: `pg_foreign_server_oid_index` (PK, 113); `pg_foreign_server_name_index` (549, unique on srvname). `[verified-by-code]`
- Syscaches: `FOREIGNSERVEROID`, `FOREIGNSERVERNAME`. `[verified-by-code]`
- No function prototypes here — runtime API lives in `foreign/foreign.h`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_foreign_data_wrapper.h.md` (parent FDW)
- `knowledge/files/src/include/catalog/pg_foreign_table.h.md` (tables reference a server)
- `knowledge/files/src/include/catalog/pg_user_mapping.h.md` (per-role auth for a server)
- `knowledge/files/src/include/catalog/pg_subscription.h.md` (`subserver` may LOOKUP_OPT here for conninfo-via-server)

## Tally

`[verified-by-code]=6 [from-comment]=1`
