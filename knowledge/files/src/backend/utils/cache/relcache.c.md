# relcache.c

- **Source path:** `source/src/backend/utils/cache/relcache.c`
- **Lines:** 7021
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `relcache.h` (public surface), `inval.c` (invalidation driver), `syscache.c` / `catcache.c` (catalog row caches consulted while building relcache entries), `relmapper.c` (rd_locator resolution for mapped relations), `partcache.c` (partition descriptor), `typcache.c` (composite-type cache that subscribes to relcache invals).

## Purpose

POSTGRES relation descriptor cache. Maintains one `RelationData` per open relation, keyed by Oid, populated on demand from `pg_class`/`pg_attribute`/`pg_index`/`pg_am`/`pg_constraint`/etc. The cache is per-backend, lives in `CacheMemoryContext`, and serves as the canonical `Relation` handle that the rest of the backend operates on. Also implements the boot-time **relcache init file** (a serialized snapshot of nailed + critical catalog entries) so backends can start without scanning pg_class. [from-comment, relcache.c:1-26; verified-by-code]

## Top-of-file comment (verbatim)

> "POSTGRES relation descriptor cache code … INTERFACE ROUTINES: RelationCacheInitialize, RelationCacheInitializePhase2, RelationCacheInitializePhase3, RelationIdGetRelation, RelationClose. NOTES: The following code contains many undocumented hacks. Please be careful…." [relcache.c:1-26]

## Public surface (functions actually `extern`)

**Lifecycle / startup**: `RelationCacheInitialize` (4004), `RelationCacheInitializePhase2` (4050) — shared catalogs, `RelationCacheInitializePhase3` (4109) — local catalogs + write init file. [verified-by-code]

**Open/close (the hottest entry points)**: `RelationIdGetRelation` (2089), `RelationClose` (2220), `RelationIncrementReferenceCount`/`RelationDecrementReferenceCount` (2187, 2200).

**Local-relation creation**: `RelationBuildLocalRelation` (3515) — used by `heap_create`. `RelationSetNewRelfilenumber` (3775), `RelationAssumeNewRelfilelocator` (3978).

**Invalidation hooks** (called from inval.c): `RelationCacheInvalidateEntry` (2938), `RelationCacheInvalidate` (2994) — sinval-overflow full sweep, `RelationCloseSmgrByOid`, `RelationForgetRelation` (2893).

**Subsidiary lookups**: `RelationGetFKeyList` (4731), `RelationGetIndexList` (4837), `RelationGetStatExtList` (4977), `RelationGetPrimaryKeyIndex` (5047), `RelationGetReplicaIndex` (5073), `RelationGetIndexExpressions` (5097), `RelationGetIndexPredicate` (5210), `RelationGetIndexAttrBitmap` (5304), `RelationGetIdentityKeyBitmap` (5577), `RelationGetExclusionInfo` (5654), `RelationBuildPublicationDesc` (5795), `RelationGetIndexAttOptions` (6012).

**Init-file**: `RelationIdIsInInitFile` (6846), `RelationCacheInitFilePreInvalidate` (6886), `RelationCacheInitFilePostInvalidate` (6911), `RelationCacheInitFileRemove` (6926).

**Misc public state**: `criticalRelcachesBuilt` (142), `criticalSharedRelcachesBuilt` (148).

## Key types / structs

- `RelIdCacheEnt` (relcache.c:130) — `{Oid reloid; Relation reldesc;}`, the only hash-table entry type. Stored in `RelationIdCache` (HTAB, 136).
- `InProgressEnt` (relcache.c:166) — stack frame for `RelationBuildDesc` recursion-with-invalidation-retry. See §invariants.
- `OpClassCacheEnt` (relcache.c:263) — cached opclass support-proc oids; keyed by opclass oid. [verified-by-code]
- The big one — `RelationData` itself — is declared in `rel.h`, NOT here. This file only allocates / populates / destroys it.

## Key invariants and locking [HIGH-RISK SECTION]

- **`CacheMemoryContext` is the parent.** All relcache entries live there or in child contexts (`rd_indexcxt`, `rd_pddcxt`, `rd_partkeycxt`, `rd_rulescxt`). On error during `RelationBuildDesc` we leak transient data unless `debug_discard_caches > 0` or `RECOVER_RELATION_BUILD_MEMORY=1`; the workspace tmp context is only created then. [from-comment, relcache.c:1063-1089]
- **Reference counting is per-backend, not shared.** `RelationIncrementReferenceCount` / `RelationDecrementReferenceCount` plus the `ResourceOwner` registration (rd_refcnt path) tracks pins. `RelationClose` calls `RelationCloseCleanup` which **does NOT** drop the entry; the entry is normally retained until invalidation or backend exit. New-in-xact relations are also retained — they cannot be dropped from cache because no other backend can manipulate them before commit. [verified-by-code, relcache.c:2220-2275, 3018-3024]
- **CREATE INDEX CONCURRENTLY ordering rule (LOAD-BEARING).** `RelationBuildDesc` registers an `InProgressEnt`; if any sinval message for `targetRelId` arrives during the build, the entry's `invalidated` flag flips and `RelationBuildDesc` retries from `retry:` until it completes without an inval. This is what guarantees that CIC's `ShareUpdateExclusiveLock`-protected catalog changes are reliably picked up by the next transaction. [from-comment, relcache.c:158-164; verified-by-code, relcache.c:1101-1104]
- **Two-phase invalidation in `RelationCacheInvalidate`.** Phase 1 walks the hashtable: zero-refcnt entries are immediately blown away via `RelationClearRelation`; refcnt>0 entries are queued onto `rebuildFirstList` (pg_class first, pg_class_oid_index second), then `rebuildList` (other nailed first, rest last). Mapped relations get `rd_locator` refreshed in phase 1 so phase-2 rebuilds can rely on it. Phase 2 rebuilds in order. **Ordering matters because pg_class itself must be rebuildable before anything else.** [from-comment, relcache.c:3048-3065; verified-by-code]
- **Nailed relations** (bootstrap catalogs like pg_class, pg_attribute, pg_proc, pg_type) are never destroyed — `RelationClearRelation` asserts `!rd_isnailed`. They are rebuilt in place via `RelationReloadNailed`. [verified-by-code, relcache.c:2549]
- **Rebuild-in-place protocol** (`RelationRebuildRelation` for refcnt>0): build a *new* `RelationData` from catalogs, then **swap fields** with the old struct so the holder's pointer stays valid. Indexes use the lighter `RelationReloadIndexInfo` path; nailed rels use `RelationReloadNailed`. Caller MUST hold some lock on the rel during rebuild, or the catalogs may be changing. [from-comment, relcache.c:2569-2582]
- **Mapped relations**: `RelationInitPhysicalAddr` consults `relmapper.c` instead of `pg_class.relfilenode`. Phase-1 inval refreshes the locator so cross-rebuilds see fresh storage. [verified-by-code, relcache.c:3036-3046]
- **Init file integrity** (`RelationCacheInitFilePreInvalidate`/`PostInvalidate`): the LWLock `RelCacheInitLock` (held across pre→post) serialises init-file unlink against concurrent writers. Caller (inval.c) is responsible for taking the lock around any catalog change that would invalidate a nailed/critical relcache entry. [from-comment, relcache.c:6872-6886; verified-by-code]
- **`criticalRelcachesBuilt` gate.** Before this flag flips, indexscans on the catalogs read by relcache building are disabled — building forces seqscan on pg_class until we have functional indexscans on it. The flag flips at the end of phase 3 once nailed indexes are loaded. [from-comment, relcache.c:138-148]

## Functions of note

1. **`RelationIdGetRelation`** (2089) — fast path. Hash lookup; on hit increments refcount and (if needed) reloads index info / re-validates. On miss calls `RelationBuildDesc` and inserts. [verified-by-code]
2. **`RelationBuildDesc`** (1055) — the big load function. Pushes an `InProgressEnt`, calls `ScanPgRelation` for the pg_class tuple, allocates a RelationData via `AllocateRelationDesc`, calls `RelationParseRelOptions`, `RelationBuildTupleDesc` (reads pg_attribute), `RelationInitPhysicalAddr`, `RelationInitTableAccessMethod`, and if it's an index, `RelationInitIndexAccessInfo`. If sinval arrived for it mid-build, restarts from `retry:`. [verified-by-code, relcache.c:1055-1334]
3. **`RelationCacheInvalidate`** (2994) — the SI-overflow / DISCARD ALL handler. Two-phase walk described above. Also calls `RelationMapInvalidateAll` first and `smgrreleaseall` between phases. [verified-by-code]
4. **`RelationClearRelation` / `RelationRebuildRelation` / `RelationInvalidateRelation`** (2546, 2585, 2518) — the three reset primitives. Clear = wipe (refcnt 0 only); Rebuild = swap contents (refcnt > 0 with lock held); Invalidate = mark struct fields not-valid without freeing.
5. **`load_relcache_init_file`** (6191) / **`write_relcache_init_file`** (6611) — boot-time serialization of nailed + critical-index relcache entries to `pg_internal.init` (per-DB) and `global/pg_internal.init` (shared). The format has a magic version word (`RELCACHE_INIT_FILEMAGIC` = `0x573266`) and stores raw `RelationData` + tupdesc + attribute array + (for indexes) opfamily/opcintype/support/indoption/indcollation vectors. [verified-by-code, relcache.c:6181-6611]
6. **`RelationBuildLocalRelation`** (3515) — fast path for CREATE: builds a relcache entry from caller-supplied tupdesc *without* reading pg_class (because the row doesn't exist yet). Sets `rd_createSubid` so the entry is protected from sinval reset until commit/abort. [verified-by-code]

## Cross-references

- **Called by**: every catalog/AM access — `table_open`, `relation_open`, `index_open` all bottom out in `RelationIdGetRelation`. Backend startup (`InitPostgres`) drives the three phase functions.
- **Calls out to**: `catcache.c` (via `SearchSysCache*` and `ScanPgRelation`'s index lookups), `inval.c` (registers via `AcceptInvalidationMessages` indirectly), `relmapper.c` (mapped relations), `partcache.c` (`RelationGetPartitionDesc` populates `rd_partdesc` lazily — separate file), `typcache.c` (relcache inval triggers typcache invals for composites).
- **Inval integration**: `inval.c`'s `LocalExecuteInvalidationMessage` → `RelationCacheInvalidateEntry` for per-rel inval, → `RelationCacheInvalidate` for sinval-overflow.

## Open questions

- Exact set of `rd_*` sub-contexts and their lifetime relative to swap-in-rebuild [unverified — need to walk `RelationDestroyRelation` to confirm what's freed vs preserved].
- Whether `rd_indexvalid` tri-state and its index-list cache invalidation interlock with sinval is captured fully here or partly in `inval.c` [unverified].
- The `eoxact_list` overflow threshold of 32 is hard-coded; under heavy DDL workloads how often is the fallback hash-seq taken? [unverified, performance-relevant]

## Confidence tag tally

verified-by-code: 18 — from-comment: 9 — from-readme: 0 — inferred: 0 — unverified: 3
