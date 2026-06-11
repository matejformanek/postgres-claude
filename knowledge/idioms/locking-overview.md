# Locking and concurrency — overview

- **Source paths:** `source/src/backend/storage/lmgr/`, `source/src/include/storage/{lock,lwlock,spin,s_lock,lockdefs,locktag,predicate}.h`, `source/src/include/port/atomics.h`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-11; §1.1–1.4 cites re-verified: atomics.h, spin.h, lwlock.h, lock.h, lockdefs.h, locktag.h. One drift fixed — `lockdefs.h:39-40` now lists `REPACK CONCURRENTLY` for ShareUpdateExclusiveLock.)
- **Primary READMEs:** `source/src/backend/storage/lmgr/README` (heavyweight lock manager), `source/src/backend/storage/lmgr/README-SSI` (predicate locks / SSI), `source/src/backend/storage/lmgr/README.barrier` (memory ordering), `source/src/backend/access/heap/README.tuplock` (row-level locks).

This is the calibration overview. Deep dives (heavyweight lock manager internals, LWLock implementation details, SSI in depth) are expected to live in subsystem files that anchor to the sections below.

## 1. The six-layer taxonomy

PostgreSQL stacks six distinct concurrency primitives. From cheapest/shortest-lived to most expressive:

| Layer | Primitive | Protects | Acquisition cost | Deadlock detection? | elog/error safe? |
|---|---|---|---|---|---|
| 1 | **Atomic ops** (`pg_atomic_*`) | a single 32- or 64-bit word | one CAS / fetch-and-add | n/a | n/a |
| 2 | **Spinlocks** (`SpinLock*` / `slock_t`) | a few instructions of shared data | one TAS in the uncontended case | no | **no** — must not error while held |
| 3 | **LWLocks** (`LWLockAcquire`) | larger shared-memory data structures | one CAS uncontended; OS sleep on contention | no | **yes** — auto-released on `elog` `[from-README]` |
| 4 | **Heavyweight (regular) locks** (`LockAcquire`) | user-visible objects (relations, tuples, xacts, advisory…) | shared hash table + LWLock partition | **yes** | yes — released at xact end |
| 5 | **Predicate locks / SIREAD** (`PredicateLock*`) | logical *predicates* read by a serializable xact | shared hash; never block | n/a (no waits) | yes |
| 6 | **Tuple-level row locks** (heap xmax + LOCKTAG_TUPLE + MultiXact) | individual heap tuples for `SELECT FOR …` | heap header bits + optional MultiXact + lmgr arbitration | inherits from heavyweight | yes |

These layers are described top-down in `README:6-46` `[from-README]`.

### 1.1 Atomics — `src/include/port/atomics.h`

API entry points: `pg_atomic_read_u32/u64`, `pg_atomic_compare_exchange_u32/u64`, `pg_atomic_fetch_add_u32/u64`, `pg_atomic_test_set_flag`, plus barriers `pg_compiler_barrier`, `pg_read_barrier`, `pg_write_barrier`, `pg_memory_barrier` `[verified-by-code]` (`atomics.h:10-30`). A platform must provide u32 atomics + barriers + a flag type; u64 falls back to spinlock-backed emulation `[from-comment]` (`atomics.h:18-23, 107-112`).

Header guidance: "Use higher level functionality (lwlocks, spinlocks, heavyweight locks) whenever possible. Writing correct code using these facilities is hard." `[from-comment]` (`atomics.h:25-26`). Pre-existing real-world use is for in-band CAS loops on packed state words (e.g. `BufferDesc.state` in the buffer manager).

For background on barrier semantics see `README.barrier`.

### 1.2 Spinlocks — `src/include/storage/{spin,s_lock}.h`, `src/backend/storage/lmgr/s_lock.c`

Type `slock_t`, API `SpinLockInit/Acquire/Release` `[verified-by-code]` (`spin.h:10-19, 49-65`). Implementation is hardware TAS in `s_lock.h`; `s_lock.c` is only the wait loop used after the inline TAS fails `[from-comment]` (`s_lock.c:5-37`).

Rules from the README and `spin.h`:
- "If a lock is to be held more than a few dozen instructions, or across any sort of kernel call (or even a call to a nontrivial subroutine), don't use a spinlock." `[from-README]` (`README:8-11`).
- "We assume it is not possible for a `CHECK_FOR_INTERRUPTS()` to occur while holding a spinlock, and so it is not necessary to do HOLD/RESUME_INTERRUPTS()." `[from-comment]` (`spin.h:26-29`).
- Query-cancel and die() are held off implicitly while a spinlock is held `[from-README]` (`README:39-45`).
- There is no deadlock detection and no automatic release on error; a stuck spinlock after `NUM_DELAYS = 1000` tries (~2 minutes) is treated as an error condition and aborts `[from-comment]` (`s_lock.c:30-45, 57-61`).

Load/store reordering across `SpinLockAcquire/Release` is forbidden by a compiler barrier built into the macros `[from-comment]` (`spin.h:21-24`).

### 1.3 LWLocks — `src/backend/storage/lmgr/lwlock.c`, `src/include/storage/lwlock.h`

Reader/writer locks (`LW_SHARED`, `LW_EXCLUSIVE`) plus a "wait until variable changes" mode used by the WAL insert locks `[from-comment]` (`lwlock.c:13-21`, `lwlock.h:102-109`).

Key facts:
- Lock state is a single `pg_atomic_uint32` packing a share-counter, exclusive sentinel, and three flag bits (`LW_FLAG_HAS_WAITERS`, `LW_FLAG_WAKE_IN_PROGRESS`, `LW_FLAG_LOCKED`) `[verified-by-code]` (`lwlock.c:96-108`, `lwlock.h:41-50`).
- Acquisition is wait-free in the uncontended shared case via CAS; on contention the backend joins a `proclist` of waiters and sleeps on a semaphore `[from-comment]` (`lwlock.c:38-75`).
- "Waiting processes will be granted the lock in arrival order. There is no timeout." `[from-README]` (`README:28-30`).
- LWLocks are auto-released during `elog` cleanup, so it is safe to `ereport(ERROR, …)` while holding one `[from-README]` (`README:23-26`).
- Query-cancel and die() interrupts are held off while waiting for an LWLock — so it is *not* a good idea to use LWLocks when wait time might exceed a few seconds `[from-README]` (`README:39-45`).
- A backend may hold at most `MAX_SIMUL_LWLOCKS = 200` LWLocks simultaneously `[verified-by-code]` (`lwlock.c:157-167`).

#### LWLock tranches and named locks — the `lwlocknames.h` mechanism

LWLocks fall into three categories `[from-comment]` (`lwlock.c:120-135`):

1. **Individually-named locks.** Each one is a single LWLock with its own tranche; declared by `PG_LWLOCK(id, name)` macros in `src/include/storage/lwlocklist.h` `[verified-by-code]` (`lwlocklist.h:34-91`). The perl script `generate-lwlocknames.pl` processes this list and emits `lwlocknames.h`, which defines `NUM_INDIVIDUAL_LWLOCKS` as `(max id + 1)` `[verified-by-code]` (`generate-lwlocknames.pl:173`). Currently these are slots 2–57 with some historical gaps (e.g. slot 0 was `BufFreelistLock`, 10 was `CheckpointLock`) `[verified-by-code]` (`lwlocklist.h:34-91`).
2. **Built-in tranches** for groups of locks not in `MainLWLockArray`: declared by `PG_LWLOCKTRANCHE(id, name)` in the same file (e.g. `BUFFER_MAPPING`, `LOCK_MANAGER`, `PREDICATE_LOCK_MANAGER`, `WAL_INSERT`, `LOCK_FASTPATH`, `XACT_BUFFER`, …) `[verified-by-code]` (`lwlocklist.h:101-143`).
3. **Extension-defined tranches**, registered at postmaster start via `RequestNamedLWLockTranche` (gets a slice of `MainLWLockArray`) or `LWLockNewTrancheId` + `LWLockInitialize` (lock lives in caller-allocated shmem) `[verified-by-code]` (`lwlock.h:139-149`, comment 130-132).

Within `MainLWLockArray`, fixed regions are laid out as `[from-comment]` (`lwlock.h:93-100`):

```
[0 .. NUM_INDIVIDUAL_LWLOCKS-1]            individual locks (OidGen, XidGen, ProcArray, …)
[BUFFER_MAPPING_LWLOCK_OFFSET ..]          NUM_BUFFER_PARTITIONS = 128 buffer-mapping locks
[LOCK_MANAGER_LWLOCK_OFFSET ..]            NUM_LOCK_PARTITIONS    =  16 heavyweight lock partitions
[PREDICATELOCK_MANAGER_LWLOCK_OFFSET ..]   NUM_PREDICATELOCK_PARTITIONS = 16 predicate-lock partitions
[NUM_FIXED_LWLOCKS ..]                     named-tranche regions requested by extensions
```

Wait-event names equal tranche names, so adding a tranche means also updating `src/backend/utils/activity/wait_event_names.txt` `[from-comment]` (`lwlock.c:134-136`, `lwlocklist.h:27-31`).

### 1.4 Heavyweight locks — `lock.c`, `lock.h`, `lockdefs.h`

These are the user-visible locks: `LOCK TABLE`, automatic locks taken by SELECT/INSERT/etc., advisory locks, transaction locks. Documented in `README:32-86` and onward.

- Backed by a partitioned shared hash table of `LOCK` + per-(lock, proc) `PROCLOCK` objects `[from-README]` (`README:50-86`).
- Per-backend `LOCALLOCK` table counts re-entry (you can lock the same table twice; only one shared `PROCLOCK` is needed) `[from-README]` (`README:78-86`, `lock.h:257-272`).
- 16 partitions in shared memory (`NUM_LOCK_PARTITIONS = 1 << 4`), one LWLock each, slot chosen by hash of LOCKTAG `[verified-by-code]` (`lwlock.h:86-87`, `lock.h:350-361`).
- Two lock methods: `DEFAULT_LOCKMETHOD` (most things), `USER_LOCKMETHOD` (advisory) `[verified-by-code]` (`locktag.h:24-26`, `lock.c:128-157`).
- 12 `LockTagType`s: RELATION, RELATION_EXTEND, DATABASE_FROZEN_IDS, PAGE, TUPLE, TRANSACTION, VIRTUALTRANSACTION, SPECULATIVE_TOKEN, OBJECT, USERLOCK, ADVISORY, APPLY_TRANSACTION `[verified-by-code]` (`locktag.h:35-52`).

#### Lock modes and conflict matrix

Eight numeric modes, ordered weakest → strongest `[verified-by-code]` (`lockdefs.h:33-48`):

| # | Mode | Typical acquirer |
|---|---|---|
| 1 | AccessShareLock | `SELECT` |
| 2 | RowShareLock | `SELECT FOR UPDATE/SHARE` |
| 3 | RowExclusiveLock | `INSERT`, `UPDATE`, `DELETE` |
| 4 | ShareUpdateExclusiveLock | `VACUUM` (non-FULL), `ANALYZE`, `CREATE INDEX CONCURRENTLY`, `REINDEX CONCURRENTLY`, `REPACK CONCURRENTLY` |
| 5 | ShareLock | `CREATE INDEX` (non-concurrent) |
| 6 | ShareRowExclusiveLock | like Exclusive but allows ROW SHARE |
| 7 | ExclusiveLock | blocks ROW SHARE / SELECT…FOR UPDATE |
| 8 | AccessExclusiveLock | `ALTER TABLE`, `DROP TABLE`, `VACUUM FULL`, plain `LOCK TABLE` |

The full conflict table is the array `LockConflicts[]` in `lock.c:68-108`. Reading it row-by-row:

```
       ASL RSL REL SUE  SL SRE  EL AEL    (column = mode held; row = mode requested)
ASL                                  X
RSL                              X   X
REL              X   X   X       X   X
SUE          X   X   X   X       X   X
SL       X   X       X   X       X   X
SRE      X   X   X   X   X       X   X
EL   X   X   X   X   X   X       X   X    (also self-conflicts: see code)
AEL  X   X   X   X   X   X   X   X   X
```

That is the canonical reference. The text version published in the docs (`https://www.postgresql.org/docs/current/explicit-locking.html`) is a re-rendering of this table `[from-comment]` (`lock.c:63-68`).

Also defined: `NoLock = 0` is *not* a mode but a "don't acquire" flag `[verified-by-code]` (`lockdefs.h:33-34`); `MAX_LOCKMODES = 10` (bitmask width budget) `[verified-by-code]` (`lock.h:84-85`).

#### Fast-path locking

Weak locks (AccessShare/RowShare/RowExclusive) on local (non-shared) relations, and VXID locks, are recorded in the backend's PGPROC fast-path array rather than the shared hash, when no conflicting strong lock could be present `[from-README]` (`README:257-336`). A separate 1024-entry `FastPathStrongRelationLocks` counter array allows lock-free "is there a strong locker?" checks; when a backend takes a strong lock it bumps the counter and walks all backends' fast-path arrays, transferring any matching weak locks to the shared table `[from-README]` (`README:286-321`).

This is why a contended `LockManager` LWLock often shows up under DDL-heavy workloads but not pure-DML ones — fast-path bypasses the partition LWLock entirely in the common case.

#### Deadlock detection — `deadlock.c`, `proc.c`

- Algorithm: timer-driven, optimistic. A backend that has to wait on a heavyweight lock arms a timeout of `DeadlockTimeout` ms (GUC `deadlock_timeout`, default 1000 ms) `[verified-by-code]` (`proc.c:62, 1401-1408`).
- When the timer fires, `CheckDeadLock()` acquires **all** lock partition LWLocks in partition-number order, then runs `DeadLockCheck(MyProc)` on the waits-for graph `[verified-by-code]` (`proc.c:1855-1939`). It releases the partition locks in reverse order to avoid O(N²) lock-release behavior and to keep partition-acquisition order consistent across processes `[from-comment]` (`proc.c:1927-1936`).
- Edges are "hard" (waiting on a granted conflicting lock) or "soft" (queue-position priority block). A soft deadlock may be resolved by re-ordering the wait queue via topological sort; a hard deadlock aborts the detecting transaction `[from-README]` (`README:393-536`).
- Group locking: locks held by processes in the same parallel group don't conflict (except `RELATION_EXTEND`), so a parallel leader+workers can't deadlock with itself `[from-README]` (`README:589-678`).
- AutoVacuum-cancellation is implemented inside the detector: if a victim would be an autovacuum worker, the detector signals cancellation instead of aborting the waiter `[from-README]` (`README:581-588`).

#### Special heavyweight-lock cases

- **Relation extension lock** (`LOCKTAG_RELATION_EXTEND`) is held for very short windows and *cannot* participate in any deadlock cycle: a backend holding it is forbidden from acquiring any other heavyweight lock; this is asserted by `IsRelationExtensionLockHeld` `[from-comment]` (`lock.c:181-194, 948-951`).
- **VXID locks** are taken self-exclusively by every backend on its own vxid; others use them only to wait for a transaction to finish (CIC, Hot Standby conflicts) `[from-README]` (`README:273-277, 322-331`).
- **Hot Standby**: regular backends on a replica may only take locks ≤ `RowExclusiveLock`; the Startup process only acquires locks at `AccessExclusiveLock` (replayed from WAL) — so no deadlock involving recovery is possible, but a regular backend can still block replay (resolved via cancellation) `[from-README]` (`README:703-731`).

### 1.5 Predicate locks / SSI — `predicate.c`, `predicate_internals.h`, `README-SSI`

Predicate locks ("SIREAD") never block; they only **track** rw-conflicts so the SSI machinery can detect dangerous structures (two adjacent rw-conflict edges through a pivot transaction) and abort one of the involved transactions with a `serialization_failure` `[from-README]` (`README-SSI:154-198`).

- Active only at `SERIALIZABLE` isolation level.
- Granularities: tuple, page, relation. Acquiring a coarser lock releases the finer-grained ones it covers; redundant finer locks are skipped when the coarser is already held `[from-README]` (`README-SSI:281-298`).
- Stored in shared memory partitioned in 16 ways (`NUM_PREDICATELOCK_PARTITIONS`, controlled by `PredicateLockManager` tranche of LWLocks) `[verified-by-code]` (`lwlock.h:90-91`, `lwlocklist.h:115`).
- Three predicate-lock-related individually-named LWLocks: `SerializableXactHash`, `SerializableFinishedList`, `SerializablePredicateList`, plus `SerialControl` for the commit-sequence-number SLRU `[verified-by-code]` (`lwlocklist.h:62-65, 86`).
- Index AMs participate by locking the "gap" they scanned, typically a B-tree leaf page or GIN entry-tree leaf; for AMs without support, the whole index is locked `[from-README]` (`README-SSI:325-380`).
- Granularity promotion: when a transaction accumulates "too many" finer-grained locks against the same parent, they're collapsed into the coarser parent lock `[from-README]` (`README-SSI:518-530`).

For details on the `RWConflictData` graph, the role of `SerialSLRU` for finished-transaction summaries, and dangerous-structure detection, see a future SSI deep dive.

### 1.6 Row-level tuple locks — `src/backend/access/heap/README.tuplock`

Row locks are *two* mechanisms working together `[from-README]` (`README.tuplock:1-37`):

1. **In-tuple storage.** The first locker stores its xid in the tuple's `xmax` + `infomask` bits indicating lock strength. Multiple simultaneous lockers replace the xid with a `MultiXactId` that points to an array of (xid, lock-strength) pairs in the multixact SLRU.
2. **Arbitration via heavyweight `LOCKTAG_TUPLE`.** When a backend must *wait* for a row lock, it takes a heavyweight lock on the tuple's `(dbOid, relOid, blockNum, offNum)` and then sleeps on `XactLockTableWait` or `MultiXactIdWait`. This serializes waiters so a stream of share-lockers cannot starve an exclusive locker.

Four lock strengths exposed at SQL level: `FOR KEY SHARE`, `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR UPDATE`, with the conflict matrix in `README.tuplock:63-69` `[from-README]`.

Crucially: at most one `LOCKTAG_TUPLE` heavyweight lock is held by a backend at any moment, so this can't overflow the lock table `[from-README]` (`README.tuplock:31-34`).

## 2. Locking-order rules — what's actually written down

These are the rules that, if violated, can cause LWLock deadlocks (which are *not* detected — the system just wedges). Be extra careful here: I tag conservatively.

### Documented rules (verbatim or near-verbatim)

1. **Heavyweight lock partition LWLocks acquired in partition-number order.** "any backend needing to lock more than one partition at once must lock them in partition-number order" `[from-README]` (`README:239-244`). Enforced by `CheckDeadLock` which iterates `i = 0 … NUM_LOCK_PARTITIONS-1` `[verified-by-code]` (`proc.c:1871-1872`).
2. **BufMapping partition LWLocks acquired in partition-number order.** "If it is necessary to lock more than one partition at a time, they must be locked in partition-number order to avoid risk of deadlock." `[from-README]` (`src/backend/storage/buffer/README:140-143`, summarized in `knowledge/subsystems/storage-buffer.md`).
3. **Pin before content-lock on a buffer.** A buffer must be pinned before its content lock may be taken `[from-README]` (`src/backend/storage/buffer/README:38-41`).
4. **Buffer-mapping partition lock is released only after the found buffer is pinned** (so the buffer can't be evicted between the hash hit and the pin) `[from-README]` (`storage/buffer/README:123-134`).
5. **Nothing else may be acquired while `buffer_strategy_lock` (spinlock) is held.** `[from-README]` (`storage/buffer/README:144-149`).
6. **Spinlocks may not be held across a kernel call, subroutine call, or `CHECK_FOR_INTERRUPTS`** `[from-README]` (`README:8-11`) `[from-comment]` (`spin.h:26-29`).
7. **Relation extension lock must not be held while requesting any other heavyweight lock.** Asserted at runtime `[from-comment]` (`lock.c:181-194, 948-951`).
8. **Deadlock detection holds *all* lock-partition LWLocks for its scan; therefore no code may run while holding *any* lock-partition LWLock if it can be re-entered through a deadlock-check path.** Comment: "Note that the deadlock check interrupt had better not be enabled anywhere that this process itself holds lock partition locks, else this will wait forever." `[from-comment]` (`proc.c:1865-1869`).
9. **`PROCLOCK.releaseMask` is modified without the partition LWLock and is therefore only safe for the owning backend to examine.** `[from-README]` (`README:185-189`).
10. **Group-leader fields in PGPROC (`lockGroupLeader`, `lockGroupMembers`, `lockGroupLink`) are protected by the lock partition LWLock chosen by `LockHashPartitionLockByProc(leader)`** — chosen so that the deadlock detector, which already holds *all* lock partition LWLocks, can read these without taking anything extra `[from-README]` (`README:660-667`) `[verified-by-code]` (`lock.h:363-373`).
11. **Fast-path lock acquisition is interlocked with strong-locker scans via the per-backend `LockFastPath` LWLock.** A backend doing a fast-path acquire takes its own `LockFastPath`; a strong locker takes *every* backend's `LockFastPath` in turn — so the strong locker is guaranteed to see any concurrent fast-path entry `[from-README]` (`README:306-321`).

### Less-explicit but verifiable rules

12. **WAL-before-data on flush.** `FlushBuffer` calls `XLogFlush(BufferGetLSN(buf))` *before* `smgrwrite` when `BM_PERMANENT` is set; see the buffer doc (`storage-buffer.md` §5.3). Conceptually this is the same family of rule as the locking-order rules: the LSN read and the flush must happen under the content lock. `[from-comment]` (`bufmgr.c:4547-4571`).
13. **Cleanup lock = exclusive content lock + refcount==1.** Ordering: acquire exclusive lock → take header spinlock → check refcount; if not 1, install waiter flag and sleep. `[verified-by-code]` (`bufmgr.c:6678-6800`).

### Ordering claims I could not pin to an explicit statement → see Open Questions

- Total ordering between content-lock and BufMapping partition lock when both are held by the same backend. `[unverified]`
- Total ordering between heavyweight lock-partition LWLocks and BufMapping partition LWLocks. `[unverified]`
- Whether an LWLock and a heavyweight lock acquisition has a documented ordering rule (i.e. always LWLock-then-heavy or heavy-then-LWLock). The lock manager itself takes LWLocks *to manipulate* heavyweight lock state, but I did not find a top-level statement about user-code paths that hold an LWLock and then call `LockAcquire`. `[unverified]`

## 3. SSI in one paragraph

A serializable transaction takes SIREAD predicate locks on everything it reads (with granularity promotion), and tracks rw-conflicts with concurrent transactions via shared `RWConflictData` lists. At commit time (or periodically) the SSI machinery looks for the *dangerous structure*: two adjacent rw-edges `Tin → Tpivot → Tout`. If found, and `Tout` would commit before `Tpivot` and `Tin`, one of the three is aborted with SQLSTATE `40001 (serialization_failure)`. Predicate locks are released when no concurrent transaction can still see the reading transaction. SSI is "snapshot isolation with abort-instead-of-block on dangerous structures" — reads never block writes and writes never block reads, but commits can fail. `[from-README]` (`README-SSI:34-104, 151-198`).

## 4. Atomics vs spinlock vs LWLock — when to use what

| Situation | Use |
|---|---|
| Counter, flag, or single packed word, very hot, accessed by many backends | `pg_atomic_*` (with explicit barriers when the order across multiple locations matters) |
| Need to update 2+ fields together, but only briefly (few instructions, no subroutine calls) | spinlock |
| Need a reader/writer lock, larger critical section, may need to sleep, must be safe across `ereport(ERROR)` | LWLock |
| Need to lock a *user-visible object* (relation, tuple, advisory id), may need deadlock detection, must auto-release on xact end | heavyweight lock |
| Need to *track* (not block on) reads in a serializable transaction | predicate lock |

`atomics.h:25-26` `[from-comment]` says "use higher level functionality whenever possible". The pragmatic interpretation: reach for atomics only when profiling shows the LWLock or spinlock is a real bottleneck, and the data fits in one or two atomic words. The buffer manager's `BufferDesc.state` is the canonical example.

## 5. Where MVCC meets locking

PostgreSQL is MVCC: reads never block writes, writes never block reads — instead each tuple's `xmin`/`xmax`/`infomask` encode its visibility per transaction snapshot (`docs/mvcc.html`, `docs/transaction-iso.html`). Locking interacts with MVCC at a small number of well-defined points:

- **Hint bits** (e.g. `HEAP_XMIN_COMMITTED`) are visibility *caches* set lazily and may be updated under a share-exclusive buffer content lock without WAL logging — see buffer doc rule 4.
- **Row locks** (§1.6) write into `xmax`+infomask; the writer is the lock holder. The MultiXact SLRU exists precisely so multiple concurrent lockers can coexist in a single tuple slot.
- **Heavyweight transaction locks** (`LOCKTAG_TRANSACTION`, `LOCKTAG_VIRTUALTRANSACTION`) are how one transaction *waits* for another to finish, when MVCC alone is not enough (e.g. a `SELECT FOR UPDATE` that hits a row whose xmax is an in-progress xid).
- **SSI** sits *between* MVCC reads and writes, intercepting rw-conflicts that pure snapshot isolation would miss.

## 6. Open questions / unverified claims

1. Total ordering between buffer content lock and BufMapping partition LWLock (`[unverified]`, see §2).
2. Total ordering between heavyweight lock-manager LWLocks and BufMapping LWLocks (`[unverified]`, see §2).
3. Whether there is a documented rule on LWLock-then-heavyweight ordering for *user* code outside the lmgr subsystem itself (`[unverified]`, see §2).
4. Exact semantics of `LWLockAcquireOrWait` vs `LWLockAcquire` — used in WAL flush paths; not covered here. `[unverified]`
5. How predicate locks interact with parallel workers — `README-SSI` mentions group locking only obliquely. `[unverified]`
6. Whether row locks acquired by `SELECT FOR KEY SHARE` always touch the lmgr (`LOCKTAG_TUPLE`) or only on contention. Source `README.tuplock:31-37` says "if there is not any active conflict for a tuple, we don't incur any extra overhead", suggesting LockTuple is skipped without conflict, but I did not trace `heap_lock_tuple` to confirm. `[from-README, but not traced]`

## 7. Glossary

- **LOCKTAG** — 16-byte key identifying a heavyweight-lockable object (relation, tuple, xact, advisory id, …). `[verified-by-code]` (`locktag.h:64-72`).
- **LOCK / PROCLOCK / LOCALLOCK** — shared per-object record / shared per-(object, backend) record / backend-private re-entry counter. `[from-README]` (`README:50-86`).
- **LOCKMODE** — integer 1..8 naming the heavyweight lock strength. `NoLock = 0` is a non-mode sentinel. `[verified-by-code]` (`lockdefs.h`).
- **Tranche** — a named group of LWLocks; tranche ID determines the wait-event name. `[from-comment]` (`lwlock.c:120-136`).
- **NUM_INDIVIDUAL_LWLOCKS** — number of named-individual LWLock slots in `MainLWLockArray`; generated from `lwlocklist.h` by `generate-lwlocknames.pl`. `[verified-by-code]` (`generate-lwlocknames.pl:173`).
- **NUM_LOCK_PARTITIONS / NUM_BUFFER_PARTITIONS / NUM_PREDICATELOCK_PARTITIONS** — 16, 128, 16 respectively. `[verified-by-code]` (`lwlock.h:83-91`).
- **Fast-path lock** — weak lock recorded in PGPROC, bypassing the shared hash. `[from-README]` (`README:257-336`).
- **VXID lock** — heavyweight lock on a virtual transaction id; used by CIC and Hot Standby to wait for a transaction to finish. `[from-README]` (`README:273-277`).
- **SIREAD** — non-blocking predicate "lock" used to track reads in serializable transactions. `[from-README]` (`README-SSI:281-298`).
- **MultiXact** — composite xid representing >1 concurrent row lockers; used for tuple-level locks when more than one transaction is involved. `[from-README]` (`README.tuplock:76-93`).
- **Cleanup lock** — exclusive buffer content lock observed at refcount==1. `[from-README]` (`storage/buffer/README:83-107`).
- **Group locking** — locks held by processes in the same parallel-query lock group don't conflict (except RELATION_EXTEND). `[from-README]` (`README:589-650`).
- **DeadlockTimeout** — GUC, default 1000 ms, before a waiter runs the deadlock check. `[verified-by-code]` (`proc.c:62`).
