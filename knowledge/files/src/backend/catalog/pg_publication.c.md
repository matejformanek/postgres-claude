# pg_publication.c

- **Source path:** `source/src/backend/catalog/pg_publication.c`
- **Lines:** ~1 700
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Publication C API manipulation." pg_publication, pg_publication_rel, pg_publication_namespace catalogs. CREATE PUBLICATION / ALTER PUBLICATION ADD TABLE / ALTER PUBLICATION ADD TABLES IN SCHEMA. Also the read side used by walsender/logical-replication to decide what changes to broadcast.

## Public surface — write side

- `check_publication_add_relation` (56), `check_publication_add_schema` (113) — sanity checks: relation must be a "publishable" kind, schema must not be system, etc.
- `publication_add_relation` (523) — insert pg_publication_rel row; handle column lists (publish only specified columns) and row filters (WHERE clauses serialised as expression trees).
- `publication_add_schema` (789) — insert pg_publication_namespace row.
- `pub_collist_validate` (675), `pub_collist_to_bitmapset` (724), `pub_form_cols_map` (756), `attnumstoint2vector` (500) — column-list machinery.

## Public surface — read side (used by walsender)

- `is_publishable_class` (154), `is_publishable_relation` (168), `is_publishable_table` (178) — predicates: must be regular table, partitioned table, or sequence; not system; not foreign; not unlogged etc.
- `pg_relation_is_publishable` (212) — SQL-callable wrapper.
- `is_schema_publication` (285), `is_table_publication` (316) — predicates over a pub.
- `check_and_fetch_column_list` (363) — resolve a pub's per-relation column list.
- `GetPubPartitionOptionRelations` (405), `GetTopMostAncestorInPublication` (449), `is_ancestor_member_tableinfos` (231), `filter_partitions` (250) — partition-tree resolution for the `publish_via_partition_root` option.
- `get_relation_publications` (876), `GetRelationIncludedPublications` (903), `GetRelationExcludedPublications` (912) — reverse lookup: which publications include a given relation.
- `get_publication_relations` (925) — forward lookup: list relations in a publication, expanding partitions per the publish_via_partition_root setting.

## Confidence tag tally

`[verified-by-code]=4`
