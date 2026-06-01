# startup.c

- **Source:** `source/src/backend/postmaster/startup.c` (377 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

The startup process. First child the postmaster launches; performs crash /
archive recovery by replaying WAL. On a primary it reaches the consistent
point and exits (exit 0 tells postmaster recovery succeeded). On a hot
standby it stays alive replaying continuously. [from-comment] `:5-10`

## Lifecycle peculiarity

Unlike other aux processes, there is **no main loop** in this file —
control jumps into `StartupXLOG()` (in `access/transam/xlogrecovery.c`) and
only returns when recovery is complete. [from-comment] `:6-9`

## Signals (`:78-116`, installed in `StartupProcessMain` `:228-235`)

- `SIGHUP` → `StartupProcSigHupHandler` → `got_SIGHUP=true; WakeupRecovery()`.
- `SIGTERM` → `StartupProcShutdownHandler` — if currently inside a restore
  command (`in_restore_command`), `proc_exit(1)` immediately; otherwise
  set flag, `WakeupRecovery`.
- `SIGUSR1` → standard procsignal handler.
- `SIGUSR2` → `StartupProcTriggerHandler` → finish recovery (promotion signal).

## `ProcessStartupProcInterrupts` (`:153-195`)

Called from inside the WAL-redo loop. Handles SIGHUP reload, shutdown,
postmaster-death poll (rate-limited on systems lacking
`USE_POSTMASTER_DEATH_SIGNAL`), and barriers / memory-log requests.

## `StartupProcessMain` (`:215-264`)

1. `AuxiliaryProcessMainCommon`.
2. Register `StartupProcExit` (calls `ShutdownRecoveryTransactionEnvironment`).
3. Install signal handlers; `InitializeTimeouts`; register standby-mode
   timeouts (`STANDBY_DEADLOCK_TIMEOUT`, etc.).
4. Unblock signals.
5. `StartupXLOG()` — does the work.
6. `proc_exit(0)`.

## Promotion API

- `PreRestoreCommand` / `PostRestoreCommand` mark windows where SIGTERM may
  safely `proc_exit(1)` even mid-recovery.
- `IsPromoteSignaled` / `ResetPromoteSignaled` — interface for `xlog.c` to
  poll the promote flag.

## Startup-progress reporting

- `log_startup_progress_interval` GUC.
- `begin_startup_progress_phase`, `enable_startup_progress_timeout`,
  `has_startup_progress_timeout_expired`. Used to log slow phases of
  recovery without polluting normal operation.

## Interactions

- `access/transam/xlogrecovery.c::StartupXLOG` (the actual recovery driver).
- `storage/ipc/standby.c` (deadlock + lock-timeout handlers).
- Header: `postmaster/startup.h`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
