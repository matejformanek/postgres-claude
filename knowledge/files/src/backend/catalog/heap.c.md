# heap.c

- **Source path:** `source/src/backend/catalog/heap.c`
- **Lines:** ~4 200
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/heap.h`, `catalog/index.c`, `catalog/storage.c`, `commands/tablecmds.c`, `access/common/heaptuple.c`.

## Purpose

"code to create and destroy POSTGRES heap relations" — the **catalog-level** create/drop of any relation (tables, matviews, sequences, indexes, toast tables, partitioned tables, foreign tables, composite types, propgraphs all go through here). Exposed entry points are `heap_create()` (uncataloged: relcache+storage only) and `heap_create_with_catalog()` (full pg_class/pg_attribute/pg_type registration plus dependency wiring). [from-comment, heap.c:3-17]

## Public surface

- `heap_create` (286) — build a relcache entry via `RelationBuildLocalRelation`, then ask the table AM (`table_relation_set_new_filelocator`) or `RelationCreateStorage` to create the physical file. **No pg_class row written.** [verified-by-code]
- `heap_create_with_catalog` (1140) — **the workhorse.** Does, in order: check for duplicate relname/typename, allocate OID (or take a binary-upgrade override), acquire `AccessExclusiveLock` on the new relid, compute initial ACL, call `heap_create` (relcache + storage), make pg_type rowtype + array type via `AddNewRelationType`+`TypeCreate`, insert pg_class row (`AddNewRelationTuple`), insert pg_attribute rows (`AddNewAttributeTuples`), record dependencies (owner, namespace, AM, current extension, default-ACL), invoke `InvokeObjectPostCreateHookArg`, then `StoreConstraints`. The 12-step recipe is documented in the comment at heap.c:411-439. [verified-by-code]
- `heap_drop_with_catalog` (1804) — DROP TABLE catalog backend. Special-cases partitions (locks parent + default partition before deletion), foreign tables (deletes pg_foreign_table tuple), partitioned tables (`RemovePartitionKeyByRelId`). Calls `RelationDropStorage` to schedule physical file unlink at commit, then `RemoveSubscriptionRel`, `remove_on_commit_action`, deletes pg_attribute/pg_class tuples, removes type. Holds `AccessExclusiveLock` until xact commit. [verified-by-code]
- `CheckAttributeNamesTypes` (452) + `CheckAttributeType` (548) — attribute name uniqueness + type legality (no pseudo-types except in special cases, no inappropriate ANYARRAY, etc.).
- `InsertPgAttributeTuples` (731) — multi-row insert into pg_attribute via `CatalogTuplesMultiInsertWithInfo`.
- `AddNewAttributeTuples` (848) — adds the 6 system attributes (`tableoid`, `cmax`, `xmax`, `cmin`, `xmin`, `ctid`) then the user attrs.
- `InsertPgClassTuple` (927) — writes one pg_class tuple. Used by `AddNewRelationTuple` and by `index.c`.
- `RelationRemoveInheritance` (1562), `DeleteRelationTuple` (1595), `DeleteAttributeTuples` (1624), `DeleteSystemAttributeTuples` (1661), `RemoveAttributeById` (1702) — DDL building blocks for ALTER TABLE DROP COLUMN / DROP TABLE.
- `StoreAttrMissingVal` (2049), `SetAttrMissing` (2105), `RelationClearMissing` (1983) — the "fast default" missing-values machinery used when adding a column with a constant default.
- `StoreRelCheck` (2167), `StoreRelNotNull` (2273), `StoreConstraints` (2329), `AddRelationNewConstraints` (2404), `AddRelationNotNullConstraints` (2916) — catalog backends for CHECK and NOT NULL constraints. `AddRelationNewConstraints` is where parser-output `Constraint` nodes get materialised into pg_constraint + pg_attrdef rows.
- `cookDefault` (3342), `cookConstraint` (3423) — parse-tree → executable expression conversion for DEFAULT / CHECK.
- `CopyStatistics` (3461), `RemoveStatistics` (3514) — pg_statistic / pg_statistic_ext_data lifecycle.
- `heap_truncate` (3610), `heap_truncate_one_rel` (3651), `heap_truncate_check_FKs` (3695), `heap_truncate_find_FKs` (3790), `RelationTruncateIndexes` (3561) — TRUNCATE backend. heap_truncate_check_FKs enforces that all FK referents are also being truncated (or have ON DELETE CASCADE), preventing inconsistency. [verified-by-code, heap.c:3695-3917]
- `StorePartitionKey` (3917), `RemovePartitionKeyByRelId` (4042), `StorePartitionBound` (4073) — pg_partitioned_table maintenance.

## Key invariants

- `heap_create_with_catalog` takes `AccessExclusiveLock` on the new relid as soon as the OID is assigned (heap.c:1293), **before** any catalog rows are inserted, so concurrent backends never see a partial relation. [verified-by-code]
- pg_type rowtype and array-type are created *before* the pg_class row; the comment notes "for largely historical reasons, the array type's OID is assigned first" (heap.c:1369). [from-comment]
- Sequences, indexes, toast tables, and propgraphs intentionally *skip* the pg_type rowtype-creation step (heap.c:1357-1361).
- Bootstrap mode skips all dependency recording (heap.c:1481).
- Shared relations must live in pg_global tablespace — last-ditch check at heap.c:1222.
- Dropping a partition requires `AccessExclusiveLock` on the parent (and on the default partition if any), because cached partition descriptors in other backends could otherwise route tuples to the doomed relation (heap.c:1810-1841). [verified-by-code]

## Atomicity contract

The whole `heap_create_with_catalog` runs in the *caller's* transaction. If anything aborts mid-way, `storage.c`'s pending-deletes machinery removes the on-disk file (heap.c:1322-1330 comment: "If we fail further down, it's the smgr's responsibility to remove the disk file again"). [from-comment]

## Confidence tag tally

`[verified-by-code]=8 [from-comment]=4`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
