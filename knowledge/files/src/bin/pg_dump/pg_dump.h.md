---
path: src/bin/pg_dump/pg_dump.h
anchor_sha: 4b0bf0788b0
loc: 839
depth: deep
---

# pg_dump.h

- **Source path:** `source/src/bin/pg_dump/pg_dump.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 839

## Purpose

`pg_dump`'s internal type system. Defines `DumpableObject` (the polymorphic
base struct for every dump-eligible object), the `DumpableObjectType` enum
(48 kinds), the `DumpComponents` bitmask (DEFINITION / DATA / COMMENT /
SECLABEL / ACL / POLICY / USERMAP / STATISTICS), and the per-kind subclasses
(`TableInfo`, `FuncInfo`, `TypeInfo`, `IndxInfo`, `ConstraintInfo`, …) that
hold the catalog data pulled by the `getXxx(Archive *)` collectors. Also
declares the cross-cutting helpers `AssignDumpId`, `findObjectByDumpId`,
`addObjectDependency`, `sortDumpableObjects`, and one prototype per catalog
collector. Companion header: `pg_backup.h` (`Archive`, `DumpOptions`,
`teSection`, `ArchiveFormat`). [verified-by-code, pg_dump.h:17, 38-89,
147-162, 758-837]

## Public surface (highlights)

- **`DumpableObjectType`** (38-89) — 48-value enum listing every kind of
  object that gets a `DumpableObject`. Members include `DO_NAMESPACE`,
  `DO_TYPE`, `DO_FUNC`, `DO_TABLE`, `DO_TABLE_DATA`, `DO_INDEX`,
  `DO_CONSTRAINT`, `DO_FK_CONSTRAINT`, the boundary markers
  `DO_PRE_DATA_BOUNDARY`/`DO_POST_DATA_BOUNDARY`, and the
  publication/subscription/policy/stats kinds. [verified-by-code,
  pg_dump.h:38-89]
- **`NUM_DUMPABLE_OBJECT_TYPES`** macro (91) — equals `DO_SUBSCRIPTION_REL +
  1`; `pg_dump_sort.c` uses this for a `StaticAssertDecl` against the
  priority table.
- **`DumpComponents`** bitmask (107-117) — `DUMP_COMPONENT_DEFINITION`,
  `_DATA`, `_COMMENT`, `_SECLABEL`, `_ACL`, `_POLICY`, `_USERMAP`,
  `_STATISTICS`. `DUMP_COMPONENT_ALL = 0xFFFF` is a sentinel; the header
  warns that `dobj->dump == DUMP_COMPONENT_NONE` is a likely-wrong test
  because irrelevant bits aren't carefully zeroed. [from-comment,
  pg_dump.h:98-106]
- **`DUMP_COMPONENTS_REQUIRING_LOCK`** (141-145) — `DEFINITION | DATA |
  STATISTICS | POLICY`. The header documents why `COMMENT`, `SECLABEL`,
  `ACL`, and `USERMAP` don't need a table lock: they query catalogs
  directly and don't go through SysCache-using server-side functions.
  [from-comment, pg_dump.h:119-145]
- **`DumpableObject`** (147-162) — the polymorphic base: `objType`, a
  `CatalogId` (tableoid+oid), an assigned `DumpId`, the `name`, optional
  namespace link, three component bitmasks (`dump`, `dump_contains`,
  `components`), extension-membership flags, and the
  `dependencies[]`/`nDeps`/`allocDeps` dependency-graph slots.
  [verified-by-code, pg_dump.h:147-162]
- **`DumpableAcl`** (164-175) + **`DumpableObjectWithAcl`** (177-182) —
  every ACL-bearing struct must put a `DumpableObject` first and a
  `DumpableAcl` immediately after, so cross-type casts work. Encodes the
  actual `acl`, the `acldefault` baseline, and the `pg_init_privs` entry
  (`privtype`, `initprivs`). [from-comment, pg_dump.h:164-175]
- **Per-kind subclasses** (184-752) — `NamespaceInfo`, `ExtensionInfo`,
  `TypeInfo`, `FuncInfo`/`AggInfo`, `OprInfo`, `AccessMethodInfo`,
  `OpclassInfo`/`OpfamilyInfo`, `CollInfo`, `ConvInfo`, `TableInfo`,
  `IndxInfo`, `RelStatsInfo`, `StatsExtInfo`, `RuleInfo`, `TriggerInfo`,
  `EventTriggerInfo`, `ConstraintInfo` (used for ALL constraint kinds —
  comment notes only the FK case gets a distinct `DO_FK_CONSTRAINT`),
  `ProcLangInfo`, `CastInfo`, `TransformInfo`, `TSParserInfo`,
  `TSDictInfo`, `TSTemplateInfo`, `TSConfigInfo`, `FdwInfo`,
  `ForeignServerInfo`, `DefaultACLInfo`, `LoInfo` (groups blobs by
  owner/ACL), `PolicyInfo`, `PublicationInfo`/`PublicationRelInfo`/
  `PublicationSchemaInfo`, `SubscriptionInfo`/`SubRelInfo`. [verified-by-code,
  pg_dump.h:184-752]
- **Common-utility prototypes** (758-789) — `getSchemaData` (the top-level
  catalog walker), `AssignDumpId`, `createDumpId`, `getMaxDumpId`,
  `findObjectByDumpId`/`findObjectByCatalogId`, `getDumpableObjects`,
  `addObjectDependency`/`removeObjectDependency`, per-kind `findXxxByOid`
  lookups, `recordExtensionMembership`/`findOwningExtension`,
  `parseOidArray`, `sortDumpableObjects`, `sortDumpableObjectsByTypeName`.
  [verified-by-code, pg_dump.h:758-789]
- **Version-specific `getXxx(Archive *fout)` collectors** (793-837) — one
  per `DO_*` kind: `getNamespaces`, `getExtensions`, `getTypes`, `getFuncs`,
  `getAggregates`, `getOperators`, `getAccessMethods`, `getOpclasses`,
  `getOpfamilies`, `getCollations`, `getConversions`, `getTables`,
  `getOwnedSeqs`, `getInherits`, `getPartitioningInfo`, `getIndexes`,
  `getExtendedStatistics`, `getConstraints`, `getRules`, `getTriggers`,
  `getProcLangs`, `getCasts`, `getTransforms`, `getTableAttrs`,
  `getTSParsers`/`getTSDictionaries`/`getTSTemplates`/`getTSConfigurations`,
  `getForeignDataWrappers`/`getForeignServers`, `getDefaultACLs`,
  `getExtensionMembership`+`processExtensionTables`, `getEventTriggers`,
  `getPolicies`, `getPublications`+`getPublicationNamespaces`+
  `getPublicationTables`, `getSubscriptions`+`getSubscriptionRelations`.
  Most are defined in `pg_dump.c`; a few live in `common.c`. [verified-by-code,
  pg_dump.h:793-837]

## Internal landmarks

- **Subclass cast contract.** Every per-kind struct starts with
  `DumpableObject dobj;` so a `DumpableObject *` can be safely cast to
  the specific subclass after switching on `objType`. The dispatch in
  `pg_dump.c:dumpDumpableObject` (line 11819) and the loop-repair code
  in `pg_dump_sort.c` rely on this layout. [verified-by-code, pg_dump.h
  passim; pg_dump.c:11832]
- **Two-tier `dump` mask** (`dump` vs `dump_contains`, both
  `DumpComponents`). `dump_contains` tracks the union over contained
  objects (e.g. a schema's contained objects); used by selection logic
  to decide whether the container needs to be created. [inferred,
  pg_dump.h:154-156]
- **`components` is the discovery mask.** `dump` is what the user
  requested; `components` is what actually exists for the object;
  `dumpDumpableObject` AND-folds `dump &= components` before dispatch.
  [verified-by-code, pg_dump.c:11826]
- **`TableInfo` is the heaviest struct** (302-393) — 50+ fields. Marks
  inheritance, partitioning, NOT NULL constraints (with the post-v17
  named-vs-unnamed distinction and v18 NOT NULL NOT VALID), RLS,
  per-column type/storage/compression/options/identity/generated/
  collation/missingval/fdwoptions arrays. `interesting` flag means
  "collect more data"; `numatts` triggers the array-allocation pass.
  [verified-by-code, pg_dump.h:302-393]
- **`InhInfo` is the only non-`DumpableObject` type** (562-567) — just
  the (child_oid, parent_oid) pair; temporary state for building the
  inheritance graph. [verified-by-code, pg_dump.h:562-567]
- **`LoInfo`** (639-646) — flexible-array struct: one group of large
  objects sharing owner+ACL, allowing parallel-restore granularity for
  blob metadata. Comment: "If there are many blobs with the same
  owner/ACL, we can divide them into multiple LoInfo groups, which will
  each spawn a BLOB METADATA and a BLOBS (data) TOC entry." [from-comment,
  pg_dump.h:631-638]

## Invariants & gotchas

- **Mirror `DumpableObjectType` ↔ `pg_dump_sort.c` priority tables.**
  The enum's leading comment (40) reads "When modifying this enum,
  update priority tables in `pg_dump_sort.c`!" — `pg_dump_sort.c:105`
  builds `dbObjectTypePriority[]` indexed by this enum and uses
  `StaticAssertDecl(lengthof(dbObjectTypePriority) ==
  NUM_DUMPABLE_OBJECT_TYPES, ...)` to catch drift at compile time.
  [from-comment, pg_dump.h:40; verified-by-code, pg_dump_sort.c:157]
- **`DumpComponents` test idiom.** The right test is `if (!(dobj->dump
  & DUMP_COMPONENT_DEFINITION))`, NOT `if (dobj->dump ==
  DUMP_COMPONENT_NONE)`. The header explicitly calls this out as a
  trap because irrelevant bits may be non-zero. [from-comment,
  pg_dump.h:98-106]
- **`DumpableAcl` MUST come immediately after `DumpableObject`.** Both
  `DumpableObjectWithAcl` and the various `XxxInfo` structs that store
  ACL data depend on this layout for generic ACL helpers. [from-comment,
  pg_dump.h:164-167]
- **`DUMP_COMPONENTS_REQUIRING_LOCK` is the lock-acquisition decider.**
  Components that need a table lock are those that invoke server-side
  functions hitting SysCache (`pg_get_*def()`, `pg_get_expr()` for
  POLICY); the others only read catalogs directly. Mis-classifying a
  new component as not-needing-lock can race against concurrent DDL.
  [from-comment, pg_dump.h:119-145]
- **`condeferrable`/`condeferred` are valid only for unique/PK
  constraints**; for other constraint types that flag info is encoded
  in `condef` instead. [from-comment, pg_dump.h:512-515]
- **NOT NULL "unnamed pre-v17" convention.** In `TableInfo.notnull_constrs[i]`,
  NULL means "no NOT NULL", empty string means "unnamed pre-v17 NOT NULL".
  Misreading the empty-string sentinel produces wrong DDL. [from-comment,
  pg_dump.h:371-374]
- **`SubscriptionInfo` binary-upgrade XXX.** Header explicitly flags
  that the current binary-upgrade ordering of "add tables to
  subscription after enabling" only works because apply workers don't
  start in binary_upgrade mode — non-binary-upgrade callers will need
  to fix the order. [from-comment, pg_dump.h:737-743]

## Cross-refs

- Consumer: `knowledge/files/src/bin/pg_dump/pg_dump.c.md` (every
  collector + dumper signature comes from here).
- Consumer: `knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md` (priority
  table + per-type tie-breakers indexed by `DumpableObjectType`).
- Archive layer: `pg_backup.h` (`Archive`, `DumpOptions`, `teSection`,
  `ArchiveFormat`).

<!-- issues:auto:begin -->
- [Issue register — `pg_dump`](../../../../issues/pg_dump.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: subclass-layout contract is unspecified
  in struct comments]** `pg_dump.h:147-162` — every `XxxInfo` struct
  starts with `DumpableObject dobj;` so the `dobj`→subclass cast in
  `dumpDumpableObject` (`pg_dump.c:11832`) is valid; this is enforced
  only by convention, no `StaticAssert` guards offsetof. Severity:
  maybe.
- **[ISSUE-doc-drift: `DumpComponents` typedef'd `uint32` but `_ALL =
  0xFFFF`]** `pg_dump.h:107, 117` — uses only the low 16 bits despite a
  32-bit type, and the comment warns about "irrelevant bits". Future
  components added beyond bit 7 (`STATISTICS`) approach the `_ALL`
  ceiling; should `_ALL` be widened to `0xFFFFFFFF`? Severity: maybe.
- **[ISSUE-stale-todo: `SubscriptionInfo` XXX about non-binary-upgrade
  ordering]** `pg_dump.h:737-743` — XXX explicitly defers ordering of
  enable-vs-add-tables. Will silently break if `binary_upgrade`
  precondition is ever loosened. Severity: maybe.

## Tally

`[verified-by-code]=15 [from-comment]=10 [inferred]=1 [unverified]=0`
