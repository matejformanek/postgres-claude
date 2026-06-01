# ts_cache.h

- **Source path:** `source/src/include/tsearch/ts_cache.h`
- **Lines:** 96
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `ts_cache.c` (impl, lives under `backend/utils/cache/` despite the header being in `tsearch/`).

## Purpose

Declares the per-tsearch-object cache entry structs and the three `lookup_ts_*_cache` accessors. Each struct has a common-header field layout (`objId` + `isvalid`) so the shared inval callback can iterate any hashtable with the same code; this is captured by `TSAnyCacheEntry` (23).

## Top-of-file comment

> "Tsearch related object caches." [ts_cache.h:3-4]

## Public surface

- **Common header type**: `TSAnyCacheEntry` (23) — `{Oid objId; bool isvalid;}`. ALL three real entry types must begin with these fields in the same order. [from-comment, ts_cache.h:19-22]
- **`TSParserCacheEntry`** (30) — parser methods (startOid/tokenOid/endOid/headlineOid/lextypeOid) and pre-resolved `FmgrInfo`s for the four most-called ones (prsstart, prstoken, prsend, prsheadline).
- **`TSDictionaryCacheEntry`** (51) — dict lexize Oid + FmgrInfo plus a `MemoryContext dictCtx` holding the dict's private data (`dictData`).
- **`ListDictionary`** (65) — `{int len; Oid *dictIds;}`; one entry of the per-token-type dict list for a config.
- **`TSConfigCacheEntry`** (71) — `cfgId`, `isvalid`, `prsId`, `lenmap`, `map` (array of ListDictionary indexed by token type).
- **GUC**: `TSCurrentConfig` (PGDLLIMPORT, 87) — current `default_text_search_config` value.
- **Functions**: `lookup_ts_parser_cache`, `lookup_ts_dictionary_cache`, `lookup_ts_config_cache`, `getTSCurrentConfig(bool emitError)`.

## Key invariants

- **`objId` MUST BE FIRST** in every entry struct — explicit comments on each (lines 32, 53, 73). This is the hashtable key and also lets the shared callback cast freely. [from-comment]
- **`isvalid` flag** is the cache's "may use this entry" gate; invalidation flips it to false rather than removing the entry, so callers holding a pointer can detect the staleness on next lookup.

## Confidence tag tally

verified-by-code: 1 — from-comment: 4 — from-readme: 0 — inferred: 0 — unverified: 0
