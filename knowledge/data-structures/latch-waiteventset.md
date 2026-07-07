# Latch + WaitEventSet — wakeups & multiplexed waiting

Two paired primitives. **`Latch`** is the lowest-level
"signal me when something happens" object — set by another
process (or this one), waited on by exactly one owner.
**`WaitEventSet`** is the multiplexed variant — wait on a
latch plus one or more sockets plus an optional postmaster-
death notification, all in one `ppoll()`/`epoll_wait()` call.
Together they implement every "block until input" path in
the backend.

Anchors:
- `source/src/include/storage/latch.h` — Latch API
  [verified-by-code]
- `source/src/include/storage/waiteventset.h:34-57` —
  event-flag bitmask [verified-by-code]
- `source/src/backend/storage/ipc/latch.c` — implementation
- `source/src/backend/storage/ipc/waiteventset.c` — multiplexer

## Latch — the simpler primitive

```c
SetLatch(latch);       /* mark "something happened" */
ResetLatch(latch);     /* clear the mark */
WaitLatch(latch, ...); /* block until mark or other event */
```

A latch is "set" or "not set" — a single bit. The owner waits
with `WaitLatch`; any process (including a signal handler in
this same process) calls `SetLatch` to wake the owner. Latches
work even from signal handlers — `SetLatch` is async-signal-
safe.

### Private vs shared

[from-comment `latch.h:22-27`]

- **Private latch** — `InitLatch()`; lives in process memory;
  only the owning process can SetLatch.
- **Shared latch** — `InitSharedLatch()` in shared memory;
  `OwnLatch()` to claim ownership; any process can `SetLatch`
  it, but only the owner can `WaitLatch`.

`MyLatch` is the per-backend process latch; signals from
generic signal handlers (`SIGINT`, `SIGTERM`, etc.) call
`SetLatch(MyLatch)` to interrupt any in-progress wait.

## The race-free coding pattern

[verified-by-code `latch.h:40-69`]

```c
for (;;)
{
    ResetLatch(MyLatch);          /* MUST come BEFORE check */
    if (work_to_do())
        do_work();
    WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH,
              0 /* no timeout */, WAIT_EVENT_SOMETHING);
}
```

The **invariant**: `ResetLatch` precedes the check. If the
order were inverted (check, then reset), `SetLatch` between
check and reset would be lost — the next `WaitLatch` would
block forever.

The pattern is so error-prone that the header comment
[`latch.h:42-69`] documents the right vs wrong orderings
explicitly.

## WaitEventSet — multiplexed waiting

For latch + N sockets + postmaster death, in one syscall:

```c
WaitEventSet *set = CreateWaitEventSet(CurrentResourceOwner, 4);
AddWaitEventToSet(set, WL_LATCH_SET, PGINVALID_SOCKET, MyLatch, NULL);
AddWaitEventToSet(set, WL_SOCKET_READABLE, sock_fd, NULL, NULL);
AddWaitEventToSet(set, WL_EXIT_ON_PM_DEATH, PGINVALID_SOCKET, NULL, NULL);

WaitEvent occurred[4];
int nev = WaitEventSetWait(set, -1, occurred, 4, WAIT_EVENT_XXX);
```

`AddWaitEventToSet` returns the position index; later use
`ModifyWaitEvent(set, pos, new_events, latch)` to change what's
being watched.

### The event-flag bitmask

[verified-by-code `waiteventset.h:34-57`]

| Flag | Purpose |
|---|---|
| `WL_LATCH_SET` | Wake on `SetLatch` |
| `WL_SOCKET_READABLE` | Wake when fd readable |
| `WL_SOCKET_WRITEABLE` | Wake when fd writable |
| `WL_TIMEOUT` | Wake after `timeout` ms (NOT for `WaitEventSetWait`) |
| `WL_POSTMASTER_DEATH` | Wake when postmaster dies (returns event) |
| `WL_EXIT_ON_PM_DEATH` | Wake AND exit (proc_exit) when postmaster dies |
| `WL_SOCKET_CONNECTED` | Connect completed (Windows; alias on Unix) |
| `WL_SOCKET_CLOSED` | Peer-closed signal |
| `WL_SOCKET_ACCEPT` | Listening socket has connection (Windows) |

`WL_EXIT_ON_PM_DEATH` is the preferred postmaster-death
handler — the backend silently exits rather than handling the
event and risking partial work. Use `WL_POSTMASTER_DEATH` only
when there's cleanup that must run before exit.

## Long-lived sets are cheap to re-wait

[from-comment `latch.h:88-91`]

> On many platforms using a long lived event set is more
> efficient than using WaitLatch or WaitLatchOrSocket.

On Linux, `WaitEventSet` uses `epoll`, which is O(1) per wait
after O(events_added) setup. `WaitLatch` uses `poll` /
`pselect` internally for one-shot waits; per-wait overhead is
O(events). For a backend that waits in a hot loop, a single
long-lived `WaitEventSet` saves significant CPU.

The backend's main loop has a process-global `FeBeWaitSet`
used for every client-message wait — set up once at backend
start.

## Memory + lifetime

- **Latch** — value type; lives in whatever memory the owner
  put it (private = process memory, shared = shmem).
- **WaitEventSet** — allocated by `CreateWaitEventSet`; owner
  is a `ResourceOwner`. On `ResourceOwnerRelease`, the set is
  freed automatically.
- **`FreeWaitEventSet`** — explicit free.
- **`FreeWaitEventSetAfterFork`** — special variant for
  postmaster's auxiliary-process fork path; the set's kernel
  state isn't inherited, but the userspace struct is.

## Timeout overhead

[from-comment `latch.h:36`]

> WaitLatch includes a provision for timeouts (which should
> be avoided when possible, as they incur extra overhead).

Setting a timeout on every wait forces the kernel to set up a
timer per call. For waits that should generally run to
completion, omit the timeout (pass -1 for `WaitEventSetWait`,
0 for `WaitLatch`). For backends that need periodic wakeup,
use a `PendingInterrupt` flag + a one-shot SetLatch from a
SIGALRM handler rather than per-call timeouts.

## Common review-time concerns

- **Reset BEFORE check.** The race-free pattern is invariant
  R1 of latch usage. Get this wrong and the bug is a
  hang.
- **Don't WaitLatch from a signal handler.** Only `SetLatch`
  is async-signal-safe.
- **Use `WL_EXIT_ON_PM_DEATH` by default.** Manual
  postmaster-death handling is for rare cleanup cases.
- **Use a long-lived `WaitEventSet`** in hot loops; recreating
  per call wastes O(events) syscalls.
- **`ModifyWaitEvent` is the in-place update** — don't
  re-create the set just to add/remove a socket.

## Invariants

- **[INV-1]** `ResetLatch` precedes the "is there work?"
  check. Always.
- **[INV-2]** `WaitLatch` only by the latch's owner.
  `SetLatch` by anyone (including async signal handlers).
- **[INV-3]** WaitEventSet is owned by a ResourceOwner;
  release-on-error is automatic.
- **[INV-4]** `WL_EXIT_ON_PM_DEATH` causes proc_exit
  silently; `WL_POSTMASTER_DEATH` returns event for explicit
  handling.
- **[INV-5]** Timeouts add per-call kernel-timer overhead;
  prefer interrupt-driven wakeup.

## Useful greps

- All WaitLatch / WaitEventSetWait sites:
  `grep -RIn 'WaitLatch\|WaitEventSetWait' source/src/backend | wc -l`
- The race-free pattern in practice:
  `grep -B2 -A4 'ResetLatch' source/src/backend/postmaster/autovacuum.c | head -30`
- Shared latch ownership:
  `grep -RIn 'OwnLatch\|InitSharedLatch' source/src/backend`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/ipc/latch.c`](../files/src/backend/storage/ipc/latch.c.md) | — | Latch implementation |
| [`src/backend/storage/ipc/waiteventset.c`](../files/src/backend/storage/ipc/waiteventset.c.md) | — | multiplexer implementation |
| [`src/include/storage/latch.h`](../files/src/include/storage/latch.h.md) | — | Latch API |
| [`src/include/storage/waiteventset.h`](../files/src/include/storage/waiteventset.h.md) | 34 | event-flag bitmask |
| [`src/include/storage/waiteventset.h`](../files/src/include/storage/waiteventset.h.md) | — | multiplexer API + event-flag bitmask |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/data-structures/pgproc-fields.md` — every PGPROC
  carries a Latch.
- `knowledge/subsystems/storage-ipc.md` — the IPC subsystem
  where the kernel-event multiplexer lives.
- `.claude/skills/bgworker-and-extensions/SKILL.md` — bgworkers
  use WaitLatch for their main loops; the canonical pattern.
- `.claude/skills/debugging/SKILL.md` — `pg_stat_activity.wait_event`
  surfaces the `wait_event_info` argument to `WaitEventSetWait`.
- `source/src/include/storage/latch.h` — Latch API.
- `source/src/include/storage/waiteventset.h` — multiplexer
  API + event-flag bitmask.
- `source/src/backend/storage/ipc/latch.c` — Latch
  implementation.
- `source/src/backend/storage/ipc/waiteventset.c` — multiplexer
  implementation.
