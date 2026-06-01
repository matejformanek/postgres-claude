# `storage/ipc/latch.c`

- **Source:** `source/src/backend/storage/ipc/latch.c` (389 lines)
- **Header:** `source/src/include/storage/latch.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The **latch** is PG's reliable wakeup primitive — replaces the older
"sleep until a signal arrives" pattern. The actual epoll/kqueue/poll
loop lives in `waiteventset.c`; this file just provides the latch
struct and the convenience wrappers `WaitLatch` / `SetLatch` /
`ResetLatch` over a singleton `WaitEventSet`. `[from-comment] :3-9`.

## Latch struct (header `latch.h`)

```
{ sig_atomic_t  is_set;          /* the signal flag */
  sig_atomic_t  maybe_sleeping;  /* set while we're inside WaitEventSetWait */
  bool          is_shared;
  pid_t         owner_pid;       /* 0 if shared latch, unattached */
  HANDLE        event;           /* Windows only */
}
```

Two kinds:
- **Process-local latch** — `InitLatch`; `owner_pid = MyProcPid` from
  the start; `is_shared = false`. Every backend has `MyLatch`.
- **Shared latch** — `InitSharedLatch` (must be called by postmaster
  *before* fork — see comment `:81-90`); other processes claim it
  via `OwnLatch` / release via `DisownLatch`. Each PGPROC has a shared
  latch used for cross-backend wakeups.

## The singleton `LatchWaitSet`

Lazy-built by `InitializeLatchWaitSet` (called once per process at
startup). Two slots: `LatchWaitSetLatchPos = 0` for `WL_LATCH_SET`,
`LatchWaitSetPostmasterDeathPos = 1` for postmaster death.
`WaitLatch` then just rewires those two slots via `ModifyWaitEvent`
on each call. `:27-57`.

Note: this means `WaitLatch` is **cheap-ish for non-socket waits but
not the most efficient** — callers that wait frequently should keep a
private `WaitEventSet`. `[from-comment]` `:218-221`.

## SetLatch — the memory-barrier dance (`:289`)

This is *the* primitive other processes call to wake us. Subtle:

```c
pg_memory_barrier();            /* publish any flag we set before this */
if (latch->is_set) return;      /* already set, no-op */
latch->is_set = true;
pg_memory_barrier();            /* publish is_set before reading maybe_sleeping */
if (!latch->maybe_sleeping) return;
/* … now actually signal the owner */
```

The pattern `is_set = true; barrier; if (maybe_sleeping) signal`
pairs with `ResetLatch`'s `is_set = false; barrier; check flags`,
plus `WaitEventSetWaitBlock`'s `maybe_sleeping = true; barrier; check
is_set`. **If we set `is_set` after they cleared it, they will see it
before they call epoll_wait.** `[from-comment] :298-303, :383-388`.

Wake mechanism:
- Self-wake (signal handler delivered to MyProc): `WakeupMyProc()` —
  writes to the self-pipe (Linux) or sends SIGURG to self (BSD).
- Other process wake: `WakeupOtherProc(owner_pid)` — `kill(pid, SIGURG)`
  or self-pipe write on Windows path.

The `owner_pid` is read **once** into a local; the comment at `:323-330`
acknowledges this assumes pid_t is atomic (effectively 32-bit) and
that in the worst case we signal the wrong process, which PG backends
tolerate (excess SIGUSR1 / SIGURG).

## WaitLatch (`:172`) and WaitLatchOrSocket (`:222`)

Both go through `WaitEventSetWait`. The `wakeEvents` bitmask:
- `WL_LATCH_SET` — wake when latch is set.
- `WL_TIMEOUT` — wake after timeout ms.
- `WL_POSTMASTER_DEATH` — wake when postmaster dies, return the bit.
- `WL_EXIT_ON_PM_DEATH` — wake AND immediately exit(1). Postmaster-
  managed callers (any process with `IsUnderPostmaster`) **must**
  request one of these two. `[verified-by-code]` `:177-180`.
- `WL_SOCKET_*` — only on `WaitLatchOrSocket`.

`WaitLatchOrSocket` builds a fresh `WaitEventSet` each call, attaches
it to the `CurrentResourceOwner`, and frees it before returning.
That's why the comment recommends a long-lived WaitEventSet for
frequent socket waits.

## ResetLatch (`:374`)

```
Assert(latch->owner_pid == MyProcPid);
Assert(latch->maybe_sleeping == false);
latch->is_set = false;
pg_memory_barrier();
```

The barrier ensures that any flag the caller examines *after*
`ResetLatch` cannot have been set by a `SetLatch` that we'll miss.
Mirror image of `SetLatch`'s barrier.

**Convention**: callers should *check the work flags after
`WaitLatch` returns, then `ResetLatch` only after they've drained the
work*. The standard pattern is:

```c
for (;;) {
    ResetLatch(MyLatch);
    if (work_pending) do_work();
    WaitLatch(MyLatch, WL_LATCH_SET|WL_EXIT_ON_PM_DEATH, ...);
}
```

Reset-before-check is wrong because work set between check and reset
would be lost. (Comment in `latch.h:80-105` describes the canonical
pattern.)

## OwnLatch / DisownLatch

`OwnLatch` panics if already owned (race-detected but not race-prevented;
caller must use an interlock). `DisownLatch` requires
`owner_pid == MyProcPid`.

Used for PGPROC latches: when a backend starts, it `OwnLatch(&MyProc->procLatch)`.
On exit, `DisownLatch`. Other backends `SetLatch(&otherProc->procLatch)`
to wake them.

## Cross-references

- `waiteventset.c` — `CreateWaitEventSet`, `WaitEventSetWait`,
  `ModifyWaitEvent`. The wakeup-from-other-process plumbing
  (`WakeupMyProc`, `WakeupOtherProc`) lives there too.
- `storage/proc.c` — each PGPROC has a `procLatch`; `InitProcess`
  calls `OwnLatch`.
- `tcop/postgres.c` — main loop pattern.

## Open questions

1. Whether `MyLatch` is actually `&MyProc->procLatch` for all backend
   types, or differs for aux processes — almost certainly the former,
   but I didn't pin it in this file. `[unverified-here]`.
2. The pid_t atomicity concern at `:323-330` is documented as
   "effective range fits in 32 bits, so atomic on real platforms" —
   on 64-bit Linux pid_t is `int` (32-bit), so this is fine.
   `[verified-by-headers]` (Linux), `[unverified]` (Windows).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
