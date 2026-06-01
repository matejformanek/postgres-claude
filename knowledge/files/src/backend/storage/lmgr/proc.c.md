# `storage/lmgr/proc.c`

- **Source:** `source/src/backend/storage/lmgr/proc.c` (2 139 lines)
- **Header:** `source/src/include/storage/proc.h`
- **Last verified commit:** `ef6a95c` (2026-06-01)

## 1. Purpose

Routines to manage the per-process `PGPROC` shared-memory structure and the entry-points the heavyweight lock manager uses to put a backend to sleep. Top-of-file comment groups the file into two interfaces `[from-comment]` (`proc.c:14-29`):

- **(a)** `JoinWaitQueue()`, `ProcSleep()`, `ProcWakeup()` — wait-on-lock primitives invoked from `lock.c`.
- **(b)** `ProcReleaseLocks` (at xact end), `ProcKill` (at backend exit).

Also owns the deadlock-timeout SIGALRM handler (`CheckDeadLockAlert`) and the deadlock-detector entry point `CheckDeadLock`.

## 2. Public surface

Per-process init/exit: `InitProcess`, `InitProcessPhase2`, `InitAuxiliaryProcess`, `ProcReleaseLocks` (`proc.c:392, 583, 618, 896`). `ProcKill` / `AuxiliaryProcKill` are registered as `on_shmem_exit` callbacks (`proc.c:924, 1079`).

Lock-wait protocol: `JoinWaitQueue(locallock, lockMethodTable, dontWait)`, `ProcSleep(locallock)`, `ProcWakeup(proc, waitStatus)`, `ProcLockWakeup(lockMethodTable, lock)` (`proc.c:1179, 1348, 1781, 1809`). `LockErrorCleanup` at `proc.c:818` is invoked from `AbortTransaction` to dequeue a still-waiting backend.

Deadlock: `CheckDeadLock` (static, `proc.c:1856`), `CheckDeadLockAlert` (signal handler, `proc.c:1947`).

Group locking: `BecomeLockGroupLeader`, `BecomeLockGroupMember(leader, pid)` (`proc.c:2075, 2105`). The PID check at member-join time defends against PGPROC recycling, per `README:669-678`.

Misc: `ProcWaitForSignal`, `ProcSendSignal`, `HaveNFreeProcs`, `AuxiliaryPidGetProc`, `GetStartupBufferPinWaitBufId`, `GetLockHoldersAndWaiters` (`proc.c:2048, 2060, 787, 1130, 771, 1974`).

Shmem callbacks: `ProcGlobalShmemRequest`, `ProcGlobalShmemInit` (`proc.c:147, 221`).

## 3. Key types

- `PGPROC` (defined in `proc.h:184-388`) — see `proc.h.md` for field-by-field. Critical fields for this file:
  - `waitLock`, `waitProcLock`, `waitLockMode`, `waitLink`, `waitStatus`, `heldLocks` — wait state.
  - `lockGroupLeader`, `lockGroupMembers`, `lockGroupLink` — group locking; protected by the partition LWLock chosen by `LockHashPartitionLockByProc(leader)` `[from-README]` (`README:660-667`).
  - `fpInfoLock`, `fpLockBits`, `fpRelId`, `fpVXIDLock`, `fpLocalTransactionId` — fast-path lock storage.
  - `myProcLocks[NUM_LOCK_PARTITIONS]` — per-partition dlist heads of this backend's PROCLOCKs `[from-README]` (`README:228-234`).
  - `lwWaiting`, `lwWaitMode`, `lwWaitLink` — LWLock wait state.
- `PROC_HDR` (`proc.h:444+`) — the global structure: `allProcs`, `freeProcs`, `autovacFreeProcs`, `bgworkerFreeProcs`, `walsenderFreeProcs`, `statusFlags[]`, `xids[]`, … Some of these arrays mirror PGPROC fields for cache-friendly scans by ProcArray. Pointer `ProcGlobal` is set in `ProcGlobalShmemInit`.
- `DeadLockState` enum (in `lock.h:339-347`) — `DS_NO_DEADLOCK`, `DS_SOFT_DEADLOCK`, `DS_HARD_DEADLOCK`, `DS_BLOCKED_BY_AUTOVACUUM`, `DS_NOT_YET_CHECKED`.
- `got_deadlock_timeout` — `volatile sig_atomic_t` set by `CheckDeadLockAlert` from the timer signal handler. Inspected by `ProcSleep` after each semaphore wake. `[verified-by-code]` (`proc.c:93`).

## 4. Key invariants and locking

### Deadlock-detector partition-lock order — **canonical statement**

`CheckDeadLock` (`proc.c:1856-1939`) acquires *all 16* lock-partition LWLocks in partition-number order and releases in reverse:

```c
for (i = 0; i < NUM_LOCK_PARTITIONS; i++)
    LWLockAcquire(LockHashPartitionLockByIndex(i), LW_EXCLUSIVE);   // 1871-1872
...
for (i = NUM_LOCK_PARTITIONS; --i >= 0;)
    LWLockRelease(LockHashPartitionLockByIndex(i));                 // 1935-1936
```

The comment at `proc.c:1862-1869` is the **authoritative statement** of the partition-number-order rule (also stated less formally in `README:239-244`):

> "Acquire exclusive lock on the entire shared lock data structures. Must grab LWLocks in partition-number order to avoid LWLock deadlock. Note that the deadlock check interrupt had better not be enabled anywhere that this process itself holds lock partition locks, else this will wait forever."

`[from-comment]` `[verified-by-code]`. This is rule #1 in the §2 of `knowledge/idioms/locking-overview.md`.

The reverse-order release at `proc.c:1928-1933` has two stated reasons `[from-comment]`: (1) keeps another waiter that needs >1 lock unblocked atomically; (2) avoids O(N²) behavior inside `LWLockRelease`'s wakeup scan.

### Wait-queue mutation requires partition LWLock

- `JoinWaitQueue` is called from `LockAcquireExtended` with the partition LWLock held EXCLUSIVE; asserted at `proc.c:1193`. `[verified-by-code]`.
- `ProcLockWakeup` (`proc.c:1809-1855`) and `RemoveFromWaitQueue` (`lock.c:2054`) both require the partition LWLock EXCLUSIVE.

### Wait/signal protocol (`ProcSleep`)

- `ProcSleep` releases the partition LWLock (`Assert(!LWLockHeldByMe(partitionLock))` at `proc.c:1363` — the caller has already released).
- Sleeps on `PGSemaphoreLock(MyProc->sem)` inside a loop, checking `MyProc->waitStatus` after each wake. The lock grantor (or `CheckDeadLock`) must set `MyProc->waitStatus = PROC_WAIT_STATUS_OK` (or `_ERROR`) **before** signalling the semaphore.
- `WaitOnLock` (`lock.c:1940`) wraps `ProcSleep` and **cannot** put cleanup logic after the call — comment at `lock.c:1968-1984` warns that a cancel/die interrupt could fire between grant and return, so the locktable state must be fully consistent before the grantor signals.

### `LockErrorCleanup` (`proc.c:818-895`)

Called from `AbortTransaction` if we error out while waiting. Must:
1. Disable the deadlock timeout.
2. Take the partition LWLock for the awaited lock.
3. If still in the wait queue, call `RemoveFromWaitQueue` (which sets `waitStatus = ERROR`).
4. If lock was granted to us between the error and now, run `GrantAwaitedLock` so the locallock reflects reality (the grantor already updated the shared state).
5. Release the partition LWLock; `ProcLockWakeup` if needed.

### Two-PGPROC freelist scheme

`ProcGlobal` has multiple freelist heads (`freeProcs`, `autovacFreeProcs`, `bgworkerFreeProcs`, `walsenderFreeProcs`) so an autovacuum slot exhaustion can't lock out a regular client `[verified-by-code]` (`proc.c:147-220`).

### Group-locking PID interlock

`BecomeLockGroupMember` (`proc.c:2105`) takes the partition LWLock for the leader, then verifies the leader still has the expected PID and is still a leader before linking the member in. This is the precaution against PID-reuse described in `README:669-678` `[from-README]`.

## 5. Functions of note

### 5.1 `InitProcess` (`proc.c:392-582`)

Allocates a PGPROC from the appropriate freelist, sets up `MyProc`, initialises `MyProc->sem`, registers `ProcKill` for shmem exit, and (eventually) `InitProcessPhase2` attaches us to `ProcArray`. `MyProc->fpInfoLock` is initialised in this function (since it's a per-PGPROC LWLock, it lives in shmem but in the backend's slot).

### 5.2 `JoinWaitQueue` (`proc.c:1179-1332`)

Called with the partition LWLock EXCLUSIVE. Decides where the requester sits in the lock's `waitProcs` dlist:

1. If the requester already holds locks on this same object that conflict with the request of any earlier waiter, jump in *just before* that waiter — avoids forcing the deadlock detector to do queue rearrangement (`proc.c:1229-1244`, mirrors `README:370-381`).
2. If by inserting earlier we'd actually have no conflict (no held lock or earlier waiter blocks us), **grant ourselves the lock immediately** (`proc.c:1281-1288`).
3. Detect the "I conflict with him and he conflicts with me" trivial-deadlock case; set `early_deadlock = true`, record via `RememberSimpleDeadLock`, return `PROC_WAIT_STATUS_ERROR` after enqueueing (`proc.c:1265-1278`).
4. Otherwise enqueue at the chosen position, set `MyProc->waitLock`, etc., return `PROC_WAIT_STATUS_WAITING`.

Group-locking subtlety at lines 1214-1227: other group members' `holdMask`s are unioned into `myHeldLocks` so the "I already hold conflicting locks" check covers the group.

### 5.3 `ProcSleep` (`proc.c:1348-1780`)

Main sleep loop. Arms `STATEMENT_TIMEOUT`, `LOCK_TIMEOUT`, `DEADLOCK_TIMEOUT`. On each wake: check `MyProc->waitStatus`, on `WAITING` re-loop; on `OK` return success; on `ERROR` return error. Runs `CheckRecoveryConflictDeadlock` before the loop if in Hot Standby. Inside, when `got_deadlock_timeout` is set, the timer handler has signaled — `ProcSleep` clears the flag and calls `CheckDeadLock` (which takes all 16 partition LWLocks). If `CheckDeadLock` returns `DS_BLOCKED_BY_AUTOVACUUM`, sends a cancel signal to the autovacuum worker (the README:581-588 "abuse the deadlock detector" hook). On hard deadlock, `CheckDeadLock` already called `RemoveFromWaitQueue(MyProc, …)`, so we just return ERROR.

### 5.4 `CheckDeadLock` (`proc.c:1856-1939`)

Documented above. Calls `DeadLockCheck(MyProc)` from `deadlock.c`; on hard deadlock removes us from the wait queue; in all cases releases all 16 partition LWLocks in reverse order.

### 5.5 `ProcLockWakeup` (`proc.c:1809-1855`)

Walks the lock's `waitProcs` dlist. For each waiter: if their request conflicts with neither `grantMask` nor the requests of un-wakable predecessors, grant + dequeue + `ProcWakeup`. Maintains the per-mode "blocked waiters" mask so a sequence of compatible requests can be granted in arrival order without re-checking from scratch.

### 5.6 `ProcReleaseLocks` (`proc.c:896-912`)

`AtCommit_Locks` / `AtEOXact_Locks` hook. Just `LockReleaseAll(DEFAULT_LOCKMETHOD, allLocks=true)` plus the `LockReleaseAll(USER_LOCKMETHOD, allLocks)` for transaction-scoped advisory locks.

### 5.7 `ProcKill` (`proc.c:924-1078`)

Backend exit handler. Releases all LWLocks (`LWLockReleaseAll`), then all heavyweight locks, then group-locking links (under the leader's partition LWLock), then puts PGPROC back on the appropriate freelist. **Must run with no other backend able to see this PGPROC as still-living** — the ProcArray detach in `InitProcessPhase2`'s symmetric exit step happens earlier.

### 5.8 `BecomeLockGroupMember` (`proc.c:2105-2138`)

PID-revalidation interlock for parallel-worker group join: take leader's partition LWLock, check `leader->pid == expected_pid && leader->lockGroupLeader == leader`, link us in, release.

## 6. Cross-references

- `lock.c` — calls `JoinWaitQueue` and `ProcSleep` from `LockAcquireExtended`; `ProcLockWakeup` from `LockRelease`/`UnGrantLock` callers.
- `deadlock.c` — `DeadLockCheck`, `RememberSimpleDeadLock`, `DeadLockReport` are called from inside `CheckDeadLock`/`JoinWaitQueue`/`ProcSleep`'s error report.
- `procarray.c` — `InitProcessPhase2` calls `ProcArrayAdd`, ProcKill calls `ProcArrayRemove`; they share the `ProcGlobal->statusFlags`/`xids[]` mirror arrays.
- `utils/timeout.c` — schedules `DEADLOCK_TIMEOUT`, `STATEMENT_TIMEOUT`, `LOCK_TIMEOUT`, `IDLE_IN_TRANSACTION_SESSION_TIMEOUT`, etc.
- `replication/syncrep.c` — uses `MyProc->syncRepLinks`; not lock-related but lives in PGPROC.

## 7. Open questions

1. **Exactly which PGPROC fields the deadlock detector reads.** It walks `lockGroupMembers`, `waitLink`, `waitLock`, `waitLockMode`, `heldLocks` — all protected by some partition LWLock. But it also reads `lockGroupLeader` for *every* visited proc; this works because all partition LWLocks are held. There may be other fields it touches that aren't obvious from a quick read of `deadlock.c`. `[unverified]` — would need a thorough audit of `FindLockCycleRecurse*`.
2. **Whether `ProcSleep`'s timeout-handling can race with `LockErrorCleanup`.** Both manipulate `awaitedLock`/`awaitedOwner` (file-static in `lock.c`); guarded by interrupt holdoff but I didn't trace the full path. `[unverified]`.
3. **Memory-ordering on `MyProc->waitStatus`.** The grantor writes it before `PGSemaphoreUnlock`; the waiter reads it after `PGSemaphoreLock`. `PGSemaphoreLock/Unlock` are documented as full barriers, but the chain of cite-able guarantees isn't all in one place. `[unverified]`.
4. **`got_deadlock_timeout` reset semantics.** `ProcSleep` reads and clears the flag; if a second timeout fires during `CheckDeadLock`, the flag is re-set and another check happens on the next loop iteration. This is fine but not commented anywhere. `[from-comment, indirect]`.

## 8. Tag tally

- `[verified-by-code]`: 11
- `[from-comment]`: 6
- `[from-README]`: 3
- `[unverified]`: 4

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/proc.c | deep (selected functions) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/proc.c.md |
| source/src/include/storage/proc.h | partial (PGPROC struct + extern protos) | 2026-06-01 | ef6a95c | (this doc) |

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/pgproc-fields.md](../../../../../data-structures/pgproc-fields.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
