# ts_cache.c

- **Source path:** `source/src/backend/utils/cache/ts_cache.c`
- **Lines:** 677
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tsearch/ts_cache.h`, `catalog/pg_ts_parser.h`, `catalog/pg_ts_dict.h`, `catalog/pg_ts_template.h`, `catalog/pg_ts_config.h`, `catalog/pg_ts_config_map.h`, `tsearch/*` runtime.

## Purpose

Three parallel caches for tsearch objects: TS parsers, TS dictionaries, TS configurations. Each entry includes parser/dictionary method pointers resolved via `fmgr` and (for configs) the per-token-type mapping array. Plus the `default_text_search_config` GUC mediation. [from-comment, ts_cache.c:6-17]

## Top-of-file comment

> "Tsearch performance is very sensitive to performance of parsers, dictionaries and mapping, so lookups should be cached as much as possible. Once a backend has created a cache entry for a particular TS object OID, the cache entry will exist for the life of the backend; hence it is safe to hold onto a pointer to the cache entry while doing things that might result in recognizing a cache invalidation. Beware however that subsidiary information might be deleted and reallocated somewhere else if a cache inval and reval happens! This does not look like it will be a big problem as long as parser and dictionary methods do not attempt any database access." [ts_cache.c:6-17]

## Public surface

- `lookup_ts_parser_cache(Oid)` (114) — returns `TSParserCacheEntry *`.
- `lookup_ts_dictionary_cache(Oid)` (209) — returns `TSDictionaryCacheEntry *`.
- `lookup_ts_config_cache(Oid)` (388) — returns `TSConfigCacheEntry *`.
- `getTSCurrentConfig(bool emitError)` (559) — resolve `default_text_search_config` GUC to oid.
- GUC hooks: `check_default_text_search_config` (605), `assign_default_text_search_config` (673).

## Key types / structs

- `TSParserCacheEntry`, `TSDictionaryCacheEntry`, `TSConfigCacheEntry` (in tsearch/ts_cache.h). Each has `objId`, validity flag, parser/dict/config-specific fields, and (importantly) **fmgr-resolved method pointers** in `CacheMemoryContext`.
- `TSAnyCacheEntry` — common header used by the shared invalidation callback.
- `MAXTOKENTYPE 256`, `MAXDICTSPERTT 100` — workspace bounds for config build (56-62).
- `lastUsedParser`, `lastUsedDictionary`, `lastUsedConfig` — single-element LRU hints to skip the hash lookup on consecutive accesses to the same object.

## Key invariants and locking

- **Backend-lifetime entries.** Like typcache, once created an entry lives forever. Pointers are stable across the backend lifetime; subsidiary memory (e.g. the mapping array inside a config entry) may be reallocated by inval/reval. [from-comment, ts_cache.c:10-17]
- **Subsidiary info caveat.** Callers may safely keep the top-level entry pointer but **must NOT** keep pointers into the entry's variable-length internals across operations that could trigger a cache flush. [from-comment, ts_cache.c:13-16]
- **No-DB-access contract for methods.** "as long as parser and dictionary methods do not attempt any database access" — invariant relied on for re-entrancy safety. [from-comment, ts_cache.c:16-17]
- **Single callback per hashtable.** `InvalidateTSCacheCallBack` is registered three times (one per HTAB), passing the HTAB pointer as the `arg`. It iterates the relevant table and marks entries dirty. [verified-by-code, ts_cache.c:94-112]
- **Cache-wide coarse inval.** Any change to pg_ts_parser/pg_ts_dict/pg_ts_config/pg_ts_config_map triggers full scan of the affected hash (cheap because few entries). [from-comment, ts_cache.c:83-93]
- **GUC `default_text_search_config` resolution.** `check_default_text_search_config` validates the name at SET time; `assign_default_text_search_config` stashes it. `getTSCurrentConfig` resolves the string to an oid, caching the oid in `TSCurrentConfigCache` until a cache inval invalidates it. [verified-by-code, ts_cache.c:559-700]

## Functions of note

1. **`lookup_ts_config_cache`** (388) — the heaviest builder. Scans `pg_ts_config_map` ordered by `(mapcfg, maptokentype, mapseqno)` and builds the per-token-type dictionary list. Uses the `MAXTOKENTYPE × MAXDICTSPERTT` workspace buffer.
2. **`lookup_ts_parser_cache`** (114) — resolves parser methods via `fmgr_info`/`GetFmgrInfo` (start, gettoken, end, headline, lextype).
3. **`getTSCurrentConfig`** (559) — bridges the GUC string `default_text_search_config` to the configured oid; caches the oid + invalidates on namespace search-path change.
4. **`InvalidateTSCacheCallBack`** (95) — same code for all three caches; selects the table via the `arg` parameter.

## Cross-references

- **Called by**: `tsearch/to_tsvector.c`, `tsearch/ts_parse.c`, `tsearch/ts_locale.c`, `tsearch/wparser.c`, and the `tsvector_*` / `tsquery_*` SQL functions.
- **Calls into**: syscache (`TSPARSEROID`, `TSDICTOID`, `TSCONFIGOID`), genam (`pg_ts_config_map` scan), fmgr (resolving parser/dict method procs).

## Open questions

- The "lastUsed" caching is a single pointer per cache; for workloads alternating between multiple configs, does this micro-optimization hurt or help? [unverified — likely small effect either way]
- Subsidiary-reallocation hazard: under what `lookup_ts_*` patterns could an integrator accidentally trigger an inval that frees the mapping array they just walked into? [unverified; documented but worth a careful reader's audit]

## Confidence tag tally

verified-by-code: 4 — from-comment: 5 — from-readme: 0 — inferred: 0 — unverified: 2
