# Patch review — spinlock in proc.c with the listed properties

This patch breaks essentially every rule that governs spinlock use in Postgres. The skill checklist (`.claude/skills/locking/SKILL.md` §2.1 "If you reached for a spinlock") and the locking-overview §1.2 enumerate the rules; here is each violation, what's broken about it, and the citation.

## Violation 1 — calls `ProcSleep()` which can `ereport(ERROR)`

**Rule.** Spinlocks are NOT released on `ereport(ERROR)`. There is no auto-release path equivalent to LWLocks. Acquisition is paired with `SpinLockRelease`; if control unwinds via longjmp through the section, the lock stays held — and `NUM_DELAYS = 1000` tries (~2 minutes) later any other waiter will PANIC the postmaster.

**Citations.** Locking-overview §1.2: "There is no deadlock detection and no automatic release on error; a stuck spinlock after `NUM_DELAYS = 1000` tries (~2 minutes) is treated as an error condition and aborts." (`source/src/backend/storage/lmgr/s_lock.c:30-45, 57-61`). Skill §2.1 checklist item: "No `ereport`/`elog` with severity ≥ ERROR. Spinlocks are not released on error."

**Consequence.** The first time `ProcSleep` actually errors with the lock held, this backend leaks the spinlock. Every subsequent backend that tries to acquire it spins for ~2 minutes and then PANICs. PANIC tears down all backends — the cluster restarts and forces crash recovery.

## Violation 2 — `CHECK_FOR_INTERRUPTS` inside the section

**Rule.** A `CHECK_FOR_INTERRUPTS` may call `ProcessInterrupts` which can `ereport(FATAL)` or `ereport(ERROR)`. That re-introduces violation 1. The codebase's working assumption is the inverse: query-cancel/die() are *held off* while a spinlock is held, so the call point shouldn't be needed inside.

**Citations.** `source/src/include/storage/spin.h:26-29` (verbatim): "We assume it is not possible for a `CHECK_FOR_INTERRUPTS()` to occur while holding a spinlock, and so it is not necessary to do HOLD/RESUME_INTERRUPTS()." Reinforced in `source/src/backend/storage/lmgr/README:39-45` and overview §1.2: "Query-cancel and die() are held off implicitly while a spinlock is held."

**Consequence.** Two ways to fail: (a) the `CHECK_FOR_INTERRUPTS` body promotes a signal to an error, leaks the lock (violation 1); (b) even when it doesn't error, you've broken the codebase-wide invariant that the assumption above relies on. Other code is free to assume no signals fire inside spinlock sections; weird future bugs follow.

## Violation 3 — held across a subroutine call (`ProcSleep`)

**Rule.** From `source/src/backend/storage/lmgr/README:8-11`: "If a lock is to be held more than a few dozen instructions, or across any sort of kernel call (or even a call to a nontrivial subroutine), don't use a spinlock." `ProcSleep` is not a "trivial subroutine" — it manipulates wait queues, sleeps on semaphores, and can take other locks (it's the heavyweight-lock wait primitive).

**Citation.** Skill §2.1 first bullet: "Critical section is **straight-line code, no calls** beyond trivial accessors. If you find yourself calling a function whose body you have not personally audited, switch to an LWLock." Overview §1.2 quotes the README directly.

**Consequence.** Even setting aside the error path, holding a spinlock while `ProcSleep` blocks on a semaphore means every other backend that touches this spinlock starves until the original backend wakes. Spinning backends burn CPU; after `NUM_DELAYS = 1000` they PANIC. Throughput collapses to zero.

## Violation 4 — held for ~50 lines while iterating ProcArray

**Rule.** "If a lock is to be held more than a few dozen instructions … don't use a spinlock" (`README:8-11`). 50 lines of C iterating a shared array is far over budget. The semantic load (touching ProcArray) is exactly the kind of work LWLocks are designed for.

**Additionally**: iterating ProcArray normally happens under `ProcArrayLock` (an LWLock). If this patch is doing it under a *new* spinlock without consulting `ProcArrayLock`, that's a second bug — it's racing against backend enter/exit which is serialized by ProcArrayLock, not by whatever new spinlock the patch added.

**Citation.** Skill §2.1 ("no I/O, no allocations, no calls into other subsystems"); overview §1.2 (`spin.h:21-29`, `README:8-11`).

**Consequence.** Long hold times mean every waiter spins on TAS. Even without the error/CFI bugs, this murders concurrency. And the unsynchronized ProcArray scan is undefined behavior: a backend exiting can free its PGPROC slot mid-scan, leading to crashes or wrong results.

## What primitive to use instead

**An LWLock.** Specifically:

- LWLocks are error-safe: `ereport(ERROR)` while holding one auto-releases it. (`README:23-26`, overview §1.3 — "LWLocks are auto-released during `elog` cleanup".)
- They tolerate sleeping; on contention they enqueue on a proclist and sleep on a semaphore (`lwlock.c:38-75`).
- They are the standard primitive for "larger shared-memory data structure, may need to sleep, may need to read/write disk, may ereport" — see overview §4 table.
- They cap at `MAX_SIMUL_LWLOCKS = 200` simultaneous holdings per backend (`lwlock.c:157-167`) which is fine for one lock.

Specifically for ProcArray iteration: the existing primitive is `ProcArrayLock` (LWLock), used `LW_SHARED` for readers and `LW_EXCLUSIVE` for backend enter/exit. The patch should be acquiring `ProcArrayLock LW_SHARED` for the scan, not a new spinlock — unless it's protecting a brand-new piece of state, in which case a brand-new tranche or individually-named LWLock is the answer (declared in `source/src/include/storage/lwlocklist.h`, with a matching entry in `source/src/backend/utils/activity/wait_event_names.txt`; skill §2.2).

If the field being mutated really is a single word (a counter, a flag, a packed state), the right answer might instead be `pg_atomic_*` from `source/src/include/port/atomics.h`. That's the only case where dropping the spinlock entirely is correct.

## Summary

| Symptom | Rule | Cite |
|---|---|---|
| `ereport(ERROR)` while holding spinlock | Spinlocks aren't auto-released | `s_lock.c:30-45, 57-61`; overview §1.2 |
| `CHECK_FOR_INTERRUPTS` while holding | Codebase assumes none fire here | `spin.h:26-29`; `README:39-45` |
| Calls `ProcSleep` while holding | No subroutine calls in spinlock sections | `README:8-11`; skill §2.1 |
| 50 lines / iterates ProcArray | Hold ≤ "few dozen instructions" | `README:8-11` |

Fix: replace the spinlock with the appropriate LWLock (existing `ProcArrayLock` if iterating ProcArray; a new tranche otherwise).
