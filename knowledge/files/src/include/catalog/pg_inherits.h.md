# pg_inherits.h

- **Source path:** `source/src/include/catalog/pg_inherits.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'inherits' system catalog (pg_inherits)." Edges between child relations and their direct parents — both for classical table inheritance and for declarative partitioning. `[from-comment]`

## Catalog definition

- `CATALOG(pg_inherits,2611,InheritsRelationId)` — not bootstrap, not shared, no rowtype-OID, no schema-macro. `[verified-by-code]`
- `FormData_pg_inherits` / `Form_pg_inherits`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| inhrelid | Oid | — | `pg_class` |
| inhparent | Oid | — | `pg_class` |
| inhseqno | int32 | — | — |
| inhdetachpending | bool | — | — |

All columns are non-nullable fixed-length; no `CATALOG_VARLEN` block.

## Key declarations beyond FormData

- Indexes: PK `pg_inherits_relid_seqno_index` (`inhrelid`, `inhseqno`), non-unique `pg_inherits_parent_index` (`inhparent`). No syscache. `[verified-by-code]`
- Function prototypes: `find_inheritance_children`, `find_inheritance_children_extended` (omit_detached / detached_exist / detached_xmin), `find_all_inheritors`, `has_subclass`, `has_superclass`, `typeInheritsFrom`, `StoreSingleInheritance`, `DeleteInheritsTuple` (with `expect_detach_pending`), `PartitionHasPendingDetach`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_class.h.md` (both FK targets)
- `knowledge/files/src/include/catalog/pg_partitioned_table.h.md` (partition metadata sibling)
- `knowledge/files/src/include/catalog/partition.h.md` (consumer)

## Tally

`[verified-by-code]=3 [from-comment]=1`
