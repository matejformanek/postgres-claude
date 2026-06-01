# attoptcache.c

- **Source path:** `source/src/backend/utils/cache/attoptcache.c`
- **Lines:** 206
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `attoptcache.h`, `access/reloptions.h` (`attribute_reloptions` parser), `relcache.c` (which handles the fixed-size pg_attribute parts; attoptcache only handles the variable-length options blob).

## Purpose

Caches the parsed form of `pg_attribute.attoptions` (per-column storage params like `n_distinct`, `n_distinct_inherited`). Separated from relcache because the parsed-options blob is variable-size and not needed by every relcache reader. [from-comment, attoptcache.c:6-8]

## Top-of-file comment

> "Attribute options are cached separately from the fixed-size portion of pg_attribute entries, which are handled by the relcache." [attoptcache.c:3-7]

## Public surface

- `get_attribute_options(Oid attrelid, int attnum)` (132) — returns a freshly-palloc'd `AttributeOpts *` (or NULL) in caller's memory context.
- Static helpers: `InitializeAttoptCache` (98), `InvalidateAttoptCacheCallback` (53), `relatt_cache_syshash` (85).

## Key types / structs

- `AttoptCacheKey` (32) — `{Oid attrelid; int attnum;}`, must be at offset 0 of the entry.
- `AttoptCacheEntry` (38) — `{AttoptCacheKey key; AttributeOpts *opts;}`.
- Global `AttoptCacheHash` (29).

## Key invariants and locking

- **Per-tuple invalidation via shared hash.** The cache's own hash function `relatt_cache_syshash` is `GetSysCacheHashValue2(ATTNUM, attrelid, attnum)` so it agrees with the ATTNUM syscache's hashvalue space. This lets `InvalidateAttoptCacheCallback` use `hash_seq_init_with_hash_value` for **O(1)-on-average targeted invalidation** instead of a full sweep. [from-comment, attoptcache.c:106-110; verified-by-code]
- **Entry-creation ordering.** `get_attribute_options` MUST do the `SearchSysCache2` + `ReleaseSysCache` BEFORE inserting into the cache hash, because the catalog read can trigger a cache flush — if we inserted first, the flush would tear out our new entry. [from-comment, attoptcache.c:190-192]
- **Result is a fresh copy.** Caller gets `palloc`'d memory in their current context; the cache retains the canonical copy in `CacheMemoryContext`. Pointer stability requirement: returned pointer is safe to keep through the immediate use but NOT across cache-flush events.
- **Hashvalue 0 = full sweep** convention is honored (line 64-67).

## Functions of note

1. **`get_attribute_options`** (132) — lazy init of the hash; lookup; on miss, fetch ATTNUM, parse with `attribute_reloptions`, store; return a fresh palloc'd copy.
2. **`InvalidateAttoptCacheCallback`** (53) — pfrees the `opts` blob, removes the entry; the next `get_attribute_options` will rebuild.

## Cross-references

- **Called by**: planner (statistics handling), `vacuumlazy.c`, `analyze.c` (e.g. for `n_distinct` overrides).
- **Calls into**: syscache (`ATTNUM`), `attribute_reloptions` (reloptions.c), inval.c (callback registration).

## Open questions

None of note — file is small and self-contained.

## Confidence tag tally

verified-by-code: 4 — from-comment: 3 — from-readme: 0 — inferred: 0 — unverified: 0
