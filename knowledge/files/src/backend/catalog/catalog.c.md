# catalog.c

- **Source path:** `source/src/backend/catalog/catalog.c`
- **Lines:** ~745
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines concerned with catalog naming conventions and other bits of hard-wired knowledge." Compact, no clear central object — just a grab bag of predicates and OID allocators that depend on bootstrap-time knowledge.

## Public surface

- `IsSystemRelation` (74), `IsSystemClass` (86) — "is this a system catalog *or* a TOAST table on one". Used by ACL/DDL to gate user-defined-only operations.
- `IsCatalogRelation` (104), `IsCatalogRelationOid` (121) — narrower: "is this in pg_catalog (and not a TOAST table)". The classic relid threshold check (relid < FirstUnpinnedObjectId or relid is in a hardcoded list).
- `IsCatalogTextUniqueIndexOid` (156) — special-case identifier for the few catalog unique indexes that use `text` (relevant for collation-version handling during initdb).
- `IsInplaceUpdateRelation` (183), `IsInplaceUpdateOid` (193) — list of catalogs that allow `heap_inplace_update_and_unlock` (pg_class, pg_database, pg_relation_relation, …). These are catalogs where MVCC visibility of the update is not required.
- `IsToastRelation` (206), `IsToastClass` (226), `IsToastNamespace` (261) — TOAST table predicates.
- `IsCatalogNamespace` (243) — `nsoid == PG_CATALOG_NAMESPACE`.
- `IsReservedName` (278) — names starting with `pg_` are reserved.
- `IsSharedRelation` (304) — hardcoded list of cluster-wide catalogs (pg_database, pg_authid, pg_tablespace, pg_shdepend, pg_shdescription, pg_shseclabel, pg_replication_origin, pg_subscription, pg_parameter_acl, pg_db_role_setting + their indexes and toast).
- `IsPinnedObject` (370) — the "pinned" predicate consulted by dependency.c to refuse drops of bootstrap-created objects. Pinning is materialised by pg_depend rows with refclassid=0; this function shortcuts the common cases (pg_authid bootstrap roles, the public schema, …) and falls back to a syscache lookup.
- `GetNewOidWithIndex` (448) — universal OID allocator for cataloged objects: spin until a freshly-`GetNewObjectId()` value is not already present in the given unique index. Used by every CREATE for any object that gets a normal OID.
- `GetNewRelFileNumber` (557) — allocate a fresh `RelFileNumber` (= initial pg_class.oid for new heap relations) avoiding both pg_class collision and physical-file collision in the tablespace.
- `pg_nextoid` (641) — SQL-callable wrapper used by pg_upgrade.
- `pg_stop_making_pinned_objects` (720) — initdb-time toggle: after initdb's bootstrap phase, stop creating pg_depend rows with refclassid=0.

## Confidence tag tally

`[verified-by-code]=5 [from-comment]=1`
