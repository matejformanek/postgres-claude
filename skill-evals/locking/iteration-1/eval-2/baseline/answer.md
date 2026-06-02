# Two BufferMapping partition LWLocks at once

## The rule

When acquiring two BufferMapping partition LWLocks at the same time, take them in a consistent order to avoid deadlock. The standard approach in Postgres is to acquire by partition number (or equivalently, lower-addressed lock first when they're in the contiguous main array).

This is the same convention applied throughout the codebase for partitioned LWLocks. Searching `src/backend/storage/buffer/` shows code paths that need two BufferMapping locks comparing them and acquiring in order.

## How many BufferMapping partitions

`NUM_BUFFER_PARTITIONS` is defined in `src/include/storage/lwlock.h`. The value is 128.

The locks live in `MainLWLockArray` starting at an offset (`BUFFER_MAPPING_LWLOCK_OFFSET`), also in `lwlock.h`. The macro to map a hash code to the lock is `BufMappingPartitionLock(hashcode)` in `src/include/storage/buf_internals.h`.

## What happens if you get the order wrong

LWLocks do not have deadlock detection. If two backends acquire two partition locks in opposite order, the system can wedge. There is no equivalent of `CheckDeadLock` for LWLocks — the deadlock checker in `src/backend/storage/lmgr/deadlock.c` operates only on the heavyweight lock manager.

The wait machinery is in `src/backend/storage/lmgr/lwlock.c`; waiters are queued FIFO and sleep on a semaphore. There's no timeout and no cycle detection.

The query-cancel mechanism also won't help — interrupts are held off while waiting on an LWLock (you can find this discussed in the `src/backend/storage/lmgr/README`). So the standard escape valve of `pg_cancel_backend()` doesn't work; the backend has to be terminated.

## Pattern

```c
if (lock1 < lock2) {
    LWLockAcquire(lock1, LW_EXCLUSIVE);
    LWLockAcquire(lock2, LW_EXCLUSIVE);
} else if (lock1 > lock2) {
    LWLockAcquire(lock2, LW_EXCLUSIVE);
    LWLockAcquire(lock1, LW_EXCLUSIVE);
} else {
    LWLockAcquire(lock1, LW_EXCLUSIVE);
}
```

You can also look at how `src/backend/storage/buffer/bufmgr.c` handles cases where it might end up touching two partitions — InvalidateBuffer and similar routines have ordering considerations.

## References

- `src/include/storage/lwlock.h` — `NUM_BUFFER_PARTITIONS`, offsets.
- `src/include/storage/buf_internals.h` — `BufMappingPartitionLock`, `BufTableHashPartition`.
- `src/backend/storage/buffer/README` — explains the buffer manager including locking conventions.
- `src/backend/storage/lmgr/README` — general lock manager notes.
- `src/backend/storage/lmgr/lwlock.c` — LWLock implementation; no deadlock detection.
