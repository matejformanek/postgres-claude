---
path: src/bin/pg_dump/common.c
anchor_sha: 4b0bf0788b0
loc: 1171
depth: deep
---

# common.c

- **Source path:** `source/src/bin/pg_dump/common.c`
- **Lines:** 1171
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_dump.h` (declares the `DumpableObject`, `CatalogId`, `DumpId` types and every `getXxx`/`findXxxByOid` prototype), `pg_dump_sort.c` (consumer of `getDumpableObjects` + the dependency arrays), `pg_backup_archiver.c` (calls `getSchemaData`), `lib/simplehash.h` (the catalog-ID hash template).

## Purpose

Two related registries plus the catalog-fetch driver:

1. **DumpId → DumpableObject** map (`dumpIdMap`, a plain array indexed by 1-based `DumpId`).
2. **CatalogId (tableoid+oid) → {DumpableObject, ExtensionInfo}** map (a simplehash table keyed on the 2-OID pair).
3. **`getSchemaData()`** — the long, ordered call sequence that builds the dumpable-object graph by invoking each `getXxx()` collector in dependency order.

[from-comment, common.c:1-15, 34-56; verified-by-code, common.c:36-82]

## Public surface (non-static functions)

- `getSchemaData(fout, *numTablesPtr)` (97) — collector spine; order matters (extensions → schemas → tables → … → policies → publications/subscriptions). [verified-by-code, common.c:97-254]
- `AssignDumpId(dobj)` (660) — assign a fresh `DumpId`, register in both maps. [verified-by-code, common.c:659-715]
- `recordAdditionalCatalogID(catId, dobj)` (722) — second CatalogId pointing at the same DumpableObject (used for blobs). [verified-by-code, common.c:721-739]
- `createDumpId(void)` (748) — bare ID, no DumpableObject (for "fixed" ArchiveEntries that skip sorting). [verified-by-code, common.c:747-751]
- `getMaxDumpId()`, `findObjectByDumpId(id)`, `findObjectByCatalogId(catId)`, `getDumpableObjects(**objs, *numObjs)` (757-813).
- `addObjectDependency` / `removeObjectDependency` (821, 846) — append-only / linear-scan removal on `dobj->dependencies[]`. [verified-by-code, common.c:820-857]
- Eleven `findXxxByOid()` lookups: `findTableByOid`, `findIndexByOid` (static), `findTypeByOid`, `findFuncByOid`, `findOprByOid`, `findAccessMethodByOid`, `findCollationByOid`, `findNamespaceByOid`, `findExtensionByOid`, `findPublicationByOid`, `findSubscriptionByOid`. Each is a thin wrapper around `findObjectByCatalogId` with the right `tableoid` constant and an asserted `objType`. [verified-by-code, common.c:865-1057]
- `recordExtensionMembership(catId, ext)` (1066) / `findOwningExtension(catId)` (1090). [verified-by-code, common.c:1065-1101]
- `parseOidArray(str, *array, arraysize)` (1114) — whitespace-separated OID list, no extra allocation. [verified-by-code, common.c:1113-1150]

## Static helpers

- `flagInhTables` (270) — wires `tblinfo[i].parents[]`, creates `DO_TABLE_ATTACH` objects for partitions; pg_fatals if a non-partition parent is missing from `tblinfo` (a "failed sanity check"). [verified-by-code, common.c:269-380]
- `flagInhIndexes` (388) — wires `IndexAttachInfo` for partitioned indexes; SILENTLY skips when `findIndexByOid(index->parentidx)` returns NULL. [verified-by-code, common.c:387-450]
- `flagInhAttrs` (480) — propagates inherited NOT NULL / DEFAULT / GENERATED attrs across the parent chain; v18 vs pre-18 split. [verified-by-code, common.c:479-649]
- `strInArray(pattern, **arr, arr_size)` (1161) — linear `strcmp` scan. [verified-by-code, common.c:1160-1171]

## Key types / structs

- `CatalogIdMapEntry` (57-64) — hash bucket holds `{CatalogId, status, hashval, *dobj, *ext}`. The dual-purpose `ext` pointer lets one entry serve both "what dumpable object is this?" and "what extension owns this?" — either may be NULL (extension membership is read before most DumpableObjects exist). [from-comment, common.c:41-56]
- The simplehash instance is named `catalogid_*` via the `SH_PREFIX` macro; `SH_RAW_ALLOCATOR=pg_malloc0`. [verified-by-code, common.c:66-78]

## Key invariants

- `dobj->dumpId == 0` is reserved as `InvalidDumpId`. First assigned dump ID is 1. [verified-by-code, common.c:39, 662]
- `dumpIdMap` is doubled on overflow starting at 256. [verified-by-code, common.c:680-693]
- Inside `AssignDumpId`, `Assert(entry->dobj == NULL)` enforces that no two DumpableObjects share a CatalogId (the dual-CatalogId case must go through `recordAdditionalCatalogID` instead). [verified-by-code, common.c:712-713]
- `OidIsValid(dobj->catId.tableoid)` gates hash registration — synthetic DumpableObjects (TableAttachInfo, IndexAttachInfo, AttrDefInfo) explicitly zero `catId.tableoid`/`oid` so they live only in `dumpIdMap`. [verified-by-code, common.c:697, 358-361, 416-418, 614-616]
- `addObjectDependency` does NOT dedupe; downstream sort must tolerate duplicates. [from-comment, common.c:818-819]
- `getSchemaData`'s ordering is load-bearing: extensions before extension-membership-aware decisions; `getTables` ASAP after `getNamespaces` to minimise the window between txn start and per-table ACCESS SHARE lock acquisition. [from-comment, common.c:107-126]

## Phase D — surfaces of concern

- **Silent drop of orphan inhrelid in `flagInhTables`** (296-304): `if (child == NULL) continue;` — a `pg_inherits` row whose `inhrelid` doesn't match any TableInfo is assumed to be a partitioned-index row. If a hostile catalog injects an `inhrelid` referencing an OID the dumper *should* see but doesn't (e.g. filtered out earlier), the dump silently loses the inheritance link rather than failing. [verified-by-code, common.c:294-305] [maybe]
- **Silent drop in `flagInhIndexes`** (410-411): `if (parentidx == NULL) continue;` — same shape, partitioned-index parent missing → silently skipped. [verified-by-code, common.c:410-411] [maybe]
- **`parseOidArray` bounds — `argNum >= arraysize` is a `pg_fatal`** (1130) but the per-token `j >= sizeof(temp) - 1` guard (1142) is also a `pg_fatal`. Both abort; no silent truncation. [verified-by-code, common.c:1130-1145] [no concern]
- **`atooid` on each token** uses the unsigned-32 path; negative inputs (`s == '-'`) are allowed in the char-class check at 1141 because this function is also used for attribute numbers per the comment. Mixing signed/unsigned interpretation is left to the caller. [from-comment, common.c:1106-1110] [no concern]
- **Race between snapshot + per-object queries.** This file does not start the snapshot itself — that's done in `pg_dump.c`'s `setup_connection` before `getSchemaData` runs. Every `getXxx()` invoked here runs inside the same repeatable-read txn, so catalog state is consistent for this session. [inferred — see pg_dump.c for the actual snapshot setup]

## Cross-references

- Callers: `pg_dump.c::main()` calls `getSchemaData`. Sort phase (`pg_dump_sort.c`) calls `getDumpableObjects` + the dependency arrays. Every `dumpXxx()` function in `pg_dump.c` calls a matching `findXxxByOid`.
- See also: `knowledge/files/src/bin/pg_dump/pg_dump.h.md` (DumpableObject schema), `knowledge/idioms/dumpable-object-registry.md` (if/when written).

## Open questions

- Why are `findIndexByOid` and `strInArray` `static` while every other `findXxxByOid` is extern? `findIndexByOid` is only needed inside `flagInhIndexes`; `strInArray` only inside `flagInhAttrs`. The other lookups are called from `dumpXxx()` paths in pg_dump.c. [inferred]

## Confidence tag tally
`[verified-by-code]=22 [from-comment]=5 [inferred]=2 [maybe]=2`
