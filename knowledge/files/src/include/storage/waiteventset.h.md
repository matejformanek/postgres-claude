# `storage/waiteventset.h`

- **Source:** `source/src/include/storage/waiteventset.h` (98 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for `waiteventset.c`. Multi-event ppoll-like primitive.

## Event mask (`WL_*`)

```
WL_LATCH_SET         = 1<<0
WL_SOCKET_READABLE   = 1<<1
WL_SOCKET_WRITEABLE  = 1<<2
WL_TIMEOUT           = 1<<3   /* not for WaitEventSetWait directly */
WL_POSTMASTER_DEATH  = 1<<4
WL_EXIT_ON_PM_DEATH  = 1<<5
WL_SOCKET_CONNECTED  = 1<<6 (Win32 only; alias for WRITEABLE elsewhere)
WL_SOCKET_CLOSED     = 1<<7
WL_SOCKET_ACCEPT     = 1<<8 (Win32 only; alias for READABLE elsewhere)
```

`WL_SOCKET_MASK` is the OR of all the socket bits.

## API

- `InitializeWaitEventSupport()` — process-wide init.
- `CreateWaitEventSet(resowner, nevents)` — bound to a resource owner.
- `AddWaitEventToSet(set, events, fd, latch, user_data)` — returns
  the slot position. `latch` and `fd` are mutually optional depending
  on the event mask.
- `ModifyWaitEvent(set, pos, events, latch)` — change a slot without
  rebuilding the set.
- `WaitEventSetWait(set, timeout_ms, occurred[], nevents,
  wait_event_info)` — block. `wait_event_info` is the `pgstat`
  wait-event ID surfaced in `pg_stat_activity`.
- `FreeWaitEventSet(set)` / `FreeWaitEventSetAfterFork(set)` — the
  fork variant drops OS resources without releasing the resowner ref
  (used after fork in the child).
- `GetNumRegisteredWaitEvents(set)` / `WaitEventSetCanReportClosed()`
  — capability queries.

## Wakeup helpers (non-Win32)

```
extern void WakeupMyProc(void);
extern void WakeupOtherProc(int pid);
```

These are how `SetLatch` actually wakes a sleeping process — self-pipe
write on POSIX, SIGURG kill on epoll/kqueue platforms. **They live
here, not in `latch.h`**, because they're tied to the underlying
event-set implementation.

## `WaitEvent` struct

```c
typedef struct WaitEvent {
    int       pos;
    uint32    events;     /* triggered bits */
    pgsocket  fd;
    void     *user_data;  /* whatever you passed to AddWaitEventToSet */
#ifdef WIN32
    bool      reset;
#endif
} WaitEvent;
```

The `user_data` pointer is how a caller maps a wake-up back to its
own per-fd state (e.g. walsender per-replica state).
