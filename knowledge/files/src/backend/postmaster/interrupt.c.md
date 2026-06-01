# interrupt.c

- **Source:** `source/src/backend/postmaster/interrupt.c` (108 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Reusable signal-handler + flag-checking helpers used by aux processes and
bgworkers to keep their main loops uniform. [from-comment] `:1-12`

## Globals

- `ConfigReloadPending` — set from SIGHUP. `:27`
- `ShutdownRequestPending` — set from SIGTERM. `:28`

## Functions

| Line | Symbol | Used as |
|---|---|---|
| 34 | `ProcessMainLoopInterrupts` | called inside aux main loops to drain barriers, reload config, exit on shutdown, log memory contexts |
| 61 | `SignalHandlerForConfigReload` | SIGHUP → set flag + `SetLatch` |
| 73 | `SignalHandlerForCrashExit` | SIGQUIT → `_exit(2)` (no atexit; `_exit(2)` forces postmaster crash-restart) |
| 104 | `SignalHandlerForShutdownRequest` | SIGTERM (or SIGUSR2 for checkpointer/parallel-apply) → flag + latch |

## Why `_exit(2)` not `_exit(0)` on crash exit

`:75-89` — using `2` forces the postmaster's dead-man-switch in `pmsignal.c`
to register this as a crash and trigger a full system-reset cycle, even if a
human accidentally SIGQUIT-ed a random backend.

## Consumers

bgwriter, walwriter, checkpointer, archiver, walsummarizer, startup, syslogger,
many bgworkers. Almost every aux loop has a `ProcessMainLoopInterrupts()` call.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
