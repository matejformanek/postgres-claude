# inval.c

- **Source path:** `source/src/backend/utils/cache/inval.c`
- **Lines:** 1966
- **Last verified commit:** `b78cd2bda5b1` (re-verified 2026-06-16 by
  pg-quality-auditor AUDIT mode after anchor-bump
  `e18b0cb7344..da1eff08a5be`; line count unchanged and all 27
  function-line cites + spot-checked top-comment ranges hold exactly —
  fully clean, the file was not line-shifted in the bump range)
- **Companion files:** `inval.h` (public surface), `catcache.c` (`PrepareToInvalidateCacheTuple`, `CatCacheInvalidate`), `syscache.c` (`SysCacheInvalidate`), `relcache.c` (`RelationCacheInvalidateEntry`, init-file pre/post hooks), `storage/sinval.c` + `sinvaladt.c` (the SI message queue infrastructure), `access/xact.c` (commit/abort drivers).

## Purpose

The transactional **dispatcher** that sits between local catalog DML and other backends. Tracks pending invalidation messages produced during a (sub)transaction, locally executes them at CommandCounterIncrement, broadcasts them on commit via the shared-invalidation (SI) queue, and processes incoming SI messages on `AcceptInvalidationMessages`. Coordinates the relcache init-file's pre/post unlink protocol so a backend restarting mid-DDL can never reload a stale init file. **This file is load-bearing for correctness across all of catalog caching.** [from-comment, inval.c:1-104]

## Top-of-file comment (verbatim — abridged but the load-bearing lines)

> "When a tuple is updated or deleted, our standard visibility rules consider that it is *still valid* so long as we are in the same command … Therefore, we cannot simply flush a tuple from the system caches during heap_update() or heap_delete(). … the correct behavior is to keep a list of outdated tuples and then do the required cache flushes at the next command boundary. We must also keep track of inserted tuples so that we can flush 'negative' cache entries that match the new tuples." [inval.c:6-22]

> "If we successfully complete the transaction, we have to broadcast all these invalidation events to other backends (via the SI message queue) so that they can flush obsolete entries from their caches. **Note we have to record the transaction commit before sending SI messages, otherwise the other backends won't see our updated tuples as good.**" [inval.c:30-34]

> "When a subtransaction aborts, we can process and discard any events it has queued. When a subtransaction commits, we just add its events to the pending lists of the parent transaction." [inval.c:36-38]

> "Updates are treated as two events, delete + insert, for simplicity. (If the update doesn't change the tuple hash value, catcache.c optimizes this into one event.)" [inval.c:40-43]

> "We keep the relcache flush requests in lists separate from the catcache tuple flush requests. This allows us to issue all the pending catcache flushes before we issue relcache flushes, which saves us from loading a catcache tuple during relcache load only to flush it again right away." [inval.c:59-64]

> "If a relcache flush is issued for a system relation that we preload from the relcache init file, we must also delete the init file so that it will be rebuilt during the next backend restart." [inval.c:82-86]

> "When making a nontransactional change to a cacheable object, we must likewise send the invalidation immediately, before ending the change's critical section. This includes inplace heap updates, relmap, and smgr." [inval.c:97-99]

> "When effective_wal_level is 'logical', write invalidations into WAL at each command end to support the decoding of the in-progress transactions. See CommandEndInvalidationMessages." [inval.c:101-103]

## Public surface

- **Driver entry**: `AcceptInvalidationMessages` (930), `LocalExecuteInvalidationMessage` (823), `InvalidateSystemCaches` (916).
- **Transaction lifecycle**: `AtEOXact_Inval` (1196), `AtEOSubXact_Inval` (1307), `CommandEndInvalidationMessages` (1406), `PostPrepare_Inval` (993), `PreInplace_Inval` (1247), `AtInplace_Inval` (1260), `ForgetInplace_Inval` (1283).
- **Producers — called by catalog DML**: `CacheInvalidateHeapTuple` (1568), `CacheInvalidateHeapTupleInplace` (1590), `CacheInvalidateCatalog` (1609), `CacheInvalidateRelcache` (1632), `CacheInvalidateRelcacheAll` (1655), `CacheInvalidateRelcacheByTuple` (1666), `CacheInvalidateRelcacheByRelid` (1688), `CacheInvalidateRelSync` (1709), `CacheInvalidateRelSyncAll` (1721), `CacheInvalidateSmgr` (1752), `CacheInvalidateRelmap` (1786).
- **Commit-record glue**: `xactGetCommittedInvalidationMessages` (1012), `ProcessCommittedInvalidationMessages` (1135).
- **Callbacks**: `RegisterCatcacheInvalidation` (604, internal), `RegisterRelcacheInvalidation` (632, internal), `RegisterSyscacheCallback`, `RegisterRelcacheCallback`, `CallSyscacheCallbacks` (1895), and similar for RelSync.
- **State**: global `transInvalInfo` (linked-list head, per-subxact), `inplaceInvalInfo` (separate path for inplace updates), `InvalMessageArrays[2]` (CatCacheMsgs + RelCacheMsgs).

## Key types / structs

- `InvalMessageArray` (175) — `{SharedInvalidationMessage *msgs; int maxmsgs;}`. Two globals: one for catcache, one for relcache. Lives in `TopTransactionContext`. [verified-by-code, inval.c:171-181]
- `InvalidationMsgsGroup` (184) — `{int firstmsg[2]; int nextmsg[2];}`. Per-(sub)transaction-or-command slice into the two arrays. [verified-by-code]
- `InvalidationInfo` (defined later) — control for one logical batch; includes `CurrentCmdInvalidMsgs`, `RelcacheInitFileInval` flag.
- `TransInvalidationInfo` — adds `my_level`, `parent` for subxact stacking, and `PriorCmdInvalidMsgs`.
- `SHAREDINVAL*_ID` constants (in `storage/sinval.h`) — message type IDs interpreted in `LocalExecuteInvalidationMessage` (msg->id >= 0 = catcache id; SHAREDINVALCATALOG_ID = catalog-wide flush; SHAREDINVALRELCACHE_ID = single rel; SHAREDINVALSMGR_ID = smgr; SHAREDINVALRELMAP_ID; SHAREDINVALSNAPSHOT_ID; SHAREDINVALRELSYNC_ID).

## Key invariants and locking [HIGH-RISK SECTION — CITE OR DON'T CLAIM]

- **Ordering: commit BEFORE broadcast.** `RecordTransactionCommit` calls `xactGetCommittedInvalidationMessages` to snapshot the pending list, writes the commit record, then later `AtEOXact_Inval(true)` actually calls `SendSharedInvalidMessages`. The top comment explicitly states: "we have to record the transaction commit before sending SI messages, otherwise the other backends won't see our updated tuples as good." [from-comment, inval.c:30-34]
- **Init-file pre/post bracket.** When `RelcacheInitFileInval` is set, `AtEOXact_Inval(isCommit=true)` does (1) `RelationCacheInitFilePreInvalidate` (takes `RelCacheInitLock`, deletes file), (2) `AppendInvalidationMessages` + `SendSharedInvalidMessages` (broadcasts), (3) `RelationCacheInitFilePostInvalidate` (releases lock). The init-file unlink happens *before* SI broadcast so other backends can't see the SI message and reload the (still-present) stale init file. [verified-by-code, inval.c:1216-1226]
- **Inplace-update path is non-transactional.** `inplaceInvalInfo` is separate from `transInvalInfo`. Messages queued by `CacheInvalidateHeapTupleInplace` are flushed inside the buffer-mutating critical section via `AtInplace_Inval`, which Asserts `CritSectionCount > 0`. Pre-unlink (which can fail) runs via `PreInplace_Inval` Asserting `CritSectionCount == 0`. [verified-by-code, inval.c:1247-1274]
- **Catcache-before-relcache ordering rule.** Per the top comment (inval.c:59-64), pending catcache flushes are issued before relcache flushes so a relcache reload doesn't bring back a catcache tuple that's about to be flushed. The flush order is enforced inside `ProcessInvalidationMessages` / `ProcessInvalidationMessagesMulti`. [from-comment, inval.c:59-64]
- **CommandCounterIncrement boundary.** `CommandEndInvalidationMessages` locally processes `CurrentCmdInvalidMsgs` (no broadcast — we haven't committed) and folds it into `PriorCmdInvalidMsgs`. This is what makes the post-CCI snapshot see the just-modified catalog row. [from-comment, inval.c:1391-1404; verified-by-code, 1406-1432]
- **Subtransaction commit = append to parent.** `AtEOSubXact_Inval(isCommit=true)` calls `CommandEndInvalidationMessages` first to drain the current-cmd list, then either bumps `my_level--` (if parent has no entry yet) or appends `PriorCmdInvalidMsgs` into parent's `PriorCmdInvalidMsgs` and re-indexes parent's `CurrentCmdInvalidMsgs`. Pending init-file inval bubbles up too. [verified-by-code, inval.c:1335-1387]
- **Subtransaction abort = locally process & discard.** No SI broadcast (changes never reached commit). Locally apply `PriorCmdInvalidMsgs` so the in-memory caches drop the entries the aborted subxact had created. [verified-by-code, inval.c:1377-1387]
- **`PostPrepare_Inval` behaves as ABORT** from this backend's perspective: 2PC prepared state is unknown to us until commit/abort arrives, so we undo our local cache changes. If the prepared txn later commits, normal SI delivery brings us back in line. [from-comment, inval.c:980-991]
- **SI-overflow handling.** `AcceptInvalidationMessages` calls `ReceiveSharedInvalidMessages` with two callbacks: `LocalExecuteInvalidationMessage` (per-message) and `InvalidateSystemCaches` (the catchall when SI queue overflowed and individual messages were lost). The overflow path blows away everything. [verified-by-code, inval.c:937-939, 904-918]
- **`debug_discard_caches` hook.** When `DISCARD_CACHES_ENABLED` and `debug_discard_caches > 0`, `AcceptInvalidationMessages` recursively forces full cache flushes up to that depth. Recursion is capped via a static counter. This is the harness that catches stale-cache-after-flush bugs. [from-comment, inval.c:941-977]
- **Logical-decoding WAL emission.** When `wal_level=logical`, command-end inval messages also get written to WAL so the decoder can rebuild a consistent catcache snapshot for in-progress transactions. [from-comment, inval.c:101-103]
- **Hash-only matching from catcache side.** `PrepareToInvalidateCacheTuple` (in catcache.c) computes hash values for the tuple and `RegisterCatcacheInvalidation` records `(cacheId, hashValue, dbId)`. Receivers match by hash, not TID, for VACUUM-FULL safety (see catcache.c notes).

## Functions of note

1. **`LocalExecuteInvalidationMessage`** (823) — the message-type dispatcher. Catcache id → `SysCacheInvalidate` + `CallSyscacheCallbacks`; CATALOG → `CatalogCacheFlushCatalog`; RELCACHE → `RelationCacheInvalidateEntry` (or full sweep if `relId == InvalidOid`) + relcache callbacks; SMGR → `smgrreleaserellocator`; RELMAP → `RelationMapInvalidate`; SNAPSHOT → `InvalidateCatalogSnapshot`; RELSYNC → `CallRelSyncCallbacks`. Also invalidates the catalog snapshot before every catcache flush. [verified-by-code, inval.c:823-902]
2. **`AcceptInvalidationMessages`** (930) — the universal pull-in point. Asserts we're in a transaction (because handlers may access catalogs). Drives `ReceiveSharedInvalidMessages`. Recursively engages `debug_discard_caches`. Called from many places: command start, lock acquire, etc.
3. **`AtEOXact_Inval`** (1196) — commit/abort end. On commit: init-file pre, broadcast, init-file post. On abort: locally process only (we never broadcast aborted changes). [verified-by-code, inval.c:1196-1236]
4. **`CommandEndInvalidationMessages`** (1406) — drains current-command-local effects so the next command sees a consistent cache. Called from `CommandCounterIncrement`.
5. **`CacheInvalidateHeapTupleCommon`** (1433) — the main producer entry point: given a catalog row and an optional newtuple, decides which catcaches to register, whether to register a relcache inval (yes for pg_class/pg_attribute/pg_index/pg_constraint on FKs per inval.c:54-57), and whether to set the init-file-inval flag. Backbone of the producer side.
6. **`PreInplace_Inval` / `AtInplace_Inval`** (1247 / 1260) — the inplace-update bracket. Pre runs outside crit section (can fail/unlink); post runs *inside* crit section after buffer mutation, broadcasts immediately. Mirror image of the transactional pre/broadcast/post triple. [verified-by-code]

## Cross-references

- **Called by**: producers — `heap_insert`/`heap_update`/`heap_delete` for catalogs (`CacheInvalidateHeapTuple`); `heap_inplace_update_and_unlock` (`CacheInvalidateHeapTupleInplace`); `RelationSetNewRelfilenumber`, DDL commands. Driver — `xact.c` (`CommitTransaction`, `AbortTransaction`, `CommandCounterIncrement`); `lock.c` (`LockAcquire` calls `AcceptInvalidationMessages` opportunistically); `InitPostgres`.
- **Calls out to**: `catcache.c` (`PrepareToInvalidateCacheTuple`, `CatCacheInvalidate`, `CatalogCacheFlushCatalog`, `ResetCatalogCaches`), `syscache.c` (`SysCacheInvalidate`), `relcache.c` (`RelationCacheInvalidateEntry`, `RelationCacheInvalidate`, `RelationCacheInitFile*`), `sinval.c` (`SendSharedInvalidMessages`, `ReceiveSharedInvalidMessages`), `relmapper.c` (`RelationMapInvalidate`), `smgr.c` (`smgrreleaserellocator`), `snapmgr.c` (`InvalidateCatalogSnapshot`).
- **Logical decoding**: `ReorderBufferAddInvalidations` consumes inval messages produced for `wal_level=logical`.

## Open questions

- Exact dedup strategy for relcache messages — comment claims "we avoid queuing multiple relcache flush requests for the same relation" but the test predicate lives in `AppendInvalidationMessages` / its helpers [unverified — need to read `RegisterRelcacheInvalidation` body around 632].
- How exactly does `RelcacheInitFileInval` get set? Implication: any inval touching a nailed/critical-index catalog. Need to confirm the gating predicate. [unverified — likely in `CacheInvalidateHeapTupleCommon`.]
- The "we're not certain other backends don't have catalog cache or even relcache entries for temp tables" caveat (inval.c:88-95) — does this still match the current temp-relation model, or has it been tightened? [unverified]

## Confidence tag tally

verified-by-code: 12 — from-comment: 14 — from-readme: 0 — inferred: 0 — unverified: 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
- [idioms/cache-invalidation-registration.md](../../../../../idioms/cache-invalidation-registration.md)
- [idioms/sinvaladt-broadcast.md](../../../../../idioms/sinvaladt-broadcast.md)
- [idioms/syscache-invalidation-flow.md](../../../../../idioms/syscache-invalidation-flow.md)

