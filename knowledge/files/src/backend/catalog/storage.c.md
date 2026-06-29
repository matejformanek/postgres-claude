# storage.c

- **Source path:** `source/src/backend/catalog/storage.c`
- **Lines:** ~1 050
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/storage.h`, `catalog/storage_xlog.h`, `storage/smgr/smgr.c`, `access/transam/xact.c`.

## Purpose

"code to create and destroy physical storage for relations." Owns the **pending-deletes list** that defers actual smgr unlink() calls until xact commit/abort, and the matching **pending-sync hash** for skip-WAL relations. Used by every CREATE TABLE / CREATE INDEX / DROP TABLE / TRUNCATE / CLUSTER / VACUUM FULL. Code used to live in `storage/smgr/smgr.c` — the function names still reflect that. [from-comment, storage.c:13-16]

## Mental model

- **PendingRelDelete linked-list** (storage.c:62-77) — every create/drop within the current xact pushes a `(RelFileLocator, procNumber, atCommit, nestLevel)` node. At commit: process nodes with `atCommit=true` (drops). At abort: process nodes with `atCommit=false` (creates that must be undone). Subtransaction commit re-tags the level upward; subtransaction abort processes that level's entries immediately. The list lives in `TopMemoryContext` "to be sure it won't disappear unbetimes". [verified-by-code]
- **pendingSyncHash** (storage.c:71-78) — for permanent relations created while `wal_level=minimal` (i.e., `XLogIsNeeded() == false`), data pages aren't WAL-logged. Instead, the file must be fsync'd at commit. This hash records which relfilenodes need that sync. Aborts drop the hash; parallel-worker exits drop it too (no syncs from workers).

## Public surface

- `RelationCreateStorage` (122) — given a RelFileLocator + persistence, call `smgropen`+`smgrcreate(MAIN_FORKNUM)`, WAL-log via `log_smgrcreate` if needed, queue a delete-on-abort entry, and (for permanent rels under wal_level=minimal) queue a pending-sync. Returns the SMgrRelation. [verified-by-code, storage.c:122-181]
- `log_smgrcreate` (187) — emit `XLOG_SMGR_CREATE` rmgr record (RM_SMGR_ID) carrying RelFileLocator + ForkNum.
- `RelationDropStorage` (207) — queue a delete-at-commit entry. **The physical file is NOT removed here.** If the same relation was created in this xact, both an at-commit and an at-abort entry coexist; either way the file goes away. Comment at storage.c:222-229. [verified-by-code]
- `RelationPreserveStorage` (252) — remove a queued delete (used by the relation mapper at commit, and by ALTER TABLE when reusing an existing index build).
- `RelationTruncate` (289) — truncate a relation to N blocks. Atomically WAL-logs and calls `smgrtruncate`. Tracks the truncation in pendingSyncHash if applicable.
- `RelationPreTruncate` (450) — flush buffers etc. before truncation.
- `RelationCopyStorage` (478) — physical block-by-block copy used by CLUSTER / VACUUM FULL.
- `RelFileLocatorSkippingWAL` (573) — predicate: is this relfilenode currently in the pendingSync set (i.e., its writes don't need to go through WAL).
- `EstimatePendingSyncsSpace` / `SerializePendingSyncs` / `RestorePendingSyncs` (587-672) — parallel-worker setup hooks so a worker knows which relations are skip-WAL.
- **`smgrDoPendingDeletes(bool isCommit)`** (673) — **the load-bearing function.** Called from `CommitTransaction` (CallSubXactCallbacks before, RecordTransactionCommit after) and from `AbortTransaction`. Walks the pending list at the current nest level; for each entry whose `atCommit == isCommit`, calls `smgrdounlinkall()` on the file. Earlier entries (outer levels) are skipped. The function unlinks list entries *before* doing the actual delete so retry-on-failure won't double-process. [verified-by-code, storage.c:673-735]
- `smgrDoPendingSyncs(bool isCommit, bool isParallelWorker)` (741) — at top-level commit: for every relfilenode still in pendingSyncHash (and not also being deleted), call `smgrimmedsync(MAIN_FORKNUM)`. Aborts/parallel-workers throw the hash away.
- `smgrGetPendingDeletes` (893) — return a flat array for 2PC PREPARE.
- `PostPrepare_smgr` (934) — after a successful PREPARE TRANSACTION: throw away the pending list (the PREPARE record carries it; commit/abort prepared will replay it).
- `AtSubCommit_smgr` (955), `AtSubAbort_smgr` (975) — subtransaction hooks. Subcommit promotes the current level's entries to the parent level; subabort processes them as a mini-rollback.
- `smgr_redo` (981) — replay of XLOG_SMGR_CREATE / XLOG_SMGR_TRUNCATE. Calls `smgrcreate` / `smgrtruncate` during recovery.

## The pending-deletes-on-abort guarantee (load-bearing)

This is what makes "CREATE TABLE; <something fails>; ROLLBACK" leak nothing on disk. The sequence is:

1. CREATE TABLE in xact T → `RelationCreateStorage` creates `base/db/N` and queues `{rlocator=N, atCommit=false, nestLevel=T's level}`.
2. T aborts → `AbortTransaction` calls `smgrDoPendingDeletes(isCommit=false)`. The entry's `atCommit (false) == isCommit (false)` → file `N` is unlinked. [verified-by-code]

Symmetric story for DROP: the queued entry has `atCommit=true`, and commit processes it. If the commit *itself* crashes between WAL flush and unlink, recovery does **not** retry the unlink — the file becomes orphaned. PG accepts this; an orphaned file is harmless (no pg_class row points at it) and can be cleaned up by the next `pg_upgrade` or manually.

## Confidence tag tally

`[verified-by-code]=8 [from-comment]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/abort-transaction-cleanup.md](../../../../idioms/abort-transaction-cleanup.md)
- [idioms/vacuum-truncate-relation.md](../../../../idioms/vacuum-truncate-relation.md)

