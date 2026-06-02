# pg_foreign_data_wrapper.h

- **Source path:** `source/src/include/catalog/pg_foreign_data_wrapper.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'foreign-data wrapper' system catalog (pg_foreign_data_wrapper)." `[from-comment]` One row per CREATE FOREIGN DATA WRAPPER — names the SQL/MED wrapper plus its handler / validator / connection-string callback functions.

## Catalog definition

- `CATALOG(pg_foreign_data_wrapper,2328,ForeignDataWrapperRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_foreign_data_wrapper.h:31`
- `FormData_pg_foreign_data_wrapper` typedef. Pointer alias: `Form_pg_foreign_data_wrapper`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| fdwname | NameData | — | — |
| fdwowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| fdwhandler | Oid | `BKI_LOOKUP_OPT` | `pg_proc` (0 = no handler) |
| fdwvalidator | Oid | `BKI_LOOKUP_OPT` | `pg_proc` (0 = no validator) |
| fdwconnection | Oid | `BKI_LOOKUP_OPT` | `pg_proc` (0 = no conn-string fn) |
| fdwacl | aclitem[1] | (varlena) | — |
| fdwoptions | text[1] | (varlena) | — |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_foreign_data_wrapper, 4149, 4150)`. `[verified-by-code]`
- Indexes: `pg_foreign_data_wrapper_oid_index` (PK, 112); `pg_foreign_data_wrapper_name_index` (548, unique on fdwname). `[verified-by-code]`
- Syscaches: `FOREIGNDATAWRAPPEROID`, `FOREIGNDATAWRAPPERNAME`. `[verified-by-code]`
- No function prototypes here — runtime API lives in `foreign/foreign.h` and `commands/defrem.h`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_foreign_server.h.md` (servers reference an fdw)
- `knowledge/files/src/include/catalog/pg_foreign_table.h.md`, `pg_user_mapping.h.md` (downstream FDW catalogs)

## Potential issues

- **[ISSUE-callback-signature-drift]** `pg_foreign_data_wrapper.h:36-43` — handler / validator / connection callbacks are looked up by Oid into `pg_proc`. The required C-level prototypes (handler returns `fdw_handler`, validator takes `text[], oid`, connection takes options + returns conninfo) are NOT named in this header — they live in `foreign/fdwapi.h` and per-FDW docs. Any extension hardcoding those signatures must follow `fdwapi.h`; the header gives no breadcrumb. The newer `fdwconnection` field (separating the connection-string callback from the handler) is also undocumented here beyond the inline comment.

## Tally

`[verified-by-code]=7 [from-comment]=1`
