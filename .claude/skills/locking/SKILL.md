---
name: locking
description: Operational decision tree for adding code that touches shared state in PostgreSQL — which lock primitive to use, what ordering rules apply, what to document.
---

# Locking — operational checklist

Companion to `knowledge/idioms/locking-overview.md`. Use this when you are about to **write code that touches shared memory** in `src/backend/`. Stop and read the overview first if you have not internalized the six-layer taxonomy (atomics → spinlocks → LWLocks → heavyweight → predicate → row).

## 0. Triage — is shared state actually involved?

Touching any of these means yes:
- A struct in `*Shmem*` allocation, anything reachable from `MainLWLockArray`, anything in `BufferDesc`/`PGPROC`/SLRU/`procArray`.
- Files on disk (pages flushed need to follow WAL-before-data).
- A relation, tuple, transaction id, or advisory key — these need heavyweight locks.

If everything you touch is on the backend's own stack/heap/`MemoryContext`, you don't need a lock at all. Per-backend `MemoryContext`s are *not* shared.

## 1. Decision tree

```
What are you protecting?
│
├─ A user-visible object (table / row / xact / advisory key)?
│  → Heavyweight lock via LockAcquire(LOCKTAG_*, mode, ...).
│    Pick the *weakest* mode in the conflict matrix that still excludes the bad
│    concurrency. See knowledge/idioms/locking-overview.md §1.4.
│
├─ A read in a serializable transaction that needs to be "remembered" so
│  later writes can detect rw-conflict?
│  → PredicateLockTuple/Page/Relation (only meaningful at SERIALIZABLE).
│
├─ A single word (counter, flag, packed state) on the hot path, where the
│  whole update fits in one CAS / fetch-and-add?
│  → pg_atomic_*. Be explicit about barriers if multiple atomics must be
│    seen in order by other backends.
│
├─ A few fields you need to mutate together, briefly (a few dozen
│  instructions, NO subroutine calls, NO kernel calls, NO
│  CHECK_FOR_INTERRUPTS, NO palloc)?
│  → Spinlock (slock_t + SpinLockAcquire/Release).
│
└─ Anything else touching shared memory (hash table, larger struct,
   may need to sleep, may need to read/write disk, may ereport)?
   → LWLock (LWLockAcquire / LW_SHARED or LW_EXCLUSIVE).
```

## 2. Per-primitive checklist

### 2.1 If you reached for a spinlock

- [ ] Critical section is **straight-line code, no calls** beyond trivial accessors. If you find yourself calling a function whose body you have not personally audited, switch to an LWLock.
- [ ] No `ereport`/`elog` with severity ≥ ERROR. Spinlocks are **not** released on error.
- [ ] No `CHECK_FOR_INTERRUPTS`. Cancel/die is held off implicitly while a spinlock is held (`storage/lmgr/README:39-45`).
- [ ] No I/O, no allocations, no calls into other subsystems.
- [ ] Acquisition is `SpinLockAcquire(&lock)`; release is `SpinLockRelease(&lock)`. The macros include a compiler barrier — no extra `pg_*_barrier()` needed for ordering against accesses inside the section.

If any of these is "no", upgrade to an LWLock.

### 2.2 If you reached for an LWLock

- [ ] Decide the lock's home: an individually-named lock (add a `PG_LWLOCK(id, name)` entry in `src/include/storage/lwlocklist.h`, then add the same name to `src/backend/utils/activity/wait_event_names.txt`), a built-in tranche (`PG_LWLOCKTRANCHE`), or an extension-style tranche (`RequestNamedLWLockTranche` / `LWLockNewTrancheId`).
- [ ] Pick mode: `LW_SHARED` for read-only access, `LW_EXCLUSIVE` for any modification.
- [ ] Don't hold across long waits. "It is therefore not a good idea to use LW locks when the wait time might exceed a few seconds." (`README:43-45`) — query-cancel is held off while waiting.
- [ ] Errors are safe: `ereport(ERROR, ...)` while holding an LWLock will auto-release it.
- [ ] Cap your simultaneous holdings under `MAX_SIMUL_LWLOCKS = 200`.
- [ ] If you might need to acquire two LWLocks of the same partitioned tranche (BufferMapping, LockManager, PredicateLockManager): **acquire in partition-number order**. This is the rule that, if violated, causes silent LWLock deadlock.

### 2.3 If you reached for a heavyweight lock

- [ ] Pick a `LockTagType` (`locktag.h`) and use the `SET_LOCKTAG_*` macro — never poke `LOCKTAG` fields directly.
- [ ] Choose the weakest lockmode in the matrix that still excludes the concurrency you need to prevent. The 8 modes are documented in `lockdefs.h:33-48` and `https://www.postgresql.org/docs/current/explicit-locking.html`.
- [ ] If you might wait, you must be in a state where `ereport(ERROR)` can unwind cleanly. Lock will be released at xact end automatically.
- [ ] If you are holding `LOCKTAG_RELATION_EXTEND`, you **must not** acquire any other heavyweight lock. There is an assertion (`IsRelationExtensionLockHeld`).
- [ ] If you are in Hot Standby (replica), regular backends are limited to ≤ `RowExclusiveLock`. AccessExclusiveLock can only come from WAL-replay by the Startup process.
- [ ] If you are inside a parallel worker, remember locks within a lock group **don't conflict** (except `RELATION_EXTEND`) — so you cannot rely on heavyweight locks to serialize between leader and workers.

### 2.4 If you reached for atomics

- [ ] Are you sure a higher-level primitive doesn't fit? The header comment explicitly says use higher-level facilities whenever possible (`port/atomics.h:25-26`).
- [ ] Document the *invariant* the atomic encodes. A bare `pg_atomic_uint64` is opaque; the comment must say what each bit means (see `buf_internals.h:33-86` for the gold-standard example).
- [ ] If you need ordering between multiple atomic locations, add `pg_read_barrier`/`pg_write_barrier`/`pg_memory_barrier` and a comment justifying the choice. Read `src/backend/storage/lmgr/README.barrier` first.
- [ ] Beware: u64 atomics fall back to spinlock-backed emulation on platforms lacking 8-byte atomicity (`atomics.h:107-112`). Don't assume they're free.

## 3. Ordering rules you must obey

These are the rules that, when violated, produce LWLock deadlocks (no detector — the system wedges) or break correctness:

1. **Same-tranche partitioned LWLocks: lock in partition-number order.** Applies to `BufferMapping` (128 partitions), `LockManager` (16), `PredicateLockManager` (16).
2. **Pin a buffer before taking its content lock.**
3. **Release the BufMapping partition lock only after pinning the found buffer** (otherwise the buffer can be evicted before you pin).
4. **Do not acquire anything while holding `buffer_strategy_lock`** (it's a spinlock; see rules in 2.1).
5. **Do not hold a spinlock across a subroutine call, kernel call, palloc, ereport, or CHECK_FOR_INTERRUPTS.**
6. **Relation-extension lock excludes all other heavyweight lock acquisition.** Asserted at runtime.
7. **Deadlock detection holds all heavyweight lock-partition LWLocks at once.** Don't enable the deadlock-check signal from a context where you hold a lock-partition LWLock.
8. **WAL before data**: any disk write of a modified buffer must `XLogFlush(BufferGetLSN(buf))` first, gated on `BM_PERMANENT`.

Citations for each are in `knowledge/idioms/locking-overview.md` §2. If you find yourself stating a *different* ordering rule that's not in the overview, **stop and verify it against the source** — confidently-wrong ordering claims are the documented failure mode of Claude on this codebase (see `pg-claude-plan.md` Appendix A).

## 4. What to document in any patch touching shared state

For every new lock, tranche, or shared-memory struct you add:

- [ ] **Header comment on the struct** stating exactly which lock protects which field. Cross-reference the lock by name.
- [ ] **Acquisition order**: if your new code path may acquire more than one lock, list the canonical order in a comment at the top of the function. If you take a partitioned LWLock and another partitioned LWLock, state which one is first.
- [ ] **Hold time**: comment the upper bound on how long the lock is held (instructions for spinlocks; "until xact end" for heavyweight; etc.).
- [ ] **Interrupt/error safety**: if you're using a spinlock, say so and confirm no error path exists inside.
- [ ] **Wait-event name** for any new tranche: must match the name in `wait_event_names.txt` exactly.
- [ ] **README update** if your subsystem has one (e.g. `src/backend/storage/buffer/README`) — add the new lock to its list of primitives.

## 5. Smell tests before you finish

- "I added a spinlock and the critical section calls a function I didn't write" → either inline the function or use an LWLock.
- "My code takes lock A then lock B somewhere, and lock B then lock A somewhere else" → potential deadlock. If both are heavyweight you'll get an `ERROR: deadlock detected`; if either is an LWLock you get a silent hang. Audit and pick one global order.
- "I'm holding an LWLock and calling something that does I/O" → fine for correctness (LWLocks are error-safe and the wait won't be cancellable, but it works); bad for throughput. Consider releasing first.
- "I'm using `pg_atomic_*` because LWLock seemed expensive" → measure first. Atomics make code much harder to reason about.
- "I added a new individually-named LWLock and `wait_event_names.txt` is unchanged" → build will fail or wait-events will show wrong names. Update both.
- "I'm taking a heavyweight lock from a critical section / signal handler / spinlock" → forbidden; heavyweight lock acquisition can sleep and ereport.

## 6. Cross-references

- `knowledge/idioms/locking-overview.md` — the conceptual map and citations.
- `knowledge/subsystems/storage-buffer.md` — the calibration deep-dive (six lock primitives in one subsystem).
- `source/src/backend/storage/lmgr/README` — heavyweight lock manager (the ~730-line canonical text).
- `source/src/backend/storage/lmgr/README-SSI` — predicate locks and SSI.
- `source/src/backend/storage/lmgr/README.barrier` — memory barriers, prerequisite reading for atomics.
- `source/src/backend/access/heap/README.tuplock` — row-level lock protocol.
- `source/src/include/storage/lwlocklist.h` — canonical list of named LWLocks and tranches.
- `source/src/include/storage/lockdefs.h` — the 8 heavyweight lock modes.
- `https://www.postgresql.org/docs/current/explicit-locking.html` — user-facing conflict matrix.
- `https://wiki.postgresql.org/wiki/Lock_dependency_information` — debugging tips for diagnosing lock waits.
