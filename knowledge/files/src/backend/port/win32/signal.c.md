---
path: src/backend/port/win32/signal.c
anchor_sha: e18b0cb7344
loc: 395
depth: read
---

# src/backend/port/win32/signal.c

## Purpose

Provides the POSIX-shaped signal API (`sigaction`, `sigprocmask`,
`pg_usleep`) on Windows, on top of:

1. A **named-pipe-based sender/receiver protocol** — sending a signal
   from process A to process B means A `CallNamedPipe`s to
   `\\.\pipe\pgsignal_<pid>` and B's signal thread `ReadFile`s a single
   byte = signum.
2. A **per-backend signal-handler thread** (`pg_signal_thread` at
   `signal.c:278`) that owns the pipe and queues incoming signums.
3. A **global event** (`pgwin32_signal_event`) that the queue sets
   whenever a signal becomes pending, so any
   `WaitForMultipleObjectsEx`-based wait can wake on signal arrival.
4. Per-signal handler dispatch on the main thread via
   `pgwin32_dispatch_queued_signals`, called from `CHECK_FOR_INTERRUPTS`
   and from every blocking primitive that includes the signal event in
   its wait set.

This is the spine that `win32_sema.c`, `win32/socket.c`, `win32/timer.c`,
and the broader Win32 port build on. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `volatile int pg_signal_queue` | `signal.c:24` | Bitmap of pending signums |
| `int pg_signal_mask` | `:25` | Main thread's signal mask |
| `HANDLE pgwin32_signal_event` | `:27` | Auto-reset event signaled when queue non-empty |
| `HANDLE pgwin32_initial_signal_pipe` | `:28` | Pre-postmaster-fork pipe handle |
| `void pg_usleep(long microsec)` | `:53` | Signal-aware sleep (replaces `src/port/pgsleep.c`) |
| `void pgwin32_signal_initialize(void)` | `:79` | Per-process init; creates event, pipe, thread |
| `void pgwin32_dispatch_queued_signals(void)` | `:120` | Main-thread call: run pending handlers |
| `int pqsigprocmask(int how, const sigset_t *set, sigset_t *oset)` | `:175` | POSIX shim |
| `int pqsigaction(int signum, const struct sigaction *act, struct sigaction *oldact)` | `:214` | POSIX shim |
| `HANDLE pgwin32_create_signal_listener(pid_t pid)` | `:231` | Postmaster pre-creates pipe for child |
| `void pg_queue_signal(int signum)` | `:263` | Set bit + signal event (called from any thread) |

## Internal landmarks

- **`pg_signal_crit_sec`** (`signal.c:34`) — protects `pg_signal_queue`,
  which is the only piece of state writable from the signal thread. All
  other globals are main-thread-only. Header comment `:31-33`.
- **`pg_signal_array[]` and `pg_signal_defaults[]`** (`:37-38`) — per-signal
  `struct sigaction` and "default action" arrays, indexed by signum.
  `pqsigaction` writes them; `pgwin32_dispatch_queued_signals` reads.
- **`pg_signal_thread`** (`:278`) — runs forever:
  - `CreateNamedPipe(\\.\pipe\pgsignal_<our pid>, PIPE_ACCESS_DUPLEX,
    PIPE_TYPE_MESSAGE)`.
  - `ConnectNamedPipe` — block until a sender connects.
  - `ReadFile` one byte = signum. Queue via `pg_queue_signal`. Echo the
    byte back so the sender's `CallNamedPipe` returns. `FlushFileBuffers`
    so the echoed byte is actually delivered.
  - **Queue-before-respond guarantee** (`:322-330`): the signum is
    queued BEFORE the response is written, so a sender that's just
    gotten its `CallNamedPipe` to return can rely on the recipient's
    next `CHECK_FOR_INTERRUPTS` seeing the signal. Stronger than POSIX
    requires, but needed to dodge observed timing bugs.
- **`pgwin32_dispatch_queued_signals`** (`:120`) — main-thread dispatcher:
  - Loop while `UNBLOCKED_SIGNAL_QUEUE() != 0` (queue ∧ ~mask).
  - For each set bit, look up handler. If real handler (not DFL/IGN/ERR):
    apply `sa_mask` (and `sigmask(i)` itself unless `SA_NODEFER`) to
    block recursive delivery, call handler, restore mask.
  - **LeaveCriticalSection around handler call** (`:151-161`) — so the
    handler can call `pg_queue_signal` (e.g. by signaling itself or
    being preempted by the signal thread) without deadlocking.
  - `ResetEvent(pgwin32_signal_event)` at end (`:169`) — empties the
    event since the queue is now drained.
- **`pg_console_handler`** (`:383`) — `SetConsoleCtrlHandler` callback.
  Maps `CTRL_C_EVENT`, `CTRL_BREAK_EVENT`, `CTRL_CLOSE_EVENT`,
  `CTRL_SHUTDOWN_EVENT` all to `SIGINT`.
- **`pg_usleep`** (`:53`) — replaces `src/port/pgsleep.c` (which is
  non-signal-aware). Calls `WaitForSingleObject(pgwin32_signal_event,
  ms)`. If the event fires, dispatch + return EINTR; if it times out,
  return normally.

## Invariants & gotchas

- **Only `pg_signal_queue` can be touched from the signal thread.**
  Header comment at `:251-256` is emphatic. All other globals
  (`pg_signal_array`, `pg_signal_mask`, `pg_signal_defaults`) are
  main-thread-exclusive. Adding a new variable readable from the signal
  thread requires adding it to the critical-section protection.
- **`pgwin32_signal_event` is auto-reset.** Set every time
  `pg_queue_signal` is called; cleared at the end of
  `pgwin32_dispatch_queued_signals`. Anyone waiting on it gets exactly
  one wakeup per signal-batch, not per signal.
- **`PIPE_UNLIMITED_INSTANCES`** (`:240, 295`) — multiple senders can
  connect simultaneously. The signal thread serves them sequentially
  via the connect/read/respond/disconnect loop.
- **Pre-fork pipe handle.** `pgwin32_initial_signal_pipe` is created by
  the postmaster before launching a child (via `pgwin32_create_signal_listener`
  at `:231`) and inherited via `CreateProcess`. The child's signal
  thread re-uses it on first iteration (`:281`), avoiding a race where
  someone could send a signal before the child's pipe came up.
- **No `kill(0, ...)`.** The Win32 `kill` shim in `src/port/kill.c`
  implements `kill(pid, sig)` as a `CallNamedPipe` to that pid's pipe.
  There is no broadcast / process-group support.
- **Signal numbers are PG-defined.** `PG_SIGNAL_COUNT` is small (typical
  ~32), and signums >= it are silently ignored by `pg_queue_signal`
  (`:266-267`).
- **Console handler runs on its own OS-created thread.** Same critsec
  protects `pg_queue_signal`. The handler returns `TRUE` so the default
  abort doesn't fire after `SIGINT` is queued.
- **EINTR is synthesized.** Whenever `pgwin32_dispatch_queued_signals`
  runs from inside a blocking primitive's wait, the primitive sets
  `errno = EINTR` and returns. Pattern visible across this file's
  consumers (`win32_sema.c::PGSemaphoreLock`,
  `win32/socket.c::pgwin32_waitforsinglesocket`, `pg_usleep`).
- **`pqsigaction` does not validate `sa_flags` beyond `SA_NODEFER`.**
  Other POSIX flags (`SA_RESTART`, `SA_SIGINFO`, etc.) are silently
  ignored. Most callers use plain `sa_handler` only.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — Win32 signal-emulation layer
  overview.
- `knowledge/files/src/backend/port/win32_sema.c.md` — uses
  `pgwin32_signal_event` and `pgwin32_dispatch_queued_signals` in
  `PGSemaphoreLock`.
- `knowledge/files/src/backend/port/win32/socket.c.md` — uses the same
  pair in every blocking socket primitive.
- `knowledge/files/src/backend/port/win32/timer.c.md` — calls
  `pg_queue_signal(SIGALRM)` from the timer thread.
- `knowledge/files/src/backend/port/win32/crashdump.c.md` — unrelated
  Win32 infrastructure; installed alongside in backend startup.
- `knowledge/files/src/port/kill.c.md` — the sender side of the pipe
  protocol.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
