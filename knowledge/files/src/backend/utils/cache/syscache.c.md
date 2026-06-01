# syscache.c

- **Source path:** `source/src/backend/utils/cache/syscache.c`
- **Lines:** 794
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `syscache.h` (the public `SysCacheIdentifier` enum + macros), `catcache.c` (underlying impl), `catalog/syscache_info.h` (genbki-generated `cacheinfo` array), `inval.c` (drives `SysCacheInvalidate`).

## Purpose

Thin, named-cache-table layer over catcache. Defines a static array `SysCache[SysCacheSize]` keyed by the `SysCacheIdentifier` enum, populated at startup from `cacheinfo[]` (generated from `MAKE_SYSCACHE` declarations in `catalog/pg_*.h`). Provides the convenience surface (`SearchSysCache1..4`, `SearchSysCacheCopy*`, `SearchSysCacheExists*`, `GetSysCacheOid`, `SysCacheGetAttr*`, the `Locked*` variants) that backend code actually calls. [from-comment, syscache.c:13-19; verified-by-code]

## Top-of-file comment (verbatim)

> "These routines allow the parser/planner/executor to perform rapid lookups on the contents of the system catalogs. see utils/syscache.h for a list of the cache IDs"
> Plus an "Adding system caches" section: each cache must have a unique index whose key matches; `MAKE_SYSCACHE` in the catalog header; bucket count must be power-of-2; DML on the catalog must go through `CatalogTupleInsert`/`CatalogTupleUpdate` (not raw `heap_insert`) so indexes get updated and inval messages get queued. [syscache.c:13-65]

## Public surface

- **Init**: `InitCatalogCache` (111), `InitCatalogCachePhase2` (181).
- **Basic lookup**: `SearchSysCache` (209), `SearchSysCache1`/`2`/`3`/`4` (221/231/241/251), `ReleaseSysCache` (265).
- **Locked variants** (for inplace-update-safe reads): `SearchSysCacheLocked1` (283), `SearchSysCacheLockedCopy1` (400).
- **Copy variants**: `SearchSysCacheCopy*` (375 + by-name/by-num at 499, 562), `SearchSysCacheExists*` (421, 518), `GetSysCacheOid` (444).
- **Attr-name lookups**: `SearchSysCacheAttName` (476), `SearchSysCacheAttNum` (539), `SearchSysCacheCopyAttNum` (562).
- **Attribute extraction**: `SysCacheGetAttr` (596), `SysCacheGetAttrNotNull` (626).
- **Multi-row + hash**: `GetSysCacheHashValue` (656), `SearchSysCacheList` (672).
- **Invalidation**: `SysCacheInvalidate` (691).
- **Schema-introspection**: `RelationHasSysCache` (738), `RelationSupportsSysCache` (763).

## Key types / structs

- `struct cachedesc` (syscache.c:70) — fields `reloid`, `indoid`, `nkeys`, `key[4]`, `nbuckets`. One array entry per `SysCacheIdentifier`; the array `cacheinfo[]` is generated and pulled in via `#include "catalog/syscache_info.h"` (82).
- `SysCache[SysCacheSize]` (87) — global `CatCache *` array, indexed by enum.
- `SysCacheRelationOid[]` / `SysCacheSupportingRelOid[]` (92/96) — sorted dedup'd oid arrays used by `RelationHasSysCache` / `RelationSupportsSysCache`. Built at init via `qsort` + `qunique`.

## Key invariants and locking [HIGH-RISK SECTION]

- **Power-of-2 buckets, unique-index requirement.** Every syscache MUST have an underlying unique index keyed on exactly the cache key. Bucket count must be a power of 2 — `cc_bucket` indexing relies on the bit mask in catcache.c. [from-comment, syscache.c:42-58]
- **DML discipline.** Any code path that mutates a syscache-backed catalog must use `CatalogTupleInsert`/`CatalogTupleUpdate` (not raw `heap_insert`/`heap_update`), so the index gets updated and `CacheInvalidateHeapTuple` runs. Bypassing this breaks cache coherency silently. [from-comment, syscache.c:60-63]
- **`SearchSysCacheLocked1` two-fetch protocol** [HIGHEST-RISK ITEM]. Because inplace updates (e.g. `pg_class.relfrozenxid`) can change tuple contents without changing TID — or worse, change the TID while the cached entry sits stale — locked reads must (1) fetch to find TID, (2) `LockTuple(InplaceUpdateTupleLock)` on that TID, (3) re-fetch, (4) compare TID; if changed, release lock and retry. The 25-line comment block (syscache.c:290-316) documents an explicit race between GRANT, CLUSTER, and VACUUM that the loop defeats. `AcceptInvalidationMessages()` is called *after* acquiring the lock so any pending syscache inval is processed before the next fetch. [from-comment, syscache.c:290-362]
- **`AcceptInvalidationMessages` placement.** Inside `SearchSysCacheLocked1`, called after `LockAcquire` and before the retry fetch. This is the specific gotcha: without it, a finished inplace update could leave a stale cached tuple visible to the loop. [from-comment, syscache.c:353-362]
- **`InitCatalogCachePhase2` is optional.** Syscaches are normally initialized lazily on first use; phase 2 is only triggered when we need to write a relcache init file, to preload the relcache with the most-used catalogs' entries. [from-comment, syscache.c:168-179]
- **`SysCacheInvalidate(cacheId, hashValue)`** is the entry point inval.c calls per pending list entry. It dispatches into `CatCacheInvalidate(SysCache[cacheId], hashValue)`. Special case: `cacheId == -1` would invalidate everything but this is not the path used; cache-wide flush goes through `ResetCatalogCaches` directly. [verified-by-code, syscache.c:691-737]
- **`RelationHasSysCache` / `RelationSupportsSysCache`** binary-search the sorted oid arrays — O(log SysCacheSize). Used by `CacheInvalidateHeapTuple` to skip work for catalogs that have no caches. [verified-by-code, syscache.c:738-790]

## Functions of note

1. **`InitCatalogCache`** (111) — Walks `cacheinfo[]`, calls `InitCatCache` per entry, asserts that every enum slot is filled, sorts the oid lookup arrays. Sets `CacheInitialized = true`. [verified-by-code]
2. **`SearchSysCache` family** (209-261) — Direct forwards to `SearchCatCache{,1,2,3,4}`. Returns the cache copy of the tuple, which **must not be modified**. [from-comment, syscache.c:194-200]
3. **`SearchSysCacheLocked1`** (283) — See invariants above; this is the canonical "I'm about to inplace-update this row" primitive. Used by GRANT, ALTER TABLE rolepublic, etc.
4. **`SearchSysCacheCopy`** (375) — Wraps `SearchSysCache + heap_copytuple + ReleaseSysCache`. Returned tuple is owned by caller and must be `heap_freetuple`d. Use this whenever you intend to modify the tuple.
5. **`SysCacheGetAttr`** (596) — Extracts one attribute from a syscache tuple, using the cache's known tupdesc. `SysCacheGetAttrNotNull` (626) asserts non-null.
6. **`SysCacheInvalidate`** (691) — One-line dispatcher; the work is in catcache.

## Cross-references

- **Called by**: nearly every catalog-aware path in the backend — lsyscache.c, relcache.c, parser, executor, etc.
- **Calls out to**: catcache.c (everything), inval.c (`AcceptInvalidationMessages` in the Locked path), lmgr.c (`LockAcquire`/`LockRelease` with LOCKTAG_TUPLE).
- **Built by genbki**: `cacheinfo[]` array assembled at compile time from `MAKE_SYSCACHE` declarations sprinkled through `catalog/pg_*.h` headers and emitted into `catalog/syscache_info.h`.

## Open questions

- The locked-read protocol only exists for the 1-key form (`SearchSysCacheLocked1`). Why has the multi-key form not needed it? [unverified — probably because inplace-updated catalogs (pg_class, pg_database) are all keyed by single oid.]
- `RelationInvalidatesSnapshotsOnly` asserted false for every syscache reloid — does the syscache layer rely on this for correctness or just for sanity? [unverified]

## Confidence tag tally

verified-by-code: 7 — from-comment: 8 — from-readme: 0 — inferred: 0 — unverified: 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
