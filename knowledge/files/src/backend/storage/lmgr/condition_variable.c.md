# `storage/lmgr/condition_variable.c`

- **Source:** `source/src/backend/storage/lmgr/condition_variable.c` (362 lines)
- **Header:** `source/src/include/storage/condition_variable.h`
- **Last verified commit:** `ef6a95c` (2026-06-01)

## 1. Purpose

> "Implementation of condition variables. Condition variables provide a way for one process to wait until a specific condition occurs, without needing to know the specific identity of the process for which they are waiting. Waits for condition variables can be interrupted, unlike LWLock waits. Condition variables are safe to use within dynamic shared memory segments." `[from-comment]` (`condition_variable.c:1-16`).

The primitive lets one backend sleep on a `ConditionVariable` until another backend `Signal`s or `Broadcast`s it. Internally it's a `slock_t mutex` + a `proclist` of waiting PGPROCs, with each waiter signalled via `SetLatch(MyLatch)` (not the semaphore used by LWLock/heavyweight waits).

Used in DSM-mapped data structures (parallel query, parallel vacuum, replication slot sync), background-worker startup synchronisation, and any "wait until some shared state changes" path that needs to also handle query cancel.

## 2. Public surface

- `ConditionVariableInit(cv)` (`condition_variable.c:37`).
- `ConditionVariablePrepareToSleep(cv)` (`condition_variable.c:58`) — optional pre-loop enqueue; required if you'd otherwise miss the signal between testing the condition and sleeping.
- `ConditionVariableSleep(cv, wait_event_info)` (`condition_variable.c:98`) — sleeps once.
- `ConditionVariableTimedSleep(cv, timeout, wait_event_info) → bool` (`condition_variable.c:114`) — returns true on timeout.
- `ConditionVariableCancelSleep(void)` (`condition_variable.c:232`) — call after the wait loop exits; dequeues if still queued.
- `ConditionVariableSignal(cv)` (`condition_variable.c:261`) — wake one waiter.
- `ConditionVariableBroadcast(cv)` (`condition_variable.c:284`) — wake all waiters.

## 3. Key types

- `ConditionVariable` (in `condition_variable.h`): `{slock_t mutex; proclist_head wakeup}`. Embeddable in shmem.
- `cv_sleep_target` (file-static, `condition_variable.c:31`) — pointer to the *one* CV this backend has called `PrepareToSleep` on. The single-static-pointer constraint is the reason `PrepareToSleep` first cancels any prior prepared sleep (`condition_variable.c:62-71`).

## 4. Key invariants and locking

### Single prepared sleep per backend

A backend can have at most one prepared sleep at a time (single `cv_sleep_target` static, single `cvWaitLink` in PGPROC). `PrepareToSleep` cancels any prior prepare. `[from-comment]` (`condition_variable.c:62-71`) `[verified-by-code]`.

### Spinlock-protected wait list

`cv->mutex` is a spinlock (`slock_t`). Held only for the duration of `proclist_push_tail` / `proclist_delete` / `proclist_pop_head` operations — fits the "spinlocks held only across very short critical sections" rule from `README:8-11` `[verified-by-code]`.

### Latch as wake-up channel

Waiters block in `WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH | …)`. Signal wakes the target via `SetLatch(waiter->procLatch)`. This is what gives CV waits **interruptibility** — `WaitLatch` honours `WL_TIMEOUT` and integrates with `CHECK_FOR_INTERRUPTS()` — vs. LWLock waits which are not interruptible.

### Cancel-sleep contract

`ConditionVariableCancelSleep` **must** be called after the wait loop, even if the loop terminated naturally (condition became true) — otherwise the backend remains queued on `cv->wakeup` and may steal a signal meant for someone else. `[from-comment, indirect]` in `condition_variable.h` documentation.

### Signal semantics

- `Signal(cv)` removes and wakes exactly one waiter (FIFO).
- `Broadcast(cv)` drains the entire queue and wakes all in one go.
- A signal lost between two CVs because we never queued on the second one is the standard CV pitfall — the comment at lines 44-55 advises using `PrepareToSleep` before the condition test if a sleep is expected at least once.

## 5. Functions of note

### 5.1 `ConditionVariablePrepareToSleep` (`condition_variable.c:58-81`)

If `cv_sleep_target != NULL`, cancels that prior sleep first. Records the target, takes the CV's spinlock, pushes `MyProc` onto `cv->wakeup` via `cvWaitLink`, releases. Now any subsequent `Signal`/`Broadcast` will see and wake us.

### 5.2 `ConditionVariableSleep` (`condition_variable.c:98-113`)

Calls `ConditionVariableTimedSleep(cv, -1, wait_event_info)`. If `cv_sleep_target != cv` (i.e. we hadn't prepared, or prepared for a different CV), calls `PrepareToSleep` first.

### 5.3 `ConditionVariableTimedSleep` (`condition_variable.c:114-231`)

The actual `WaitLatch` loop. On wake:
- If latch was set, `ResetLatch` and return false (not a timeout).
- If timeout elapsed, return true.
- Otherwise loop (could be a spurious wake or interrupt).

Maintains its own deadline accounting for the `timeout >= 0` case (since `WaitLatch`'s `timeout_ms` argument needs to be decremented across wakes).

### 5.4 `ConditionVariableCancelSleep` (`condition_variable.c:232-260`)

Idempotent. If `cv_sleep_target == NULL`, no-op. Otherwise takes the CV mutex, removes us from `cv->wakeup` if still queued, sets `cv_sleep_target = NULL`.

A subtle detail: if `Signal` already removed us from the queue (in which case our latch was set), we still need this call to clear `cv_sleep_target`.

### 5.5 `ConditionVariableSignal` (`condition_variable.c:261-283`)

Take mutex, `proclist_pop_head` (if any), release mutex, then `SetLatch(waiter->procLatch)`. Setting the latch outside the spinlock keeps the lock-hold time minimal.

### 5.6 `ConditionVariableBroadcast` (`condition_variable.c:284-362`)

Pop all entries into a local list under the mutex; set each latch outside.

## 6. Cross-references

- `latch.c` / `WaitLatch` — the actual sleep primitive.
- `parallel.c`, `parallel.h` (parallel query) — barrier synchronisation built on top of CVs.
- `replication/slotsync.c` — waits for slot-sync background worker.
- `dsm.c` — CVs are explicitly safe to embed in DSM.
- `proc.h` — `PGPROC.cvWaitLink` proclist node.

## 7. Open questions

1. **Whether spurious wakes are handled by every caller.** `Sleep` may return without the condition being true (timeout, interrupt). Callers must always re-check the condition in a loop. The header file documents this pattern but `Sleep` itself does not enforce it. `[from-comment]`.
2. **Interaction with parallel-worker shutdown.** If a CV in DSM is destroyed while a worker is sleeping on it, undefined behaviour. The typical pattern is to broadcast before tearing down. `[unverified]`.
3. **Memory-ordering on `proclist_*` operations.** Implicit in the spinlock barrier. `[from-comment, indirect]`.

## 8. Tag tally

- `[verified-by-code]`: 7
- `[from-comment]`: 5
- `[unverified]`: 2

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/condition_variable.c | full-read | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/condition_variable.c.md |
| source/src/include/storage/condition_variable.h | not opened in detail | 2026-06-01 | ef6a95c | (this doc) |

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
