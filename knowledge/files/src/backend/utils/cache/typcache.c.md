# typcache.c

- **Source path:** `source/src/backend/utils/cache/typcache.c`
- **Lines:** 3228
- **Last verified commit:** `031904048aa2`
- **Companion files:** `typcache.h`, `lsyscache.c` (basic pg_type lookups), `relcache.c` (relid→composite-typid link), `executor/spi.c` and `array.c`/`record.c` (heavy users), `lib/dshash.c` (shared rowtype typmod registry for parallel workers).

## Purpose

Type cache. Memoizes things that pg_type alone doesn't give you: default btree/hash opclasses, equality/comparison/hashing function oids, array element properties, record field properties, domain constraint trees, rowtype TupleDescs and the typmod allocation for anonymous record types. **Entries are immortal** — once created, they live for the life of the backend. [from-comment, typcache.c:6-23]

## Top-of-file comment (verbatim — load-bearing paragraphs)

> "Once created, a type cache entry lives as long as the backend does, so there is no need for a call to release a cache entry. If the type is dropped, the cache entry simply becomes wasted storage. This is not expected to happen often, and assuming that typcache entries are good permanently allows caching pointers to them in long-lived places." [typcache.c:19-23]

> "We have some provisions for updating cache entries if the stored data becomes obsolete. Core data extracted from the pg_type row is updated when we detect updates to pg_type. Information dependent on opclasses is cleared if we detect updates to pg_opclass. We also support clearing the tuple descriptor and operator/function parts of a rowtype's cache entry, since those may need to change as a consequence of ALTER TABLE. Domain constraint changes are also tracked properly." [typcache.c:25-31]

## Public surface

- **Core**: `lookup_type_cache` (389) — flag-driven lazy fill of a `TypeCacheEntry`.
- **Rowtype/typmod**: `lookup_rowtype_tupdesc` (1949), `lookup_rowtype_tupdesc_noerror` (1966), `lookup_rowtype_tupdesc_copy` (1983), `lookup_rowtype_tupdesc_domain` (2005), `assign_record_type_typmod` (2069), `SharedRecordTypmodRegistryInit` (2224).
- **Domain constraints**: `InitDomainConstraintRef` (1406), `UpdateDomainConstraintRef` (1444), `DomainHasConstraints` (1497).
- **Inval callbacks (static)**: `TypeCacheRelCallback` (2447), `TypeCacheTypCallback` (2543), `TypeCacheOpcCallback` (2600), `TypeCacheConstrCallback` (2638).

## Key types / structs

- `TypeCacheEntry` (in `typcache.h`) — fat struct: type_id, type_id_hash, typbyval/typlen/typalign/typstorage, typtype, typrelid (for composites), eq_opr/lt_opr/gt_opr/cmp_proc/hash_proc + their FmgrInfos, btree_opf/hash_opf, range/multirange links, domain_constraints, tupDesc (for composites), `flags` bitmask (`TCFLAGS_*`).
- `RelIdToTypeIdCacheEntry` — secondary map relid → composite_typid, used by `TypeCacheRelCallback` to find the composite typcache entry from a pg_class relid. Static `RelIdToTypeIdCacheHash`.
- `DomainConstraintRef` — caller-held handle; refreshed via `UpdateDomainConstraintRef`. Domain entries thread together via `nextDomain` for cheap iteration in `TypeCacheConstrCallback`.
- `SharedRecordTypmodRegistry` — dshash-based shared registry of anonymous rowtype typmods, so parallel workers can decode RECORD tuples.

## Key invariants and locking

- **Pointer stability is a contract.** Because entries are never freed, callers may cache `TypeCacheEntry *` pointers in long-lived places (planner state, executor state). [from-comment, typcache.c:19-23]
- **Flags-driven lazy fill.** `lookup_type_cache(type_id, flags)` does the cheap hashtable lookup then only computes the bits the caller asked for; flags like `TYPECACHE_EQ_OPR`, `TYPECACHE_BTREE_OPFAMILY`, `TYPECACHE_HASH_PROC`, etc. drive which fields to populate. Cached "I tried and there isn't one" results use a `TCFLAGS_CHECKED_*` flag to avoid recomputation. [verified-by-code, typcache.c:389ff]
- **Inval scheme**: three-callback design.
  1. `TypeCacheTypCallback` (2543) — pg_type row changed → clear `TCFLAGS_HAVE_PG_TYPE_DATA` (and domain-constraint-checked flag if applicable). Drives by hash_value; uses `hash_seq_init_with_hash_value` to skip non-matching entries. Hashvalue 0 = full sweep. [verified-by-code]
  2. `TypeCacheOpcCallback` (2600) — pg_opclass row changed → clear `TCFLAGS_OPERATOR_FLAGS` on ALL entries. Coarse but pg_opclass updates are rare. **Does not watch pg_amop/pg_amproc** — comment explains why this is safe (cross-type ops can be added/dropped but primary ops cannot). [from-comment, typcache.c:2595-2596]
  3. `TypeCacheRelCallback` (2447) — relcache event for `relid` → invalidate composite type whose `typrelid == relid` (via `RelIdToTypeIdCacheHash`). Also visits every domain entry (linked-listed via `firstDomainTypeEntry`/`nextDomain`) and resets operator flags if the domain is over a composite. `relid == InvalidOid` sweeps all composites + domain-over-composite. This is **how composite-type caches stay in sync with ALTER TABLE**. [verified-by-code, typcache.c:2447-2532; from-comment]
  4. `TypeCacheConstrCallback` (2638) — pg_constraint changed → walk only the threaded domain list. "It's slightly annoying that we can't tell whether the inval event was for a domain constraint record or not." [from-comment]
- **Composite-type relcache linkage.** When you `lookup_type_cache` on a composite typid, the secondary `RelIdToTypeIdCacheHash` gets a row keyed by `typrelid → composite_typid` so future `TypeCacheRelCallback(relid)` events can find the typcache entry in O(1). Entries are deleted when typcache entry no longer has anything to clean (`delete_rel_type_cache_if_needed`).
- **Anonymous RECORD typmods.** `assign_record_type_typmod` allocates a fresh typmod for an ad-hoc tupdesc; the registry is per-backend but with `SharedRecordTypmodRegistry` parallel workers can share it. [verified-by-code, typcache.c:2067ff, 2222ff]
- **Domain constraint freshness.** `InitDomainConstraintRef` returns a `DomainConstraintRef` (caller's handle); the constraint list pointer is filled by `UpdateDomainConstraintRef`, which respects `TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS`. Constraints expressions are stored as ready-to-run expression states in long-lived memory. [verified-by-code, typcache.c:1406-1497]
- **OOM-resilient lazy initialization (re-entry safe).** `lookup_type_cache`'s first-time setup is split into independent `if (X == NULL)` steps — `TypeCacheHash`, `RelIdToTypeIdCacheHash`, `CacheMemoryContext`, then the `in_progress_list` allocation (deliberately *last* of the allocations), and finally the four SI-invalidation callback registrations (which "can fail only with a FATAL error"). If any allocation throws (e.g. OOM), a later re-entry finds the already-done steps intact and completes the rest, rather than leaving the cache half-initialized. The static `in_progress_list` (`:226-228`, reserved 4 slots, doubled via `repalloc` when full at `:453-460`) records the `type_id`s currently mid-lookup so invalidations arriving *during* a fill can be applied to in-progress entries. [verified-by-code, typcache.c:395-460 @ `031904048aa2`; added by 73dab12719ee "Make type cache initialization more resilient on re-entry after OOM", in this anchor batch]

## Functions of note

1. **`lookup_type_cache`** (389) — the entry point. Big function that, depending on flags, fetches pg_type row, fills typbyval/typlen, resolves default btree/hash opclass via `GetDefaultOpClass`, then looks up the comparison/equality/hash operators and functions via syscache, threads domains and ranges onto their respective lists.
2. **`assign_record_type_typmod`** (2069) — given a fresh anonymous tupdesc, search the registry for a match; if none, allocate a new typmod and insert. Critical for RECORD function returns and composite literals.
3. **`lookup_rowtype_tupdesc_internal`** (1855) — resolve `(type_id, typmod) → TupleDesc`. For named composites uses relcache; for anonymous RECORD uses the typmod registry; for domain over composite recurses.
4. **`TypeCacheRelCallback`** (2447) — see above. Most surprising part: domain entries iterated through `nextDomain` chain rather than full hash scan, for perf.
5. **`TypeCacheTypCallback`** (2543) — uses `hash_seq_init_with_hash_value` for targeted iteration — only the buckets a given hashvalue could land in get visited. [verified-by-code, typcache.c:2558]
6. **`DomainHasConstraints`** (1497) — drives volatility analysis in the optimizer; populates `*has_volatile` for caller.

## Cross-references

- **Called by**: array.c / arrayfuncs.c (`array_eq`, `hash_array` etc.), record.c (`record_cmp`, `record_eq`, `hash_record`), planner (sort/group operator resolution), executor (plpgsql RECORD-typmod assignment), CHECK constraint evaluator (domain constraints).
- **Calls into**: syscache (`TYPEOID`, `OPEROID`, etc.), lsyscache (`GetDefaultOpClass`), relcache (for composite typrelid resolution), inval.c (callbacks).

## Open questions

- The shared-record-typmod-registry uses `dshash`; under heavy parallel queries with many anonymous RECORDs, is the dshash contention a known issue? [unverified]
- Domain-over-composite inval path resets `TCFLAGS_OPERATOR_FLAGS` even for unrelated composites. Acceptable today; would tightening be possible? [from-comment notes this is intentional simplification]

## Confidence tag tally

verified-by-code: 10 — from-comment: 7 — from-readme: 0 — inferred: 0 — unverified: 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
