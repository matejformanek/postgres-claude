# pg_publication_rel.h

- **Source path:** `source/src/include/catalog/pg_publication_rel.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the system catalog for mappings between relations and publications (pg_publication_rel)." `[from-comment]` One row per (publication, relation) edge, carrying the optional row filter (`prqual`) and column list (`prattrs`).

## Catalog definition

- `CATALOG(pg_publication_rel,6106,PublicationRelRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_publication_rel.h:31`
- `FormData_pg_publication_rel` typedef. Pointer alias: `Form_pg_publication_rel`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| prpubid | Oid | `BKI_LOOKUP` | `pg_publication` |
| prrelid | Oid | `BKI_LOOKUP` | `pg_class` |
| prexcept | bool | `BKI_DEFAULT(f)` | — (true = EXCEPT-clause entry) |
| prqual | pg_node_tree | (varlena) | — (WHERE row filter) |
| prattrs | int2vector | (varlena) | — (column-list attnums) |

The two trailing fields live under `#ifdef CATALOG_VARLEN`. `[verified-by-code]`

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_publication_rel, 6228, 6229)` — has a TOAST table for the row-filter / column-list payloads. `[verified-by-code]`
- Indexes: `pg_publication_rel_oid_index` (PK, 6112); `pg_publication_rel_prrelid_prpubid_index` (6113, unique on (prrelid, prpubid)); `pg_publication_rel_prpubid_index` (6116, non-unique on prpubid). `[verified-by-code]`
- Syscaches: `PUBLICATIONREL` (by oid), `PUBLICATIONRELMAP` (by (prrelid, prpubid)). `[verified-by-code]`
- No function prototypes declared here.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_publication.h.md` (parent + helper prototypes; `publication_add_relation` writes here)
- `knowledge/files/src/include/catalog/pg_publication_namespace.h.md` (sibling: per-schema edges)
- `knowledge/subsystems/replication.md` (when written)

## Tally

`[verified-by-code]=6 [from-comment]=1`
