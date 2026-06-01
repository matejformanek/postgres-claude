# inval.h

- **Source path:** `source/src/include/utils/inval.h`
- **Lines:** 104
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `inval.c` (impl), `catalog/syscache_ids.h`, `storage/relfilelocator.h`, `relcache.h`.

## Purpose

Public surface of the cache-invalidation dispatcher. Declares the `debug_discard_caches` GUC, the three callback-function types (`SyscacheCallbackFunction`, `RelcacheCallbackFunction`, `RelSyncCallbackFunction`), and the transactional + nontransactional inval entry points.

## Top-of-file comment

> "POSTGRES cache invalidation dispatcher definitions." [inval.h:3-4]

## Public surface

- **Globals**: `debug_discard_caches` (PGDLLIMPORT, 22) — int GUC; bounds defined by `MIN_DEBUG_DISCARD_CACHES`/`DEFAULT_DEBUG_DISCARD_CACHES`/`MAX_DEBUG_DISCARD_CACHES`. When `DISCARD_CACHES_ENABLED` is NOT defined at compile time, default and max are both 0. Compile-time defines `CLOBBER_CACHE_ALWAYS` ⇒ default 1; `CLOBBER_CACHE_RECURSIVELY` ⇒ default 3. Max under DISCARD_CACHES_ENABLED is 5. [verified-by-code, inval.h:22-39]
- **Callback typedefs**: `SyscacheCallbackFunction(arg, cacheid, hashvalue)` (42), `RelcacheCallbackFunction(arg, relid)` (44), `RelSyncCallbackFunction(arg, relid)` (45).
- **Driver**: `AcceptInvalidationMessages`.
- **Transactional**: `AtEOXact_Inval(bool isCommit)`, `AtEOSubXact_Inval(bool isCommit)`, `PostPrepare_Inval`, `CommandEndInvalidationMessages`.
- **Inplace bracket**: `PreInplace_Inval`, `AtInplace_Inval`, `ForgetInplace_Inval`.
- **Producer entry points**: `CacheInvalidateHeapTuple(rel, tuple, newtuple)`, `CacheInvalidateHeapTupleInplace(rel, key_equivalent_tuple)`, `CacheInvalidateCatalog(catalogId)`, `CacheInvalidateRelcache(rel)`, `CacheInvalidateRelcacheAll`, `CacheInvalidateRelcacheByTuple(classTuple)`, `CacheInvalidateRelcacheByRelid(relid)`, `CacheInvalidateRelSync(relid)`, `CacheInvalidateRelSyncAll`, `CacheInvalidateSmgr(rlocator)`, `CacheInvalidateRelmap(databaseId)`.
- **Callback registration**: `CacheRegisterSyscacheCallback`, `CacheRegisterRelcacheCallback`, `CacheRegisterRelSyncCallback`.
- **Callback firing**: `CallSyscacheCallbacks`, `CallRelSyncCallbacks`.
- **Full sweep**: `InvalidateSystemCaches`, `InvalidateSystemCachesExtended(bool debug_discard)`.
- **Logical decoding**: `LogLogicalInvalidations`.

## Key invariants

- **`debug_discard_caches`** is the standard knob for stress-testing cache invalidation. Forcing a flush on every `AcceptInvalidationMessages` shakes out stale-pointer bugs (this is the modern replacement for the old compile-time `CLOBBER_CACHE_ALWAYS` / `CLOBBER_CACHE_RECURSIVELY` macros, whose values map to 1 and 3 respectively). [verified-by-code, inval.h:26-39]
- **Three callback flavors with distinct signatures.** Sys-cache callbacks get the SysCacheIdentifier + hashvalue (hashvalue=0 means "all entries"); relcache callbacks get the relid (InvalidOid means "all"); relsync is the publication/subscription bridge.

## Confidence tag tally

verified-by-code: 2 — from-comment: 1 — from-readme: 0 — inferred: 0 — unverified: 0
