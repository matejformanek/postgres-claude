# `storage/lmgr/README` — summary

- **Source path:** `source/src/backend/storage/lmgr/README` (731 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **Companion idiom doc:** `knowledge/idioms/locking-overview.md` (already summarises §1 taxonomy and the conflict table)

This README is the authoritative narrative for the **regular (heavyweight) lock manager**. The taxonomy of all four primitives — spinlocks, LWLocks, regular locks, predicate locks (SIREAD) — lives in lines 1-46; the rest of the file is about the heavyweight manager only.

## Section map

| README lines | Topic |
|---|---|
| 6-46 | Four-primitive taxonomy + interrupt-handling rules `[from-README]` |
| 50-86 | LOCK / PROCLOCK / LOCALLOCK data structures `[from-README]` |
| 89-199 | Field-by-field walkthrough of LOCK and PROCLOCK `[from-README]` |
| 202-254 | Lock manager internal locking — **partition LWLocks, the canonical "partition-number order" rule** `[from-README]` |
| 257-336 | Fast-path locking (the FastPathStrongRelationLocks design) `[from-README]` |
| 338-536 | Deadlock detection algorithm (matches `deadlock.c`) `[from-README]` |
| 538-588 | Miscellaneous notes (autovacuum cancellation hack at lines 581-588) `[from-README]` |
| 589-678 | Group locking (parallel query) `[from-README]` |
| 681-702 | User/advisory locks `[from-README]` |
| 703-732 | Locking during Hot Standby `[from-README]` |

## Canonical statements that the rest of the codebase relies on

These are the lines other code points back to. Cite the README at these line numbers, not the C file, when stating these rules:

1. **Partition-number-order rule** (`README:239-244`): "any backend needing to lock more than one [lock manager] partition at once must lock them in partition-number order." `CheckDeadLock` at `proc.c:1871-1872` is the canonical enforcement (acquires all 16 in `i = 0..NUM_LOCK_PARTITIONS-1`).
2. **`PROCLOCK.releaseMask` rule** (`README:185-189`): "modified without taking the partition LWLock, and therefore it is unsafe for any backend except the one owning the PROCLOCK to examine/change it."
3. **Group-locking field protection** (`README:660-667`): the three lockGroupLeader/Members/Link fields are protected "by taking the leader's pgprocno modulo the number of lock manager partitions" — `LockHashPartitionLockByProc(leader)` in `lock.h:372-373`. This is what lets the deadlock detector inspect them safely because it already holds *all* partition locks.
4. **Fast-path / strong-locker memory-sync rule** (`README:306-321`): the explicit proof that `FastPathStrongRelationLocks` is consistent without atomics — relies on the fact that LWLock acquisition is a memory sequence point, and the strong-locker acquires *every* backend's `fpInfoLock`.
5. **HS lock-level invariant** (`README:711-718`): regular backends in recovery may take at most `RowExclusiveLock`; Startup process only acquires `AccessExclusiveLock`. Therefore deadlock involving recovery is impossible by construction.

## Things the README does NOT promise

- It says nothing about ordering between heavyweight-partition LWLocks and any other LWLock family (buffer-mapping, predicate-lock partition, …). See Open Questions in `locking-overview.md` §6.
- It says nothing about the relative ordering of `fpInfoLock` and the heavyweight partition LWLock; one has to read `lock.c:2885-2954` (`FastPathTransferRelationLocks`) to learn that the strong-locker holds `fpInfoLock` and then takes the partition lock inside that section. See `lock.c.md` §5 for the trace.

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/README | full-read | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/README.md |

## Synthesized by
<!-- backlinks:auto -->
- [idioms/locking-overview.md](../../../../../idioms/locking-overview.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
