# `storage/lmgr/lock.c`

- **Source:** `source/src/backend/storage/lmgr/lock.c` (4 865 lines)
- **Header:** `source/src/include/storage/lock.h`
- **Last verified commit:** `ef6a95c` (2026-06-01)
- **README:** `source/src/backend/storage/lmgr/README` (see `README.md` summary)

## 1. Purpose

POSTGRES primary heavyweight-lock mechanism. Implements the shared-memory `LOCK` + `PROCLOCK` tables, the per-backend `LOCALLOCK` table, the fast-path locking shortcut, conflict checking, and the 2PC integration. Most callers go through `lmgr.c` rather than calling here directly. Top-of-file comment `[from-comment]` (`lock.c:13-26`):

> A lock table is a shared memory hash table. When a process tries to acquire a lock of a type that conflicts with existing locks, it is put to sleep using the routines in storage/lmgr/proc.c.
>
> For the most part, this code should be invoked via lmgr.c or another lock-management module, not directly.
>
> Interface: `LockManagerShmemInit()`, `GetLocksMethodTable()`, `GetLockTagsMethodTable()`, `LockAcquire()`, `LockRelease()`, `LockReleaseAll()`, `LockCheckConflicts()`, `GrantLock()`.

## 2. Public surface

Acquisition/release: `LockAcquire`, `LockAcquireExtended`, `LockRelease`, `LockReleaseAll`, `LockReleaseSession`, `LockReleaseCurrentOwner`, `LockReassignCurrentOwner` (`lock.c:806, 833, 2110, 2315, 2589, 2619, 2714`).

Queries: `LockHeldByMe`, `LockHasWaiters`, `LockWaiterCount`, `DoLockModesConflict` (`lock.c:640, 693, 4836, 620`).

Internal but called by `proc.c` / `deadlock.c`: `GrantLock`, `LockCheckConflicts`, `RemoveFromWaitQueue`, `GetLockConflicts`, `MarkLockClear`, `GrantAwaitedLock`, `GetAwaitedLock` (`lock.c:1666, 1537, 2054, 3077, 1928, 1897, 1906`).

Status/reporting: `GetLockStatusData`, `GetBlockerStatusData`, `GetRunningTransactionLocks`, `GetLockmodeName`, `DescribeLockTag` (in `lmgr.c`).

2PC: `lock_twophase_recover`, `lock_twophase_standby_recover`, `lock_twophase_postcommit`, `lock_twophase_postabort`, `AtPrepare_Locks`, `PostPrepare_Locks` (`lock.c:4339-4598, 3484, 3580`).

VXID: `VirtualXactLockTableInsert`, `VirtualXactLockTableCleanup`, `VirtualXactLock`, `XactLockForVirtualXact` (`lock.c:4602, 4625, 4725, 4674`).

Hash codes & method table: `LockTagHashCode`, `proclock_hash`, `ProcLockHashCode`, `GetLocksMethodTable`, `GetLockTagsMethodTable` (`lock.c:554, 571, 602, 524, 536`).

Init/shmem: `LockManagerShmemRequest`, `LockManagerShmemInit`, `InitLockManagerAccess` (`lock.c:451, 493, 502`).

## 3. Key types and structures

- `LockMethodData` / `LockMethod` — per-method conflict table. Only two instances: `default_lockmethod` and `user_lockmethod`, both with identical conflict tables. `[verified-by-code]` (`lock.c:128-157`).
- `LockConflicts[]` — the canonical 8×8 conflict matrix in `LOCKBIT_ON` form `[verified-by-code]` (`lock.c:68-108`). This is *the* reference for what mode-pairs conflict; the SQL docs page is generated from it `[from-comment]` (`lock.c:63-68`).
- `FastPathStrongRelationLockData` — `{slock_t mutex; uint32 count[1024]}`; spinlock-protected counter array `[verified-by-code]` (`lock.c:309-315`).
- `IsRelationExtensionLockHeld` — assertion-only flag enforcing rule 7 in `locking-overview.md`: relation-extension lock cannot be held while acquiring any other heavyweight lock `[from-comment]` (`lock.c:181-194`); asserted at `lock.c:951`.
- `TwoPhaseLockRecord` — 2PC state file record `{LOCKTAG, LOCKMODE}` `[verified-by-code]` (`lock.c:161-165`).
- `LOCK`, `PROCLOCK`, `LOCALLOCK` — defined in `lock.h:139-272` (see `README` §50-199). LOCK is hash-keyed by LOCKTAG; PROCLOCK by `(myLock, myProc)`; LOCALLOCK is backend-private, hash-keyed by `(LOCKTAG, LOCKMODE)`.

`FastPathLocalUseCounts[FP_LOCK_GROUPS_PER_BACKEND_MAX]` is a static per-backend counter array; "might be higher than the real number if another backend has transferred our locks to the primary lock table, but it can never be lower" `[from-comment]` (`lock.c:168-179`).

## 4. Key invariants and locking

These are the rules a contributor must know before editing this file.

### Partition LWLock rules

- 16 partitions (`NUM_LOCK_PARTITIONS = 1 << 4` in `lwlock.h:86-87`). Partition = `hashcode mod 16`.
- `LockHashPartitionLock(hashcode)` selects the partition LWLock for a single lock; macros in `lock.h:355-361` `[verified-by-code]`.
- **Multi-partition acquisitions must be in partition-number order.** Enforced by `CheckDeadLock` in `proc.c:1871-1872` `[verified-by-code]`. See `README:239-244` `[from-README]`.
- Group-leader fields (`lockGroupLeader`, `lockGroupMembers`, `lockGroupLink`) are protected by the partition LWLock chosen via `LockHashPartitionLockByProc(leader)` = `hash(leader's pgprocno) mod 16` `[from-README]` (`README:660-667`) `[verified-by-code]` (`lock.h:363-373`).

### Fast-path interlock — the **canonical** statement is `README:306-321` + the strong-locker code at `lock.c:2885-2954`

- Each backend's `fpLockBits/fpRelId/fpVXIDLock` are protected by its own `PGPROC.fpInfoLock` LWLock (declared `proc.h:330`).
- **Weak (fast-path) acquirer** order: `LWLockAcquire(&MyProc->fpInfoLock, LW_EXCLUSIVE)` → check `FastPathStrongRelationLocks->count[fasthashcode] == 0` → `FastPathGrantRelationLock` → release `fpInfoLock`. `[verified-by-code]` (`lock.c:998-1004`).
- **Strong-locker** order (in `FastPathTransferRelationLocks`, `lock.c:2885-2954`): for each PGPROC in `ProcGlobal->allProcs`: `LWLockAcquire(&proc->fpInfoLock)` → inside that, `LWLockAcquire(partitionLock)` → transfer slots → `LWLockRelease(partitionLock)` → `LWLockRelease(&proc->fpInfoLock)`. **So the operative ordering is `fpInfoLock → partitionLock`.** `[verified-by-code]` (`lock.c:2890, 2928, 2948, 2953`).
- This ordering is **not stated** anywhere else in the codebase as a top-level rule; it is implicit in `FastPathTransferRelationLocks`. `[unverified]` whether `LockAcquireExtended`'s weak path is allowed to hold `fpInfoLock` while *also* taking the partition lock — reading `lock.c:998-1064`, the weak path releases `fpInfoLock` at line 1004 *before* taking the partition lock at line 1064, so the ordering doesn't actually arise on the weak path.

### Relation-extension lock

- Asserted at `lock.c:951`: `Assert(!IsRelationExtensionLockHeld)` is checked on entry to `LockAcquireExtended` for any lock other than the same RELATION_EXTEND lock itself. `[verified-by-code]`.
- The deadlock detector also short-circuits any waits-for edge from a relation-extension lock at `deadlock.c:556-557`: "The relation extension lock can never participate in actual deadlock cycle." `[from-comment]`.

### Strong-lock acquire/commit/abort dance

- `BeginStrongLockAcquire` at `lock.c:1832`: bumps `FastPathStrongRelationLocks->count[fasthashcode]` under the spinlock, sets `locallock->holdsStrongLockCount = true`, and remembers `StrongLockInProgress = locallock`.
- `FinishStrongLockAcquire` at `lock.c:1858`: clears `StrongLockInProgress` (does *not* decrement the counter).
- `AbortStrongLockAcquire` at `lock.c:1868`: decrements the counter under the spinlock, if `holdsStrongLockCount`.
- The counter is only decremented at full lock release (`UnGrantLock` path via `LockRelease` / `LockReleaseAll`); never during the acquire flow once `FinishStrongLockAcquire` ran. `[verified-by-code]`.

### LOCK / PROCLOCK lifetime

- LOCK is garbage-collected (hash entry removed) only when `nRequested` drops to zero — see `CleanUpLock` at `lock.c:1746`. `[verified-by-code]`.
- A PROCLOCK with `holdMask == 0` is also removed *unless* the backend is currently waiting on it (in which case its presence in the wait queue is required).

## 5. Functions of note (control flow)

### 5.1 `LockAcquireExtended` (`lock.c:833-1290`) — the central entry point

End-to-end sketch with line cites:

1. **Validate** `lockmethodid` and `lockmode`. Reject `lockmode > RowExclusiveLock` on `LOCKTAG_OBJECT`/`LOCKTAG_RELATION` during recovery (`lock.c:861-869`). `[verified-by-code]`.
2. **LOCALLOCK lookup or create** (`lock.c:887-925`). If already held (`nLocks > 0`), bump `locallock->nLocks` and return `ALREADY_HELD` or `ALREADY_CLEAR`.
3. **Assert no relation-extension lock held** (`lock.c:951`).
4. **Prepare standby WAL** for AccessExclusiveLock on a RELATION outside recovery (`lock.c:965-972`).
5. **Try fast path** if `EligibleForRelationFastPath` (`lock.c:984-1026`). Takes `fpInfoLock` EXCLUSIVE, checks strong-locker counter, grants if 0.
6. **If our lock is "strong"**: `BeginStrongLockAcquire` and `FastPathTransferRelationLocks` (`lock.c:1034-1055`). This is where the strong-locker iterates *every* backend's fpInfoLock — see §4.
7. **Take partition LWLock** (`lock.c:1062-1064`).
8. `SetupLockInTable` inserts the shared LOCK + PROCLOCK entries (`lock.c:1075`, definition at `lock.c:1291-1471`).
9. **Conflict check**: first against `lock->waitMask` (someone else is queued), then `LockCheckConflicts` against `grantMask` (`lock.c:1102-1106`).
10. **Either grant + release partition lock, or join the wait queue.** Joining calls `JoinWaitQueue` in `proc.c:1179` (under partition LWLock still held), then releases partition lock and calls `WaitOnLock` → `ProcSleep`.
11. **On wake**: lock is either granted (state set by the releaser before signalling — see `WaitOnLock` comment at `lock.c:1968-1984`) or `PROC_WAIT_STATUS_ERROR` (deadlock / timeout). On error, cleanup the locallock and ereport.

### 5.2 `LockCheckConflicts` (`lock.c:1537-1652`)

Two-stage check: bitmask compare against `grantMask`, then subtract own locks and group-member locks if any conflicts remain.

- The `proclock->groupLeader == MyProc && MyProc->lockGroupLeader == NULL` short-circuit at line 1592 is the "not in a parallel group" fast exit.
- **Relation-extension lock is excluded from group-member subtraction** (`lock.c:1603-1608`): "The relation extension lock conflict even between the group members." `[from-comment]`.
- O(N) walk of the lock's procLocks dlist with `myProcHeldLocks` adjustment.

### 5.3 `FastPathTransferRelationLocks` (`lock.c:2868-2956`)

The strong-locker's "move all weak locks into the shared table" routine. Iterates `ProcGlobal->allProcs`; for each PGPROC, acquires `fpInfoLock`, scans the fast-path slots for matches by group, acquires the partition lock, calls `SetupLockInTable` + `GrantLock`, releases the partition lock, releases `fpInfoLock`. This is the canonical lock-ordering moment: **`fpInfoLock` (foreign-backend) → partition LWLock**. `[verified-by-code]`.

### 5.4 `LockRelease` (`lock.c:2110-2314`) and `LockReleaseAll` (`lock.c:2315-2588`)

Decrement the LOCALLOCK first; only when `locallock->nLocks` reaches zero do we touch shared state. Strong-lock releases also decrement `FastPathStrongRelationLocks->count[…]` under its spinlock (`UnGrantLock` path). `LockReleaseAll` takes care of fast-path VXID cleanup (`VirtualXactLockTableCleanup` at `lock.c:2341-2342`), then walks each backend partition's `myProcLocks[i]` list under the partition LWLock to free PROCLOCKs.

### 5.5 `VirtualXactLock` (`lock.c:4725-4835`)

Wait-for-vxid primitive used by CIC and recovery. If the target vxid still has the owner's fast-path VXID lock set, takes the partition lock and transfers it to the shared table (so the waiter can sleep on a real PROCLOCK).

### 5.6 `GetLockConflicts` (`lock.c:3077-3291`)

Used by CREATE INDEX CONCURRENTLY and similar to enumerate `VirtualTransactionId`s of all conflicting holders. Holds the partition LWLock SHARED during the scan; if a holder is fast-path, takes the holder's `fpInfoLock` SHARED to inspect their bits.

### 5.7 `lock_twophase_recover` and `PostPrepare_Locks` (`lock.c:4339, 3580`)

2PC support: a prepared xact reassigns its session-level locks to a dummy PGPROC (`PreparedXactProcs[i]`) so they survive the original backend's exit. Reads `TwoPhaseLockRecord` from the 2PC state file.

## 6. Cross-references

- `proc.c` — `JoinWaitQueue`, `ProcSleep`, `ProcLockWakeup` (called from inside the partition LWLock).
- `deadlock.c` — `DeadLockCheck`, `RememberSimpleDeadLock` (called with all 16 partition LWLocks held).
- `lmgr.c` — user-facing façade (`LockRelation`, `LockTuple`, etc.) that builds the `LOCKTAG` and calls `LockAcquire`.
- `predicate.c` — independent of this file; `LOCKTAG_TUPLE` is the only point where row locks borrow heavyweight semantics (via `lmgr.c`).
- `lwlock.c` — implementation of partition LWLocks.
- `lock.h` (`source/src/include/storage/lock.h`) — all structs and the `LockHashPartition*` macros.

## 7. Open questions

1. **Total ordering between `fpInfoLock` of different backends.** The strong-locker walks them in `pgprocno` order via the `for (i = 0; i < ProcGlobal->allProcCount; i++)` loop at `lock.c:2885`, but this order is not stated as a *rule* anywhere — only as the implementation. If two strong-lockers run concurrently, they both follow this order, so they cannot deadlock against each other; this is implicit. `[unverified-as-rule]`.
2. **Whether `LockAcquireExtended`'s weak path holds any other LWLock while taking the partition lock.** Reading `lock.c:1062-1064`, the partition lock is taken after `fpInfoLock` has been released; the partition lock is the *only* LWLock the slow path holds. But there's no comment saying so. `[from-comment]` would require an `Assert` that doesn't exist.
3. **Ordering between heavyweight partition LWLocks and buffer-mapping partition LWLocks.** Not addressed in this file. Cross-referenced from `knowledge/subsystems/storage-buffer.md` §6 (also flagged unverified there).
4. **`releaseMask` lifecycle in `LockReleaseAll`.** The README at lines 185-189 says only the owning backend may modify it. A reader has to trust that no other path writes `releaseMask` — I did not exhaustively grep this.

## 8. Tag tally

- `[verified-by-code]`: 17
- `[from-comment]`: 6
- `[from-README]`: 5
- `[unverified]` / `[unverified-as-rule]`: 4

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/lock.c | deep (selected functions + structures) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/lock.c.md |
| source/src/include/storage/lock.h | full-read | 2026-06-01 | ef6a95c | (this doc + lock.h.md) |

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/pgproc-fields.md](../../../../../data-structures/pgproc-fields.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
- [data-structures/locallock.md](../../../../../data-structures/locallock.md)
- [data-structures/lock-struct.md](../../../../../data-structures/lock-struct.md)
- [data-structures/locktag.md](../../../../../data-structures/locktag.md)
- [data-structures/proclock.md](../../../../../data-structures/proclock.md)
- [idioms/fastpath-locks.md](../../../../../idioms/fastpath-locks.md)


- [idioms/parser-pipeline.md](../../../../../idioms/parser-pipeline.md)