# Lock manager (heavyweight + lightweight + spinlock + predicate)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Heikki Linnakangas (49), Peter Eisentraut (16), Michael Paquier (15), Nathan Bossart (14)
- **Top reviewers (last 24mo):** Andres Freund (20), Matthias van de Meent (11), Ashutosh Bapat (11), Michael Paquier (10)
- **Recent landmark commits (12mo):**
  - `3fd05777282 (Heikki Linnakangas, 2026-03-27): Refactor PredicateLockShmemInit to not reuse var for different things`
  - `fd6ecbfa75f (Fujii Masao, 2026-03-16): Ensure "still waiting on lock" message is logged only once per wait.`
  - `ec317440716 (Álvaro Herrera, 2026-01-29): Replace literal 0 with InvalidXLogRecPtr for XLogRecPtr assignments`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/storage/lmgr/`
- **Header path:** `source/src/include/storage/{lock,lwlock,proc,predicate,predicate_internals,s_lock,spin,lmgr,lockdefs,locktag,condition_variable,proclist,proclist_types}.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **README anchors:** `source/src/backend/storage/lmgr/README` (heavyweight + taxonomy), `source/src/backend/storage/lmgr/README-SSI` (predicate locks / SSI), `source/src/backend/storage/lmgr/README.barrier` (memory ordering)
- **Companion overview:** `knowledge/idioms/locking-overview.md` (six-layer taxonomy, conflict matrix; this doc is the subsystem-level synthesis grounded in file:line citations from the file-level docs under `knowledge/files/src/backend/storage/lmgr/`).

## 1. Purpose

`storage/lmgr` is PostgreSQL's concurrency engine. It owns four distinct primitives stacked in one directory: hardware spinlocks (`s_lock.c`), lightweight reader/writer locks (`lwlock.c`), the heavyweight per-object lock manager with deadlock detection (`lock.c` + `proc.c` + `deadlock.c` + `lmgr.c`), and the non-blocking predicate-lock / SSI machinery (`predicate.c`). It also contains `condition_variable.c`, the interruptible CV primitive used by parallel query and DSM. The heavyweight manager is the user-visible lock layer (`LOCK TABLE`, automatic relation locks, advisory, tuple-wait, vxid-wait, 2PC); the README opens with the four-primitive taxonomy at `README:6-46` and devotes the rest to the heavyweight manager. `[from-README]` (`README:6-46`, summarised in `knowledge/files/src/backend/storage/lmgr/README.md`).

## 2. Mental model

To navigate this subsystem hold these eight concepts in your head:

- **Heavyweight LOCK / PROCLOCK / LOCALLOCK triple.** `LOCK` is one shared-memory entry per lockable object (keyed by `LOCKTAG`); `PROCLOCK` is one entry per `(LOCK, PGPROC)`; `LOCALLOCK` is a per-backend re-entry counter so that double-locking the same relation only allocates one PROCLOCK. `[from-README]` (`README:50-86`, `lock.h:139-272`, via `knowledge/files/src/backend/storage/lmgr/README.md` and `lock.c.md`).
- **16 partitioned LWLocks gate the shared hash.** `NUM_LOCK_PARTITIONS = 1 << 4 = 16`; partition = `LockTagHashCode(tag) mod 16`; the LWLock for a given partition lives in `MainLWLockArray` at `LOCK_MANAGER_LWLOCK_OFFSET + n`. `[verified-by-code]` (`lwlock.h:86-87`, `lock.h:355-361`, via `lock.c.md` §4).
- **Fast-path bypass.** Weak relation locks (AccessShare/RowShare/RowExclusive on non-shared rels) and self-VXID locks are recorded in `PGPROC.fpLockBits/fpRelId/fpVXIDLock` under that backend's own `fpInfoLock` LWLock, bypassing the shared hash entirely. A 1024-entry `FastPathStrongRelationLocks` counter array lets fast-path acquirers cheaply check "is anybody about to take a strong lock?" `[from-README]` (`README:257-336`, via `lock.c.md` §4).
- **8 lock modes + conflict matrix.** `AccessShareLock` (1) … `AccessExclusiveLock` (8); `LockConflicts[]` at `lock.c:68-108` is the canonical 8×8 bitmask table — the SQL docs page is generated from it. `[verified-by-code]` (`lock.c:68-108`, `lockdefs.h:33-48`, via `lock.c.md` §3).
- **LWLocks = wait-free CAS + sleep-on-contention.** Single packed `pg_atomic_uint32` state word; shared count + exclusive sentinel + 3 flag bits (`LW_FLAG_HAS_WAITERS`, `WAKE_IN_PROGRESS`, `LOCKED`). Four-phase race protocol: try CAS, queue, retry CAS, sleep. Auto-released on `elog(ERROR)`. At most `MAX_SIMUL_LWLOCKS = 200` per backend. `[from-comment]` (`lwlock.c:6-12, 60-75, 96-108, 157-167`, via `lwlock.c.md` §1, §4).
- **Spinlocks are hardware TAS.** `slock_t`, `SpinLockAcquire/Release` macros, contended-wait loop in `s_lock.c` with exponential 1ms→1s backoff and `NUM_DELAYS = 1000` cap (~2 minute timeout → PANIC). Spinlocks are *not* deadlock-detected, *not* auto-released on error, *not* allowed to span kernel/subroutine calls or `CHECK_FOR_INTERRUPTS`. `[from-comment]` (`s_lock.c:5-37, 57-61`, `spin.h:21-29`, via `s_lock.c.md` §4).
- **Predicate locks = SIREAD.** Non-blocking "flags" tracked per serializable transaction (`SERIALIZABLEXACT`) on `PREDICATELOCKTARGET`s of three granularities (tuple, page, relation). Coarser covers finer; conflicts contribute to the `RWConflictData` graph; commit-time check aborts one transaction in a *dangerous structure* (`Tin → Tpivot → Tout`). Partitioned 16 ways (`NUM_PREDICATELOCK_PARTITIONS`). `[from-README]` (`README-SSI:151-298`, `predicate.c:1-150`, via `README-SSI.md` and `predicate.c.md` §1, §3).
- **Group locking for parallel query.** Locks held by procs in the same parallel group don't conflict (except `LOCKTAG_RELATION_EXTEND`). Group leadership is stored in `PGPROC.lockGroupLeader/Members/Link`, protected by *one* partition LWLock chosen by `LockHashPartitionLockByProc(leader)`. `[from-README]` (`README:589-678, 660-667`, `lock.h:363-373`, via `lock.c.md` §4).

## 3. Key files

- `README` (731 lines) — heavyweight lock manager narrative + the four-primitive taxonomy in `README:6-46`. Section map in `knowledge/files/src/backend/storage/lmgr/README.md`.
- `README-SSI` (646 lines) — Serializable Snapshot Isolation algorithm narrative. Section map in `README-SSI.md`.
- `lock.c` (4 865 lines) — heavyweight lock primary. Top-of-file at `lock.c:13-26`. Hosts `LockAcquireExtended`, `LockRelease(All)`, `LockCheckConflicts`, `FastPathTransferRelationLocks`, `LockConflicts[]`, 2PC integration. See `lock.c.md`.
- `lwlock.c` (1 939 lines) — LWLock implementation. Top-of-file at `lwlock.c:6-75` (incl. 4-phase race protocol). See `lwlock.c.md`.
- `proc.c` (2 139 lines) — PGPROC management + the lock-wait wait/sleep/wake protocol (`JoinWaitQueue`, `ProcSleep`, `ProcLockWakeup`) + the deadlock-timeout SIGALRM entry `CheckDeadLock`. See `proc.c.md`.
- `deadlock.c` (1 162 lines) — WFG construction, hard/soft edge classification, soft-cycle rearrangement via topological sort. Top-of-file refers to `README:338-588`. See `deadlock.c.md`.
- `predicate.c` (4 993 lines) — predicate locks + SSI dangerous-structure detection. Top-of-file at `predicate.c:1-150` lists the seven SIREAD properties; lines `84-141` are the canonical LWLock acquisition order. See `predicate.c.md`.
- `lmgr.c` (1 351 lines) — `LOCKTAG`-building façade: `LockRelation*`, `LockTuple`, `XactLockTableWait`, `LockDatabaseObject`, `LockRelationForExtension`, `WaitForLockers`, speculative-insertion locks. See `lmgr.c.md`.
- `s_lock.c` (300 lines) — only the contended wait loop; `s_lock`, `perform_spin_delay`, `finish_spin_delay`, `update_spins_per_delay`. The TAS itself lives in `s_lock.h`. See `s_lock.c.md`. **There is no `spin.c`.**
- `condition_variable.c` (362 lines) — interruptible CV primitive built on `WaitLatch`; one prepared sleep per backend; safe to embed in DSM. See `condition_variable.c.md`.

## 4. Key data structures

- **`LOCK`** — shared hash entry keyed by `LOCKTAG`. Fields: `tag`, `grantMask`, `waitMask`, `procLocks` (dlist), `waitProcs` (PROC_QUEUE), `requested[MAX_LOCKMODES]`, `nRequested`, `granted[]`, `nGranted`. Garbage-collected by `CleanUpLock` (`lock.c:1746`) when `nRequested` hits zero. `[from-README]` (`README:50-199`, `lock.h:139-272`, via `lock.c.md` §3-§4).
- **`PROCLOCK`** — shared per-(LOCK, PGPROC) entry; lives on `LOCK.procLocks` and on `PGPROC.myProcLocks[NUM_LOCK_PARTITIONS]`. `holdMask` (bitmask of granted modes), `releaseMask` (intended releases at next opportunity), `groupLeader`, `myLock`, `tag`. **`releaseMask` is modified without holding the partition LWLock and is therefore only safe for the owning backend to examine.** `[from-README]` (`README:185-189`, via `README.md` and `lock.c.md` §4 / §7).
- **`LOCALLOCK`** — backend-private hash entry keyed by `(LOCKTAG, LOCKMODE)`. Tracks per-mode `nLocks` (re-entry count), pointer to shared LOCK + PROCLOCK, `holdsStrongLockCount`, and an `lockOwners[]` array for ResourceOwner tracking. `[from-README]` (`README:78-86`, `lock.h:257-272`, via `lock.c.md` §3).
- **`LWLock`** — `{tranche : uint16; state : pg_atomic_uint32; waiters : proclist_head}`. State packs share-count + exclusive sentinel + `LW_FLAG_LOCKED` (wait-list mutex) + `LW_FLAG_WAKE_IN_PROGRESS` + `LW_FLAG_HAS_WAITERS`. `[verified-by-code]` (`lwlock.c:96-108`, via `lwlock.c.md` §3).
- **`LWLockHandle`** — per-backend stack-entry: `{LWLock *lock; LWLockMode mode}`; held in `held_lwlocks[MAX_SIMUL_LWLOCKS=200]`. Overflow is `elog(ERROR, "too many LWLocks taken")` at `lwlock.c:1182`. `[verified-by-code]` (via `lwlock.c.md` §3).
- **`PGPROC`** — per-process shared-memory slot, defined at `proc.h:184-388`. Key fields:
  - Lock-wait state: `waitLock`, `waitProcLock`, `waitLockMode`, `waitLink`, `waitStatus`, `heldLocks`.
  - Group locking: `lockGroupLeader`, `lockGroupMembers`, `lockGroupLink` — **protected by `LockHashPartitionLockByProc(leader)`**, the partition LWLock chosen from leader's pgprocno. `[from-README]` (`README:660-667`, `lock.h:363-373`, via `proc.c.md` §3 + `lock.c.md` §4).
  - Fast-path: `fpInfoLock`, `fpLockBits`, `fpRelId`, `fpVXIDLock`, `fpLocalTransactionId`.
  - `myProcLocks[NUM_LOCK_PARTITIONS]` — per-partition dlist heads of this backend's PROCLOCKs.
  - LWLock-wait: `lwWaiting`, `lwWaitMode`, `lwWaitLink`.
- **`PROC_HDR` / `ProcGlobal`** — `allProcs`, `freeProcs`, `autovacFreeProcs`, `bgworkerFreeProcs`, `walsenderFreeProcs`, `statusFlags[]`, `xids[]`. Separate freelists keep autovac slot exhaustion from locking out regular clients. `[verified-by-code]` (`proc.h:444+`, `proc.c:147-220`, via `proc.c.md` §3).
- **`PredXact` / `SERIALIZABLEXACT`** — per-serializable-xact state: `vxid`, `topXid`, `commitSeqNo`, `predicateLocks`, `inConflicts`/`outConflicts` dlists of `RWConflictData`, `perXactPredicateListLock` (used only in parallel mode). `[verified-by-code]` (`predicate_internals.h`, via `predicate.c.md` §3).
- **`PredicateLockTargetData` / `PREDICATELOCK`** — `(db, rel, page, offset)` PREDICATELOCKTARGETTAG → PREDICATELOCKTARGET (head of dlist of locks); PREDICATELOCK is keyed by `(target, sxact)` and links into both `target->predicateLocks` and `sxact->predicateLocks`. `InvalidBlockNumber` = relation-granularity; `InvalidOffsetNumber` = page-granularity. `[verified-by-code]` (`predicate.c:232-246`, via `predicate.c.md` §3).
- **`FastPathStrongRelationLockData`** — `{slock_t mutex; uint32 count[1024]}` spinlock-protected counter array indexed by `fasthashcode`; incremented by `BeginStrongLockAcquire`, decremented at lock release. `[verified-by-code]` (`lock.c:309-315`, via `lock.c.md` §3).

## 5. Control flow — common paths

### 5.1 `LockAcquireExtended` (heavyweight acquisition, `lock.c:833-1290`)

End-to-end `[verified-by-code]` (via `lock.c.md` §5.1):

1. Validate `lockmethodid`, `lockmode`. Reject any mode > `RowExclusiveLock` on relation/object during recovery (`lock.c:861-869`).
2. LOCALLOCK lookup/create (`lock.c:887-925`); if `nLocks > 0`, bump and return `ALREADY_HELD`.
3. **Assert `!IsRelationExtensionLockHeld`** at `lock.c:951` — see §6 canonical citation #4.
4. Prepare standby WAL record for AccessExclusiveLock on relations (outside recovery) (`lock.c:965-972`).
5. **Fast-path attempt** (`lock.c:984-1026`): if `EligibleForRelationFastPath`, `LWLockAcquire(&MyProc->fpInfoLock, LW_EXCLUSIVE)` → check `FastPathStrongRelationLocks->count[fasthashcode] == 0` → `FastPathGrantRelationLock` → `LWLockRelease(fpInfoLock)`.
6. If our lock is *strong*: `BeginStrongLockAcquire` + `FastPathTransferRelationLocks` (the strong-locker walks all backends' `fpInfoLock`s to drain weak locks into the shared table — see §6 canonical #3 and §5.2 below).
7. **Take partition LWLock** at `lock.c:1062-1064` (after `fpInfoLock` is released — the weak path never holds both).
8. `SetupLockInTable` (`lock.c:1291-1471`) inserts/finds the shared LOCK + PROCLOCK.
9. Conflict check: first against `lock->waitMask` (someone's already queued), then `LockCheckConflicts` against `grantMask` (`lock.c:1102-1106`).
10. Grant + release partition lock, OR `JoinWaitQueue` (`proc.c:1179`, called under partition LWLock still held) → release partition LWLock → `WaitOnLock` → `ProcSleep`.
11. On wake: `waitStatus` is `OK` (grantor already updated shared state before signalling — comment at `lock.c:1968-1984`) or `ERROR` (deadlock / timeout / cancel).

### 5.2 `FastPathTransferRelationLocks` (strong-locker drain, `lock.c:2868-2956`)

For each PGPROC in `ProcGlobal->allProcs`: `LWLockAcquire(&proc->fpInfoLock)` → `LWLockAcquire(partitionLock)` → transfer matching fast-path slots into shared `LOCK`+`PROCLOCK` → `LWLockRelease(partitionLock)` → `LWLockRelease(&proc->fpInfoLock)`. **Operative ordering: `fpInfoLock` → partition LWLock.** This is the only place this ordering arises. `[verified-by-code]` (`lock.c:2890, 2928, 2948, 2953`, via `lock.c.md` §5.3).

### 5.3 `LockRelease` (`lock.c:2110-2314`)

Decrement LOCALLOCK first. Only when `nLocks` reaches zero do we touch shared state: take partition LWLock, `UnGrantLock`, `CleanUpLock` (which may remove the LOCK entry), `ProcLockWakeup` to advance any waiters; if `holdsStrongLockCount`, decrement `FastPathStrongRelationLocks->count[...]` under its spinlock. `[verified-by-code]` (via `lock.c.md` §5.4).

### 5.4 `LWLockAcquire` four-phase race protocol (`lwlock.c:1150-1311`)

Phases match the top-of-file comment at `lwlock.c:60-75`. `HOLD_INTERRUPTS()` at `lwlock.c:1189`. (1) `LWLockAttemptLock` CAS; if free, return. (2) Else `LWLockQueueSelf` (proclist push under `LW_FLAG_LOCKED` wait-list mutex). (3) Retry CAS — handles the race where the holder released between our failed CAS and our queue-push. (4) `PGSemaphoreLock(MyProc->sem)`. On wake, loop back to phase 1. **The releaser does not hand the lock directly to a waiter; the waiter retries the CAS** — avoids forced process swap per acquisition (comment at `lwlock.c:1195-1206`). `[verified-by-code]` (via `lwlock.c.md` §5.2).

### 5.5 `CheckDeadLock` + soft-edge rearrangement (`proc.c:1886-1970` + `deadlock.c:220-282`)

Fires from `ProcSleep` after `deadlock_timeout` (default 1 s) when `got_deadlock_timeout` is set by `CheckDeadLockAlert` (the SIGALRM handler).

1. Acquire **all 16** lock-partition LWLocks in exclusive mode, in partition-number order: `for (i = 0; i < NUM_LOCK_PARTITIONS; i++) LWLockAcquire(LockHashPartitionLockByIndex(i), LW_EXCLUSIVE)` at `proc.c:1902-1903`. `[verified-by-code]`.
2. Call `DeadLockCheck(MyProc)` → `DeadLockCheckRecurse`. WFG walk uses `FindLockCycleRecurse` (`deadlock.c:457-533`) + `FindLockCycleRecurseMember` (`deadlock.c:536-789`); group-leader collapsing means cycles are reported in leader space.
3. Edge classification: *hard* (waiting on a granted conflicting lock) vs *soft* (queue-position conflict with someone ahead). Soft-only cycles attempt every reversal subset via `TestConfiguration` + `ExpandConstraints` + `TopoSort` (`deadlock.c:378-1052`); if one survives, apply by zeroing the wait queue and re-pushing.
4. Outcomes: `DS_NO_DEADLOCK`, `DS_SOFT_DEADLOCK` (rearranged), `DS_HARD_DEADLOCK` (abort the start-point's txn), `DS_BLOCKED_BY_AUTOVACUUM` (caller sends cancel signal instead of aborting — the README:581-588 "abuse" hook).
5. **Release partition LWLocks in reverse order** at `proc.c:1959-1967` — keeps multi-lock waiters atomically unblocked and avoids O(N²) wakeup behavior. `[from-comment]`.
6. `DeadLockReport` runs *after* partition release, off a value-copied `deadlockDetails[]` (no shared-memory access — `DEADLOCK_INFO` is value-copied for this reason at `deadlock.c:64-77`).

### 5.6 Predicate-lock acquisition (`CreatePredicateLock`, `predicate.c:2382-2436`)

Obeys the 7-level acquisition order documented at `predicate.c:84-141`:

```c
LWLockAcquire(SerializablePredicateListLock, LW_SHARED);        // level 2
if (IsInParallelMode())
    LWLockAcquire(&sxact->perXactPredicateListLock, LW_EXCLUSIVE); // level 3
LWLockAcquire(partitionLock, LW_EXCLUSIVE);                      // level 4
// look up / create PREDICATELOCKTARGET, PREDICATELOCK; link into both lists
LWLockRelease(partitionLock);
if (IsInParallelMode()) LWLockRelease(&sxact->perXactPredicateListLock);
LWLockRelease(SerializablePredicateListLock);
```

The full prescribed ordering covers levels 1-7 from the comment: `SerializableFinishedListLock` → `SerializablePredicateListLock` → per-xact list lock → predicate partition lock (ascending-index order when more than one is needed, via `PredicateLockHashPartitionLockByIndex`) → `SerializableXactHashLock` → `SerialControlLock` → SLRU per-bank locks. Reverse-order release throughout. `[from-comment]` (`predicate.c:84-141`) `[verified-by-code]` (`predicate.c:2392-2435`, via `predicate.c.md` §4).

## 6. Locking and invariants — **THE KEY SECTION**

### Canonical ordering citations (the four that have explicit text in the tree)

1. **Heavyweight lock-partition LWLocks: partition-number order.** The deadlock detector iterates `i = 0 … NUM_LOCK_PARTITIONS-1` taking all 16 exclusive. Comment at `proc.c:1893-1897` is the authoritative statement: *"Acquire exclusive lock on the entire shared lock data structures. Must grab LWLocks in partition-number order to avoid LWLock deadlock. Note that the deadlock check interrupt had better not be enabled anywhere that this process itself holds lock partition locks, else this will wait forever."* `[from-comment]` (`proc.c:1887-1897` [via `knowledge/files/src/backend/storage/lmgr/proc.c.md` §4]) + `[from-README]` (`README:239-244` [via `knowledge/files/src/backend/storage/lmgr/README.md`]).

2. **Predicate-lock LWLock 7-level chain.** *"Lightweight locks to manage access to the predicate locking shared memory objects must be taken in this order, and should be released in reverse order: (1) SerializableFinishedListLock, (2) SerializablePredicateListLock, (3) per-xact perXactPredicateListLock (parallel only), (4) PredicateLockHashPartitionLock(hashcode), (5) SerializableXactHashLock, (6) SerialControlLock, (7) SLRU per-bank locks."* `[from-comment]` (`predicate.c:84-141` [via `knowledge/files/src/backend/storage/lmgr/predicate.c.md` §4]) `[verified-by-code]` against `CreatePredicateLock` at `predicate.c:2392-2435`. **When citing predicate-lock ordering, prefer `predicate.c:84-141` over README-SSI** — the C-file comment is what the implementation obeys.

3. **Group-leader fast-path fields under `LockHashPartitionLockByProc`.** `PGPROC.lockGroupLeader`, `lockGroupMembers`, `lockGroupLink` are protected by the *single* partition LWLock chosen by `LockHashPartitionLockByProc(leader)` = `hash(leader's pgprocno) mod NUM_LOCK_PARTITIONS`. This is chosen specifically so that the deadlock detector — which already holds *all* partition LWLocks — can read these without taking anything extra. Macro at `lock.h:363-373` [via `knowledge/files/src/backend/storage/lmgr/lock.c.md` §4]; README narrative at `README:660-667` [via `knowledge/files/src/backend/storage/lmgr/README.md`]. `[from-README]` `[verified-by-code]`.

4. **Relation-extension lock cannot deadlock.** `LOCKTAG_RELATION_EXTEND` is held for very short windows and a backend holding it is forbidden from acquiring any other heavyweight lock. Declaration of the assertion-tracking flag at `lock.c:181-194` [via `knowledge/files/src/backend/storage/lmgr/lock.c.md` §4]: *"`IsRelationExtensionLockHeld` is set true while a relation extension lock is held."* Enforced by `Assert(!IsRelationExtensionLockHeld)` at `lock.c:951` on entry to `LockAcquireExtended` (for any tag other than the same RELATION_EXTEND lock). Short-circuited by the deadlock detector at `deadlock.c:556-557` [via `deadlock.c.md` §4]: *"The relation extension lock can never participate in actual deadlock cycle. See Assert in LockAcquireExtended."* `[from-comment]` `[verified-by-code]`.

### Other rules with explicit citations (cross-referenced from `knowledge/idioms/locking-overview.md`)

5. **`PROCLOCK.releaseMask`** modified without partition LWLock; only the owning backend may examine/change. `[from-README]` (`README:185-189` [via `README.md`]).

6. **Fast-path / strong-locker memory sync.** Relies on LWLock acquisition being a memory sequence point (the CAS in `LWLockAttemptLock` "doubles as a memory barrier", comment at `lwlock.c:797-803`). The strong-locker takes *every* backend's `fpInfoLock`, so any concurrent fast-path entry must have been published. `[from-README]` (`README:306-321` [via `README.md`]) + `[from-comment]` (`lwlock.c:797-803` [via `lwlock.c.md` §4]).

7. **Hot Standby lock-level invariant.** Regular backends in recovery may take at most `RowExclusiveLock`; Startup process only acquires `AccessExclusiveLock` (replayed from WAL). Deadlock involving recovery is impossible by construction. `[from-README]` (`README:703-732, 711-718` [via `README.md`]).

8. **`LWLockReleaseAll` is interrupt-balance-neutral** — does a paired `HOLD_INTERRUPTS()` per held lock to match the upcoming `RESUME_INTERRUPTS()` from each `LWLockRelease`. `[from-comment]` (`lwlock.c:1855-1863` [via `lwlock.c.md` §4]).

9. **Spinlocks must not span kernel/subroutine calls or `CHECK_FOR_INTERRUPTS`.** No deadlock detection, no auto-release on error; stuck-spinlock after `NUM_DELAYS = 1000` (~2 min) PANICs the backend. `[from-comment]` (`s_lock.c:5-37, 57-92`, `spin.h:21-29` [via `s_lock.c.md` §4]) `[from-README]` (`README:8-11`).

10. **CV `mutex` is a spinlock**, held only for `proclist_push_tail` / `proclist_delete` / `proclist_pop_head`. The wake itself (`SetLatch`) happens *outside* the spinlock so the lock-hold time stays inside the spinlock rules. `[verified-by-code]` (`condition_variable.c:261-362` [via `condition_variable.c.md` §4-§5]).

### Unverified ordering rules carried forward to §9

Four ordering claims that the file-by-file pass identified as either implicit-only or completely unstated:

- **U1: `PGPROC.fpInfoLock` vs heavyweight lock-partition LWLock.** Implementation in `FastPathTransferRelationLocks` (`lock.c:2890-2953`) is `fpInfoLock → partitionLock`. **This ordering is implicit in the code; it is not stated as a top-level rule anywhere.** A reader has to trace `lock.c:2868-2956` to learn it. `[unverified-as-rule]` ([via `lock.c.md` §4, §7]).
- **U2: heavyweight lock-partition LWLock vs BufMapping LWLock.** No comment or README in either subsystem establishes a total order between these families. Flagged in both `knowledge/subsystems/storage-buffer.md` §9 and `knowledge/idioms/locking-overview.md` §6. `[unverified]`.
- **U3: `predicate.c:84-141` top-comment vs actual call sites.** The full 7-level chain is *prescribed* by the comment, but no call site in `predicate.c` takes all four/five/six/seven in one stretch — most paths take a subset (`CreatePredicateLock` takes levels 2-4). Whether the full chain is exercised anywhere, vs being purely prescriptive, was not verified. `[unverified]` ([via `predicate.c.md` §7 item 1]).
- **U4: user-code LWLock-then-heavyweight ordering.** No top-level rule states whether user code outside the lmgr subsystem may hold an LWLock and then call `LockAcquire`. The lmgr itself routinely takes LWLocks to manipulate heavyweight lock state, but no rule constrains callers. `[unverified]` ([via `knowledge/idioms/locking-overview.md` §6 item 3]).

## 7. Interactions with other subsystems

- **`storage/procarray`** (`procarray.c`): shares PGPROC slots. `InitProcessPhase2` adds to ProcArray; `ProcKill` removes. `ProcGlobal->statusFlags[]` / `xids[]` arrays are mirror caches read by ProcArray scans. Cross-ref: `proc.c.md` §6.
- **`storage/buffer`** (`bufmgr.c`): the buffer manager assumes relation-level heavyweight locks are held by callers (`storage/buffer/README:6-10`) `[from-README]`. The buffer manager uses its own `BufMapping` partition LWLocks — same primitive (LWLock), separate partition family, ordering between them and the heavyweight partition family is unverified (U2).
- **`access/heap`** + index AMs: routes through `lmgr.c` wrappers (`LockRelation`, `LockTuple`, `XactLockTableWait`). `heap_lock_tuple` is the sole architect of the "at most one `LOCKTAG_TUPLE` per backend" invariant (`README.tuplock:31-34`).
- **`access/heap` visibility hooks** call `PredicateLockTID`, `CheckForSerializableConflictOut/In` (predicate.c.md §5).
- **`executor`** invokes `LockAcquire` indirectly via `LockRelationOid` for every relation touched; `AcceptInvalidationMessages` runs immediately after acquisition (`lmgr.c:135-148`) so the catalog cache is coherent.
- **`access/transam`**: every transaction starts by `XactLockTableInsert` (`lmgr.c:622`) on its own xid; `XactLockTableWait` is how other transactions wait for it. 2PC support routes through `lock_twophase_recover` etc. at `lock.c:4339-4598`.
- **`replication/walsender` + `replication/logical`**: `LOCKTAG_APPLY_TRANSACTION` (`lmgr.c:1209-1247`) and `LOCKTAG_VIRTUALTRANSACTION` (CIC, Hot Standby conflict resolution).
- **`postmaster/autovacuum`**: deadlock detector signals autovac cancellation via `blocking_autovacuum_proc` + `GetBlockingAutoVacuumPgproc` (`deadlock.c:290`) read by `ProcSleep` after partition-lock release. The README:581-588 "abuse the deadlock detector" hook.
- **`utils/timeout`**: schedules `DEADLOCK_TIMEOUT`, `STATEMENT_TIMEOUT`, `LOCK_TIMEOUT` armed by `ProcSleep`.
- **`storage/lwlock` clients beyond `lock.c`**: predicate lock partition LWLocks (`predicate.c`), buffer-mapping partition LWLocks (`bufmgr.c`), WAL-insert locks via `LWLockAcquireOrWait` / `LWLockWaitForVar` / `LWLockUpdateVar` (`xlog.c`), all SLRU control locks.
- **`storage/condition_variable`** clients: `parallel.c` (barriers), `replication/slotsync.c`, `dsm.c`-mapped data structures.

## 8. Tests

- **Regress** (`source/src/test/regress/sql/`): `lock.sql`, `advisory_lock.sql` exercise the SQL-visible lock surface; many other tests exercise it implicitly.
- **Isolation** (`source/src/test/isolation/specs/`): the canonical test bed for concurrency.
  - Predicate-lock / SSI specs: `read-only-anomaly*`, `read-write-unique*`, `simple-write-skew`, `partial-index`, `predicate-*`, dozens more.
  - Deadlock specs: `deadlock-soft`, `deadlock-hard`, `deadlock-parallel`, `deadlock-simple`.
  - Group-locking: `parallel-*` specs.
  - Tuple lock specs: `tuplelock-*`.
- **`pg_locks` SQL view tests**: `source/src/test/regress/sql/lock.sql` exercises the `pg_locks` SRF and `pg_blocking_pids` interrogation; many isolation specs check `pg_locks` snapshots between steps.
- **TAP / modules**: there is no dedicated `src/test/modules/test_lmgr*`; coverage is via the above plus the implicit use by every other test.

## 9. Open questions / unverified claims

The four ordering items from §6:

1. **U1 — `fpInfoLock` vs heavyweight partition LWLock**: implicit-only; needs an in-tree comment or a `[verified-as-rule]` audit. `[unverified-as-rule]` ([via `knowledge/files/src/backend/storage/lmgr/lock.c.md` §4, §7]).
2. **U2 — heavyweight partition LWLock vs BufMapping partition LWLock**: no documented total order across LWLock families. Cross-flagged in `storage-buffer.md` §9 and `locking-overview.md` §6. `[unverified]`.
3. **U3 — `predicate.c:84-141` chain vs actual call sites**: full chain is prescriptive; subset usage is what's actually observed. `[unverified]`.
4. **U4 — LWLock-then-heavyweight in user code**: undocumented. `[unverified]`.

Additional items from the file-level pass:

5. **`LockAcquireExtended` weak path holding any other LWLock when taking the partition lock.** Reading `lock.c:1062-1064`, the partition lock is taken *after* `fpInfoLock` has been released; the partition lock is the only LWLock the slow path holds. No comment or assertion enforces this. `[unverified]` ([via `lock.c.md` §7 item 2]).
6. **Total ordering between `fpInfoLock` of different backends** in `FastPathTransferRelationLocks` — order is `pgprocno`-increasing by the for-loop at `lock.c:2885`, but this is implementation, not a stated rule. `[unverified-as-rule]` ([via `lock.c.md` §7 item 1]).
7. **`LWLockHeldByMe*` correctness with non-uniform-stride extension tranches** — documented debug-only. `[from-comment]` (`lwlock.c:1879-1928`).
8. **Memory ordering of every non-CAS atomic in `lwlock.c`** — not exhaustively verified. `[unverified]` ([via `lwlock.c.md` §7 item 1]).
9. **Cycle reporting under simultaneous deadlock detection**: README:553-555 acknowledges the race; the later detector finds the cycle broken and returns `DS_NO_DEADLOCK`. `[from-README]` ([via `deadlock.c.md` §7 item 1]).
10. **Autovacuum-cancel race**: `blocking_autovacuum_proc` set under all partition locks, read by `ProcSleep` after release; a second detection on another waiter might clear it via `GetBlockingAutoVacuumPgproc`. Not obviously a bug, but the race is subtle. `[unverified]` ([via `deadlock.c.md` §7 item 4]).
11. **Whether non-blocking predicate-lock paths inside index AMs (e.g. `nbtree` calling `PredicateLockPage` under buffer content lock) need any ordering against buffer content locks.** `[unverified]` ([via `predicate.c.md` §7 item 5]).
12. **`speculativeInsertionToken` wrap-around frequency**: 2^32 in the relevant window is essentially never; worth a one-line "no observed instances" comment. `[from-comment]` (`lmgr.c:32-44`).
13. **`SetLocktagRelationOid` shared-relation logic** relies on `IsSharedRelation(relid)`; a new shared catalog without that list update would cause lock-tag aliasing. `[from-comment, indirect]` ([via `lmgr.c.md` §7 item 1]).

## 10. Glossary

- **LOCKMODE** — integer 1..8 naming the heavyweight lock strength; `NoLock = 0` is the "don't acquire" sentinel; `MAX_LOCKMODES = 10` is the bitmask budget. `[verified-by-code]` (`lockdefs.h:33-48`, `lock.h:84-85`).
- **LOCKTAG** — 16-byte key identifying a heavyweight-lockable object. Twelve `LockTagType`s: RELATION, RELATION_EXTEND, DATABASE_FROZEN_IDS, PAGE, TUPLE, TRANSACTION, VIRTUALTRANSACTION, SPECULATIVE_TOKEN, OBJECT, USERLOCK, ADVISORY, APPLY_TRANSACTION. `[verified-by-code]` (`locktag.h:35-72`).
- **LWLock tranche** — a named group of LWLocks; tranche ID determines the wait-event name. Three kinds: individually-named (slot in `MainLWLockArray`), built-in groups (`BUFFER_MAPPING`, `LOCK_MANAGER`, `PREDICATE_LOCK_MANAGER`, `WAL_INSERT`, `LOCK_FASTPATH`, …), extension-defined. Wait-event names == tranche names. `[from-comment]` (`lwlock.c:120-136`).
- **Fast-path lock** — weak relation lock (AccessShare/RowShare/RowExclusive) on a local rel, recorded in `PGPROC.fpLockBits/fpRelId` under that backend's `fpInfoLock` LWLock; bypasses the shared hash. Strong-locker drains via `FastPathTransferRelationLocks`. `[from-README]` (`README:257-336`).
- **SIREAD** — non-blocking predicate "lock" used by serializable transactions to track reads. Created only by serializable xacts; survives commit until all overlapping xacts finish. `[from-comment]` (`predicate.c:1-150`).
- **Dangerous structure** — `Tin → Tpivot → Tout` chain of rw-conflict edges between three concurrent transactions; SSI aborts one when this is detected (with two PG-specific optimisations). `[from-README]` (`README-SSI:151-198`).
- **Soft edge** — wait-queue position conflict; resolvable by reordering the queue. **Hard edge** — waiting on a granted conflicting lock; not resolvable. Cycle of all-soft → try reversals; any-hard → abort. `[from-README]` (`README:393-536`, `deadlock.c.md` §4).
- **WFG cycle** — waits-for-graph cycle; detected by DFS from the timed-out waiter; reported in group-leader space. `[from-README]` `[verified-by-code]` (`deadlock.c:457-789`).
- **Tranche** vs **tranche ID** — name vs integer; ID range 0..(NUM_INDIVIDUAL_LWLOCKS-1) is individuals, then built-in `LWTRANCHE_*` enum, then ≥`LWTRANCHE_FIRST_USER_DEFINED` for extensions. `[verified-by-code]` (`lwlock.c:120-135`).
- **NUM_LOCK_PARTITIONS / NUM_BUFFER_PARTITIONS / NUM_PREDICATELOCK_PARTITIONS** — 16 / 128 / 16. `[verified-by-code]` (`lwlock.h:83-91`).
- **DeadlockTimeout** — GUC, default 1000 ms, before a waiter arms `CheckDeadLockAlert`. `[verified-by-code]` (`proc.c:62`).
- **Group locking** — locks held by procs in the same parallel group don't conflict *except* `LOCKTAG_RELATION_EXTEND` (which conflicts even between group members — see `lock.c:1603-1608`). `[from-README]` (`README:589-650`).
- **Stuck spinlock** — `NUM_DELAYS = 1000` (~2 minute) cap; `s_lock_stuck` PANICs. `[verified-by-code]` (`s_lock.c:78-92`).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**27 files.**

| File |
|---|
| [`src/backend/storage/lmgr/README`](../files/src/backend/storage/lmgr/README.md) |
| [`src/backend/storage/lmgr/README-SSI`](../files/src/backend/storage/lmgr/README-SSI.md) |
| [`src/backend/storage/lmgr/condition_variable.c`](../files/src/backend/storage/lmgr/condition_variable.c.md) |
| [`src/backend/storage/lmgr/deadlock.c`](../files/src/backend/storage/lmgr/deadlock.c.md) |
| [`src/backend/storage/lmgr/lmgr.c`](../files/src/backend/storage/lmgr/lmgr.c.md) |
| [`src/backend/storage/lmgr/lock.c`](../files/src/backend/storage/lmgr/lock.c.md) |
| [`src/backend/storage/lmgr/lwlock.c`](../files/src/backend/storage/lmgr/lwlock.c.md) |
| [`src/backend/storage/lmgr/predicate.c`](../files/src/backend/storage/lmgr/predicate.c.md) |
| [`src/backend/storage/lmgr/proc.c`](../files/src/backend/storage/lmgr/proc.c.md) |
| [`src/backend/storage/lmgr/s_lock.c`](../files/src/backend/storage/lmgr/s_lock.c.md) |
| [`src/include/storage/block.h`](../files/src/include/storage/block.h.md) |
| [`src/include/storage/checksum_block_internal.h`](../files/src/include/storage/checksum_block_internal.h.md) |
| [`src/include/storage/lmgr.h`](../files/src/include/storage/lmgr.h.md) |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) |
| [`src/include/storage/lockdefs.h`](../files/src/include/storage/lockdefs.h.md) |
| [`src/include/storage/locktag.h`](../files/src/include/storage/locktag.h.md) |
| [`src/include/storage/lwlock.h`](../files/src/include/storage/lwlock.h.md) |
| [`src/include/storage/lwlocklist.h`](../files/src/include/storage/lwlocklist.h.md) |
| [`src/include/storage/predicate.h`](../files/src/include/storage/predicate.h.md) |
| [`src/include/storage/predicate_internals.h`](../files/src/include/storage/predicate_internals.h.md) |
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) |
| [`src/include/storage/procarray.h`](../files/src/include/storage/procarray.h.md) |
| [`src/include/storage/proclist.h`](../files/src/include/storage/proclist.h.md) |
| [`src/include/storage/proclist_types.h`](../files/src/include/storage/proclist_types.h.md) |
| [`src/include/storage/procnumber.h`](../files/src/include/storage/procnumber.h.md) |
| [`src/include/storage/procsignal.h`](../files/src/include/storage/procsignal.h.md) |
| [`src/include/storage/s_lock.h`](../files/src/include/storage/s_lock.h.md) |

<!-- /files-owned:auto -->
