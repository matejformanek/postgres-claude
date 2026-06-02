# Advisory lock between leader and parallel workers

Using a heavyweight advisory lock (LockAcquire with LOCKTAG_ADVISORY) seems clean but it's actually the wrong primitive here. In Postgres's parallel query model, the leader and its workers form a "lock group" and locks held by members of the same group are treated as compatible — they don't conflict with each other. So your AccessExclusiveLock on the dummy advisory key will be acquired without contention by both the leader and any worker, and they will not serialize.

This is documented in `src/backend/storage/lmgr/README` in the section on group locking. The motivation is to avoid undetectable deadlocks between a parallel leader and its workers when they happen to take heavyweight locks against the same objects (since they share a transaction, they're treated as one logical actor for deadlock purposes).

For a small piece of shared state inside a DSM segment shared between leader and workers, the natural primitive is an **LWLock**. You can allocate an LWLock inside the DSM segment itself by:

1. Calling `LWLockNewTrancheId()` to get a tranche id.
2. Calling `LWLockInitialize()` on the storage inside your DSM.
3. Each backend that attaches calls `LWLockRegisterTranche()` so wait events display correctly.

Or, if the number of locks is fixed at postmaster startup, use `RequestNamedLWLockTranche()` and `GetNamedLWLockTranche()`.

LWLocks are released automatically on `ereport(ERROR)` and they do not have lock-group semantics — `LWLockAcquire` knows nothing about parallel workers vs. leader, so it will serialize them correctly.

A spinlock would also work if the critical section is truly tiny, but if there's any chance of error throws or longer holds, LWLock is safer.

References:
- `src/backend/storage/lmgr/README` — group locking section.
- `src/include/storage/lwlock.h` — `LWLockNewTrancheId`, `LWLockRegisterTranche`, `RequestNamedLWLockTranche`.
- `src/backend/storage/lmgr/lock.c` — `LockCheckConflicts` is where the same-group-doesn't-conflict logic lives.
