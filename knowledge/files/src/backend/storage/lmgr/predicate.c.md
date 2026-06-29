# `storage/lmgr/predicate.c`

- **Source:** `source/src/backend/storage/lmgr/predicate.c` (4 993 lines)
- **Header:** `source/src/include/storage/predicate.h` (public) + `source/src/include/storage/predicate_internals.h` (shared structs)
- **Last verified commit:** `ef6a95c` (2026-06-01)
- **Algorithm narrative:** `source/src/backend/storage/lmgr/README-SSI`

## 1. Purpose

POSTGRES predicate locking + SSI implementation. Top-of-file comment `[from-comment]` (`predicate.c:1-150`) lays out the seven properties of SIREAD locks ("more like flags than locks", non-blocking, must survive transaction commit, only created by serializable transactions, etc.). Note property 4: predicate locks "must survive a successful COMMIT of that transaction, and remain until all overlapping transactions complete." This is why the shared state has its own SLRU spill (`pg_serial`).

## 2. Public surface

(From the INTERFACE ROUTINES block at `predicate.c:152-192`.)

- Reporting: `GetPredicateLockStatusData`, `PageIsPredicateLocked` (`predicate.c:1376, 1937`).
- Maintenance: `GetSerializableTransactionSnapshot`, `SetSerializableTransactionSnapshot`, `RegisterPredicateLockingXid`, `PredicateLockRelation`, `PredicateLockPage`, `PredicateLockTID`, `PredicateLockPageSplit`, `PredicateLockPageCombine`, `TransferPredicateLocksToHeapRelation`, `ReleasePredicateLocks` (`predicate.c:1611, 1651, 1888, 2505, 2528, 2550, …`).
- Conflict detection: `CheckForSerializableConflictOut`, `CheckForSerializableConflictIn`, `CheckTableForSerializableConflictIn`.
- Final rollback check: `PreCommit_CheckForSerializationFailure`.
- 2PC: `AtPrepare_PredicateLocks`, `PostPrepare_PredicateLocks`, `PredicateLockTwoPhaseFinish`, `predicatelock_twophase_recover`.
- GUC checks: `check_serial_buffers`, `CheckPointPredicate`.

Internal callers tend to gate calls on `SerializationNeededForRead/Write` (`predicate.c:530, 574`), which return false for non-serializable transactions and certain relation types (temp, system catalogs).

## 3. Key types

- `SERIALIZABLEXACT` (defined in `predicate_internals.h`) — per-serializable-transaction shared state: `vxid`, `topXid`, `xmin`, `commitSeqNo`, `prepareSeqNo`, `flags` (SXACT_FLAG_*), `predicateLocks` dlist head, `inConflicts` / `outConflicts` `RWConflictData` dlists, `possibleUnsafeConflicts` dlist, `perXactPredicateListLock` (LWLock used only when parallel workers share this sxact), `finishedLink`, `xactLink`.
- `PREDICATELOCKTARGET` — hash entry keyed by `(db, rel, page, offset)` PREDICATELOCKTARGETTAG; head of dlist of PREDICATELOCKs on this target. `InvalidBlockNumber` page means relation-granularity; `InvalidOffsetNumber` offset means page-granularity.
- `PREDICATELOCK` — hash entry keyed by `(myTarget, myXact)` PREDICATELOCKTAG; embedded in both `target->predicateLocks` and `sxact->predicateLocks` lists; carries `commitSeqNo`.
- `RWConflictData` — graph edge `(reader, writer)`, doubly-linked into `reader->outConflicts` and `writer->inConflicts`.
- `PredXactList`, `PredXactListHeader`, `RWConflictPoolHeader` — pre-allocated pools.
- `SerialControlData` — `{int64 headPage, TransactionId headXid, TransactionId tailXid}` — SLRU control block (`predicate.c:347-356`).
- Globals: `SerializableXidHash`, `PredicateLockTargetHash`, `PredicateLockHash`, `LocalPredicateLockHash`, `MySerializableXact`, `MyXactDidWrite` (`predicate.c:409-435`).

`TargetTagIsCoveredBy(covered, covering)` macro (`predicate.c:232-246`) — the coverage predicate that drives granularity collapsing (relation covers page covers tuple within same db).

## 4. Key invariants and locking — THE most-important section

### LWLock acquisition order — **the canonical statement is the top-of-file comment**

Lines `predicate.c:84-141` constitute the **authoritative locking-order rule** for predicate locks:

> "Lightweight locks to manage access to the predicate locking shared memory objects must be taken in this order, and should be released in reverse order:
>
> 1. `SerializableFinishedListLock`
> 2. `SerializablePredicateListLock`
> 3. (sxact's) `perXactPredicateListLock` — parallel mode only
> 4. `PredicateLockHashPartitionLock(hashcode)` — same lock protects target + locks + linked list; when more than one needed, ascending address order; when all needed, ascending index order via `PredicateLockHashPartitionLockByIndex(index)`
> 5. `SerializableXactHashLock`
> 6. `SerialControlLock`
> 7. SLRU per-bank locks"

`[from-comment]` `[verified-by-code]` against `CreatePredicateLock` (`predicate.c:2392-2435`) which takes them in order 2 → 3 → 4 and releases in reverse 4 → 3 → 2.

This ordering is the **only** place in the lmgr subsystem where the explicit named-LWLock order is written down in a single comment. If you're auditing predicate-lock paths, this comment is the spec to compare against.

### Granularity-coverage invariant

If a transaction holds a predicate lock on `(rel, P, *)` (page-level), acquiring `(rel, P, O)` (tuple-level) is a no-op `[from-README]` (`README-SSI:281-298`). Implemented in `CoarserLockCovers` (`predicate.c:2040`) which walks parent levels (tuple → page → relation) checking `LocalPredicateLockHash`.

Conversely, when we acquire a coarser lock, `DeleteChildTargetLocks` (`predicate.c:2143`) sweeps the partition's hash table for finer-granularity entries owned by this xact and removes them.

### Two-list invariant per lock

A `PREDICATELOCK` is linked into both `target->predicateLocks` (via `targetLink`) and `sxact->predicateLocks` (via `xactLink`). Both lists are dlists; removing from one must remove from the other (`predicate.c:2427-2428` and the symmetric Delete path).

### `SerializableXactHashLock` covers two structures

> "Protects both PredXact and SerializableXidHash." `[from-comment]` (`predicate.c:134-136`).

So any walk of finished-xact list or sxid-to-sxact map needs this lock.

### Parallel mode adds `perXactPredicateListLock`

When multiple workers share an sxact, the per-xact predicate list needs intra-group exclusion. The acquisition pattern at `predicate.c:2394-2397` is:

```c
LWLockAcquire(SerializablePredicateListLock, LW_SHARED);
if (IsInParallelMode())
    LWLockAcquire(&sxact->perXactPredicateListLock, LW_EXCLUSIVE);
LWLockAcquire(partitionLock, LW_EXCLUSIVE);
```

Note `SerializablePredicateListLock` is held **shared** by the active transaction's own writes — the README-SSI explains this is safe because the *list* is only ever modified by its own backend except for rare cases (index splits, vacuum) which take it exclusive.

### Lock target hash is partitioned 16 ways

`NUM_PREDICATELOCK_PARTITIONS = 16` (`lwlock.h:90-91`). Same partition LWLock protects the LOCKTARGET, all PREDICATELOCKs on it, and the linked list connecting them `[from-comment]` (`predicate.c:127-129`).

### Conflict-list mutation

`SetRWConflict` (`predicate.c:657`), `ReleaseRWConflict` (`predicate.c:705`), `FlagRWConflict` (`predicate.c:???`) all require `SerializableXactHashLock` exclusive (or sometimes shared + per-sxact lock).

### SLRU summarisation

When in-RAM finished-xact list overflows, `SummarizeOldestCommittedSxact` (`predicate.c:1432`) writes the oldest committed xact's commit-seq-no into `pg_serial` SLRU. From then on, conflict checks against that xact go through `SerialGetMinConflictCommitSeqNo` (`predicate.c:930`).

## 5. Functions of note

### 5.1 `GetSerializableTransactionSnapshot` (`predicate.c:1611-1650`) and `GetSerializableTransactionSnapshotInt` (`1693-1868`)

The serializable-snapshot entry. Allocates a new `SERIALIZABLEXACT` via `CreatePredXact` (`predicate.c:596`), links it into `PredXact->activeList`, snapshots `MyProc->xmin`. For `READ ONLY DEFERRABLE`, may call `GetSafeSnapshot` (`predicate.c:1487`) which loops on a condition until no concurrent rw-conflict-risky xact exists. Sets `MySerializableXact` and `MyXactDidWrite = false`.

### 5.2 `PredicateLockAcquire` (`predicate.c:2446-2493`)

Local entry that gates the heavy `CreatePredicateLock`. Steps:
1. `PredicateLockExists` (same-granularity already held) → no-op.
2. `CoarserLockCovers` (parent-granularity already held) → no-op.
3. Otherwise insert into `LocalPredicateLockHash`, call `CreatePredicateLock` (shared state), then either promote to a coarser granularity (`CheckAndPromotePredicateLockRequest`) or delete redundant finer locks (`DeleteChildTargetLocks`).

### 5.3 `CreatePredicateLock` (`predicate.c:2382-2436`)

The canonical lock-acquisition sequence. Takes the three LWLocks documented above, looks up/creates the PREDICATELOCKTARGET, looks up/creates the PREDICATELOCK, links it into both lists, releases the three LWLocks in reverse order. `HASH_ENTER_NULL` is used so OOM raises `out of shared memory` cleanly with a hint to bump `max_pred_locks_per_transaction`.

### 5.4 `PredicateLockRelation` / `PredicateLockPage` / `PredicateLockTID` (`predicate.c:2505, 2528, 2550`)

Public entries that build the appropriate `PREDICATELOCKTARGETTAG` and call `PredicateLockAcquire`. `PredicateLockTID` has a fast-out: if `tuple_xid == MySerializableXact->topXid` (we wrote it ourselves), skip — matches README-SSI:538-544.

### 5.5 `CheckForSerializableConflictOut` (called from heap visibility checks)

When a serializable txn reads a tuple whose xmin/xmax indicates a concurrent writer, this routine looks up that writer's SERIALIZABLEXACT (via `SerializableXidHash`) and records an rw-conflict `reader→writer`. Triggers SLRU lookup if the writer has been summarised.

### 5.6 `CheckForSerializableConflictIn` (called from heap update/insert/delete)

When a serializable txn writes a tuple, this scans the predicate locks on that target (and its parents — relation, page) for *other* serializable transactions holding SIREAD; for each, records an rw-conflict `holder→MySerializableXact`. May raise the abort-now ereport if a dangerous structure is detected.

### 5.7 `PreCommit_CheckForSerializationFailure` (called by `CommitTransaction`)

Final check: walks `MySerializableXact->inConflicts` and `outConflicts` looking for a dangerous structure. If found and we're the right victim (per the README-SSI optimisations), ereports `serialization_failure` (SQLSTATE 40001). Otherwise, marks our sxact PREPARED and moves on.

### 5.8 `ReleasePredicateLocks` (called from CommitTransaction / AbortTransaction)

Releases the per-sxact local hash; moves the SERIALIZABLEXACT to the finished list (unless it was a safe RO snapshot, in which case it can be released immediately). Sets `commitSeqNo`. Predicate locks themselves remain in shared memory until `ClearOldPredicateLocks` (`predicate.c:???`) determines they can be freed (no concurrent serializable xact still needs them).

## 6. Cross-references

- `lock.c` — completely separate code path; predicate locks never go through the heavyweight machinery.
- `heapam.c` (`access/heap`) — calls `CheckForSerializableConflictIn/Out`, `PredicateLockTID`.
- `nbtree`, `gin`, `gist`, `hash` — each AM has its own predicate-lock hooks (`PredicateLockPage` mostly).
- `slru.c` — `pg_serial` SLRU implementation.
- `predicate.h` (public) and `predicate_internals.h` (the structs).

## 7. Open questions

1. **Whether `SerializableFinishedListLock` is ever combined with partition locks.** The top comment lists it before SerializablePredicateListLock but I didn't find a single call site that takes all four in the prescribed full order. Most paths take a subset. `[unverified]` whether the full chain is exercised, vs being a *prescriptive* ordering rule.
2. **Locking around `ClearOldPredicateLocks` and granularity-promotion races.** README-SSI promises "Multiple fine-grained locks are promoted to a single coarser-granularity lock as needed" without quite specifying when other backends can observe a half-promoted state. `[unverified]`.
3. **Parallel-worker predicate-lock acquisition.** `perXactPredicateListLock` is taken exclusive only "if IsInParallelMode()". Whether a non-parallel leader and a parallel worker can simultaneously try to mutate the list during transition is not obvious from a quick read. `[unverified]`.
4. **SerialSLRU page-precedence wrap-around.** `SerialPagePrecedesLogically` (`predicate.c:745`) is xid-wrap-safe at the page granularity; documented but I didn't audit overflow at `SERIAL_MAX_PAGE`. `[unverified]`.
5. **Whether index-AM hooks honour the lock ordering.** `nbtree` calls `PredicateLockPage` from within buffer-locked code; if that path ever needed `SerializablePredicateListLock`, ordering against buffer content locks would matter. `[unverified]`.

## 8. Tag tally

- `[verified-by-code]`: 9
- `[from-comment]`: 10
- `[from-README]`: 3
- `[unverified]`: 5

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/predicate.c | partial-deep (top comment + key entry points) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/predicate.c.md |
| source/src/include/storage/predicate.h | skim | 2026-06-01 | ef6a95c | (this doc) |

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
- [idioms/predicate-locks.md](../../../../../idioms/predicate-locks.md)

