# pg_index.h

- **Source path:** `source/src/include/catalog/pg_index.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'index' system catalog (pg_index)." One row per index, complementing the index's own pg_class row with key/predicate/state metadata. `[from-comment]`

## Catalog definition

- `CATALOG(pg_index,2610,IndexRelationId) BKI_SCHEMA_MACRO` — not bootstrap, not shared, no rowtype-OID. `[verified-by-code]`
- `FormData_pg_index` / `Form_pg_index`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| indexrelid | Oid | — | `pg_class` |
| indrelid | Oid | — | `pg_class` |
| indnatts | int16 | — | — |
| indnkeyatts | int16 | — | — |
| indisunique | bool | — | — |
| indnullsnotdistinct | bool | — | — |
| indisprimary | bool | — | — |
| indisexclusion | bool | — | — |
| indimmediate | bool | — | — |
| indisclustered | bool | — | — |
| indisvalid | bool | — | — |
| indcheckxmin | bool | — | — |
| indisready | bool | — | — |
| indislive | bool | — | — |
| indisreplident | bool | — | — |
| indkey | int2vector | `BKI_FORCE_NOT_NULL` | — (0 = expression) |
| indcollation | oidvector | `BKI_LOOKUP_OPT(pg_collation) BKI_FORCE_NOT_NULL` (varlena) | `pg_collation` (OPT) |
| indclass | oidvector | `BKI_LOOKUP(pg_opclass) BKI_FORCE_NOT_NULL` (varlena) | `pg_opclass` |
| indoption | int2vector | `BKI_FORCE_NOT_NULL` (varlena) | — (per-col AM-specific flags) |
| indexprs | pg_node_tree | — (varlena, nullable) | — |
| indpred | pg_node_tree | — (varlena, nullable) | — |

Per header: `indkey` is variable-length but direct C-struct access is permitted (it is the first varlena and all preceding fields are non-nullable fixed-length). `[from-comment]`

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST_WITH_MACRO(pg_index, 6351, 6352, PgIndexToastTable, PgIndexToastIndex)`; non-unique `pg_index_indrelid_index`, PK `pg_index_indexrelid_index`. Syscache: `INDEXRELID`. `[verified-by-code]`
- `DECLARE_ARRAY_FOREIGN_KEY_OPT((indrelid, indkey), pg_attribute, (attrelid, attnum))` — array FK declared as optional because `indkey` may contain 0 (`InvalidAttrNumber`) for expression columns. `[verified-by-code]`
- `EXPOSE_TO_CLIENT_CODE` macros for `indoption` per-column flag bits: `INDOPTION_DESC=0x0001`, `INDOPTION_NULLS_FIRST=0x0002`. Comment: "Index AMs that support ordered scans must support these two indoption bits. Otherwise, the content of the per-column indoption fields is open for future definition." `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_class.h.md` (indexrelid + indrelid both → pg_class)
- `knowledge/files/src/include/catalog/pg_attribute.h.md` (indkey array FK)
- `knowledge/files/src/include/catalog/index.h.md` (heap-side index DDL API)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: indkey direct C-struct access pun]** `pg_index.h:50-52` — same fragile pun as in `pg_proc.h` (proargtypes). Inserting any nullable fixed-length column above `indkey` silently breaks readers using `idx->indkey`. Worth a defensive comment + static-assert on the offset.

## Tally

`[verified-by-code]=5 [from-comment]=2`
