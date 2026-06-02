# Patch review — spinlock with ereport-able call, CFI, long hold

This patch has several problems. Spinlocks in Postgres are a very restricted primitive; the rules are in `src/backend/storage/lmgr/README` and `src/include/storage/spin.h`.

## Problem 1: `ProcSleep()` can `ereport(ERROR)`

Spinlocks are not automatically released if control jumps out of the section via an error. They are paired strictly with `SpinLockAcquire` / `SpinLockRelease`. The README (`src/backend/storage/lmgr/README`) lays out the rules for spinlocks in the first part of the file: don't error out while holding one. If `ProcSleep` calls `ereport(ERROR)` and unwinds through this section, the lock stays held. Other backends will spin until `s_lock.c` decides the lock is stuck and PANICs (which kills the cluster).

## Problem 2: `CHECK_FOR_INTERRUPTS` inside the section

`spin.h` documents that the codebase assumes you do NOT call `CHECK_FOR_INTERRUPTS` while holding a spinlock — interrupts are held off implicitly. Calling it explicitly is wrong for two reasons:

1. It can trigger an error path (FATAL on SIGTERM, ERROR on cancel), which leaks the spinlock as in problem 1.
2. It violates the documented assumption, which other code may rely on.

## Problem 3: Calling a non-trivial subroutine

`src/backend/storage/lmgr/README` is explicit early on: spinlocks are for cases where you hold the lock for a few dozen instructions and don't call kernel routines or non-trivial subroutines. `ProcSleep` is anything but trivial — it queues the backend on a wait list and sleeps on a semaphore.

Holding a spinlock while sleeping is a category error. Spinlocks are "busy-wait" primitives; everyone else spins burning CPU until you release.

## Problem 4: ~50 lines, iterating ProcArray

Again, the README says hold time is meant to be very short. 50 lines is much too long.

Worse: `ProcArray` is normally protected by `ProcArrayLock` (an LWLock). Iterating it under some other lock is racy with backends entering and exiting.

## What to use instead

An **LWLock** is the right primitive:

- LWLocks are released on error (the cleanup path in `lwlock.c` handles that).
- They can be held across blocking operations.
- They support shared and exclusive modes.
- The ProcArray already has `ProcArrayLock`; if you're iterating ProcArray, take that lock in shared mode, don't invent a new one.

If you really need protection for a new piece of state, add a named LWLock to `src/include/storage/lwlocklist.h` and a matching wait-event entry.

## References

- `src/backend/storage/lmgr/README` — top of file, rules for spinlocks.
- `src/include/storage/spin.h` — comments about interrupts.
- `src/include/storage/s_lock.h` and `src/backend/storage/lmgr/s_lock.c` — implementation; the stuck-spinlock PANIC.
- `src/backend/storage/lmgr/lwlock.c` — LWLock implementation and error-safe release.
- `src/backend/storage/ipc/procarray.c` and `src/include/storage/proc.h` — ProcArrayLock usage.
