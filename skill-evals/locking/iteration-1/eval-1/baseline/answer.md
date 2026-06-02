# Counter for autovacuum-skip events — which primitive?

For a single shared-memory counter that is incremented frequently on the hot path and read occasionally by a stats reader, the right primitive is an **atomic** — `pg_atomic_uint64` with `pg_atomic_fetch_add_u64` to increment.

## Why an atomic

Atomics are the cheapest of the available primitives. The Postgres porting layer defines the API in `src/include/port/atomics.h`; functions like `pg_atomic_read_u64`, `pg_atomic_fetch_add_u64`, and the compare-exchange family are available everywhere. A bare counter increment fits in a single fetch-and-add and so doesn't need a heavier lock around it.

Alternatives:

- A **spinlock** (`SpinLockAcquire`/`SpinLockRelease` from `src/include/storage/spin.h`) would work, but you'd be acquiring a lock to do a single increment. The `src/backend/storage/lmgr/README` says spinlocks are appropriate when you need to hold the lock for "a few dozen instructions"; a single counter update is below that threshold.
- An **LWLock** is even heavier — you'd be paying the cost of `LWLockAcquire`/`LWLockRelease` and potentially serializing all incrementers, when the hardware can do the increment atomically.
- A **heavyweight lock** (`LockAcquire`) is wrong: those are for user-visible objects like relations and tuples, with deadlock detection. A skip counter isn't a user-visible object.

## Implementation sketch

Add the field to your shared-memory struct:

```c
typedef struct AutoVacShared
{
    ...
    pg_atomic_uint64 skip_count;
    ...
} AutoVacShared;
```

Initialize at shmem setup with `pg_atomic_init_u64(&shared->skip_count, 0);`.

Increment on the hot path:

```c
pg_atomic_fetch_add_u64(&shared->skip_count, 1);
```

Read for stats:

```c
uint64 skipped = pg_atomic_read_u64(&shared->skip_count);
```

## What to document on the struct

- A comment by the field saying what it counts (e.g. "number of times this autovacuum cycle was skipped due to lock conflict").
- That it's incremented by any backend without a lock (atomic ops only).
- The stats reader can read a slightly stale value; this is intentional and acceptable for a counter.

## Ordering rules

For a single atomic counter, there is nothing to order — there's only one location. If you ever pair this counter with another shared field that must be read consistently together with the counter, then either:

- Wrap both in an LWLock (simpler), or
- Use `pg_read_barrier()` / `pg_write_barrier()` from `src/include/port/atomics.h` to publish writes in the right order.

The general locking-order rules in Postgres apply to LWLock partitions (BufferMapping, LockManager, PredicateLockManager) where you must acquire in partition-number order; they don't apply to a lone atomic.

## Headers and references

- `src/include/port/atomics.h` — `pg_atomic_uint64`, `pg_atomic_fetch_add_u64`, `pg_atomic_read_u64`, barriers.
- `src/backend/storage/lmgr/README` — taxonomy of primitives in the first ~50 lines.
- `src/include/storage/spin.h` and `src/include/storage/lwlock.h` for the alternatives if you decide the atomic isn't enough later.
