# `storage/lmgr/lmgr.c`

- **Source:** `source/src/backend/storage/lmgr/lmgr.c` (1 351 lines)
- **Header:** `source/src/include/storage/lmgr.h`
- **Last verified commit:** `ef6a95c` (2026-06-01)

## 1. Purpose

Object-locking façade over `lock.c`. Builds the appropriate `LOCKTAG` value for each kind of database object (relation, tuple, page, transaction, vxid, database object, advisory, …) and calls `LockAcquire` / `LockRelease` from `lock.c`. Top-of-file comment is just the standard boilerplate `[from-comment]` (`lmgr.c:1-15`); the file is essentially a long list of small wrapper functions.

This is the **user-facing** API: `LockRelation`, `LockTuple`, `XactLockTableWait`, `LockDatabaseObject`, etc.

## 2. Public surface (grouped)

- **Relation locks**: `LockRelation`, `ConditionalLockRelation`, `UnlockRelation`, `LockRelationOid`, `ConditionalLockRelationOid`, `UnlockRelationOid`, `LockRelationId`, `UnlockRelationId`, `LockRelationIdForSession`, `UnlockRelationIdForSession`, `CheckRelationLockedByMe`, `CheckRelationOidLockedByMe`, `LockHasWaitersRelation` (`lmgr.c:107-414`).
- **Relation extension lock**: `LockRelationForExtension`, `ConditionalLockRelationForExtension`, `UnlockRelationForExtension`, `RelationExtensionLockWaiterCount` (`lmgr.c:424-489`). Uses `LOCKTAG_RELATION_EXTEND`.
- **Database frozen-IDs lock**: `LockDatabaseFrozenIds` (`lmgr.c:491`).
- **Page lock**: `LockPage`, `ConditionalLockPage`, `UnlockPage` (`lmgr.c:507-560`). Used by GIN cleanup and a few other places.
- **Tuple lock**: `LockTuple`, `ConditionalLockTuple`, `UnlockTuple` (`lmgr.c:562-620`). Heavyweight tuple lock used as the **arbiter** for row locks; actual row-lock state still lives in xmax/infomask.
- **Transaction-wait**: `XactLockTableInsert`, `XactLockTableDelete`, `XactLockTableWait`, `ConditionalXactLockTableWait` (`lmgr.c:622-784`). Backend takes an exclusive `LOCKTAG_TRANSACTION` on its own xid at start, so a `XactLockTableWait(xid)` blocks until that xid commits/aborts.
- **Speculative insertion** (used by `INSERT … ON CONFLICT`): `SpeculativeInsertionLockAcquire`, `SpeculativeInsertionLockRelease`, `SpeculativeInsertionWait` (`lmgr.c:786-844`). Uses `LOCKTAG_SPECULATIVE_TOKEN`.
- **Wait-for-lockers** (used by CREATE INDEX CONCURRENTLY): `WaitForLockers`, `WaitForLockersMultiple` (`lmgr.c:911, 989`).
- **Database object lock**: `LockDatabaseObject`, `ConditionalLockDatabaseObject`, `UnlockDatabaseObject` (`lmgr.c:1008-1086`).
- **Shared object lock**: `LockSharedObject`, `ConditionalLockSharedObject`, `UnlockSharedObject`, `LockSharedObjectForSession`, `UnlockSharedObjectForSession` (`lmgr.c:1088-1207`).
- **Apply-transaction lock** (logical replication): `LockApplyTransactionForSession`, `UnlockApplyTransactionForSession` (`lmgr.c:1209-1247`). Uses `LOCKTAG_APPLY_TRANSACTION`.
- **Locktag introspection**: `RelationInitLockInfo`, `SetLocktagRelationOid`, `DescribeLockTag`, `GetLockNameFromTagType` (`lmgr.c:70, 88, 1249, 1346`).

## 3. Key types

- `LockRelId` (in `lock.h`): `{Oid relId; Oid dbId}` — owns the dbId-zero-for-shared-rel convention set by `RelationInitLockInfo`.
- `XactLockTableWaitInfo` (`lmgr.c:54-59`): error-callback context for `XactLockTableWait`. Records `oper, rel, ctid` so a wait-on-xact aborts with a helpful errcontext.
- `XLTW_Oper` enum (in `lmgr.h`): names the operation reason for the wait (`XLTW_None`, `XLTW_Update`, `XLTW_Delete`, `XLTW_Lock`, `XLTW_LockUpdated`, `XLTW_InsertIndex`, `XLTW_InsertIndexUnique`, …).

## 4. Key invariants and locking

### `LOCKTAG_TUPLE` is held by at most one backend

`README.tuplock:31-34` `[from-README]`: a backend holds at most one `LOCKTAG_TUPLE` heavyweight lock at a time, so this can't overflow the lock table no matter how many rows are touched. `LockTuple` itself doesn't enforce this — it's an architectural invariant maintained by `heap_lock_tuple`'s single-row scope.

### `LOCKTAG_RELATION_EXTEND` is non-deadlock-eligible

Both checked at `lock.c:951` (`Assert(!IsRelationExtensionLockHeld)` before any other heavyweight acquire) and short-circuited in `deadlock.c:556-557`. `LockRelationForExtension` at `lmgr.c:424` is the only entry that takes this kind.

### Session-level locks survive xact end

`LockRelationIdForSession` (`lmgr.c:391`) calls `LockAcquire(…, sessionLock=true)`. Used by `CREATE INDEX CONCURRENTLY` to keep the relation locked across the multiple internal transactions.

### Speculative-insertion token semantics

`speculativeInsertionToken` is a per-backend counter (`lmgr.c:45`). Wraps freely. Comment at `lmgr.c:32-44` admits the wrap-around race is theoretically possible but worst case results in unrelated wait that resolves quickly.

### `SetLocktagRelationOid` for shared rels

If `relid < FirstNormalObjectId` (system catalog), tries to look up whether it's a shared catalog (databaseId = 0); otherwise uses MyDatabaseId. Builds locktag with the right db field so shared and per-db catalogs don't alias. `[verified-by-code]` (`lmgr.c:88-105`).

## 5. Functions of note

### 5.1 `LockRelationOid` (`lmgr.c:107-150`) — the most-called lock acquisition site

Builds a `LOCKTAG_RELATION` tag for `(MyDatabaseId, relid)` (or `(0, relid)` if shared), calls `LockAcquire(…, dontWait=false)`. On `LOCKACQUIRE_NOT_AVAIL` (never, since dontWait=false) returns. On `LOCKACQUIRE_OK` (genuinely new), runs `AcceptInvalidationMessages` to absorb any sinval invalidations issued while we were waiting — this is the standard PG pattern for ensuring you see a coherent system-catalog view after locking. `[verified-by-code]` (`lmgr.c:135-148`).

### 5.2 `XactLockTableWait` (`lmgr.c:663-738`)

Wait for transaction `xid` to finish. Loops:
1. `SubTransGetTopmostTransaction(xid)` — collapse subxact to top.
2. If `TransactionIdIsCurrentTransactionId` → assert and return (we are the xid; would deadlock).
3. `LockAcquire(LOCKTAG_TRANSACTION(xid), ShareLock, sessionLock=false, dontWait=false)`.
4. `LockRelease(…)` — we wanted the wait, not the lock.
5. If still in progress (`TransactionIdIsInProgress`), loop. Otherwise return.

The loop handles the case where `xid` is a *sub*-xact that committed but its top is still running — the lock on the top-xact will block until the top really finishes.

### 5.3 `WaitForLockers` (`lmgr.c:989-1007`) and `WaitForLockersMultiple` (`lmgr.c:911-988`)

Build a list of every PGPROC currently holding a lock that conflicts with `lockmode` on the given lock tag(s) (via `GetLockConflicts` in `lock.c`); take their VXID locks one by one (which blocks until each backend finishes its transaction). Used by `CREATE INDEX CONCURRENTLY` to wait out concurrent writers without holding a strong lock on the table itself.

### 5.4 `DescribeLockTag` (`lmgr.c:1249-1345`)

Human-readable rendering of a `LOCKTAG`. Used by lock-status SRFs (`pg_locks`) and by deadlock-error messages.

### 5.5 `XactLockTableInsert` (`lmgr.c:622-638`)

Called from `AssignTransactionId` to take the self-exclusive `LOCKTAG_TRANSACTION(xid)` that other backends will wait on. Always succeeds via fast-path because no one else can be holding it (per `README:273-277`).

### 5.6 `LockRelationForExtension` (`lmgr.c:424-441`)

Takes `LOCKTAG_RELATION_EXTEND`. `lock.c:LockAcquireExtended` knows this tag is special and sets `IsRelationExtensionLockHeld = true` after success (so the assertion at line 951 catches violators). The corresponding `Unlock` clears the flag.

## 6. Cross-references

- `lock.c` — every wrapper here is ultimately `LockAcquire`/`LockRelease`.
- `inval.c` — `AcceptInvalidationMessages` called after relation-lock acquisition.
- `subtrans.c` — `SubTransGetTopmostTransaction` used by `XactLockTableWait`.
- `procarray.c` — `TransactionIdIsInProgress` used by `XactLockTableWait`.
- `heapam.c` — invokes `LockTuple`, `SpeculativeInsertionLock*`.
- `index.c` / `indexcmds.c` — invoke `WaitForLockers` for CIC.

## 7. Open questions

1. **The `SetLocktagRelationOid` shared-relation logic.** It uses `IsSharedRelation(relid)` from `catalog/catalog.c`. If a new shared relation is added without updating that list, lock tags would alias. `[from-comment, indirect]`.
2. **Whether session-level locks acquired in a parallel leader propagate to workers.** `LockRelationIdForSession` is leader-only; workers see a fresh PGPROC and don't share session-lock state. Group locking still applies via `LockCheckConflicts`. `[unverified]`.
3. **`speculativeInsertionToken` wrap-around real-world frequency.** 2^32 unrelated insertions in the window is essentially never, but worth a one-line comment that no observed instances exist. `[from-comment]` (`lmgr.c:32-44`).

## 8. Tag tally

- `[verified-by-code]`: 8
- `[from-comment]`: 5
- `[from-README]`: 2
- `[unverified]`: 2

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/lmgr.c | medium (function index + key entries) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/lmgr.c.md |
| source/src/include/storage/lmgr.h | not opened in detail | 2026-06-01 | ef6a95c | (this doc) |
