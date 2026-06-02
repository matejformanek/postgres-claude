# Advisory heavyweight lock between leader and parallel workers — wrong primitive

## The trap

Your instinct is wrong, and the failure mode is silent. Heavyweight locks held by members of the **same lock group do not conflict**. The advisory lock you take in the leader will be visible — but trivially compatible — to the worker, and vice versa. They will not serialize.

The skill (`.claude/skills/locking/SKILL.md` §2.3) flags this exactly: *"If you are inside a parallel worker, remember locks within a lock group don't conflict (except `RELATION_EXTEND`) — so you cannot rely on heavyweight locks to serialize between leader and workers."*

## Where this is documented and enforced

- **Conceptual statement**: `source/src/backend/storage/lmgr/README:629-634` — "we take the approach of deciding that locks within a lock group do not conflict. This eliminates the possibility of an undetected deadlock, but also opens up some problem cases: if the leader and worker try to do some operation at the same time which would ordinarily be prevented by the heavyweight lock mechanism, undefined behavior might result."
- **Enforcement (the "subtract out" step)**: `source/src/backend/storage/lmgr/lock.c:1610-1618` in `LockCheckConflicts` — "Locks held in conflicting modes by members of our own lock group are not real conflicts; we can subtract those out…". So the conflict matrix is *literally* bypassed for same-group holders.
- **The one exception**: `source/src/backend/storage/lmgr/lock.c:1600-1608` — `LOCKTAG_RELATION_EXTEND` *does* conflict even within a group. That's the only heavyweight tag that still serializes parallel workers against the leader.
- **Lock-group machinery on PGPROC**: `source/src/backend/storage/lmgr/README:651-667` — `lockGroupLeader`/`lockGroupMembers`/`lockGroupLink`; the leader's lock-group is identified by `leader_pgprocno % NUM_LOCK_PARTITIONS`.

## What you should use instead

You're working in a DSM segment shared between leader and workers; the natural primitive is an **LWLock from a custom tranche allocated alongside the DSM state**.

Two routes:

1. **`RequestNamedLWLockTranche()` at postmaster startup**, then `GetNamedLWLockTranche()` to retrieve the array. Suitable if the number of locks is known at startup.
2. **`LWLockNewTrancheId()` + `LWLockInitialize()` on a slot inside your DSM segment**, then `LWLockRegisterTranche()` in each backend that attaches. This is the right pattern for DSM-resident state since the lock storage *is* the DSM. See `source/src/include/storage/lwlock.h` for the API; the parallel infrastructure itself uses this pattern (e.g. `ParallelContext` workspace).

Why LWLock and not spinlock or atomic:

- The skill decision tree (§1) routes "anything else touching shared memory… may need to sleep" to LWLock. A leader/worker serialization point is almost certainly not a single-word CAS.
- LWLocks are auto-released on `ereport(ERROR)` (`source/src/backend/storage/lmgr/lwlock.c` cleanup; skill §2.2), which matters because aggregate state can throw.
- They have no group-bypass semantics — `LWLockAcquire` doesn't know about lock groups at all; it serializes by raw PGPROC waiter queue.

## Things to document on the patch

Per skill §4: the DSM-resident lock's tranche name must match an entry registered via `LWLockRegisterTranche` (so `pg_stat_activity.wait_event` shows the right name), and the struct header must say "protected by `foo_lock` — held only across the short critical section that updates `…`". Note in a comment that the choice of LWLock is *deliberate* because heavyweight locks would silently no-op between leader and workers; otherwise a future reader will "fix" your LWLock to be a "cleaner" advisory lock and break it.

## Ordering rules

If you only take this one LWLock, no ordering issue. If your worker code also takes other LWLocks (BufMapping partitions, ProcArrayLock, etc.), document the global order in a comment per skill §4. Note that the partition-number-order rule (skill §3 rule 1) only applies *within* a single partitioned tranche — your custom tranche has its own independent order.

## Summary

- Heavyweight advisory lock between leader/worker = silent no-op, except `RELATION_EXTEND`. `lock.c:1610-1618`.
- Use an LWLock in a custom tranche (named or DSM-resident) instead.
- Document that the choice is deliberate to defend against a future "cleanup" patch.
