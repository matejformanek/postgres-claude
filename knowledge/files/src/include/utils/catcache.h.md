# catcache.h

- **Source path:** `source/src/include/utils/catcache.h`
- **Lines:** 234
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catcache.c` (impl), `syscache.h` (named-cache enum), `inval.h` (`PrepareToInvalidateCacheTuple` callback type).

## Purpose

Defines the low-level catcache structs (`CatCache`, `CatCTup`, `CatCList`, `CatCacheHeader`), the `CATCACHE_MAXKEYS = 4` constant, the hash/equality function-pointer types, and the public API surface (`InitCatCache`, `SearchCatCache{,1,2,3,4}`, `ReleaseCatCache`, `SearchCatCacheList`, etc.).

## Top-of-file comment (verbatim)

> "Low-level catalog cache definitions. NOTE: every catalog cache must have a corresponding unique index on the system table that it caches --- ie, the index must match the keys used to do lookups in this cache. All cache fetches are done with indexscans (under normal conditions). The index should be unique to guarantee that there can only be one matching row for a key combination." [catcache.h:3-11]

## Public surface

- Constants: `CATCACHE_MAXKEYS = 4` (35), `CT_MAGIC = 0x57261502` (99), `CL_MAGIC = 0x52765103` (166).
- Types: `CCHashFN` (39), `CCFastEqualFN` (42), `CatCache` (44), `CatCTup` (88), `CatCList` (157), `CatCacheHeader` (186).
- Globals: `CacheMemoryContext` (PGDLLIMPORT, 194) — note "this extern duplicates utils/memutils.h".
- Functions: `CreateCacheMemoryContext`, `InitCatCache`, `InitCatCachePhase2`, `SearchCatCache{,1,2,3,4}`, `ReleaseCatCache`, `GetCatCacheHashValue`, `SearchCatCacheList`, `ReleaseCatCacheList`, `ResetCatalogCaches`, `ResetCatalogCachesExt`, `CatalogCacheFlushCatalog`, `CatCacheInvalidate`, `PrepareToInvalidateCacheTuple`.

## Key types / structs

- **`CatCache`** (44) — per-cache control. Fields: `id`, `cc_nbuckets`, `cc_tupdesc`, `cc_bucket` (dlist heads), `cc_hashfunc[4]`, `cc_fastequal[4]`, `cc_keyno[4]`, `cc_nkeys`, `cc_ntup`, `cc_nlist`, `cc_nlbuckets`, `cc_lbucket`, `cc_relname`, `cc_reloid`, `cc_indexoid`, `cc_relisshared`, `cc_next` (slist link), `cc_skey[4]`. Under `CATCACHE_STATS`: `cc_searches/cc_hits/cc_neg_hits/cc_newloads/cc_invals/cc_lsearches/cc_lhits`. Stats fields are at the END to preserve ABI when CATCACHE_STATS not defined. [from-comment, catcache.h:67-70]
- **`CatCTup`** (88) — individual cached tuple. `cache_elem` (dlist_node — first field, for Valgrind reachability), `ct_magic`, `hash_value`, `keys[4]`, `refcount`, `dead`, `negative`, `tuple` (HeapTupleData), `c_list` (parent CatCList or NULL), `my_cache`. Comment at 110-119 explains the dead/negative semantics. [from-comment]
- **`CatCList`** (157) — multi-row result of a partial-key search. `cache_elem` (first), `cl_magic`, `hash_value`, `keys[4]`, `refcount`, `dead`, `ordered` (whether members are in index order — false during bootstrap/recovery, true otherwise — namespace.c short-circuits when ordered), `nkeys`, `n_members`, `my_cache`, `members[]` (flexible array of CatCTup pointers). Members are pinned by the list's refcount. [from-comment, catcache.h:141-156]
- **`CatCacheHeader`** (186) — `ch_caches` (slist of all CatCaches), `ch_ntup` (sum over all caches).

## Key invariants

- **Unique index requirement** restated here as the top NOTE. Cache fetches use indexscans under normal conditions. [from-comment, catcache.h:6-11]
- **Negative entries** are managed identically to positive ones from the dead/refcount POV. [from-comment, catcache.h:116-119]
- **At most one CatCList membership per CatCTup**: a single tuple may appear in multiple lists only by being duplicated; "Currently, that's not expected to be common, so we accept the potential inefficiency." [from-comment, catcache.h:127-131]
- **dlist_node first** (in both CatCTup and CatCList) so Valgrind can trace reachability through the bucket linkage. [from-comment, catcache.h:91-94, 160-162]

## Confidence tag tally

verified-by-code: 1 — from-comment: 6 — from-readme: 0 — inferred: 0 — unverified: 0
