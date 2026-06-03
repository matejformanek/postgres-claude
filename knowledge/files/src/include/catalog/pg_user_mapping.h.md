# pg_user_mapping.h

- **Source path:** `source/src/include/catalog/pg_user_mapping.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'user mapping' system catalog (pg_user_mapping)." `[from-comment]` One row per CREATE USER MAPPING — binds a local role (or PUBLIC) to a foreign server and stores the connection credentials as FDW options.

## Catalog definition

- `CATALOG(pg_user_mapping,1418,UserMappingRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_user_mapping.h:30`
- `FormData_pg_user_mapping` typedef. Pointer alias: `Form_pg_user_mapping`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| umuser | Oid | `BKI_LOOKUP_OPT` | `pg_authid` (InvalidOid = PUBLIC) |
| umserver | Oid | `BKI_LOOKUP` | `pg_foreign_server` |
| umoptions | text[1] | (varlena) | — |

The inline comment makes `umuser=0` the explicit sentinel for "USER MAPPING FOR PUBLIC". `[from-comment]` `pg_user_mapping.h:34-36`

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_user_mapping, 4173, 4174)`. `[verified-by-code]`
- Indexes: `pg_user_mapping_oid_index` (PK, 174); `pg_user_mapping_user_server_index` (175, unique on (umuser, umserver)). `[verified-by-code]`
- Syscaches: `USERMAPPINGOID`, `USERMAPPINGUSERSERVER`. `[verified-by-code]`
- No function prototypes here.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_foreign_server.h.md` (parent)
- `knowledge/files/src/include/catalog/pg_authid.h` (role side)

## Potential issues

- **[ISSUE-credential-store-in-text-array]** `pg_user_mapping.h:41` — `umoptions text[]` is where postgres_fdw etc. stash `password=...`. The catalog has no special ACL gate beyond `has_column_privilege`-style checks in the FDW; `pg_user_mappings` (the view, not this catalog) is what hides options from non-owners. Anyone reading `pg_user_mapping` directly (e.g. an extension joining catalogs) bypasses that view-level filter. The header gives no such warning.

## Tally

`[verified-by-code]=6 [from-comment]=2`
