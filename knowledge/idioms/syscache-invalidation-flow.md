# Syscache invalidation flow — local queue → commit-time broadcast → backend dequeue

`inval.c` is the **dispatcher** sitting between catalog DML and the
shared invalidation queue (`sinvaladt`). Its job: queue up invalidation
events as a transaction modifies catalogs, locally apply them at
command boundaries, broadcast them at commit, and process incoming
messages from other backends at transaction start.

The headline tension: when `UPDATE pg_class SET reloptions = ...` runs,
the tuple is **still valid for the current command** (visibility rule:
old tuple is still good until `CommandCounterIncrement`). So we can't
flush the catcache immediately — that would break the very command
that issued the update. We must defer the flush to the **next command
boundary** (locally) and to the **next transaction start** (for other
backends).

The phases:

1. **DML emits inval-message intent** via `CacheInvalidateHeapTuple`.
   Messages accumulate in a per-(sub)transaction `TransInvalidationInfo`.
2. **Each `CommandCounterIncrement` calls `CommandEndInvalidationMessages`**
   which locally processes the current command's queued messages
   (flushes our own catcache/relcache entries) and merges them into
   the prior-commands list.
3. **`xactGetCommittedInvalidationMessages` collects** the full list
   into the commit WAL record. The relcache init-file flag rides
   along.
4. **`RecordTransactionCommit` sends** the messages to the shared
   sinval queue via `SendSharedInvalidMessages`.
5. **Every backend's next `AcceptInvalidationMessages`** dequeues and
   calls `LocalExecuteInvalidationMessage` for each, dispatching
   into `SysCacheInvalidate` / `RelationCacheInvalidate(Entry)` /
   smgr-release / etc.
6. **A queue overflow** triggers `InvalidateSystemCaches` — a
   nuclear-option blow-away-and-rebuild for the whole cache.

This doc walks the deferral rationale, the per-xact message arrays,
the local-then-broadcast sequence at xact commit, the
`AcceptInvalidationMessages` consumer, the message-type dispatch,
and the inplace-update + subxact + 2PC variants.

Companion docs:
- [[syscache-catcache-internals]] — the `CatCacheInvalidate` target.
- [[relcache-build]] — `RelationCacheInvalidateEntry` target.
- [[cache-invalidation-registration]] — the public `CacheRegister*Callback` API.
- [[sinvaladt-broadcast]] — the underlying shared queue.

## Anchors

- `source/src/backend/utils/cache/inval.c:1-112` — banner: "This is subtle stuff, so pay attention." The full deferral + commit-time-broadcast rationale.
- `source/src/backend/utils/cache/inval.c:570-680` — `Register*Invalidation` builders.
- `source/src/backend/utils/cache/inval.c:822-902` — `LocalExecuteInvalidationMessage` (the consumer dispatch).
- `source/src/backend/utils/cache/inval.c:915-978` — `InvalidateSystemCaches` + `AcceptInvalidationMessages`.
- `source/src/backend/utils/cache/inval.c:1011-1090` — `xactGetCommittedInvalidationMessages` (collect at commit).
- `source/src/backend/utils/cache/inval.c:1134-1172` — `ProcessCommittedInvalidationMessages` (recovery / hot standby).
- `source/src/backend/utils/cache/inval.c:1195-1238` — `AtEOXact_Inval` (the actual broadcast).
- `source/src/backend/utils/cache/inval.c:1306-1388` — `AtEOSubXact_Inval` (subxact roll-up vs roll-back).
- `source/src/backend/utils/cache/inval.c:1405-1425` — `CommandEndInvalidationMessages` (CCI hook).
- `source/src/backend/utils/cache/inval.c:1432-1700` — `CacheInvalidateHeapTuple*` (write side; called from heapam).
- `source/src/backend/storage/ipc/sinvaladt.c` — the shared queue itself.
- `source/src/include/storage/sinval.h` — `SharedInvalidationMessage` union + `SHAREDINVAL*_ID` constants.

## The deferral rule

The banner spells it out:

> When a tuple is updated or deleted, our standard visibility rules
> consider that it is *still valid* so long as we are in the same
> command, ie, until the next CommandCounterIncrement() or transaction
> commit. … Therefore, we cannot simply flush a tuple from the system
> caches during heap_update() or heap_delete(). The tuple is still
> good at that point; what's more, even if we did flush it, it might
> be reloaded into the caches by a later request in the same command.

[from-comment] (`inval.c:7-22`).

The corollary: we also can't immediately flush inserts (they could be
needed by negative-cache-entry invalidations), and we need to remember
**both** deletes and inserts until end-of-xact in case we abort.

## The message struct — SharedInvalidationMessage

```c
/* storage/sinval.h (sketch) */
typedef union SharedInvalidationMessage {
    struct {                                    /* id >= 0: catcache */
        int8       id;
        char       __padding[3];
        Oid        dbId;
        uint32     hashValue;
    } cc;                                       /* SHAREDINVALCATCACHE = cache.id */

    struct {                                    /* id = SHAREDINVALCATALOG_ID */
        int8       id;
        char       __padding[3];
        Oid        dbId;
        Oid        catId;
    } cat;

    struct {                                    /* id = SHAREDINVALRELCACHE_ID */
        int8       id;
        char       __padding[3];
        Oid        dbId;
        Oid        relId;
    } rc;

    struct {                                    /* id = SHAREDINVALSMGR_ID */
        int8       id;
        int8       backend_hi;
        uint16     backend_lo;
        RelFileLocator rlocator;
    } sm;

    struct sn {                                 /* id = SHAREDINVALSNAPSHOT_ID */
        int8       id;
        char       __padding[3];
        Oid        dbId;
        Oid        relId;
    } sn;

    struct rm {                                 /* id = SHAREDINVALRELMAP_ID */
        int8       id;
        char       __padding[7];
        Oid        dbId;
    } rm;

    struct rs {                                 /* id = SHAREDINVALRELSYNC_ID */
        int8       id;
        char       __padding[3];
        Oid        dbId;
        Oid        relid;
    } rs;
} SharedInvalidationMessage;
```

Fixed 16-byte messages on 64-bit (the union is sized by the largest
member). `id >= 0` means catcache invalidation with `id == cache_id`;
negative IDs are the discriminated-union tags for the other types
(catalog-wide, relcache, smgr, snapshot, relmap, relsync).
[verified-by-code] (`inval.c:825,836,847,866,878,886,894`).

## The write side — CacheInvalidateHeapTuple

Called by `heapam.c` for every catalog tuple insert/update/delete:

```c
/* inval.c:1567 */
void CacheInvalidateHeapTuple(Relation relation, HeapTuple tuple, HeapTuple newtuple) {
    CacheInvalidateHeapTupleCommon(relation, tuple, newtuple, PrepareInvalidationState);
}

/* inval.c:1432 — common body */
static void CacheInvalidateHeapTupleCommon(rel, tuple, newtuple, prepare) {
    if (IsBootstrapProcessingMode()) return;
    if (!IsCatalogRelation(relation)) return;        /* short-circuit for user tables */

    info = prepare();                                /* allocate TransInvalidationInfo etc. */
    PrepareToInvalidateCacheTuple(relation, tuple, newtuple, RegisterCatcacheInvalidation, info);

    /* For pg_class/pg_attribute/pg_index/pg_constraint, also register relcache inval */
    if (relation == pg_class) RegisterRelcacheInvalidation(info, dbId, relId);
    ...
}
```

Three properties:

1. **Bootstrap exit**: bootstrap has no caches yet; messages would
   leak.
2. **User-table short-circuit**: a tuple in `user_table` is never
   in any catcache and can't affect any relcache. Skip.
   [from-comment] (`inval.c:1450-1456`).
3. **Cross-catalog cascade**: a single `UPDATE pg_class` may register
   *multiple* invalidations — one per catcache that has `pg_class`
   as its relation, plus a relcache flush for the relation
   described by the pg_class row. `PrepareToInvalidateCacheTuple`
   (in `catcache.c`) walks the cache-list and calls back
   `RegisterCatcacheInvalidation` once per relevant cache. [from-comment]
   (`inval.c:44-52`).

The actual message just goes onto an in-memory array keyed by the
current `TransInvalidationInfo` stack level.

## In-xact local processing — CommandEndInvalidationMessages

```c
/* inval.c:1405 */
void CommandEndInvalidationMessages(void) {
    if (transInvalInfo == NULL) return;

    /* Locally flush the current command's invalidations */
    ProcessInvalidationMessages(&transInvalInfo->ii.CurrentCmdInvalidMsgs,
                                LocalExecuteInvalidationMessage);

    /* WAL-log per-command invalidations for logical decoding */
    if (XLogLogicalInfoActive())
        LogLogicalInvalidations();

    /* Roll CurrentCmdInvalidMsgs into PriorCmdInvalidMsgs */
    AppendInvalidationMessages(&transInvalInfo->PriorCmdInvalidMsgs,
                               &transInvalInfo->ii.CurrentCmdInvalidMsgs);
}
```

Called from `CommandCounterIncrement` (after the CID bump). Two phases:

1. **Locally execute** the current command's queued messages —
   flushes *our own* catcache/relcache entries so we don't see
   stale data in the *next* command of this transaction.
2. **Roll forward**: messages move from `CurrentCmdInvalidMsgs` to
   `PriorCmdInvalidMsgs`. The "current command" arena is reset for
   the next command.

The `LogLogicalInvalidations` call at the bottom is the WAL-emit for
**logical decoding**: invalidations that happen during a transaction
must be replayable by `wal_level = logical` consumers so they can
keep their own catcache in sync as decoding scans the WAL stream
forward. [from-comment] (`inval.c:101-103`).

## End-of-xact broadcast — AtEOXact_Inval

```c
/* inval.c:1195 */
void AtEOXact_Inval(bool isCommit) {
    inplaceInvalInfo = NULL;
    if (transInvalInfo == NULL) return;
    Assert(transInvalInfo->my_level == 1 && transInvalInfo->parent == NULL);

    if (isCommit) {
        /* Step 1: pre-invalidate the relcache init file */
        if (transInvalInfo->ii.RelcacheInitFileInval)
            RelationCacheInitFilePreInvalidate();

        /* Step 2: merge current command into prior */
        AppendInvalidationMessages(&transInvalInfo->PriorCmdInvalidMsgs,
                                   &transInvalInfo->ii.CurrentCmdInvalidMsgs);

        /* Step 3: BROADCAST */
        ProcessInvalidationMessagesMulti(&transInvalInfo->PriorCmdInvalidMsgs,
                                         SendSharedInvalidMessages);

        /* Step 4: post-invalidate the relcache init file */
        if (transInvalInfo->ii.RelcacheInitFileInval)
            RelationCacheInitFilePostInvalidate();
    } else {
        /* Abort: locally process PriorCmdInvalidMsgs to undo our local cache changes */
        ProcessInvalidationMessages(&transInvalInfo->PriorCmdInvalidMsgs,
                                    LocalExecuteInvalidationMessage);
    }
    /* Memory freed by TopTransactionContext reset */
}
```

[verified-by-code] (`inval.c:1195-1238`).

**Commit path**: send to other backends (not to ourselves —
`SendSharedInvalidMessages` does not deliver to the sender). The next
`AcceptInvalidationMessages` at xact-start *will* re-deliver, so
processing-our-own at commit is unnecessary.

**Abort path**: locally process to undo any local cache state we
might have created (e.g. negative entries for inserts that are now
rolled back). No broadcast — other backends never saw our changes.

The **relcache init-file** pre/post-invalidate dance is for crash
safety: if we crash between pre and broadcast, the init file is
already known-stale so backends will rebuild from scratch. If we
crash between broadcast and post, the same. The combination "send
SI message + delete init file" is what makes a DDL truly visible to
all backends after recovery.

## Commit WAL — xactGetCommittedInvalidationMessages

```c
/* inval.c:1011 */
int xactGetCommittedInvalidationMessages(SharedInvalidationMessage **msgs,
                                          bool *RelcacheInitFileInval)
{
    if (transInvalInfo == NULL) {
        *RelcacheInitFileInval = false; *msgs = NULL; return 0;
    }
    Assert(transInvalInfo->my_level == 1);
    *RelcacheInitFileInval = transInvalInfo->ii.RelcacheInitFileInval;

    /* Allocate one contiguous array and copy in PriorCmdInvalidMsgs + CurrentCmdInvalidMsgs */
    nummsgs = NumMessagesInGroup(&PriorCmdInvalidMsgs) +
              NumMessagesInGroup(&CurrentCmdInvalidMsgs);
    *msgs = msgarray = MemoryContextAlloc(CurTransactionContext, ...);
    nmsgs = 0;
    ProcessMessageSubGroupMulti(...);              /* prior messages */
    ProcessMessageSubGroupMulti(...);              /* current messages */
    Assert(nmsgs == nummsgs);
    return nmsgs;
}
```

Called from `RecordTransactionCommit` to **embed the full inval
message set in the commit WAL record**. Crash recovery and hot
standby replay re-execute these messages via
`ProcessCommittedInvalidationMessages` so the standby's caches
mirror the primary's. [from-comment] (`inval.c:999-1009`).

`ProcessCommittedInvalidationMessages` (`inval.c:1135`) is the replay
counterpart:

```c
if (RelcacheInitFileInval) {
    if (OidIsValid(dbid)) DatabasePath = GetDatabasePath(dbid, tsid);
    RelationCacheInitFilePreInvalidate();
    ...
}
SendSharedInvalidMessages(msgs, nmsgs);
if (RelcacheInitFileInval) RelationCacheInitFilePostInvalidate();
```

Same pre/broadcast/post pattern. The standby's connected backends
will pick up the messages at their next `AcceptInvalidationMessages`.

## The consumer — AcceptInvalidationMessages

```c
/* inval.c:929 */
void AcceptInvalidationMessages(void) {
    ReceiveSharedInvalidMessages(LocalExecuteInvalidationMessage,
                                 InvalidateSystemCaches);
#ifdef DISCARD_CACHES_ENABLED
    /* debug_discard_caches: forcibly invalidate everything at each call */
    if (recursion_depth < debug_discard_caches) {
        recursion_depth++;
        InvalidateSystemCachesExtended(true);
        recursion_depth--;
    }
#endif
}
```

`ReceiveSharedInvalidMessages(callback, reset_callback)` walks the
sinval queue from the backend's last-read position to the head:

- For each message: call `callback(msg)` — i.e.
  `LocalExecuteInvalidationMessage`.
- If the queue overflowed (we missed messages): call
  `reset_callback()` — i.e. `InvalidateSystemCaches` — which blows
  away everything and rebuilds refcounted entries.

The `debug_discard_caches` mechanism (formerly `CLOBBER_CACHE_ALWAYS`)
forces invalidation at every `AcceptInvalidationMessages` for testing.
At depth 1 the regression tests run ~100× slower; at depth 3 ~10000×
slower. [from-comment] (`inval.c:941-963`).

## The dispatcher — LocalExecuteInvalidationMessage

```c
/* inval.c:822 */
void LocalExecuteInvalidationMessage(SharedInvalidationMessage *msg) {
    if (msg->id >= 0) {                              /* catcache */
        if (msg->cc.dbId == MyDatabaseId || msg->cc.dbId == InvalidOid) {
            InvalidateCatalogSnapshot();
            SysCacheInvalidate(msg->cc.id, msg->cc.hashValue);
            CallSyscacheCallbacks(msg->cc.id, msg->cc.hashValue);
        }
    }
    else if (msg->id == SHAREDINVALCATALOG_ID) {     /* whole catalog */
        if (msg->cat.dbId == MyDatabaseId || msg->cat.dbId == InvalidOid) {
            InvalidateCatalogSnapshot();
            CatalogCacheFlushCatalog(msg->cat.catId);
        }
    }
    else if (msg->id == SHAREDINVALRELCACHE_ID) {    /* relcache */
        if (msg->rc.dbId == MyDatabaseId || msg->rc.dbId == InvalidOid) {
            if (msg->rc.relId == InvalidOid)
                RelationCacheInvalidate(false);
            else
                RelationCacheInvalidateEntry(msg->rc.relId);
            /* Call registered relcache callbacks */
            for (i = 0; i < relcache_callback_count; i++)
                relcache_callback_list[i].function(arg, msg->rc.relId);
        }
    }
    else if (msg->id == SHAREDINVALSMGR_ID) {        /* smgr release */
        rlocator.locator = msg->sm.rlocator;
        rlocator.backend = (msg->sm.backend_hi << 16) | msg->sm.backend_lo;
        smgrreleaserellocator(rlocator);             /* no db-filter (cross-db smgr exists) */
    }
    else if (msg->id == SHAREDINVALRELMAP_ID) {       /* pg_filenode.map invalidated */
        if (msg->rm.dbId == InvalidOid)              RelationMapInvalidate(true);
        else if (msg->rm.dbId == MyDatabaseId)       RelationMapInvalidate(false);
    }
    else if (msg->id == SHAREDINVALSNAPSHOT_ID) {    /* catalog snapshot */
        InvalidateCatalogSnapshot();
    }
    else if (msg->id == SHAREDINVALRELSYNC_ID) {     /* logical-replica relsync */
        if (msg->rs.dbId == MyDatabaseId)
            CallRelSyncCallbacks(msg->rs.relid);
    }
    else
        elog(FATAL, "unrecognized SI message ID: %d", msg->id);
}
```

[verified-by-code] (`inval.c:822-902`).

Three properties:

1. **Database scoping** — catcache, catalog, relcache, relmap,
   snapshot all check `dbId == MyDatabaseId || dbId == InvalidOid`
   (shared catalogs). smgr does **not** (smgr entries can exist
   for other databases — e.g. during ALTER DATABASE).
2. **Catalog snapshot eviction first** — every catcache invalidation
   also calls `InvalidateCatalogSnapshot` because the cached
   catalog snapshot may have already cached invisible-to-us tuples.
3. **Callback fan-out** — `CallSyscacheCallbacks` and the
   `relcache_callback_list` walk are how higher-level caches
   (typcache, plancache, partition pruning, etc.) get notified.
   See [[cache-invalidation-registration]].

## Subtransaction handling — AtEOSubXact_Inval

```c
/* inval.c:1306 */
void AtEOSubXact_Inval(bool isCommit) {
    if (transInvalInfo == NULL) return;
    if (transInvalInfo->my_level != GetCurrentTransactionNestLevel()) return;

    if (isCommit) {
        CommandEndInvalidationMessages();                 /* finalize current command */

        /* Pop level, hand messages up to parent */
        if (myInfo->parent == NULL || myInfo->parent->my_level < my_level - 1) {
            myInfo->my_level--;                           /* just decrement label */
            return;
        }
        AppendInvalidationMessages(&parent->PriorCmdInvalidMsgs,
                                   &myInfo->PriorCmdInvalidMsgs);
        if (myInfo->ii.RelcacheInitFileInval)
            myInfo->parent->ii.RelcacheInitFileInval = true;
        transInvalInfo = myInfo->parent;
    } else {
        /* Abort: locally execute messages to undo our cache state */
        ProcessInvalidationMessages(&myInfo->PriorCmdInvalidMsgs,
                                    LocalExecuteInvalidationMessage);
        transInvalInfo = myInfo->parent;
    }
}
```

[verified-by-code] (`inval.c:1306-1388`).

Subxact **commit**: bubble messages up; parent xact will broadcast at
its own end. Subxact **abort**: locally execute to undo our local
cache mutations; messages discarded.

The lazy-create optimization at line 1346 ("just adjust the level of
our own entry") avoids allocating a parent `TransInvalidationInfo` if
we can simply relabel the current one. Common case: every subxact
inherits its parent's empty inval state, so subxact-commit just
relabels.

## Inplace updates — bypassing the normal flow

`heap_inplace_update_and_unlock` (used by VACUUM to update pg_class
stats, by certain catalog ops) cannot defer invalidation because the
update is **not** transactional — it commits with the WAL record
itself. The variant flow:

- `CacheInvalidateHeapTupleInplace(rel, tuple, newtuple)` registers
  into `inplaceInvalInfo` (NOT `transInvalInfo`).
- `PreInplace_Inval()` runs **before** the buffer-write critical
  section — unlinks the relcache init file if needed.
- `AtInplace_Inval()` runs **inside** the critical section,
  **immediately broadcasts** via `SendSharedInvalidMessages` (no
  defer).
- The inplaceInvalInfo is allocated in `CurrentMemoryContext` (vs
  TopTransactionContext for transactional inval) because it lives
  only for the duration of the update.

[from-comment] (`inval.c:97-99`, `inval.c:1239-1273`).

This is one of the **few** places PostgreSQL broadcasts inval
synchronously — the rule is otherwise "transactional, defer until
commit." Inplace must bypass because there's no commit boundary to
defer to.

## 2PC — PostPrepare_Inval

`PostPrepare_Inval(void)` (`inval.c:992`) just calls
`AtEOXact_Inval(false)` — treats prepared-not-committed as a local
abort. The prepared xact is "outside the world" until it commits,
so its catcache changes must be undone locally. On the eventual
commit (possibly from another backend), the SI messages are sent
just like any other xact commit; the original session participates
like any other backend via `AcceptInvalidationMessages`.

## InvalidateSystemCaches — the nuclear option

```c
/* inval.c:915 */
void InvalidateSystemCaches(void) {
    InvalidateSystemCachesExtended(false);
}
```

Called when the sinval queue overflows. Walks every catcache and
`ResetCatalogCache`s it; walks the relcache and either flushes or
soft-evicts each entry. Refcounted entries get rebuilt from scratch
on next access.

Also called by the `debug_discard_caches` test mechanism (forcibly,
at every `AcceptInvalidationMessages` if `debug_discard_caches > 0`).

## The relcache init-file dance

The init file (`pg_internal.init`) caches the nailed-catalog relcache
entries plus frequently-used-system relcache entries (see
[[relcache-build]]). When *any* DDL changes a nailed catalog (or a
critical index), the init file must be invalidated so new backends
rebuild from scratch.

The `RelcacheInitFileInval` flag on `TransInvalidationInfo` rides
with the inval messages:

- DDL that changes a nailed relation sets `RelcacheInitFileInval = true`
  via `RelationCacheInvalidateEntry`'s caller path.
- `AtEOXact_Inval` calls `RelationCacheInitFilePreInvalidate` (delete
  the file) BEFORE broadcasting messages and
  `RelationCacheInitFilePostInvalidate` AFTER. The pre+post bracketing
  is for crash safety — a crash in any phase leaves the system in a
  consistent "init file is gone, must rebuild" state. [from-comment]
  (`inval.c:82-86`).

## Invariants and races

1. **Local processing happens at CCI** (or end-of-(sub)command), not
   at heap-write time. The tuple is still valid for the writer
   within the same command. [from-comment] (`inval.c:7-22`).
2. **Broadcast happens at top-xact commit**, not at subxact commit.
   Subxacts roll their messages up to the parent. [from-comment]
   (`inval.c:36-38`).
3. **Sender does not receive its own messages** — local processing
   at command/xact end handles that. [verified-by-code]
   (`inval.c:1178-1183`).
4. **Inplace updates bypass deferral** — must broadcast inside the
   WAL crit section. [from-comment] (`inval.c:97-99`).
5. **Queue overflow triggers InvalidateSystemCaches** — a wholesale
   blow-away. The cost is amortized: if a backend falls so far
   behind that the queue overflows, rebuilding everything is
   cheaper than reading thousands of missed messages.
   [from-comment] (`inval.c:911-913`).
6. **`AcceptInvalidationMessages` is called at xact start** (in
   `StartTransaction`) and at every catalog-relation `table_open` in
   the slow path. [verified-by-code] (`inval.c:925-928`).
7. **Database scoping is one-way**: catcache/relcache messages for
   other databases are dropped silently. Shared catalogs use
   `dbId == InvalidOid` and reach every backend.
8. **smgr messages cross databases** because a backend can have
   smgr entries for any database it has touched (rare, but possible
   via ALTER DATABASE).
9. **Logical decoding requires per-command WAL inval logging** —
   `LogLogicalInvalidations` in `CommandEndInvalidationMessages`
   only fires when `wal_level = logical`. [from-comment]
   (`inval.c:101-103`).

## Useful greps

```bash
# Producers (write side):
grep -nE "^CacheInvalidate[A-Z]" source/src/backend/utils/cache/inval.c

# Consumer dispatch:
grep -nE "^LocalExecuteInvalidationMessage|^AcceptInvalidationMessages|^InvalidateSystemCaches" \
       source/src/backend/utils/cache/inval.c

# End-of-(sub)xact handling:
grep -nE "^AtEOXact_Inval|^AtEOSubXact_Inval|^PostPrepare_Inval|^PreInplace_Inval|^AtInplace_Inval|^CommandEndInvalidationMessages" \
       source/src/backend/utils/cache/inval.c

# Commit-WAL embedding:
grep -nE "xactGetCommittedInvalidationMessages|ProcessCommittedInvalidationMessages" \
       source/src/backend/utils/cache/inval.c

# Init-file pre/post:
grep -nE "RelationCacheInitFilePreInvalidate|RelationCacheInitFilePostInvalidate" \
       source/src/backend/utils/cache/

# SI message type IDs:
grep -n "SHAREDINVAL" source/src/include/storage/sinval.h
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/ipc/sinvaladt.c`](../files/src/backend/storage/ipc/sinvaladt.c.md) | — | shared queue itself |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1 | banner: "This is subtle stuff, so pay attention." The full deferral + commit-time-broadcast rationale |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 570 | RegisterInvalidation builders |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 822 | LocalExecuteInvalidationMessage (the consumer dispatch) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 915 | InvalidateSystemCaches + AcceptInvalidationMessages |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1011 | xactGetCommittedInvalidationMessages (collect at commit) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1134 | ProcessCommittedInvalidationMessages (recovery / hot standby) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1195 | AtEOXact_Inval (the actual broadcast) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1306 | AtEOSubXact_Inval (subxact roll-up vs roll-back) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1405 | CommandEndInvalidationMessages (CCI hook) |
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | 1432 | CacheInvalidateHeapTuple (write side; called from heapam) |
| [`src/include/storage/sinval.h`](../files/src/include/storage/sinval.h.md) | — | SharedInvalidationMessage union + SHAREDINVAL_ID constants |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[syscache-catcache-internals]] — `SysCacheInvalidate` → `CatCacheInvalidate` target.
- [[relcache-build]] — `RelationCacheInvalidateEntry` target.
- [[cache-invalidation-registration]] — public `CacheRegister*Callback` API for higher-level caches.
- [[sinvaladt-broadcast]] — shared queue mechanics + overflow detection.
- [[logical-decoding-snapshot]] — per-command inval WAL log for decoders.
- `source/src/include/storage/sinval.h` — message struct + IDs.
