# Syscache + CatCache — per-backend tuple cache with hash+dlist storage

`syscache.c` exposes a numbered enum (`AUTHOID`, `RELOID`, `TYPEOID`,
`PROCOID`, …) over a layer of `CatCache` instances defined in
`catcache.c`. Each `CatCache` is **one per (catalog, index, key
columns)** combination — `pg_class` keyed by `relname/relnamespace`
(RELNAMENSP) is a different `CatCache` from `pg_class` keyed by `oid`
(RELOID), even though they share the underlying relation.

`SearchSysCache1/2/3/4(cache_id, v1[, v2[, v3[, v4]]])` is the
**universal entry point** for backend code that needs to look up a
single catalog row by key. It:

1. Computes a 32-bit hash from the key values via cached per-key
   `CCHashFN`.
2. Probes the per-cache hash table; walks the bucket's dlist looking
   for a tuple with matching hash + matching keys.
3. On hit: bumps refcount, **moves to front of dlist** (LRU), returns
   the `HeapTuple` pointer.
4. On miss: opens the catalog with `AccessShareLock`, runs a
   `systable_beginscan` using the cache's pre-built ScanKey,
   constructs a `CatCTup`, inserts at front of bucket, returns.
5. If the catalog lookup returns nothing: insert a **negative entry**
   so the next miss is also O(1).

This doc walks the `CatCache` struct, the `SearchCatCacheInternal`
fast path, the `SearchCatCacheMiss` slow path (including the
`AcceptInvalidationMessages`-during-TOAST retry), the **partial-key
list-search** API (`SearchCatCacheList` → `CatCList`), and the
`CatCacheInvalidate` hash-targeted eviction the sinval layer calls.

Companion docs:
- [[syscache-invalidation-flow]] — how `CatCacheInvalidate` gets called via the inval queue.
- [[relcache-build]] — sibling cache for `RelationDesc`s.
- [[cache-invalidation-registration]] — the `CacheRegister*Callback` registration API.
- [[sinvaladt-broadcast]] — the shared-inval queue beneath.

## Anchors

- `source/src/backend/utils/cache/catcache.c:1-100` — banner + module setup.
- `source/src/backend/utils/cache/catcache.c:44-110` — `CatCInProgress` stack (race-detection for in-build entries).
- `source/src/backend/utils/cache/catcache.c:642-710` — `CatCacheInvalidate` (the sinval callback target).
- `source/src/backend/utils/cache/catcache.c:895-1090` — `InitCatCache` (constructor).
- `source/src/backend/utils/cache/catcache.c:1147-1253` — `CatalogCacheInitializeCache` (phase-2 setup; runs lazily on first use).
- `source/src/backend/utils/cache/catcache.c:1371-1521` — `SearchCatCacheInternal` (the hot path).
- `source/src/backend/utils/cache/catcache.c:1530-1665` — `SearchCatCacheMiss` (slow path with retry).
- `source/src/backend/utils/cache/catcache.c:1718-1733` — `GetCatCacheHashValue`.
- `source/src/backend/utils/cache/catcache.c:1750-2120` — `SearchCatCacheList` (partial-key result).
- `source/src/include/utils/catcache.h:44-183` — struct definitions (`CatCache`, `CatCTup`, `CatCList`).
- `source/src/include/utils/syscache.h` — `SysCacheIdentifier` enum, declarations of `SearchSysCache*`.

## Struct hierarchy

```c
/* catcache.h:44 — one per (catalog, index, key columns) tuple */
typedef struct catcache {
    int             id;                                 /* SysCacheIdentifier */
    int             cc_nbuckets;                        /* power of 2 */
    TupleDesc       cc_tupdesc;
    dlist_head     *cc_bucket;                          /* the hash table */
    CCHashFN        cc_hashfunc[CATCACHE_MAXKEYS];      /* per-key hash fn */
    CCFastEqualFN   cc_fastequal[CATCACHE_MAXKEYS];     /* per-key eq fn */
    int             cc_keyno[CATCACHE_MAXKEYS];         /* attno in catalog */
    int             cc_nkeys;                           /* 1..4 */
    int             cc_ntup, cc_nlist;
    int             cc_nlbuckets;
    dlist_head     *cc_lbucket;                         /* list-search hash */
    const char     *cc_relname;
    Oid             cc_reloid, cc_indexoid;
    bool            cc_relisshared;
    slist_node      cc_next;                            /* in CacheHdr->ch_caches */
    ScanKeyData     cc_skey[CATCACHE_MAXKEYS];          /* precomputed */
} CatCache;
```

```c
/* catcache.h:88 — one per cached tuple */
typedef struct catctup {
    dlist_node      cache_elem;                         /* in cc_bucket[h] dlist */
    int             ct_magic;                           /* 0x57261502 */
    uint32          hash_value;
    Datum           keys[CATCACHE_MAXKEYS];             /* point into tuple for + entries */
    int             refcount;
    bool            dead, negative;
    HeapTupleData   tuple;
    struct catclist *c_list;                            /* if a list member */
    CatCache       *my_cache;
    /* tuple data follows, unless negative */
} CatCTup;
```

```c
/* catcache.h:157 — partial-key result set */
typedef struct catclist {
    dlist_node      cache_elem;                         /* in cc_lbucket[h] */
    int             cl_magic;                           /* 0x52765103 */
    uint32          hash_value;
    Datum           keys[CATCACHE_MAXKEYS];
    int             refcount;
    bool            dead, ordered;
    short           nkeys;                              /* < cc_nkeys */
    int             n_members;
    CatCache       *my_cache;
    CatCTup        *members[FLEXIBLE_ARRAY_MEMBER];
} CatCList;
```

The `dlist_node` is **first in CatCTup** "so that Valgrind understands
the struct is reachable" via the per-bucket dlist head. Same for
`CatCList`. The magic constants distinguish the two on free-list
traversals. [from-comment] (`catcache.h:90-94`, `catcache.h:159-164`).

## Hash table layout

```
CatCache (e.g. for RELOID = pg_class keyed by oid)
  cc_nbuckets = 256  (power of 2)
  cc_bucket[256]: array of dlist_head
       ↓ each head links to a chain of CatCTup
       dlist_head ←→ CatCTup{hash=h1, keys=[oid1], tuple=t1} ←→ CatCTup{hash=h2, keys=[oid2], ...} ...

  cc_lbucket[16..N]: array of dlist_head for partial-key list results
       ↓ each head links a chain of CatCList
       dlist_head ←→ CatCList{nkeys=1, members[]} ←→ ...
```

`HASH_INDEX(h, sz) = h & (sz - 1)` (power-of-2 mask)
[verified-by-code] (`catcache.c:70`).

## The fast path — SearchCatCacheInternal

```c
/* catcache.c:1422 (abridged) */
static inline HeapTuple
SearchCatCacheInternal(CatCache *cache, int nkeys, Datum v1, v2, v3, v4) {
    ConditionalCatalogCacheInitializeCache(cache);    /* lazy first-use init */

    arguments[] = {v1, v2, v3, v4};
    hashValue = CatalogCacheComputeHashValue(cache, nkeys, v1, v2, v3, v4);
    hashIndex = HASH_INDEX(hashValue, cache->cc_nbuckets);

    bucket = &cache->cc_bucket[hashIndex];
    dlist_foreach(iter, bucket) {
        ct = dlist_container(CatCTup, cache_elem, iter.cur);
        if (ct->dead) continue;                       /* skip tombstones */
        if (ct->hash_value != hashValue) continue;    /* quick hash skip */
        if (!CatalogCacheCompareTuple(cache, nkeys, ct->keys, arguments))
            continue;                                  /* full key compare */

        /* HIT: move-to-front LRU */
        dlist_move_head(bucket, &ct->cache_elem);

        if (!ct->negative) {
            ResourceOwnerEnlarge(CurrentResourceOwner);
            ct->refcount++;
            ResourceOwnerRememberCatCacheRef(CurrentResourceOwner, &ct->tuple);
            return &ct->tuple;
        }
        return NULL;                                   /* negative hit */
    }
    return SearchCatCacheMiss(cache, nkeys, hashValue, hashIndex, v1, v2, v3, v4);
}
```

Three key properties:

1. **Triple-filter walk** — `dead` check, then `hash_value` quick
   compare (fits in a cache-line), then full-key compare. The hash
   check exists because `dlist_foreach` is doing a linear scan of the
   bucket, and most chain members will hash-mismatch
   immediately. [verified-by-code] (`catcache.c:1471-1478`).
2. **Move-to-front** — `dlist_move_head(bucket, &ct->cache_elem)`. The
   bucket is LRU-ordered; frequently accessed entries cluster near the
   head. Cheap O(1) under the dlist primitive. [from-comment]
   (`catcache.c:1481-1485`).
3. **Refcount + ResourceOwner** — every returned tuple bumps refcount.
   The `ResourceOwnerRememberCatCacheRef` ties the reference to the
   current `ResourceOwner`, so an error path's resource-owner cleanup
   will auto-`ReleaseCatCache` everything we forgot.

The "negative entry as O(1) miss" pattern is what makes pg_xxx_isnull
type queries cheap: the first lookup populates a negative entry, all
subsequent lookups short-circuit at the bucket walk.

## The slow path — SearchCatCacheMiss

```c
/* catcache.c:1530 (skeleton) */
static pg_noinline HeapTuple
SearchCatCacheMiss(CatCache *cache, int nkeys, hashValue, hashIndex,
                   v1, v2, v3, v4)
{
    relation = table_open(cache->cc_reloid, AccessShareLock);

    /* Copy precomputed ScanKey, fill argument datums */
    memcpy(cur_skey, cache->cc_skey, sizeof(ScanKeyData) * nkeys);
    cur_skey[0].sk_argument = v1;
    ...

    do {
        scandesc = systable_beginscan(relation, cache->cc_indexoid,
                                      IndexScanOK(cache), NULL, nkeys, cur_skey);
        ct = NULL; stale = false;

        while ((ntp = systable_getnext(scandesc))) {
            ct = CatalogCacheCreateEntry(cache, ntp, NULL, hashValue, hashIndex);
            if (ct == NULL) {                          /* stale during detoast */
                stale = true; break;
            }
            ResourceOwnerEnlarge(CurrentResourceOwner);
            ct->refcount++;
            ResourceOwnerRememberCatCacheRef(...);
            break;                                     /* unique-key, one match */
        }
        systable_endscan(scandesc);
    } while (stale);

    table_close(relation, AccessShareLock);

    if (ct == NULL) {                                  /* no row found */
        if (IsBootstrapProcessingMode()) return NULL;  /* no neg cache during bootstrap */
        ct = CatalogCacheCreateEntry(cache, NULL, arguments, hashValue, hashIndex);
        return NULL;
    }
    return &ct->tuple;
}
```

The `do { ... } while (stale)` retry handles a subtle race: while
`CatalogCacheCreateEntry` detoasts the catalog tuple (which involves
opening a TOAST table and thus another `AcceptInvalidationMessages`
opportunity), an inval message may arrive for **this very tuple**. The
in-progress entry detects this via the `CatCInProgress` stack and
sets `dead = true`; the create call returns NULL; we restart the
scan. [from-comment] (`catcache.c:1568-1574`).

The "no negative entries in bootstrap" rule (`IsBootstrapProcessingMode`)
is the explicit exception: bootstrap can't process inval messages
(machinery isn't alive yet), so a negative entry would never clear
when the row is later created. [from-comment] (`catcache.c:1626-1629`).

`IndexScanOK(cache)` decides whether to use the index or fall back to a
seq scan — false during early initialization when the system catalog
indexes themselves aren't yet usable.

## The `CatCInProgress` stack — invalidation during build

```c
/* catcache.c:44-61 */
typedef struct CatCInProgress {
    CatCache             *cache;
    uint32                hash_value;
    bool                  list;
    bool                  dead;
    struct CatCInProgress *next;
} CatCInProgress;

static CatCInProgress *catcache_in_progress_stack = NULL;
```

The stack tracks entries currently being built. When `CatCacheInvalidate`
fires for a `(cache, hashValue)`, it walks this stack and marks any
matching in-progress entry as `dead`:

```c
/* catcache.c:701-709 */
for (CatCInProgress *e = catcache_in_progress_stack; e != NULL; e = e->next) {
    if (e->cache == cache) {
        if (e->list || e->hash_value == hashValue)
            e->dead = true;
    }
}
```

The `e->list` clause means: any *list* search in this cache is
clobbered by any inval in this cache (list searches build on top of
N tuple lookups, so even one bad tuple kills the list). Tuple searches
only invalidate on exact-hash match. The `CatalogCacheCreateEntry`
caller detects `dead = true` and returns NULL, triggering the retry.

## CatCacheInvalidate — the sinval drop site

`CatCacheInvalidate(cache, hashValue)` is called by `inval.c` when a
catcache message arrives in the inval queue (see
[[syscache-invalidation-flow]]):

```c
/* catcache.c:642-710 (key parts) */
void CatCacheInvalidate(CatCache *cache, uint32 hashValue) {
    /* Step 1: zap ALL CatCLists (impossible to tell which depend on this hash) */
    for (i = 0; i < cache->cc_nlbuckets; i++) {
        dlist_foreach_modify(iter, &cache->cc_lbucket[i]) {
            cl = dlist_container(CatCList, cache_elem, iter.cur);
            if (cl->refcount > 0) cl->dead = true;
            else CatCacheRemoveCList(cache, cl);
        }
    }

    /* Step 2: zap matching tuples in the relevant bucket */
    hashIndex = HASH_INDEX(hashValue, cache->cc_nbuckets);
    dlist_foreach_modify(iter, &cache->cc_bucket[hashIndex]) {
        ct = dlist_container(CatCTup, cache_elem, iter.cur);
        if (hashValue == ct->hash_value) {
            if (ct->refcount > 0 || (ct->c_list && ct->c_list->refcount > 0))
                ct->dead = true;
            else
                CatCacheRemoveCTup(cache, ct);
        }
    }

    /* Step 3: mark matching in-progress entries dead */
    for (CatCInProgress *e = catcache_in_progress_stack; e; e = e->next) {
        if (e->cache == cache && (e->list || e->hash_value == hashValue))
            e->dead = true;
    }
}
```

Three properties:

1. **Tuple targeting is hash-precise** — only the matching bucket is
   scanned; mismatching tuples in other buckets are untouched.
2. **List targeting is wholesale** — every `CatCList` in the cache
   gets killed because lists are partial-key results and we can't
   prove a list doesn't contain the invalidated tuple without
   scanning every member. [from-comment] (`catcache.c:655-657`).
3. **Refcount > 0 → soft delete** — set `dead = true`, defer
   physical removal until the last reference is released. The
   `dlist_foreach_modify` iterator is safe for this dual-mode
   deletion.

The in-progress-stack zap (step 3) is what catches "we just inserted a
tuple into the cache and then immediately got an inval for that same
tuple before we finished" — the create call returns NULL and the
caller restarts.

## SearchCatCacheList — partial-key fan-out

`SearchCatCacheList(cache, nkeys, v1, v2, v3)` (`catcache.c:1750`)
returns a `CatCList` of *all* matching tuples for a partial key
(`nkeys < cc_nkeys`). Used heavily by code like
`OpernameGetOprid` that needs all operators of a given name regardless
of operand types.

The implementation:

1. **Compute a list-hash** combining only the first `nkeys` key values.
2. **Probe `cc_lbucket`** — same dlist + hash + key-compare pattern as
   single-tuple search.
3. **On miss** — open the catalog, scan via the index for matching
   rows, build one `CatCTup` per row (some may be cache hits from
   earlier single searches), assemble the `CatCList`, insert at front
   of bucket.

Each `CatCTup` member is part of **at most one** `CatCList`
(`ct->c_list`). The list's refcount must drop to zero (and all
members' refcounts must drop to zero) before physical removal —
captured by the `c_list->refcount` check in `CatCacheInvalidate`.

The "list-search is full-cache invalidation" property is the key
design tradeoff: invalidating one tuple invalidates every list result
that *could* have contained it. Acceptable because lists are far
rarer than tuple searches, and lists are typically short-lived
within a backend command.

## Lazy initialization — `ConditionalCatalogCacheInitializeCache`

Each `CatCache` has a two-phase lifecycle:

- **InitCatCache** (`catcache.c:895`) — called at backend startup;
  allocates the CatCache struct + the initial `cc_bucket[]` array but
  does **not** open the catalog yet. Stores `cc_reloid` and
  `cc_indexoid`.
- **CatalogCacheInitializeCache** (`catcache.c:1147`) — called lazily
  on first `SearchCatCache*` for this cache. Opens the relation, reads
  the tuple descriptor (`cc_tupdesc`), builds the per-key `ScanKey`
  template (`cc_skey[]`). [verified-by-code] (`catcache.c:1442`).

This lazy initialization avoids paying the cost for caches that a
particular backend never uses (e.g. `PUBLICATIONOID` for a non-logical
backend).

## Invariants and races

1. **Move-to-front is O(1) under dlist**; long buckets degrade
   gracefully because hot keys cluster at the front.
2. **`hash_value` quick check before full key-compare** — the chain
   walk is fast even with hash collisions because most chain
   members hash-mismatch. [verified-by-code]
   (`catcache.c:1473-1475`).
3. **`refcount > 0` → defer physical free.** The
   `ResourceOwnerRememberCatCacheRef`/`ResourceOwnerForgetCatCacheRef`
   discipline ensures every search has a matching release at command
   end. [verified-by-code] (`catcache.c:1494-1496`).
4. **Stale-during-build retry** — if an inval arrives mid-build (e.g.
   during TOAST detoast), `CatalogCacheCreateEntry` returns NULL and
   `SearchCatCacheMiss` re-scans. [from-comment] (`catcache.c:1568-1574`).
5. **Negative entries skipped in bootstrap** — no inval machinery to
   clear them. [from-comment] (`catcache.c:1626-1629`).
6. **List inval is wholesale** — one CatCList invalidation per any
   tuple invalidation in the same cache, because we can't prove
   non-membership cheaply. [from-comment] (`catcache.c:655-657`).
7. **`dead` is the soft-tombstone** — set by inval when refcount > 0;
   read by every search ahead of hash/key compare. Physical removal
   happens at refcount-drop or at `CleanupCatalogCache` time.
8. **`ct_magic = 0x57261502`** and `cl_magic = 0x52765103` distinguish
   tuple vs list entries when iterating mixed free lists or doing
   assertion checks. [verified-by-code] (`catcache.h:99,166`).

## Useful greps

```bash
# Every public SearchCatCache* entry point:
grep -nE "^SearchCatCache|^SearchSysCache" \
       source/src/backend/utils/cache/catcache.c \
       source/src/backend/utils/cache/syscache.c

# The CatCache hash + invalidation surface:
grep -nE "CatCacheInvalidate|GetCatCacheHashValue|CatalogCacheCreateEntry|CatCacheRemove" \
       source/src/backend/utils/cache/catcache.c

# All syscache IDs and their (relation, index, key) tuples:
grep -A 4 "static const struct cachedesc" \
       source/src/backend/utils/cache/syscache.c | head -40

# Callers of SearchSysCache (it's everywhere):
grep -c "SearchSysCache" source/src/backend/**/*.c 2>/dev/null | head

# CatCInProgress stack discipline:
grep -n "catcache_in_progress_stack\|CatCInProgress" \
       source/src/backend/utils/cache/catcache.c
```

## Cross-references

- [[syscache-invalidation-flow]] — how `CatCacheInvalidate` gets called from inval queue.
- [[relcache-build]] — sibling cache for whole-relation descriptors.
- [[cache-invalidation-registration]] — public `CacheRegister*Callback` API.
- [[sinvaladt-broadcast]] — the shared queue feeding inval messages.
- `knowledge/subsystems/utils-cache.md` — subsystem-level overview (if exists).
- `source/src/include/utils/syscache.h` — `SysCacheIdentifier` enum.
