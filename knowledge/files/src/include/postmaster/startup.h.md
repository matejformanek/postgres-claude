# startup.h

- **Source:** `source/src/include/postmaster/startup.h`
- **Depth:** skim

## Symbols

- `StartupProcessMain` (the `B_STARTUP` `main_fn`).
- `ProcessStartupProcInterrupts` — called from inside the redo loop.
- Promotion helpers: `IsPromoteSignaled`, `ResetPromoteSignaled`.
- Restore-command bracketing: `PreRestoreCommand`, `PostRestoreCommand`.
- Startup-progress: `enable_startup_progress_timeout`,
  `disable_startup_progress_timeout`, `begin_startup_progress_phase`,
  `has_startup_progress_timeout_expired`, GUC `log_startup_progress_interval`.

Consumers: `postmaster.c`, `launch_backend.c`, `xlog.c`, `xlogrecovery.c`.
