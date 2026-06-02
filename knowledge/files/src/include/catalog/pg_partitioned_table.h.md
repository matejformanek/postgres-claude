# pg_partitioned_table.h

- **Source path:** `source/src/include/catalog/pg_partitioned_table.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'partitioned table' system catalog (pg_partitioned_table)." One row per partitioned parent (table or index) carrying the partition key and default-partition OID. `[from-comment]`

## Catalog definition

- `CATALOG(pg_partitioned_table,3350,PartitionedRelationId)` — not bootstrap, not shared, no rowtype-OID, no schema-macro. `[verified-by-code]`
- `FormData_pg_partitioned_table` / `Form_pg_partitioned_table`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| partrelid | Oid | — | `pg_class` |
| partstrat | char | — | — (partitioning strategy: list/range/hash) |
| partnatts | int16 | — | — |
| partdefid | Oid | — | `pg_class` (OPT; 0 if no default) |
| partattrs | int2vector | `BKI_FORCE_NOT_NULL` | — (0 = expression column) |
| partclass | oidvector | `BKI_FORCE_NOT_NULL` (varlena) | `pg_opclass` |
| partcollation | oidvector | `BKI_LOOKUP_OPT(pg_collation) BKI_FORCE_NOT_NULL` (varlena) | `pg_collation` (OPT) |
| partexprs | pg_node_tree | — (varlena, nullable) | — |

Per header comment on `partattrs`: it's the first varlena but direct C-struct access is allowed "because the first variable-length field of a heap tuple can be reliably accessed using its C struct offset, as previous fields are all non-nullable fixed-length fields." `[from-comment]`

Note: `partstrat` values (the partitioning strategy chars `'l'`/`'r'`/`'h'`) are NOT defined in this header — see `partition.h` / `parsenodes.h`. `[inferred]`

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST(pg_partitioned_table, 4165, 4166)`; PK `pg_partitioned_table_partrelid_index`. Syscache: `PARTRELID`. `[verified-by-code]`
- `DECLARE_ARRAY_FOREIGN_KEY_OPT((partrelid, partattrs), pg_attribute, (attrelid, attnum))` — array FK declared as optional because `partattrs` can contain 0 for expression keys. `[verified-by-code]`
- No function prototypes declared in this header.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_class.h.md` (partrelid + partdefid → pg_class)
- `knowledge/files/src/include/catalog/pg_inherits.h.md` (parent↔child edges live there)
- `knowledge/files/src/include/catalog/partition.h.md` (partition strategy/bound API)

## Potential issues

- **[ISSUE-undocumented-invariant: partstrat char values are on-disk]** `pg_partitioned_table.h:35` — `partstrat` is a `char` column persisted in catalog rows; the symbolic values (`PARTITION_STRATEGY_LIST` etc.) live in another header. Reader of just this file can't tell which letters are on-disk-stable. Worth a `/* see PARTITION_STRATEGY_* in <header> */` cross-reference.
- **[ISSUE-undocumented-invariant: partattrs direct C-struct access pun]** `pg_partitioned_table.h:40-46` — same pattern as `pg_proc.h` proargtypes and `pg_index.h` indkey: any future fixed-length nullable column between `partdefid` and `partattrs` quietly breaks all readers using `form->partattrs`. The header does explain the rationale (unlike pg_proc), but a static-assert on offsetof would make it enforceable.

## Tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=1`
