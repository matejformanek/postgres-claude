---
path: src/backend/port/win32/timer.c
anchor_sha: e18b0cb7344
loc: 122
depth: read
---

# src/backend/port/win32/timer.c

## Purpose

Emulates POSIX `setitimer(ITIMER_REAL, ...)` on Windows. PG uses
`setitimer` for statement-timeout, lock-timeout, deadlock-timeout,
authentication-timeout, etc. — anything that arms a per-process timer to
deliver `SIGALRM`. Linux/BSD have a native syscall; Windows does not, so
this file fakes it with a dedicated **timer thread** that calls
`WaitForSingleObjectEx` with the requested timeout and then posts
`SIGALRM` to the main thread via `pg_queue_signal(SIGALRM)`.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int setitimer(int which, const struct itimerval *value, struct itimerval *ovalue)` | `timer.c:86` | POSIX-compat signature; `which` must be `ITIMER_REAL` |

## Internal landmarks

- **`timerCA` struct** (`timer.c:23-28`) — inter-thread comm area shared
  between the main thread and the timer thread:
  - `value` — current `struct itimerval` request.
  - `event` — auto-reset `HANDLE` that the main thread signals when it
    changes `value`.
  - `crit_sec` — Win32 critical section protecting `value`.
- **`pg_timer_thread`** (`timer.c:36`) — runs forever. `WaitForSingleObjectEx`
  with the current `waittime`:
  - `WAIT_OBJECT_0` → main thread changed `value`. Recompute `waittime`
    from `tv_sec*1000 + (tv_usec+999)/1000`. If both fields zero, set
    `waittime = INFINITE` (cancel the timer).
  - `WAIT_TIMEOUT` → fire `pg_queue_signal(SIGALRM)` and set
    `waittime = INFINITE` (one-shot).
- **`setitimer`** (`timer.c:86`) — main-thread entry:
  - First call lazy-initializes the event, critical section, and timer
    thread (`:92-110`).
  - Subsequent calls just take the critical section, copy the new value
    into `timerCommArea.value`, and `SetEvent` to wake the thread
    (`:113-118`).

## Invariants & gotchas

- **One-shot only — no interval timers.** The header comment
  (`timer.c:7-9`) and the assertion at `:89` explicitly forbid
  `value->it_interval` being nonzero. `ITIMER_REAL` only; `ITIMER_VIRTUAL`
  and `ITIMER_PROF` are not emulated.
- **One thread per backend.** The timer thread is per-process, lazily
  created on first `setitimer` call and never destroyed. Lives in
  process-private memory; not inherited across `CreateProcess`. Each
  child backend re-creates its own on first use.
- **Millisecond resolution.** `WaitForSingleObjectEx` takes milliseconds
  and is rounded up: `(tv_usec + 999) / 1000` (`:59`). A `tv_usec = 1`
  request results in a 1ms wait; PG's timer code (`backend/utils/misc/
  timeout.c`) is aware of this floor.
- **Signal delivery is asynchronous.** `pg_queue_signal(SIGALRM)` sets a
  bit in `pg_signal_queue` and signals `pgwin32_signal_event`. The main
  thread sees it on its next `CHECK_FOR_INTERRUPTS` (or via
  `pgwin32_dispatch_queued_signals` from a wait that includes the signal
  event). There is no preemption — the main thread is not interrupted
  mid-instruction the way a real Unix signal would. This matches PG's
  policy of not actually handling signals in async-signal-safe context
  anywhere.
- **Wait granularity vs accuracy.** Windows timer ticks are typically
  15.6ms unless the process has called `timeBeginPeriod(1)`. PG doesn't,
  so a "1ms" wait may take up to 15ms. Not a correctness issue (PG
  always treats timeouts as "at least N ms"), but a tuning surprise on
  Windows.
- **No timer reset on fork.** N/A — Windows doesn't fork; `CreateProcess`
  starts a fresh process whose `timerThreadHandle` is `INVALID_HANDLE_VALUE`
  so the thread is created on demand.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — covers PG's Win32 signal
  emulation layer.
- `knowledge/files/src/backend/port/win32/signal.c.md` — defines
  `pg_queue_signal` and `pgwin32_signal_event` consumed here.
- `knowledge/files/src/backend/utils/misc/timeout.c.md` — the consumer
  of `setitimer` (statement timeout etc.).
