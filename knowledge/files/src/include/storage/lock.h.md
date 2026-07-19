# `include/storage/lock.h`

- **Source:** `source/src/include/storage/lock.h` (~570 lines)
- **Last verified commit:** `ef6a95c` (2026-06-01)

## Purpose

Public types for the heavyweight lock manager. Defines `LOCKTAG`, `LOCKMODE`, `LOCK`, `PROCLOCK`, `LOCALLOCK`, `LockAcquireResult`, `DeadLockState`, and the partition-LWLock-selection macros. Companion to `lockdefs.h` (lock mode enum) and `locktag.h` (LOCKTAG type + LockTagType enum).

## Key declarations

- `MAX_LOCKMODES = 10` (`lock.h:85`) — bitmask width budget for `LOCKMASK` (`uint16`). Actual `MaxLockMode = AccessExclusiveLock = 8`.
- `LockMethodData` / `LockMethod` (`lock.h:111-119`) — `{numLockModes, conflictTab, lockModeNames, trace_flag}`. Two instances in `lock.c`: `default_lockmethod` (id=1) and `user_lockmethod` (id=2).
- `LOCK` struct (`lock.h:139-153`). Field-by-field documented in `README:89-156`.
- `PROCLOCKTAG` (`lock.h:193-198`): `{LOCK *myLock; PGPROC *myProc}` — NB **no padding** assumed (the comment at line 195 is critical: padding would randomise the hash).
- `PROCLOCK` (`lock.h:200-211`): `groupLeader`, `holdMask`, `releaseMask`, `lockLink`, `procLink`. **`releaseMask` is owning-backend-only without partition LWLock** `[from-README]` (`README:185-189`).
- `LOCALLOCKTAG` / `LOCALLOCKOWNER` / `LOCALLOCK` (`lock.h:239-272`). LOCALLOCK is the backend-private hash entry recording per-(tag, mode) state — `nLocks` (total holds), `lockOwners[]` (per-ResourceOwner counts), `holdsStrongLockCount` (whether we bumped FastPathStrongRelationLocks), `lockCleared` (whether all sinval msgs were absorbed).
- `LockAcquireResult` enum (`lock.h:330-336`): `LOCKACQUIRE_NOT_AVAIL`, `_OK`, `_ALREADY_HELD`, `_ALREADY_CLEAR`.
- `DeadLockState` enum (`lock.h:339-347`).
- Partition macros (`lock.h:355-373`):
  - `LockHashPartition(hashcode) = hashcode % NUM_LOCK_PARTITIONS`
  - `LockHashPartitionLock(hashcode) = &MainLWLockArray[LOCK_MANAGER_LWLOCK_OFFSET + (hashcode % 16)].lock`
  - `LockHashPartitionLockByIndex(i)`
  - `LockHashPartitionLockByProc(leader_pgproc) = LockHashPartitionLock(GetNumberFromPGProc(leader_pgproc))` — used for the group-locking field protection.

## Cross-references

- `lock.c` — implementation of every function declared here.
- `lockdefs.h` — `LOCKMODE` enum (1=AccessShareLock … 8=AccessExclusiveLock, plus NoLock=0).
- `locktag.h` — `LOCKTAG` struct + `LockTagType` enum.
- `lwlock.h` — defines `LOCK_MANAGER_LWLOCK_OFFSET` and `NUM_LOCK_PARTITIONS`.

## Tag tally

- `[verified-by-code]`: 5
- `[from-README]`: 1
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/locallock.md](../../../../data-structures/locallock.md)
- [data-structures/lock-struct.md](../../../../data-structures/lock-struct.md)
- [data-structures/proclock.md](../../../../data-structures/proclock.md)

- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)