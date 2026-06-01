# catcache.c

- **Source path:** `source/src/backend/utils/cache/catcache.c`
- **Lines:** 2500
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catcache.h` (public surface — `CatCache`, `CatCTup`, `CatCList`, `HeapTupleData`-derived macros), `syscache.c` (named-cache table built on top), `inval.c` (calls `CatCacheInvalidate` / `PrepareToInvalidateCacheTuple`), `lsyscache.c` (convenience wrappers).

## Purpose

The low-level system-catalog tuple cache. Each `CatCache` indexes one system table by one specific key combination; rows are cached as `CatCTup` (positive entries) or negative entries (key-only, marks "row absent"). Multi-row results (e.g. all rows matching a non-unique key) are cached as `CatCList`. Every `SearchSysCache*` call in PG bottoms out here. [from-comment, catcache.c:1-13; verified-by-code]

## Top-of-file comment (verbatim)

> "System catalog cache for tuples matching a key." — that single sentence is the entire top-of-file comment. The substantive contract lives instead in catcache.h and in inval.c's top comment. [catcache.c:1-13]

## Public surface

- **Lifecycle / setup**: `CreateCacheMemoryContext` (725), `InitCatCache` (896), `InitCatCachePhase2` (1255), `CatalogCacheInitializeCache` (1147) [static but the core init step].
- **Lookup**: `SearchCatCache` (1372), `SearchCatCache1..4` (1389/1397/1405/1413), `SearchCatCacheList` (1751), `GetCatCacheHashValue` (1718).
- **Release**: `ReleaseCatCache` (1679), `ReleaseCatCacheList` (2125), plus the `WithOwner` variants used by ResourceOwner cleanup.
- **Invalidation (quasi-public — only inval.c should call)**: `CatCacheInvalidate` (643), `ResetCatalogCaches` (816), `ResetCatalogCachesExt` (822), `CatalogCacheFlushCatalog` (852), `PrepareToInvalidateCacheTuple` (2403).
- **Internal but important**: `SearchCatCacheMiss` (1531), `SearchCatCacheInternal` (1423, the inline fast-path), `CatalogCacheCreateEntry` (2165), `RehashCatCache` (1003), `RehashCatCacheLists` (1048).

## Key types / structs

- `CatCInProgress` (catcache.c:52) — singly linked stack used to detect "the entry I'm building was just invalidated by a sinval message processed during my catalog scan". `dead` flag flips if matched by a `CatCacheInvalidate`. [verified-by-code]
- `CatCacheHeader` (in catcache.h) — global header `CacheHdr` (84). Keeps total tuple count + chain of caches.
- `CatCache`, `CatCTup`, `CatCList` — defined in catcache.h. CatCache has cc_bucket / cc_lbucket arrays (separately sized, separately rehashed), cc_nkeys ≤ CATCACHE_MAXKEYS (= 4), cc_keyno, cc_skey, cc_hashfunc, cc_fastequal, cc_relisshared, cc_reloid, cc_indexoid.
- Hash policy: `HASH_INDEX(h, sz) = h & (sz-1)` (70) — buckets are always a power of two.

## Key invariants and locking [HIGH-RISK SECTION]

- **No shared state.** catcache is **per-backend**. Cross-backend coherency is delivered entirely via sinval messages processed by `inval.c`, which calls `CatCacheInvalidate(cache, hashValue)`. [from-comment, catcache.c:625-641]
- **Invalidation by hash, not by TID.** "We used to try to match positive cache entries by TID, but that is unsafe after a VACUUM FULL on a system catalog: an inval event could be queued before VACUUM FULL, and then processed afterwards, when the target tuple … has a different TID." Now matches purely by hash value, accepting false-positive invalidations. [from-comment, catcache.c:633-638]
- **CatCList wipe-all-on-inval.** Any matching catcache invalidation kills *every* CatCList in the cache, not just lists containing matching tuples — "it's too hard to tell which searches might still be correct". This is conservative but explains why list-style lookups (e.g. amop/opfamily enumeration) churn faster than single-tuple lookups. [from-comment, catcache.c:655-658; verified-by-code, 659-672]
- **Refcount-deferred deletion.** If `refcount > 0` (or the parent list is pinned), an invalidated entry is only marked `dead`; it is freed when the last reference drops. `CATCACHE_FORCE_RELEASE` (build flag) overrides this to free immediately for testing. [verified-by-code, catcache.c:667-692; from-comment, 1673-1677]
- **Recursive-lookup tolerance.** `SearchCatCacheMiss` opens the underlying relation with `AccessShareLock`, and **recursive cache lookups during `table_open` are explicitly allowed** — they may even insert a duplicate of the row we are also fetching. The duplicate ages out; this is documented as cheaper than detecting the case. [from-comment, catcache.c:1559-1567]
- **TOAST-detoast race.** `CatalogCacheCreateEntry` flattens out-of-line toast columns via `toast_flatten_tuple`; that scan can call `AcceptInvalidationMessages`. To avoid handing the caller a stale entry, the in-progress entry is pushed on `catcache_in_progress_stack` with `hash_value` set; if `CatCacheInvalidate` matches, the entry's `dead` flag is set and create returns NULL, forcing `SearchCatCacheMiss` to restart its `systable_beginscan`. [from-comment, catcache.c:1569-1574, 2189-2230; verified-by-code]
- **Negative cache entries** are never made in bootstrap mode (cache inval not running yet would let stale negatives persist). They have `refcount == 0` permanently — the caller never sees them. [from-comment, catcache.c:1621-1652]
- **`CatalogCacheInitializeCache` is delay-initialized.** The CatCache exists from `InitCatCache` time but its tupdesc / skey are not filled until first use, because `pg_class` may not yet be readable. This is the catcache analog of relcache's `criticalRelcachesBuilt` gate. [verified-by-code, catcache.c:1147-1255]
- **Memory context.** All CatCTups live in `CacheMemoryContext`. CatCTup + the heaptuple data are allocated as a single chunk (`MAXALIGN(sizeof(CatCTup)) + dtp->t_len`). [verified-by-code, catcache.c:2234-2247]
- **In-progress detection during list build.** `SearchCatCacheList` registers `list=true` so any inval for the cache kills the list-in-progress regardless of hash. [verified-by-code, catcache.c:701-709]
- **`PrepareToInvalidateCacheTuple` contract.** Called by inval.c during transactional DDL: given an inserted/deleted/updated tuple, recompute the hash value(s) for each relevant catcache and append entries to inval's pending lists. For UPDATE the old and new hashes may differ → two list entries. [from-comment, catcache.c:2368-2401]

## Functions of note

1. **`SearchCatCacheInternal`** (1423, `pg_attribute_always_inline`) — the hot path. Computes hash via `cache->cc_hashfunc(keys)`, walks the bucket dlist with `cc_fastequal`, on hit moves the entry to bucket head (MRU) and increments refcount. Misses fall through to `SearchCatCacheMiss`. [verified-by-code]
2. **`SearchCatCacheMiss`** (1531) — opens the catalog with `AccessShareLock`, does a `systable_beginscan` with `IndexScanOK(cache)`, builds a CatCTup, retries the whole scan if `CatalogCacheCreateEntry` returns NULL (stale-detoast race). Builds a negative entry if scan returned no rows. [verified-by-code]
3. **`CatalogCacheCreateEntry`** (2165) — allocate CatCTup + tuple body, detoast (with in-progress stack), extract keys, push onto bucket head, bump counts, `RehashCatCache` if fill factor > 2. Has a 0.1% random NULL return under `USE_ASSERT_CHECKING` to test the retry path. [verified-by-code, catcache.c:2184-2187]
4. **`CatCacheInvalidate`** (643) — kill every list in the cache; walk one bucket by hash; mark in-progress entries dead. [verified-by-code]
5. **`ResetCatalogCache` / `ResetCatalogCaches`** (753 / 816) — used by sinval-overflow and DISCARD ALL. Marks/removes everything. `debug_discard` mode skips zapping in-progress entries (else `debug_discard_caches` would deadlock on its own infinite retries). [from-comment, catcache.c:747-751]
6. **`SearchCatCacheList`** (1751) — multi-row variant. Builds a CatCList whose members reference (and pin) individual CatCTups, so each list pin keeps tuples alive transitively. [verified-by-code, sketched]

## Cross-references

- **Called by**: `syscache.c` (`SearchSysCache*` is a thin wrapper around `SearchCatCacheN`), `lsyscache.c`, and direct callers throughout the backend.
- **Calls out to**: `genam.c` / `table.c` (`systable_beginscan` for misses), `inval.c` indirectly (`AcceptInvalidationMessages` is the source of in-progress kills), `heaptoast.c` (`toast_flatten_tuple`), `resowner.c` (catcache-ref tracking).

## Open questions

- The 0.1% random NULL test injection in `CatalogCacheCreateEntry` — does any production tunable expose this rate? [unverified — appears to be assert-only.]
- Exact rehash thresholds for `cc_lbucket` vs `cc_bucket` and when each fires [unverified — `RehashCatCacheLists` looks separate from `RehashCatCache`].
- Whether `CATCACHE_FORCE_RELEASE` is actually exercised by buildfarm or only manual stress runs [unverified].

## Confidence tag tally

verified-by-code: 10 — from-comment: 10 — from-readme: 0 — inferred: 0 — unverified: 3
