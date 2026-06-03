# pg_publication_namespace.h

- **Source path:** `source/src/include/catalog/pg_publication_namespace.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the system catalog for mappings between schemas and publications (pg_publication_namespace)." `[from-comment]` One row per FOR TABLES IN SCHEMA / FOR ALL SEQUENCES IN SCHEMA membership edge.

## Catalog definition

- `CATALOG(pg_publication_namespace,6237,PublicationNamespaceRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_publication_namespace.h:32`
- `FormData_pg_publication_namespace` typedef. Pointer alias: `Form_pg_publication_namespace`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| pnpubid | Oid | `BKI_LOOKUP` | `pg_publication` |
| pnnspid | Oid | `BKI_LOOKUP` | `pg_namespace` |

No `#ifdef CATALOG_VARLEN` block. `[verified-by-code]`

## Key declarations beyond FormData

- Indexes: `pg_publication_namespace_oid_index` (PK, 6238); `pg_publication_namespace_pnnspid_pnpubid_index` (6239, unique on (pnnspid, pnpubid)). `[verified-by-code]`
- Syscaches: `PUBLICATIONNAMESPACE` (by oid), `PUBLICATIONNAMESPACEMAP` (by (pnnspid, pnpubid)). `[verified-by-code]`
- No function prototypes declared here (helpers live in `pg_publication.h`, e.g. `publication_add_schema`, `GetPublicationSchemas`). `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_publication.h.md` (parent catalog and helper prototypes)
- `knowledge/files/src/include/catalog/pg_publication_rel.h.md` (sibling: per-relation edges)
- `knowledge/subsystems/replication.md` (when written)

## Tally

`[verified-by-code]=4 [from-comment]=1`
