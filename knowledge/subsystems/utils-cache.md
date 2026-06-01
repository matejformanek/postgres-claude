# Catalog / relation / plan caches (`utils/cache`)

- **Source path:** `source/src/backend/utils/cache/`
- **Header path:** `source/src/include/utils/{catcache,syscache,relcache,plancache,typcache,inval,lsyscache,attoptcache,evtcache,spccache,partcache,relfilenumbermap,ts_cache}.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchors:** there is no README in this directory; the load-bearing prose lives in the top-of-file comments of `inval.c:1-104`, `relcache.c:1-26`, `typcache.c:6-31`, `plancache.c:6-39`, `ts_cache.c:6-17`, and the "Adding system caches" instructions at `syscache.c:13-65`.
- **Companion docs:** `knowledge/idioms/catalog-conventions.md`, `knowledge/data-structures/snapshot-lifecycle.md` (CatalogSnapshot section), and the per-file docs under `knowledge/files/src/backend/utils/cache/`. This doc is the subsystem-level synthesis grounded in those per-file docs; concrete claims cite `source/...:line` or carry a confidence tag.

## 1. Purpose and the cache stack

`utils/cache` owns every per-backend memo of catalog state that PostgreSQL keeps in private memory. Cross-backend coherency is **not** maintained by sharing the caches — caches are strictly per-process — but by the **shared-invalidation (SI) message queue** flowing through `inval.c`. A backend's caches are therefore a private materialization of `pg_class` / `pg_attribute` / `pg_proc` / etc., kept honest by `AcceptInvalidationMessages` at every safe boundary.

Conceptually there are six independently-managed cache layers, stacked roughly from "cheapest single fact" to "longest-lived big object":

1. **catcache** (`catcache.c`) — per-(catalog, key) hash of `HeapTuple` copies. Negative entries supported. The substrate of all catalog row lookups. [via `knowledge/files/src/backend/utils/cache/catcache.c.md`]
2. **syscache** (`syscache.c`) — named-cache facade over catcache: a static `SysCache[]` array indexed by the `SysCacheIdentifier` enum, populated from a genbki-generated `cacheinfo[]`. Public API is `SearchSysCacheN`, `SearchSysCacheLockedN`, `SearchSysCacheCopyN`, `SysCacheGetAttr`. [via `syscache.c.md`]
3. **lsyscache** (`lsyscache.c`) — ~130 stateless one-liner wrappers (`get_func_rettype`, `get_attname`, `get_opclass_family`, …) that do `SearchSysCache → extract → ReleaseSysCache`. Pure thin layer; no state of its own. [via `lsyscache.c.md`]
4. **relcache** (`relcache.c`, `partcache.c`, `attoptcache.c`) — `RelationData` descriptors keyed by Oid, with the bootstrap **init file** for nailed catalogs and lazy sub-caches for partition info, opclass support, attribute options.
5. **plancache** (`plancache.c`) — `CachedPlanSource` / `CachedPlan` for PREPARE/EXECUTE, SPI, extended-protocol Parse/Bind/Execute, plus `CachedExpression` for ad-hoc scalar expressions. Tracks dependencies and revalidates against sinval. [via `plancache.c.md`]
6. **Domain-specific immortal caches** — `typcache` (one entry per type, lives for the backend), `ts_cache` (TS parsers/dicts/configs), `evtcache` (event-trigger lookup table), `spccache` (parsed `pg_tablespace.spcoptions`), `relfilenumbermap` (reverse `(spc, relfile) → relid`).

And the dispatcher that ties it all together:

- **inval** (`inval.c`) — the transactional engine that (a) collects pending invalidations as catalog DML runs, (b) processes them locally at CommandCounterIncrement, (c) broadcasts them on commit through `storage/sinval`, (d) drains incoming SI messages via `AcceptInvalidationMessages`, and (e) brackets the relcache init-file unlink across commit. **This file is load-bearing for catalog correctness across the entire backend** [from-comment, `inval.c:1-104`, via `inval.c.md`].

Memory: everything that survives a single function call lives in `CacheMemoryContext` (created by `CreateCacheMemoryContext`, `catcache.c:725`). Relcache and typcache create child contexts (`rd_indexcxt`, `rd_pddcxt`, `rd_partkeycxt`, `rd_rulescxt`, domain-constraint contexts) for sub-objects so they can be freed in one shot.

## 2. catcache — the hashed tuple cache

`CatCache` indexes one catalog by one specific N-tuple of key columns (1 ≤ N ≤ `CATCACHE_MAXKEYS = 4`, `catcache.h:35`). Each `CatCache` has two separately sized, separately rehashed bucket arrays (`cc_bucket` for `CatCTup`, `cc_lbucket` for `CatCList`). Bucket sizing is always a power of two; `HASH_INDEX(h, sz) = h & (sz-1)` (`catcache.c:70`). [via `catcache.c.md`]

### 2.1 Entries

- **`CatCTup`** — one cached row (positive entry) or one absent-row marker (negative entry). Allocated as a single chunk `MAXALIGN(sizeof(CatCTup)) + dtp->t_len` so the embedded HeapTuple body is contiguous with the descriptor (`catcache.c:2234-2247`, via `catcache.c.md` §"Functions of note"). [verified-by-code]
- **`CatCList`** — cached *list* of CatCTups for a non-unique-key query (e.g. all pg_amop rows for an opfamily). Pins its members transitively.
- **Negative entries** mark "no row matches this key" so that the next `SearchSysCache` does not re-scan. They have `refcount == 0` permanently and are never returned to callers; `SearchCatCacheInternal` translates a negative hit into `NULL`. **Never created in bootstrap mode**, because the inval machinery is not running yet and a stale negative would persist. [from-comment, `catcache.c:1621-1652`, via `catcache.c.md`]

### 2.2 Lookup — `SearchCatCacheInternal` (`catcache.c:1423`)

`pg_attribute_always_inline`. Computes `cache->cc_hashfunc(keys)`, walks the bucket dlist comparing via `cc_fastequal`, on hit promotes the entry to bucket head (MRU) and bumps refcount. Miss falls through to `SearchCatCacheMiss` (`catcache.c:1531`), which opens the catalog with `AccessShareLock`, runs a `systable_beginscan` with `IndexScanOK(cache)`, builds a CatCTup, and **retries the whole scan if `CatalogCacheCreateEntry` returns NULL** — that is the stale-detoast race in §2.4. [verified-by-code, via `catcache.c.md`]

### 2.3 Invalidation — hash-only, never TID

Critical invariant — **matching is by hash value, not by TID**. The top-of-file comment of `CatCacheInvalidate` (`catcache.c:633-638`) is explicit: *"We used to try to match positive cache entries by TID, but that is unsafe after a VACUUM FULL on a system catalog: an inval event could be queued before VACUUM FULL, and then processed afterwards, when the target tuple … has a different TID."* Hash matching admits false positives (invalidating an unrelated row that hashes the same), which is accepted as the cheaper correct option. [from-comment, via `catcache.c.md` §"Key invariants"]

Three flavors of inval:

- `CatCacheInvalidate(cache, hashValue)` (`catcache.c:643`) — kills every CatCList in the cache (see below), walks the one matching bucket, marks matching entries dead or removes them.
- `ResetCatalogCache` / `ResetCatalogCaches` / `ResetCatalogCachesExt` (`catcache.c:753, 816, 822`) — used by SI overflow and `DISCARD ALL`. Removes everything.
- `CatalogCacheFlushCatalog(catId)` (`catcache.c:852`) — sweeps caches over a single catalog.

**CatCList wipe-all-on-inval**: any matching catcache invalidation kills *every* CatCList in the cache, not just lists containing matching tuples — *"it's too hard to tell which searches might still be correct"* [from-comment, `catcache.c:655-672`, via `catcache.c.md`]. This is conservative and explains why list-style enumerations (amop walk, opfamily walk) churn faster than single-tuple lookups.

**Refcount-deferred deletion**: if `refcount > 0` (or a parent list is pinned), an invalidated entry is only marked `dead`; freed on last release. `CATCACHE_FORCE_RELEASE` is a build flag that forces immediate free, used by testing. [verified-by-code, `catcache.c:667-692`, via `catcache.c.md`]

### 2.4 The TOAST-detoast race and the in-progress stack

`CatalogCacheCreateEntry` flattens out-of-line TOAST columns via `toast_flatten_tuple`; that scan can recurse into `AcceptInvalidationMessages` and consume an SI message that invalidates the entry we are *in the act of building*. The defence is a per-backend in-progress stack (`catcache_in_progress_stack`, frame type `CatCInProgress` at `catcache.c:52`) populated before detoast. `CatCacheInvalidate` matches against the stack and flips `dead`; create then returns NULL, forcing `SearchCatCacheMiss` to restart its `systable_beginscan`. [from-comment, `catcache.c:1569-1574`, `2189-2230`, via `catcache.c.md` §"Key invariants" item 5]

A 0.1% random NULL return is injected under `USE_ASSERT_CHECKING` to exercise this retry path (`catcache.c:2184-2187`, via `catcache.c.md`).

### 2.5 Recursive-lookup tolerance

`SearchCatCacheMiss` opens the underlying relation with `AccessShareLock`, and **recursive cache lookups during `table_open` are explicitly allowed** — they may even insert a duplicate of the row we are also fetching. The duplicate ages out; the comment documents this as cheaper than detecting the collision. [from-comment, `catcache.c:1559-1567`, via `catcache.c.md`]

### 2.6 `PrepareToInvalidateCacheTuple`

Producer-side entry called by inval.c during catalog DML. Given the old/new tuples for an INSERT/UPDATE/DELETE, recomputes the hash value for each cache keyed on that catalog and appends pending-list entries. UPDATE may produce two entries (old hash + new hash) if the keys change. [from-comment, `catcache.c:2368-2401`, via `catcache.c.md`]

## 3. relcache — `RelationData` lifecycle

Per-backend hash `RelationIdCache` of `RelIdCacheEnt {Oid reloid; Relation reldesc;}` (`relcache.c:130-136`). The big `RelationData` struct itself is declared in `rel.h`; `relcache.c` only allocates / populates / destroys it. All relcache memory lives in `CacheMemoryContext` or one of `rd_indexcxt` / `rd_pddcxt` / `rd_partkeycxt` / `rd_rulescxt`. [via `relcache.c.md` §"Purpose" + "Key invariants"]

### 3.1 The three phases of `RelationCacheInitialize*`

1. **`RelationCacheInitialize`** (`relcache.c:4004`) — create the hashtable.
2. **`RelationCacheInitializePhase2`** (`relcache.c:4050`) — initialize shared catalogs (`pg_database`, `pg_authid`, `pg_auth_members`, `pg_database_oid_index`, …). Reads `global/pg_internal.init` if present, else does a hand-built bootstrap.
3. **`RelationCacheInitializePhase3`** (`relcache.c:4109`) — initialize the current-DB nailed catalogs and the critical-index set; flips `criticalRelcachesBuilt` (`relcache.c:142`) once nailed indexes are loaded; writes the per-DB `pg_internal.init` if it's missing.

Before `criticalRelcachesBuilt` flips, indexscans on the catalogs read by relcache building are **disabled** — building is forced to seqscan on pg_class until functional indexscans on pg_class exist. This is the relcache analog of catcache's bootstrap-mode rule. [from-comment, `relcache.c:138-148`, via `relcache.c.md` §"Key invariants" item 7]

### 3.2 The init file (`pg_internal.init`)

Boot-time serialized snapshot of the **nailed + critical-index** relcache entries. Two locations: `global/pg_internal.init` for shared catalogs, and `<dboid>/pg_internal.init` per database. Format magic `RELCACHE_INIT_FILEMAGIC = 0x573266` (`relcache.c:6181-6611`, via `relcache.c.md` §"Functions of note" 5). Stores `RelationData` + tupdesc + attribute array + (for indexes) opfamily / opcintype / support / indoption / indcollation vectors.

**Pre/post unlink protocol**: `RelationCacheInitFilePreInvalidate` takes the LWLock `RelCacheInitLock` and `unlink`s the file; `RelationCacheInitFilePostInvalidate` releases the lock. inval.c brackets these around `SendSharedInvalidMessages` (§5.3) so other backends can't see the SI message and reload the (still-present) stale init file. [from-comment, `relcache.c:6872-6886`, via `relcache.c.md` §"Key invariants" item 6; cross-cited at `inval.c:1216-1226` via `inval.c.md`]

### 3.3 `RelationIdGetRelation` and `RelationBuildDesc`

Hot path: `RelationIdGetRelation` (`relcache.c:2089`) hashes the OID, on hit bumps refcount (and re-runs index info validation if needed), on miss calls `RelationBuildDesc` (`relcache.c:1055`).

`RelationBuildDesc` pushes an `InProgressEnt` (`relcache.c:166`) onto a stack, scans `pg_class`, calls `AllocateRelationDesc`, `RelationParseRelOptions`, `RelationBuildTupleDesc` (reads `pg_attribute`), `RelationInitPhysicalAddr`, `RelationInitTableAccessMethod`, and for indexes `RelationInitIndexAccessInfo`. **If any sinval message for `targetRelId` arrives during the build, the in-progress entry's `invalidated` flag flips and `RelationBuildDesc` restarts from `retry:`** until it completes without interruption. This is what guarantees CREATE INDEX CONCURRENTLY's `ShareUpdateExclusiveLock`-protected catalog changes are reliably picked up by the next transaction. [from-comment, `relcache.c:158-164`; verified-by-code, `relcache.c:1101-1104`, via `relcache.c.md` §"Key invariants" item 3]

### 3.4 Reset primitives: Clear vs Rebuild vs Invalidate

Three sibling functions (`RelationClearRelation`, `RelationRebuildRelation`, `RelationInvalidateRelation` at `relcache.c:2546, 2585, 2518`):

- **Clear** — wipe everything; only legal when `refcnt == 0` and rel is not nailed. Asserts `!rd_isnailed`. [verified-by-code, `relcache.c:2549`]
- **Rebuild-in-place** — for `refcnt > 0`: build a *new* `RelationData` from catalogs, then **swap fields** with the old struct so the holder's pointer stays valid. Caller MUST hold *some* lock on the rel during rebuild, or the catalogs may be changing. Indexes use the lighter `RelationReloadIndexInfo` path; nailed rels use `RelationReloadNailed` (in-place re-read, never destroyed). [from-comment, `relcache.c:2569-2582`, via `relcache.c.md`]
- **Invalidate** — mark struct fields not-valid without freeing; the next access path triggers actual reload.

### 3.5 Two-phase invalidation sweep — `RelationCacheInvalidate`

Used by SI overflow and `DISCARD ALL`. The hashtable walk is split into two phases [from-comment, `relcache.c:3048-3065`, via `relcache.c.md` §"Key invariants" item 4]:

- **Phase 1**: walk the table. Zero-refcnt entries are blown away immediately via `RelationClearRelation`. refcnt>0 entries are queued onto two ordered lists: `rebuildFirstList` (`pg_class` first, `pg_class_oid_index` second), then `rebuildList` (other nailed, then everything else). Mapped relations get `rd_locator` refreshed in phase 1 (via `relmapper.c`) so phase-2 rebuilds can rely on it.
- **Phase 2**: rebuild in list order. **Ordering matters because `pg_class` itself must be rebuildable before anything else.**

Also calls `RelationMapInvalidateAll` first and `smgrreleaseall` between phases.

### 3.6 `RelationBuildLocalRelation`

Fast path for CREATE: builds a relcache entry from a caller-supplied tupdesc *without* reading `pg_class` (because the row doesn't exist yet). Sets `rd_createSubid` so the entry is protected from sinval reset until commit/abort. [verified-by-code, `relcache.c:3515`, via `relcache.c.md`]

### 3.7 Sub-caches attached to RelationData

- **`partcache.c`** owns `rd_partkey` (partition key — strategy, attrs, exprs, collations, opclasses, support functions) and `rd_partcheck` (partition constraint qual). Partition keys never change after creation, so `RelationClearRelation` preserves `rd_partkey` across rebuilds — callers may hold pointers as long as they hold the relation open. [from-comment, `partcache.c:42-48`, via `partcache.c.md` §"Key invariants"] `rd_partdesc` (the partition descriptor) is built in `catalog/partition.c`, not here.
- **`attoptcache.c`** owns parsed `pg_attribute.attoptions`. Its hash function uses `GetSysCacheHashValue2(ATTNUM, attrelid, attnum)` so the inval callback can use `hash_seq_init_with_hash_value` for **O(1)-on-average targeted invalidation** instead of a full sweep. [from-comment, `attoptcache.c:106-110`, via `attoptcache.c.md`]
- **`relfilenumbermap.c`** owns the reverse `(reltablespace, relfilenumber) → relid` lookup needed by logical decoding and pg_buffercache. Keyed by `RelfilenumberMapKey`; the inval callback is registered on relcache and removes either the specific relation, all entries on InvalidOid sweep, or any cached negative entry on every event (`relfilenumbermap.c:52-79`, `125-127`). Temporary relations are explicitly ignored because they can share relfilenumbers across backends and the cache has no `proc number` to disambiguate (`relfilenumbermap.c:133-138`). [verified-by-code]

## 4. syscache — the named-cache facade

The public lookup surface most code uses. `SysCache[SysCacheSize]` is a global `CatCache *` array indexed by the `SysCacheIdentifier` enum (`syscache.c:87`); each slot is created by `InitCatalogCache` (`syscache.c:111`) walking a genbki-generated `cacheinfo[]` array (`syscache.c:82` includes `catalog/syscache_info.h`). [via `syscache.c.md`]

### 4.1 Adding a syscache — the rules

[from-comment, `syscache.c:13-65`, via `syscache.c.md`]:

- Every syscache MUST have an underlying **unique index** keyed on exactly the cache key.
- Bucket count MUST be a power of 2 (catcache's `cc_bucket` indexing uses the bit mask).
- Catalog DML must go through `CatalogTupleInsert` / `CatalogTupleUpdate`, **not** raw `heap_insert` / `heap_update`, so the index gets updated and `CacheInvalidateHeapTuple` runs. Bypassing this silently breaks cache coherency.
- The matching `MAKE_SYSCACHE` declaration in the relevant `catalog/pg_*.h` header feeds `cacheinfo[]` at build time.

### 4.2 The `SearchSysCacheLocked1` two-fetch protocol — **HIGHEST-RISK GOTCHA**

`pg_class.relfrozenxid` and similar columns are mutated by *inplace updates* (`heap_inplace_update_and_unlock`) that bypass MVCC. The cached tuple a syscache reader holds may be stale-with-respect-to-inplace-update by the time the caller decides to do something with it. The fix is the locked-read protocol at `syscache.c:283-362` [from-comment, via `syscache.c.md` §"Key invariants"]:

1. `SearchSysCache1(cacheId, key)` — find the row, note its TID.
2. `LockTuple(InplaceUpdateTupleLock)` on that TID.
3. **`AcceptInvalidationMessages()`** — so any pending syscache inval for this row is processed *before* the re-fetch (this placement is the specific gotcha — without it, a finished inplace update could leave a stale cached tuple visible to the loop).
4. Re-fetch via syscache.
5. Compare TID; if changed, release the tuple lock and retry.

The 25-line comment at `syscache.c:290-316` documents an explicit GRANT / CLUSTER / VACUUM race that this loop defeats. Only the 1-key form exists because every inplace-updated catalog (pg_class, pg_database) is keyed by single oid. [from-comment, via `syscache.c.md` §"Open questions"]

### 4.3 The other public surface

- `SearchSysCache*` family (`syscache.c:209-261`) — direct forwards to `SearchCatCacheN`. **Returned tuple must not be modified.** [from-comment, `syscache.c:194-200`]
- `SearchSysCacheCopy*` (`syscache.c:375`) — wraps `SearchSysCache + heap_copytuple + ReleaseSysCache`. Returned tuple is caller-owned and must be `heap_freetuple`d. Use this whenever you intend to modify.
- `SysCacheGetAttr` / `SysCacheGetAttrNotNull` (`syscache.c:596, 626`) — extract one attribute, using the cache's tupdesc.
- `SysCacheInvalidate(cacheId, hashValue)` (`syscache.c:691`) — one-line dispatcher; the real work is `CatCacheInvalidate(SysCache[cacheId], hashValue)`.
- `RelationHasSysCache` / `RelationSupportsSysCache` (`syscache.c:738, 763`) — binary search over sorted oid arrays; used by `CacheInvalidateHeapTuple` to skip work for catalogs that have no caches.

### 4.4 `InitCatalogCachePhase2`

Optional. Syscaches are normally lazy on first use. Phase 2 is triggered only when writing a relcache init file, to preload the most-used catcaches before serialization. [from-comment, `syscache.c:168-179`, via `syscache.c.md`]

## 5. inval — the dispatcher and SI message flow

**The most important file in the directory.** Sits between local catalog DML and other backends; coordinates the relcache init-file unlink; processes incoming SI messages. [via `inval.c.md`]

### 5.1 Pending lists per (sub)transaction

`InvalMessageArray` (`inval.c:175`): two global pools (`InvalMessageArrays[2]` — one for catcache, one for relcache messages), arena-allocated in `TopTransactionContext`. `InvalidationMsgsGroup` (`inval.c:184`) is a per-batch slice `{firstmsg[2]; nextmsg[2]}`. `TransInvalidationInfo` stacks `InvalidationInfo` per subtransaction with `my_level`, `parent`, `CurrentCmdInvalidMsgs`, `PriorCmdInvalidMsgs`, `RelcacheInitFileInval`. A separate `inplaceInvalInfo` exists for the non-transactional inplace-update path (§5.4). [verified-by-code, `inval.c:171-181`, via `inval.c.md` §"Key types"]

### 5.2 Producer side — `CacheInvalidateHeapTuple` family

Called by `heap_insert` / `heap_update` / `heap_delete` for catalog rows. The backbone is `CacheInvalidateHeapTupleCommon` (`inval.c:1433`): given a catalog row and an optional newtuple, it decides which catcaches to register (via `PrepareToInvalidateCacheTuple`), whether to register a relcache inval (yes for `pg_class` / `pg_attribute` / `pg_index` / `pg_constraint` on FKs per the top-comment at `inval.c:54-57`), and whether to set the init-file-inval flag. Updates are modeled as delete + insert events; if the hash didn't change, catcache.c optimizes to one event [from-comment, `inval.c:40-43`].

Other producer entries: `CacheInvalidateRelcache(rel)`, `CacheInvalidateRelcacheByRelid(oid)`, `CacheInvalidateRelcacheAll()` (`inval.c:1632, 1688, 1655`); `CacheInvalidateSmgr` (`inval.c:1752`); `CacheInvalidateRelmap` (`inval.c:1786`); `CacheInvalidateRelSync` for publication-sync invalidation (`inval.c:1709`).

### 5.3 Commit ordering — **the ordering rule that matters**

> *"we have to record the transaction commit before sending SI messages, otherwise the other backends won't see our updated tuples as good."* [from-comment, `inval.c:30-34`, via `inval.c.md` §"Key invariants" item 1]

Concretely: `RecordTransactionCommit` calls `xactGetCommittedInvalidationMessages` (`inval.c:1012`) to snapshot the pending list, writes the commit WAL record, then `AtEOXact_Inval(true)` (`inval.c:1196`) actually broadcasts via `SendSharedInvalidMessages`.

**Init-file pre/post bracket** wraps the broadcast (`inval.c:1216-1226`) when `RelcacheInitFileInval` is set:

1. `RelationCacheInitFilePreInvalidate` — take `RelCacheInitLock`, `unlink` the init file.
2. `AppendInvalidationMessages` + `SendSharedInvalidMessages` — broadcast.
3. `RelationCacheInitFilePostInvalidate` — release the lock.

Other backends that observe the SI message find the init file already gone and rebuild from catalogs.

**Catcache-before-relcache** within local processing: pending catcache flushes issue before relcache flushes, so a relcache reload doesn't pull in a catcache tuple that's about to be flushed. [from-comment, `inval.c:59-64`]

### 5.4 Inplace-update path is non-transactional

Inplace updates (e.g. `pg_class.relfrozenxid` adjusted by VACUUM) bypass MVCC and bypass the normal commit-time broadcast. `inplaceInvalInfo` is separate from `transInvalInfo`. The protocol [verified-by-code, `inval.c:1247-1274`, via `inval.c.md`]:

- **`PreInplace_Inval`** runs *outside* the critical section (Asserts `CritSectionCount == 0`); does the init-file unlink (which may fail / palloc).
- **`AtInplace_Inval`** runs *inside* the buffer-mutating critical section (Asserts `CritSectionCount > 0`); broadcasts immediately after the buffer mutation.

This mirrors the transactional pre/broadcast/post triple but with no commit gate.

### 5.5 Consumer side — `AcceptInvalidationMessages` and the SI queue

`AcceptInvalidationMessages` (`inval.c:930`) is the universal pull-in point. Asserts we're in a transaction (handlers may access catalogs). Drives `ReceiveSharedInvalidMessages` with two callbacks:

- `LocalExecuteInvalidationMessage` (`inval.c:823`) — per-message dispatcher. Routes by `msg->id`: catcache id (≥ 0) → `SysCacheInvalidate` + `CallSyscacheCallbacks` + `InvalidateCatalogSnapshot`; `SHAREDINVALCATALOG_ID` → `CatalogCacheFlushCatalog`; `SHAREDINVALRELCACHE_ID` → `RelationCacheInvalidateEntry` (or full sweep if `relId == InvalidOid`) + relcache callbacks; `SHAREDINVALSMGR_ID` → `smgrreleaserellocator`; `SHAREDINVALRELMAP_ID` → `RelationMapInvalidate`; `SHAREDINVALSNAPSHOT_ID` → `InvalidateCatalogSnapshot`; `SHAREDINVALRELSYNC_ID` → `CallRelSyncCallbacks`. [verified-by-code, via `inval.c.md` §"Functions of note" 1]
- `InvalidateSystemCaches` (`inval.c:916`) — the SI-overflow fallback. Blows away everything when the queue overflowed and individual messages were lost.

**When `AcceptInvalidationMessages` runs**: every command start, every `LockAcquire` (lmgr opportunistically calls it after acquisition so the caller sees a coherent cache), once at the top of `InitPostgres`, after every CommandCounterIncrement (via `CommandEndInvalidationMessages`), inside `SearchSysCacheLocked1` (§4.2), inside `RelationBuildDesc`'s retry loop (§3.3).

### 5.6 CommandCounterIncrement and subtransactions

- **`CommandEndInvalidationMessages`** (`inval.c:1406`) — locally processes `CurrentCmdInvalidMsgs` (no broadcast — uncommitted) and folds them into `PriorCmdInvalidMsgs`. This is what makes the post-CCI snapshot see the just-modified catalog row. [from-comment, `inval.c:1391-1404`]
- **Subtransaction commit = append to parent** (`AtEOSubXact_Inval(true)`, `inval.c:1335-1387`): drain current-cmd, then either bump `my_level--` if parent has no entry, or splice `PriorCmdInvalidMsgs` into parent. Pending init-file inval bubbles up too.
- **Subtransaction abort = locally process & discard** (`inval.c:1377-1387`): no broadcast (changes never reached commit); locally apply `PriorCmdInvalidMsgs` so the in-memory caches drop entries created by the aborted subxact.
- **`PostPrepare_Inval` behaves as ABORT** (`inval.c:993`): 2PC prepared state is unknown to us until commit/abort arrives, so we undo our local cache changes. If the prepared txn later commits, normal SI delivery brings us back. [from-comment, `inval.c:980-991`, via `inval.c.md`]

### 5.7 `debug_discard_caches` harness

When `DISCARD_CACHES_ENABLED` and `debug_discard_caches > 0`, `AcceptInvalidationMessages` recursively forces full cache flushes up to the configured depth; a static counter caps recursion. This is the harness that catches stale-cache-after-flush bugs across the tree. [from-comment, `inval.c:941-977`, via `inval.c.md`]

### 5.8 Logical decoding emission

When `wal_level = logical`, command-end inval messages are also written to WAL so the decoder can rebuild a consistent catcache snapshot for in-progress transactions; consumed by `ReorderBufferAddInvalidations`. [from-comment, `inval.c:101-103`, via `inval.c.md` §"Cross-references"]

### 5.9 Callbacks subsystem

`RegisterSyscacheCallback(cacheid, callback, arg)` and `RegisterRelcacheCallback(callback, arg)` let other caches (typcache, plancache, ts_cache, evtcache, attoptcache, spccache, relfilenumbermap) subscribe. `LocalExecuteInvalidationMessage` calls `CallSyscacheCallbacks` after the catcache flush so subscribers see a coherent state. The current registrations from the other caches in this directory:

- **plancache**: 1 relcache + 2 specific syscaches (`PROCOID`, `TYPEOID`) + 5 coarse-trigger syscaches (`NAMESPACEOID`, `OPEROID`, `AMOPOPID`, `FOREIGNSERVEROID`, `FOREIGNDATAWRAPPEROID`). [verified-by-code, `plancache.c:148-158`, via `plancache.c.md`]
- **typcache**: 1 relcache + 1 `TYPEOID` + 1 `CLAOID` + 1 `CONSTROID`. [via `typcache.c.md`]
- **ts_cache**: 1 callback per HTAB, registered on `TSPARSEROID` / `TSDICTOID` / `TSCONFIGMAP`. [via `ts_cache.c.md`]
- **evtcache**: 1 `EVENTTRIGGEROID`.
- **attoptcache**: 1 `ATTNUM` (hash-targeted).
- **spccache**: 1 `TABLESPACEOID` (coarse — flushes all).
- **relfilenumbermap**: 1 relcache.

## 6. plancache — prepared statements and generic vs custom plans

Two responsibilities, both in `plancache.c` [from-comment, `plancache.c:6-13`, via `plancache.c.md`]:

1. **Generic-vs-custom plan policy** — `choose_custom_plan`.
2. **Invalidation tracking** — `CachedPlanSource` watches sinval and revalidates.

### 6.1 The CachedPlanSource lifecycle

- **`CreateCachedPlan`** (`plancache.c:185`) — called after `raw_parser`, before `parse_analyze*`. Sets `magic = CACHEDPLANSOURCE_MAGIC = 195726186` (`plancache.h:44`), copies the raw tree into a fresh child of `CurrentMemoryContext`. A partial build dies cleanly on ereport.
- **`CompleteCachedPlan`** (`plancache.c:393`) — called after analyze + rewrite. Attaches the querytree (with dependency lists: `relationOids` for relcache deps, `invalItems` for syscache deps). Optionally reparents into long-lived memory.
- **`SaveCachedPlan`** (`plancache.c:547`) — pushes onto the backend-global `saved_plan_list` (`plancache.c:84`). **Only then does the plan receive sinval events.** Builders need not worry about callbacks invalidating a half-built plan. [verified-by-code, via `plancache.c.md` §"Key invariants" items 2-3]
- **`DropCachedPlan`** (`plancache.c:591`) — remove from list, free.

### 6.2 The two dependency sources

`CachedPlanSource.relationOids` is a list of OIDs the querytree depends on; `invalItems` is a list of `PlanInvalItem {cacheId, hashValue}` for fine-grained syscache deps (PROCOID, TYPEOID). The generic plan, if any, may carry **more** dependencies than the querytree (planner-introduced through inlining, e.g.); both lists are checked on every callback. [from-comment, `plancache.c:2156-2160`, via `plancache.c.md`]

### 6.3 Invalidation = mark only; revalidate on next use

`PlanCacheRelCallback` (`plancache.c:2126`) and `PlanCacheObjectCallback` (`plancache.c:2210`) set `is_valid = false` on the source (and on `gplan` if present). They do not destroy anything. The next `GetCachedPlan` triggers `RevalidateCachedQuery` (`plancache.c:684`) to re-analyze + re-rewrite, then `BuildCachedPlan` to re-plan. Replan can throw (e.g. dropped column). [verified-by-code, via `plancache.c.md` §"Key invariants" item 4]

`PlanCacheSysCallback` (`plancache.c:2319`) for coarse-trigger syscaches (`NAMESPACEOID` etc.) just calls `ResetPlanCache` — cheap correctness over fine-grained tracking.

`ResetPlanCache` (`plancache.c:2328`) deliberately **does not** invalidate transaction-control statements (ROLLBACK, COMMIT, …) — they may need to execute in an aborted transaction where revalidation is impossible (cf bug #5269). Gate is `StmtPlanRequiresRevalidation`. [from-comment, `plancache.c:2342-2352`, via `plancache.c.md`]

### 6.4 Generic vs custom plan policy

`choose_custom_plan` (`plancache.c:1175`) decides per call [verified-by-code, via `plancache.c.md` §"Key invariants" item 6]:

- one-shot ⇒ always custom;
- zero params ⇒ always generic;
- planner no-op ⇒ generic;
- GUC `plan_cache_mode = force_generic_plan | force_custom_plan` overrides;
- `CURSOR_OPT_GENERIC_PLAN` / `CURSOR_OPT_CUSTOM_PLAN` flags override;
- **first 5 invocations are always custom** so we can measure custom cost;
- afterwards generic wins iff `generic_cost < avg_custom_cost` (custom cost includes the planner's own cost). [from-comment, `plancache.c:1202-1216`]

This is the "5 customs then compare" heuristic users notice when PREPARE'd statements suddenly switch plans.

### 6.5 Transient plans and `saved_xmin`

If any `PlannedStmt.transientPlan` is true (e.g. plan depends on a snapshot-only invariant), the `CachedPlan.saved_xmin` is set to `TransactionXmin`; the plan is reusable only while `RecentXmin` hasn't advanced past it. Test in `CheckCachedPlan`. [verified-by-code, `plancache.c:1143-1154`, via `plancache.c.md` §"Key invariants" item 9]

### 6.6 ResourceOwner integration

`CachedPlan` refcounts go through `planref_resowner_desc` (`plancache.c:117`). Releases happen at `RESOURCE_RELEASE_AFTER_LOCKS` so executor locks come off first. [verified-by-code, via `plancache.c.md`]

## 7. The immortal caches — typcache, ts_cache, evtcache, spccache

### 7.1 typcache (`typcache.c`)

Memoizes things `pg_type` alone doesn't give you: default btree/hash opclasses, equality/comparison/hashing function oids, array element properties, record field properties, domain constraint trees, rowtype TupleDescs, anonymous RECORD typmod registry.

**Entries are immortal.** *"Once created, a type cache entry lives as long as the backend does … assuming that typcache entries are good permanently allows caching pointers to them in long-lived places."* [from-comment, `typcache.c:19-23`, via `typcache.c.md`]

**Flag-driven lazy fill.** `lookup_type_cache(type_id, flags)` (`typcache.c:389`) does the cheap lookup, then only computes the bits the caller asked for (`TYPECACHE_EQ_OPR`, `TYPECACHE_BTREE_OPFAMILY`, `TYPECACHE_HASH_PROC`, …). `TCFLAGS_CHECKED_*` flags cache "I tried and there isn't one" results. [verified-by-code, via `typcache.c.md`]

**Three-callback inval design** [verified-by-code, via `typcache.c.md` §"Key invariants"]:

- **`TypeCacheTypCallback`** (`typcache.c:2541`) — pg_type row → clear `TCFLAGS_HAVE_PG_TYPE_DATA`. Uses `hash_seq_init_with_hash_value` for targeted iteration.
- **`TypeCacheOpcCallback`** (`typcache.c:2598`) — pg_opclass row → clear `TCFLAGS_OPERATOR_FLAGS` on ALL entries. Coarse but pg_opclass updates are rare. Doesn't watch pg_amop/pg_amproc — cross-type ops can be added/dropped but primary ops cannot. [from-comment, `typcache.c:2591-2595`]
- **`TypeCacheRelCallback`** (`typcache.c:2445`) — relcache event for `relid` → invalidate the composite type whose `typrelid == relid` via a secondary `RelIdToTypeIdCacheHash`. Also walks every domain entry (threaded via `nextDomain`) and resets operator flags if the domain is over a composite. **This is how composite-type caches stay in sync with ALTER TABLE.**
- **`TypeCacheConstrCallback`** (`typcache.c:2636`) — pg_constraint changed → walk only the threaded domain list.

**Anonymous RECORD typmods**: `assign_record_type_typmod` (`typcache.c:2067`) allocates a fresh typmod for an ad-hoc tupdesc; `SharedRecordTypmodRegistry` (dshash-backed, `typcache.c:2222`) lets parallel workers share it.

### 7.2 ts_cache (`ts_cache.c`)

Three parallel caches: TS parsers, TS dictionaries, TS configurations, plus the `default_text_search_config` GUC resolver. **Backend-lifetime entries**, like typcache. [via `ts_cache.c.md`]

**Pointer-stability contract with subsidiary-info caveat.** *"It is safe to hold onto a pointer to the cache entry while doing things that might result in recognizing a cache invalidation. Beware however that subsidiary information might be deleted and reallocated somewhere else if a cache inval and reval happens! This does not look like it will be a big problem as long as parser and dictionary methods do not attempt any database access."* [from-comment, `ts_cache.c:10-17`, via `ts_cache.c.md`]

Single shared callback (`InvalidateTSCacheCallBack`, `ts_cache.c:95`) registered three times with the HTAB pointer as `arg`; coarse invalidation per hash.

### 7.3 evtcache (`evtcache.c`)

Maps `EventTriggerEvent` (`ddl_command_start`, `ddl_command_end`, `sql_drop`, `table_rewrite`, `login`) to the ordered list of enabled event-trigger functions. Rebuilt by full scan of `pg_event_trigger` in name order. [via `evtcache.c.md`]

**Tri-state rebuild guard**: `EventTriggerCacheState ∈ {ETCS_NEEDS_REBUILD, ETCS_REBUILD_STARTED, ETCS_VALID}`. If an inval arrives mid-build, the callback (`evtcache.c:258`) notices we're not VALID, leaves in-progress memory alone, and re-sets `ETCS_NEEDS_REBUILD`. The builder still installs its result but leaves the state at NEEDS_REBUILD so the *next* lookup rebuilds again. This avoids both infinite recursion and stale-after-inval. [verified-by-code, `evtcache.c:114, 205-213, 261-273`, via `evtcache.c.md`]

### 7.4 spccache (`spccache.c`)

Caches parsed `pg_tablespace.spcoptions`. Coarse: any `TABLESPACEOID` inval flushes the entire cache. *"Pointers returned by this function should not be stored, since a cache flush will invalidate them."* *"This value is not locked by the transaction, so this value may be changed while a SELECT that has used these values for planning is still executing."* — acceptable because the values are planner cost hints, not correctness-critical. [from-comment, `spccache.c:50-53, 104-105, 178-180`, via `spccache.c.md`]

## 8. Common pitfalls

These are the failure modes most likely to bite a patch author working in catalog code:

1. **Bypassing `CatalogTupleInsert` / `CatalogTupleUpdate`.** Raw `heap_insert` / `heap_update` skips index update and (more importantly) skips `CacheInvalidateHeapTuple`. The cache silently goes stale. [from-comment, `syscache.c:60-63`]
2. **Stale relcache across DDL when no lock is held.** `RelationRebuildRelation` requires the caller hold *some* lock on the rel; without it, catalog rows may be changing mid-rebuild. [from-comment, `relcache.c:2569-2582`] Compounded by: a relcache entry's `RelationData *` is **stable across rebuilds** (fields are swapped in place — see §3.4) so holders can keep the pointer, but any `rd_*` substructure may have been reallocated.
3. **Syscache lookup outside a transaction.** `AcceptInvalidationMessages` asserts we're in a transaction; calling syscache functions outside one risks operating on a cache populated by a previous transaction with no SI processing since. [verified-by-code, `inval.c:930-940` Assert via `inval.c.md`]
4. **Inplace updates and stale syscache.** Use `SearchSysCacheLocked1` whenever the next step is to inplace-update the row. The 5-step protocol (lock TID, AcceptInval, re-fetch, compare TID, retry) is the only correct sequence. [from-comment, `syscache.c:290-362`]
5. **CatalogSnapshot interplay.** `LocalExecuteInvalidationMessage` calls `InvalidateCatalogSnapshot` before every catcache flush. If your code is holding the `CatalogSnapshot` across an inval-processing point, you'll see the snapshot pointer change under you. Use `RegisterSnapshot` if you need stability. [verified-by-code, `inval.c:823-902`, via `inval.c.md` §"Functions of note" 1; cross-ref `knowledge/data-structures/snapshot-lifecycle.md` §5]
6. **Holding pointers into immortal caches across an inval.** typcache and ts_cache promise that the **top-level entry pointer** stays stable but subsidiary memory (tupdesc, mapping arrays) may be reallocated. Don't keep pointers into the variable-length internals across operations that could trigger a cache flush. [from-comment, `typcache.c:25-31`, `ts_cache.c:13-16`]
7. **Build-then-insert ordering for ad-hoc caches.** `attoptcache.get_attribute_options` and `spccache.get_tablespace` MUST do the syscache fetch + parse *before* inserting their own hash entry — the syscache fetch can trigger a cache flush that would tear out a too-eager insert. [from-comment, `attoptcache.c:190-192`, `spccache.c:161-164`]
8. **CIC and `RelationBuildDesc` retry.** If your code does anything inside `RelationBuildDesc` that can trigger `AcceptInvalidationMessages`, expect to be restarted from `retry:` if an sinval for the rel arrives. This is correct behavior; don't try to suppress it. [from-comment, `relcache.c:158-164`]
9. **`CatCList` invalidation is all-or-nothing.** Any matching catcache inval kills *every* list in that cache, not just lists containing the affected tuple. Don't expect fine-grained list invalidation. [from-comment, `catcache.c:655-672`]
10. **Plan cache and search_path / RLS.** `RevalidateCachedQuery` also forces re-analysis if `active_search_path` differs from the previous call or if the user / RLS environment changed. A "no schema change" inval can still trigger a replan. [from-comment, `plancache.c:14-21`]
11. **Negative entries are not created in bootstrap mode.** During initdb / bootstrap, a missing-row lookup produces no negative entry; the next miss will re-scan. [from-comment, `catcache.c:1621-1652`]
12. **Init-file unlink must bracket the SI broadcast.** If you produce a producer path that bypasses `RelcacheInitFileInval` accounting for a nailed catalog mutation, restarting backends will reload stale data. Always go through `CacheInvalidateRelcache*` for catalogs that participate in the init file. [from-comment, `inval.c:82-86`; verified-by-code, `relcache.c:6872-6886`]

## 9. Cross-references

- **`knowledge/idioms/catalog-conventions.md`** — the day-to-day rules for adding catalog columns, builtin functions, and how `MAKE_SYSCACHE` plus `CatalogTupleInsert` keep the cache layer coherent.
- **`knowledge/data-structures/snapshot-lifecycle.md`** §5 — the CatalogSnapshot is refreshed per catalog read, invalidated by every catcache inval through `InvalidateCatalogSnapshot`. The interaction is the trickiest cross-subsystem dependency catcache has.
- **`knowledge/idioms/memory-contexts.md`** — `CacheMemoryContext` is the singleton parent; the per-subcache child contexts (`rd_indexcxt` &c.) follow the standard "carve a context so one `MemoryContextDelete` cleans everything" idiom.
- **`knowledge/subsystems/storage-lmgr.md`** §7 — `LockAcquire` calls `AcceptInvalidationMessages` opportunistically after acquisition (`lmgr.c:135-148` per that doc) so the catalog cache is coherent before the caller proceeds.
- **`knowledge/subsystems/access-heap.md`** — `heap_insert` / `heap_update` / `heap_delete` invoke `CacheInvalidateHeapTuple` for system relations; `heap_inplace_update_and_unlock` invokes `CacheInvalidateHeapTupleInplace` inside the critical section.
- **`storage/sinval` + `storage/sinvaladt`** — the SI message queue infrastructure. `AcceptInvalidationMessages` is the only utils/cache-side consumer; `SendSharedInvalidMessages` is the only producer. [verified-by-code, via `inval.c.md` §"Cross-references"]
- **`access/xact.c`** — drives `AtEOXact_Inval`, `AtEOSubXact_Inval`, `CommandEndInvalidationMessages`, `PostPrepare_Inval`.
- **Logical decoding (`replication/logical/reorderbuffer.c`)** — `ReorderBufferAddInvalidations` consumes the WAL'd inval messages from `wal_level = logical`.
- **`catalog/syscache_info.h`** (generated) — the genbki output that populates `cacheinfo[]` for syscache.c from `MAKE_SYSCACHE` declarations.

## 10. Open questions / unverified claims carried forward

From the per-file pass:

1. **`debug_discard_caches` exercise frequency in production buildfarm runs** — assert-only path; the 0.1% random NULL injection in `CatalogCacheCreateEntry` is also assert-only. Unconfirmed whether buildfarm consistently exercises both. [unverified, via `catcache.c.md` §"Open questions"]
2. **`eoxact_list` overflow threshold of 32** in relcache is hard-coded; performance-relevant under heavy DDL. [unverified, via `relcache.c.md` §"Open questions" item 3]
3. **Dedup strategy for relcache inval messages** — comment claims "we avoid queuing multiple relcache flush requests for the same relation" but the test predicate lives implicit in `RegisterRelcacheInvalidation`'s body; not surfaced as a top-level rule. [unverified, via `inval.c.md` §"Open questions" item 1]
4. **Exact gating predicate for `RelcacheInitFileInval`** — implied to be "any inval touching a nailed/critical-index catalog" but the gate lives implicit in `CacheInvalidateHeapTupleCommon`. [unverified, via `inval.c.md` §"Open questions" item 2]
5. **Multi-key inplace-update protocol** — only `SearchSysCacheLocked1` exists; presumably because every inplace-updated catalog is single-oid-keyed. Not stated as a rule. [unverified, via `syscache.c.md` §"Open questions" item 1]
6. **Subsidiary-reallocation hazard in ts_cache** — documented but un-audited across all callers. [unverified, via `ts_cache.c.md` §"Open questions" item 2]
7. **dshash contention on SharedRecordTypmodRegistry** under heavy parallel anonymous-RECORD workloads. [unverified, via `typcache.c.md` §"Open questions" item 1]
8. **`rd_partkey` / `rd_partcheckvalid` reset semantics on detach/attach.** Partition keys are documented as never changing, but ATTACH/DETACH PARTITION's exact relcache reset path is not surfaced in the per-file docs. [unverified, via `partcache.c.md` §"Open questions"]
9. **Whether the relcache init-file format magic** `RELCACHE_INIT_FILEMAGIC = 0x573266` is bumped on minor catalog changes or only major-version layout changes. [unverified — need to grep usages]
10. **`CachedExpression` dependency-extraction** — appears to track invalItems identically to `CachedPlanSource` but the relation-vs-syscache split has not been confirmed end-to-end. [unverified, via `plancache.c.md` §"Open questions" item 2]

## 11. Glossary

- **`CatCache`** — per-key-tuple hashed catalog row cache. One CatCache per `(catalog, key-column-set)` pair. [from-comment, `catcache.c:1-13`]
- **`CatCTup`** — one cached catalog tuple (positive) or absent-row marker (negative). Allocated as a single contiguous chunk with the embedded HeapTuple body. [verified-by-code, `catcache.c:2234-2247`]
- **`CatCList`** — multi-row cached list for non-unique key lookups. All lists in a cache die together on any matching inval. [from-comment, `catcache.c:655-672`]
- **syscache** — the named `SysCache[]` array indexed by `SysCacheIdentifier`. Public API surface.
- **`SysCacheIdentifier`** — enum populated by `MAKE_SYSCACHE` declarations in `catalog/pg_*.h`, materialized into `cacheinfo[]` at build time via `catalog/syscache_info.h`. [from-comment, `syscache.c:13-65`]
- **`SearchSysCacheLocked1`** — locked-read protocol that defeats the inplace-update-vs-cached-tuple race. 5 steps: fetch, LockTuple, AcceptInval, re-fetch, compare TID. [from-comment, `syscache.c:290-362`]
- **`AcceptInvalidationMessages`** — drains the SI queue into local caches. Universal pull-in point; safe only inside a transaction. [verified-by-code, `inval.c:930`]
- **SI message** — `SharedInvalidationMessage` enqueued via `SendSharedInvalidMessages`, received via `ReceiveSharedInvalidMessages`. Type IDs: catcache (≥ 0), CATALOG, RELCACHE, SMGR, RELMAP, SNAPSHOT, RELSYNC. [verified-by-code, `inval.c:823-902`]
- **Init file** — `pg_internal.init` (per DB) / `global/pg_internal.init` (shared) — serialized snapshot of nailed + critical-index relcache entries; magic `0x573266`. [verified-by-code, `relcache.c:6181-6611`]
- **Nailed relation** — bootstrap catalog (pg_class, pg_attribute, pg_proc, pg_type, …) whose relcache entry is never destroyed, only rebuilt in place via `RelationReloadNailed`. [verified-by-code, `relcache.c:2549`]
- **Mapped relation** — relation whose physical address comes from `relmapper.c` instead of `pg_class.relfilenode`. `RelationInitPhysicalAddr` consults the mapper; phase-1 relcache inval refreshes `rd_locator`. [verified-by-code, `relcache.c:3036-3046`]
- **CatalogSnapshot** — per-command snapshot used for catalog reads; refreshed before every catcache miss, invalidated by `InvalidateCatalogSnapshot` on every catcache inval. See `knowledge/data-structures/snapshot-lifecycle.md` §5.
- **`CachedPlanSource`** — long-lived parse + analyze + dependency-tracking record; magic `CACHEDPLANSOURCE_MAGIC = 195726186`. [verified-by-code, `plancache.h:44`]
- **`CachedPlan`** — one specific planning generation; refcounted via ResourceOwner; carries optional `saved_xmin` for transient plans. [verified-by-code, `plancache.c:1143-1154`]
- **Generic vs custom plan** — generic = parameter-independent, planned once and reused; custom = re-planned per parameter set. The "first 5 always custom, then compare averaged cost" heuristic lives in `choose_custom_plan`. [from-comment, `plancache.c:1202-1216`]
- **Transient plan** — `PlannedStmt.transientPlan == true`; only reusable while `RecentXmin <= saved_xmin`. [verified-by-code, `plancache.c:1143-1154`]
- **`CacheMemoryContext`** — singleton parent context for all backend cache memory. Created by `CreateCacheMemoryContext`. [verified-by-code, `catcache.c:725`]
- **`PrepareToInvalidateCacheTuple`** — producer-side hash-computation entry called by inval.c on catalog DML. UPDATE produces up to two pending entries (old + new hash). [from-comment, `catcache.c:2368-2401`]
- **`RegisterSyscacheCallback` / `RegisterRelcacheCallback`** — subscription API for derivative caches (typcache, plancache, ts_cache, evtcache, attoptcache, spccache, relfilenumbermap). Called from `LocalExecuteInvalidationMessage` after the underlying catcache flush.
