# syscache.h

- **Source path:** `source/src/include/utils/syscache.h`
- **Lines:** 136
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `syscache.c`, `catalog/syscache_ids.h` (the generated enum), `lsyscache.h` (convenience wrappers built on top).

## Purpose

Public surface for the named-cache layer over catcache. Pulls in `catalog/syscache_ids.h` for the `SysCacheIdentifier` enum, declares the `SearchSysCache*` family, and provides the macro forms (`SearchSysCacheCopy1..4`, `SearchSysCacheExists1..4`, `GetSysCacheOid1..4`, `GetSysCacheHashValue1..4`, `SearchSysCacheList1..3`) that insulate callers from `CATCACHE_MAXKEYS` changes.

## Top-of-file comment

> "System catalog cache definitions. See also lsyscache.h, which provides convenience routines for common cache-lookup operations." [syscache.h:3-7]

Note: deliberately **does not** include `utils/catcache.h` (comment at line 21). Callers that need the `CatCList *` return of `SearchSysCacheList` must include catcache.h themselves.

## Public surface

- **Init**: `InitCatalogCache`, `InitCatalogCachePhase2`.
- **Search**: `SearchSysCache`, `SearchSysCache1..4`, `ReleaseSysCache`.
- **Locked variant**: `SearchSysCacheLocked1`, `SearchSysCacheLockedCopy1`.
- **Convenience**: `SearchSysCacheCopy`, `SearchSysCacheExists`, `GetSysCacheOid`, `SearchSysCacheAttName`/`AttNum` + copy/exists variants.
- **Attribute extraction**: `SysCacheGetAttr`, `SysCacheGetAttrNotNull`.
- **Hash / list**: `GetSysCacheHashValue`, `SearchSysCacheList`, `ReleaseSysCacheList` (a `#define` aliasing `ReleaseCatCacheList`).
- **Inval**: `SysCacheInvalidate`.
- **Schema-introspection**: `RelationInvalidatesSnapshotsOnly`, `RelationHasSysCache`, `RelationSupportsSysCache`.
- **Numbered-arg macros**: `SearchSysCacheCopy{1..4}`, `SearchSysCacheExists{1..4}`, `GetSysCacheOid{1..4}`, `GetSysCacheHashValue{1..4}`, `SearchSysCacheList{1..3}` (lines 91-133).

## Key invariants

- **Macros, not inlines, for keyed wrappers.** The comment at 86-90 says: "The use of the macros below rather than direct calls to the corresponding functions is encouraged, as it insulates the caller from changes in the maximum number of keys." [from-comment]
- **`SearchSysCacheList` is special**: returns `struct catclist *` so its callers must also include `catcache.h`. [from-comment, syscache.h:75-78]

## Confidence tag tally

verified-by-code: 0 — from-comment: 3 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)
- [idioms/syscache-catcache-internals.md](../../../../idioms/syscache-catcache-internals.md)
