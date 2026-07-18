---
path: src/port/pgsleep.c
anchor_sha: e18b0cb7344
loc: 57
depth: read
---

# src/port/pgsleep.c

## Purpose

Provides `pg_usleep(long microsec)` — a portable microsecond-resolution
sleep. On Unix this wraps `nanosleep(2)`; on Win32 (frontend only — backend
Win32 uses a signal-aware version in `src/backend/port/win32/signal.c`) it
wraps `SleepEx`. The header comment is emphatic that long sleeps in the
backend are a code smell: they silently return early on a signal but **do
not** wake on latch sets on most OSes, so `WaitLatch()` with a timeout is
the correct pattern instead. `[from-comment]` `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pg_usleep(long microsec)` | `pgsleep.c:41` | No return value; non-positive delays are no-ops |

## Internal landmarks

- Unix arm (`pgsleep.c:45-50`) — fills a `struct timespec` and calls
  `nanosleep`; `(void)` cast on the return ignores `EINTR` (early wakeup),
  which matches the documented "silently returns early on signal" behavior.
  `[verified-by-code]`
- Win32 frontend arm (`:51-53`) — `SleepEx` takes milliseconds; the rounding
  `(microsec + 500) / 1000` rounds-to-nearest, with a special case bumping
  sub-500us requests to a 1ms sleep so we don't degenerate to a 0ms (yield-only)
  call.
- Backend Win32 is **excluded** by the `defined(FRONTEND) || !defined(WIN32)`
  guard at the top of the file (`:21`); the backend has its own
  signal-aware wrapper. `[verified-by-code]` `[from-comment]`

## Invariants & gotchas

- **Interruptible by signals, but NOT by latches.** This is the headline
  gotcha: backends sleeping via `pg_usleep` will not respond promptly to
  `MyLatch` being set unless a SIGUSR1 also arrives. The header comment
  flags this and points callers at `WaitLatch()`. Long backend sleeps via
  this function are bugs in the making. `[from-comment]`
- 32-bit `long` caps the max delay at ~2000 seconds; portable code that
  needs longer must loop. `[from-comment]`
- Kernel-tick granularity (up to ~20ms slop on some platforms) means
  short requested delays can run significantly longer. `[from-comment]`

## Cross-refs

- `source/src/backend/port/win32/signal.c` — backend Win32 version of `pg_usleep`.
- `source/src/backend/utils/init/miscinit.c` and `storage/lmgr/latch.c` —
  `WaitLatch` is the preferred sleep primitive in the backend.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
