# Review: SearchSysCache1 under ProcArrayLock LW_SHARED

This is not OK. The "LWLocks are error-safe so this is fine" justification glosses over the real problems.

## (a) Error safety

It's true that LWLocks are released on `ereport(ERROR)` — the lwlock cleanup runs as part of transaction abort. But that's only one of several concerns; safety on error doesn't make calling expensive code under the lock OK.

## (b) Lock ordering

The bigger issue is what `SearchSysCache1` actually does. On a syscache miss it:

- Opens `pg_authid` (which acquires `AccessShareLock` — a heavyweight lock).
- Scans the catalog, which involves buffer pins and `BufferDesc.content_lock` acquisitions, and a `BufMapping` partition LWLock.
- May process invalidation messages and take SInval locks.
- May allocate memory.

So the patch is effectively claiming the lock order:

```
ProcArrayLock → heavyweight pg_authid → BufMapping partition → BufferDesc.content_lock → SInval*
```

ProcArrayLock is acquired on practically every snapshot, commit, and backend startup. The codebase convention is that it's held briefly and **early** in any sequence. Holding it across catalog access inverts that — and since LWLocks have no deadlock detection, any other path that takes ProcArrayLock from inside catalog access will silently deadlock with this one.

## (c) CHECK_FOR_INTERRUPTS / query cancel

Query cancel is held off while waiting on an LWLock. If `SearchSysCache1` triggers a buffer-I/O wait or has to wait on the heavyweight pg_authid lock (e.g. someone is running `REVOKE` or `DROP ROLE`), the backend can't be cancelled while holding ProcArrayLock. That's a system-wide stall: ProcArrayLock blocks every other backend trying to take a snapshot or commit.

## (d) MAX_SIMUL_LWLOCKS

There's a limit on how many LWLocks a single backend can hold at once (MAX_SIMUL_LWLOCKS, somewhere around 200 in `lwlock.c`). Transiently acquiring a few more inside the syscache lookup won't approach that limit by itself. But it's a code smell — you're holding more locks at once than the design assumed.

## (e) LW_EXCLUSIVE instead of LW_SHARED

That makes it worse, not better. ProcArrayLock in exclusive mode blocks every snapshot acquisition and every transaction commit. Holding it across syscache I/O would stall the cluster. The deadlock concerns are the same; the contention concerns are amplified.

## Recommendation

Restructure so the syscache lookup is *outside* the ProcArrayLock section. Read the fields you need from PGPROC under the lock, release, then do the syscache work. If the result has to feed back into shared state, take ProcArrayLock again briefly to publish.

## References

- `src/backend/storage/lmgr/README` — LWLock rules; cancel held off during wait; auto-release on error.
- `src/backend/storage/lmgr/lwlock.c` — MAX_SIMUL_LWLOCKS, cleanup.
- `src/backend/storage/ipc/procarray.c` — ProcArrayLock usage; brief hold times.
- `src/backend/utils/cache/syscache.c` and `catcache.c` — what `SearchSysCache1` actually does.
