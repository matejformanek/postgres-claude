# Two BufferMapping partition LWLocks — the ordering rule

## The rule

**If you need to hold more than one BufferMapping partition LWLock at the same time, acquire them in partition-number order (lowest partition index first).**

This is rule §2 in the skill's "Ordering rules you must obey" list (`.claude/skills/locking/SKILL.md` §3) and the canonical statement lives in `source/src/backend/storage/buffer/README:140-143` (paraphrased: "If it is necessary to lock more than one partition at a time, they must be locked in partition-number order to avoid risk of deadlock."). The locking-overview cross-references this as rule §2.2 with that same README anchor.

It's the same family of rule as the one for the heavyweight lock manager partitions (`source/src/backend/storage/lmgr/README:239-244`, enforced by `CheckDeadLock` which iterates `i = 0 … NUM_LOCK_PARTITIONS-1` in `source/src/backend/storage/lmgr/proc.c:1871-1872`). All three partitioned LWLock families (BufferMapping, LockManager, PredicateLockManager) share the same convention — see locking-overview §2 rules 1 and 2.

## How many BufferMapping partitions

**128** — `NUM_BUFFER_PARTITIONS = 1 << 7 = 128`, defined in `source/src/include/storage/lwlock.h` (the locking-overview cites lines 83-91 as the canonical anchor for the three partition-count macros together: `NUM_BUFFER_PARTITIONS = 128`, `NUM_LOCK_PARTITIONS = 16`, `NUM_PREDICATELOCK_PARTITIONS = 16`).

The 128 locks occupy a contiguous slice of `MainLWLockArray` starting at `BUFFER_MAPPING_LWLOCK_OFFSET` (`lwlock.h:93-100`); their tranche is `LWTRANCHE_BUFFER_MAPPING` declared in `source/src/include/storage/lwlocklist.h`.

The partition for a given buffer tag is chosen by `BufTableHashPartition()` (hash of the BufferTag mod 128); the helper that returns the LWLock pointer is `BufMappingPartitionLock(hashcode)` in `source/src/include/storage/buf_internals.h`.

## What if you get the order wrong

**You hang. Silently. No detector saves you.**

LWLocks have no deadlock detection (overview §1.3 and the table in §1: "Deadlock detection? — no" for LWLocks). The proclist-based wait machinery in `lwlock.c:38-75` and the README ("Waiting processes will be granted the lock in arrival order. There is no timeout." — `source/src/backend/storage/lmgr/README:28-30`) does not check for cycles. Two backends each holding partition A and waiting for B (where one took them in A→B order and the other in B→A order) wedge until one of them is killed externally.

This is *the* failure mode the skill flags repeatedly. From the skill's smell tests (§5): "My code takes lock A then lock B somewhere, and lock B then lock A somewhere else → potential deadlock. … if either is an LWLock you get a silent hang."

From ordering rules (§3): the partitioned-tranche rule is "the rule that, if violated, causes silent LWLock deadlock."

Worth noting: query-cancel and `die()` are held off while waiting for an LWLock (`README:39-45`, overview §1.3). So a hung backend will not respond to `pg_cancel_backend()`. The only escape is `SIGTERM`/`SIGKILL` of the stuck backend or a restart.

## Canonical pattern for two-partition acquire

```c
LWLock *lock1 = BufMappingPartitionLock(hash1);
LWLock *lock2 = BufMappingPartitionLock(hash2);

if (lock1 == lock2)
{
    LWLockAcquire(lock1, LW_EXCLUSIVE);
}
else
{
    /* Acquire in partition-number order to avoid silent deadlock. */
    if (lock1 < lock2)              /* MainLWLockArray is contiguous,
                                       so pointer order == partition order */
    {
        LWLockAcquire(lock1, LW_EXCLUSIVE);
        LWLockAcquire(lock2, LW_EXCLUSIVE);
    }
    else
    {
        LWLockAcquire(lock2, LW_EXCLUSIVE);
        LWLockAcquire(lock1, LW_EXCLUSIVE);
    }
}
```

Comparing the LWLock pointers works because the buffer-mapping locks all live in `MainLWLockArray` contiguously from `BUFFER_MAPPING_LWLOCK_OFFSET`; if you'd rather be explicit, compare the partition indices you computed via the BufTableHashPartition macro.

## What to write in the code comment

The skill's documentation checklist (§4) says: "if your new code path may acquire more than one lock, list the canonical order in a comment at the top of the function. If you take a partitioned LWLock and another partitioned LWLock, state which one is first." So a one-liner above the function explaining "acquires up to two BufferMapping partition LWLocks; partition-number order to avoid LWLock deadlock (see buffer/README)" is mandatory, not optional.

## Related rules that often come up together

- Pin the buffer before taking its content lock (overview §2 rule 3, `storage/buffer/README:38-41`).
- Release the BufMapping partition lock only after pinning the looked-up buffer, or the buffer can be evicted between the hash hit and the pin (overview §2 rule 4, `storage/buffer/README:123-134`).
- Don't acquire *anything else* while holding `buffer_strategy_lock` — it's a spinlock (overview §2 rule 5, `storage/buffer/README:144-149`).
