# pg_foreign_table.h

- **Source path:** `source/src/include/catalog/pg_foreign_table.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'foreign table' system catalog (pg_foreign_table)." `[from-comment]` Per-foreign-table sidecar of `pg_class` rows whose `relkind='f'`; carries the server binding and FDW-specific options.

## Catalog definition

- `CATALOG(pg_foreign_table,3118,ForeignTableRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_foreign_table.h:30`
- `FormData_pg_foreign_table` typedef. Pointer alias: `Form_pg_foreign_table`. `[verified-by-code]`
- **No `oid` column.** PK is `ftrelid` (the underlying pg_class.oid). `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| ftrelid | Oid | `BKI_LOOKUP` | `pg_class` |
| ftserver | Oid | `BKI_LOOKUP` | `pg_foreign_server` |
| ftoptions | text[1] | (varlena) | — |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_foreign_table, 4153, 4154)`. `[verified-by-code]`
- Index: `pg_foreign_table_relid_index` (PK, 3119, unique on ftrelid). `[verified-by-code]`
- Syscache: `FOREIGNTABLEREL`. `[verified-by-code]`
- No function prototypes here.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_class.h.md` (RELKIND_FOREIGN_TABLE='f' — must have a matching row here)
- `knowledge/files/src/include/catalog/pg_foreign_server.h.md` (parent server)
- `knowledge/files/src/include/catalog/pg_foreign_data_wrapper.h.md` (grandparent FDW)

## Potential issues

- **[ISSUE-invariant-not-enforced-by-schema: pg_class RELKIND='f' ↔ pg_foreign_table row]** `pg_foreign_table.h:30-38` — every `pg_class` row with `relkind='f'` MUST have exactly one matching `pg_foreign_table.ftrelid`, and vice versa. This pairing is enforced only by the DDL paths (`CREATE/DROP FOREIGN TABLE`) and dependency machinery; no FK exists. A buggy in-place catalog edit (or partial DROP) can leave an orphan in either direction, which the planner / FDW dispatch then assumes-away.

## Tally

`[verified-by-code]=5 [from-comment]=1`
