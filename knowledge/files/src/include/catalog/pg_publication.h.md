# pg_publication.h

- **Source path:** `source/src/include/catalog/pg_publication.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'publication' system catalog (pg_publication)." `[from-comment]` A publication is the publisher-side declaration of a set of changes to replicate (tables/sequences, optionally filtered by row or column).

## Catalog definition

- `CATALOG(pg_publication,6104,PublicationRelationId)` — per-DB catalog (NOT shared). No `BKI_BOOTSTRAP`, no `BKI_ROWTYPE_OID`. `[verified-by-code]` `pg_publication.h:31`
- `FormData_pg_publication` typedef. Pointer alias: `Form_pg_publication`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| pubname | NameData | — | — |
| pubowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| puballtables | bool | — | — (FOR ALL TABLES) |
| puballsequences | bool | — | — (FOR ALL SEQUENCES) |
| pubinsert | bool | — | — |
| pubupdate | bool | — | — |
| pubdelete | bool | — | — |
| pubtruncate | bool | — | — |
| pubviaroot | bool | — | — (publish via root for partitioned) |
| pubgencols | char | — | — (see `PublishGencolsType`) |

No `#ifdef CATALOG_VARLEN` block. All columns are fixed-width. `[verified-by-code]`

## Key declarations beyond FormData

- **On-disk char constants** (under `#ifdef EXPOSE_TO_CLIENT_CODE`) `pg_publication.h:123-135` — `PUBLISH_GENCOLS_NONE='n'`, `PUBLISH_GENCOLS_STORED='s'`. Stored verbatim in `pubgencols`. `[verified-by-code]`
- In-memory descriptor structs (not on-disk):
  - `PublicationActions` — {pubinsert, pubupdate, pubdelete, pubtruncate}. `[verified-by-code]`
  - `PublicationDesc` — actions + row-filter / column-list / gencol validity flags vs replica identity. `[verified-by-code]`
  - `Publication` — runtime cache form of a row. `[verified-by-code]`
  - `PublicationRelInfo` — {Relation, whereClause, columns, except}. `[verified-by-code]`
  - `PublicationPartOpt` enum — `ROOT` / `LEAF` / `ALL` for partition-traversal selection. `[verified-by-code]`
- Indexes: `pg_publication_oid_index` (PK, 6110), `pg_publication_pubname_index` (6111). Syscaches: `PUBLICATIONOID`, `PUBLICATIONNAME`. `[verified-by-code]`
- Function prototypes: `GetPublication`, `GetPublicationByName`, `GetRelationIncludedPublications`, `GetRelationExcludedPublications`, `GetIncludedPublicationRelations`, `GetExcludedPublicationTables`, `GetAllTablesPublications`, `GetAllPublicationRelations`, `GetPublicationSchemas`, `GetSchemaPublications`, `GetSchemaPublicationRelations`, `GetAllSchemaPublicationRelations`, `GetPubPartitionOptionRelations`, `GetTopMostAncestorInPublication`, `is_publishable_relation`, `is_schema_publication`, `is_table_publication`, `check_and_fetch_column_list`, `publication_add_relation`, `pub_collist_validate`, `publication_add_schema`, `pub_collist_to_bitmapset`, `pub_form_cols_map`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_publication_rel.h.md` (per-relation membership + row filter + column list)
- `knowledge/files/src/include/catalog/pg_publication_namespace.h.md` (per-schema membership)
- `knowledge/files/src/include/catalog/pg_subscription.h.md` (downstream side)
- `knowledge/subsystems/replication.md` (when written)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: `pubgencols` char values are on-disk]** `pg_publication.h:128-131` — `PUBLISH_GENCOLS_NONE='n'` / `PUBLISH_GENCOLS_STORED='s'` are stored verbatim in `pg_publication.pubgencols`. The enum comment does not flag this as an on-disk format constant. Adding a third value (e.g. virtual gencols) is safe but renaming any letter would silently corrupt existing publications.

## Tally

`[verified-by-code]=10 [from-comment]=1`
