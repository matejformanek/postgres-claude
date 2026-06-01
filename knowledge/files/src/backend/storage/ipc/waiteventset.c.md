# `storage/ipc/waiteventset.c`

- **Source:** `source/src/backend/storage/ipc/waiteventset.c` (2039 lines)
- **Header:** `source/src/include/storage/waiteventset.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + per-impl skims; not deep)

## Purpose

The actual `ppoll()/pselect()`-like primitive behind `WaitLatch`. PG
abstracts over four OS facilities; `latch.c` is just a thin wrapper.

Wait reasons multiplexed in a `WaitEventSet`:
- `WL_LATCH_SET` — a registered `Latch *` was set.
- `WL_SOCKET_*` — one of several socket-ready conditions.
- `WL_POSTMASTER_DEATH` — postmaster died (returned as a bit).
- `WL_EXIT_ON_PM_DEATH` — postmaster died, exit immediately.
- `WL_TIMEOUT` — timeout fired.

## Implementations (compile-time choice)

Selection order: epoll > kqueue > poll > Win32, with manual override
via `WAIT_USE_*` macros. `:88-100`.

- **`WAIT_USE_EPOLL`** (Linux) — `epoll_create1`, `epoll_wait`. SIGURG
  is kept blocked and a `signalfd` is added to the set; latch wakes
  consume from the signalfd. **No self-pipe needed.** `[from-comment]
  :30-33`.
- **`WAIT_USE_KQUEUE`** (BSD/macOS) — `kqueue`, `kevent`. Latch wakes
  use `EVFILT_SIGNAL` on `SIGURG`.
- **`WAIT_USE_POLL`** (fallback Unix) — `poll(2)` + **the self-pipe
  trick**. Signal handler writes a byte to a pipe to ensure poll
  returns. Race-free with `ppoll` semantics. `[from-comment] :20-29`.
- **`WAIT_USE_WIN32`** — Windows events inherited by child processes.

## SIGURG as the wake signal

Latch implementation uses `SIGURG` (not `SIGUSR1`) to wake a sleeping
peer. SIGURG is otherwise unused by PG, and it doesn't carry a
`procsignal_reason` — pure wake-only. `WakeupOtherProc(pid)` calls
`kill(pid, SIGURG)`; the signal-handling layer (or signalfd/kqueue
equivalent) interrupts the wait without going through
`procsignal_sigusr1_handler`.

## API

- `CreateWaitEventSet(resowner, nevents)` — allocate; charged to the
  resowner.
- `AddWaitEventToSet(set, events, fd, latch, user_data)` — returns the
  position. `events` is a `WL_*` bitmask.
- `ModifyWaitEvent(set, pos, events, latch)` — change watch criteria
  without rebuilding the set (e.g. flipping `WL_SOCKET_READABLE` ↔
  `WL_SOCKET_WRITEABLE`). This is what `latch.c::WaitLatch` uses to
  reconfigure the shared `LatchWaitSet`.
- `WaitEventSetWait(set, timeout_ms, occurred, nevents, wait_event_info)`
  — block; `wait_event_info` is the `pgstat`-reported wait state.
- `FreeWaitEventSet(set)`.

## `nevents` parameter

`WaitEventSetWait` returns up to `nevents` ready events into the
caller's `occurred[]` array. For `WaitLatch`, this is 1; for the
postmaster main loop and walsender, it's larger so multiple sockets
can be drained per wake.

## maybe_sleeping handshake

Right before the OS sleep call, `WaitEventSetWaitBlock` sets
`latch->maybe_sleeping = true` with a memory barrier. After waking
(or upon early exit) it clears it. This pairs with `SetLatch`'s
"check maybe_sleeping before signaling" optimization in `latch.c`.

## Postmaster-death detection

- Unix: a self-pipe (`postmaster_alive_fds[0]`) is kept open by the
  postmaster; when postmaster dies, the kernel closes it and our
  poll/epoll sees POLLHUP/EOF. Translated to `WL_POSTMASTER_DEATH`.
- Windows: a process handle is added to the wait set; signaled on
  process exit.

`WL_EXIT_ON_PM_DEATH` is converted to immediate `proc_exit(1)` inside
the wait function — caller never sees the bit.

## Cross-references

- `latch.c` — the thin wrapper most callers actually use.
- `postmaster.c::ServerLoop` — keeps a long-lived `WaitEventSet`
  ([listen sockets, latch, postmaster-pipe]).
- `replication/walsender.c` — uses a persistent set with both the
  client socket and the latch.
- `libpq` — handles client I/O via these wait sets too.

## Open questions

1. **epoll edge-triggered vs level-triggered**: not chased here. The
   default appears to be level-triggered (`EPOLLIN` without `EPOLLET`).
   `[unverified]`.
2. **signalfd inheritance across fork**: PG's epoll path adds a
   signalfd per process; if EXEC_BACKEND re-execs, the signalfd must be
   recreated. `[unverified-here]`.
3. The `wait_event_info` reporting (visible in `pg_stat_activity.wait_event`)
   uses `pgstat_report_wait_start(wait_event_info)` /
   `_end` around the OS sleep. `[verified-by-code]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
