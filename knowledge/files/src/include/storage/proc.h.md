# `include/storage/proc.h`

- **Source:** `source/src/include/storage/proc.h` (~580 lines)
- **Last verified commit:** `ef6a95c` (2026-06-01)

## Purpose

Defines `PGPROC` (the per-process shared-memory state) and `PROC_HDR` (the global pointer-to-arrays anchor). Every backend has exactly one PGPROC slot allocated from `ProcGlobal->allProcs` at startup; cleared and returned to a freelist at exit.

## Key declarations

- `PGPROC` (`proc.h:184-388`). Cache-line-aligned. Logical sections marked by comment banners:
  - **Backend identity** (`proc.h:195-218`): `pid`, `backendType`, `databaseId`, `roleId`, `tempNamespaceId`, `pgxactoff`, `statusFlags`.
  - **Transactions and snapshots** (`proc.h:220-256`): `vxid {procNumber, lxid}`, `xid`, `xmin`, `subxidStatus`, `subxids`.
  - **Inter-process signalling** (`proc.h:258-276`): `procLatch`, `sem`, `delayChkptFlags`, `pendingRecoveryConflicts`.
  - **LWLock waiting** (`proc.h:278-294`): `lwWaiting`, `lwWaitMode`, `lwWaitLink`, `cvWaitLink`.
  - **Lock manager data** (`proc.h:296-335`):
    - `lockGroupLeader`, `lockGroupMembers`, `lockGroupLink` — group locking, protected by `LockHashPartitionLockByProc(leader)` `[from-README]` (`README:660-667`).
    - `waitLock`, `waitLink`, `waitProcLock`, `waitLockMode`, `heldLocks`, `waitStart`, `waitStatus` — wait state, protected by the awaited lock's partition LWLock.
    - `myProcLocks[NUM_LOCK_PARTITIONS]` — per-partition dlist heads of *all* PROCLOCKs this backend owns.
    - `fpInfoLock` (LWLock), `fpLockBits`, `fpRelId`, `fpVXIDLock`, `fpLocalTransactionId` — fast-path lock storage.
  - **Synchronous replication** (`proc.h:337-388`): `waitLSN`, `syncRepLinks`, `syncRepState`.

- `PROC_HDR` (`proc.h:444+`): the global; pointed to by `ProcGlobal`. Contains:
  - `allProcs[TotalProcs]` — pointer to PGPROC array.
  - `xids[]`, `subxidStates[]`, `statusFlags[]` — flat mirrors of PGPROC fields for cache-friendly ProcArray scans.
  - Freelist heads: `freeProcs`, `autovacFreeProcs`, `bgworkerFreeProcs`, `walsenderFreeProcs`.
  - `procArrayGroupFirst` (atomic), `clogGroupFirst` (atomic) — group-clear lists for batched ProcArray and CLOG updates.
  - `spins_per_delay` (shared).

- `MyProc` global (`proc.h:388`): `extern PGPROC *MyProc`. Set in `InitProcess`; valid for the lifetime of the backend.

- GUCs `DeadlockTimeout`, `StatementTimeout`, `LockTimeout`, `IdleInTransactionSessionTimeout`, `TransactionTimeout`, `IdleSessionTimeout`, `log_lock_waits` (`proc.h:538-544`). All in milliseconds.

- `ProcWaitStatus` enum (`proc.h:149-156`): `PROC_WAIT_STATUS_OK`, `_WAITING`, `_ERROR`. Set by lock grantor and read by waiter after `PGSemaphoreLock`.

## Key invariants

- **PGPROC pointer stability**: a PGPROC slot is never moved during the lifetime of the postmaster cluster. PROCLOCK keys (`{LOCK*, PGPROC*}`) are safe because the PGPROC outlives any PROCLOCK referencing it `[from-README]` (`README:174-177`).
- **`pgxactoff` mirroring**: fields tagged "mirrored in ProcGlobal->…[pgxactoff]" must be written *both* places by the owning backend. Other backends scan the flat arrays for cache reasons.
- **`fpInfoLock` is initialised inside the PGPROC** — it's a per-backend LWLock with its own tranche (`LWTRANCHE_LOCK_FASTPATH` per `lwlocklist.h`).
- **`waitStart`** is atomic so a monitoring backend can sample wait durations from `pg_locks` without a lock.

## Cross-references

- `proc.c` — initialises, owns lifecycle.
- `procarray.h` / `procarray.c` — uses the `pgxactoff` mirror arrays.
- `lock.h` — declares `NUM_LOCK_PARTITIONS` used for `myProcLocks` array sizing.
- `lwlock.h` — `LWLock` type definition for `fpInfoLock`.

## Tag tally

- `[verified-by-code]`: 6
- `[from-README]`: 2
- `[from-comment]`: 2
