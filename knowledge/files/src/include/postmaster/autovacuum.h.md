# autovacuum.h

- **Source:** `source/src/include/postmaster/autovacuum.h`
- **Depth:** skim

## Symbols

- `AutoVacLauncherMain`, `AutoVacWorkerMain` (the `main_fn`s).
- `AutoVacuumingActive()` — GUC check.
- `AutoVacWorkerFailed()` — launcher-side flag after fork failure.
- `autovac_init()`, `AutoVacuumShmemSize`, `AutoVacuumShmemInit`.
- GUC globals: `autovacuum_start_daemon`, `autovacuum_max_workers`,
  `autovacuum_naptime`, etc.

Consumers: `postmaster.c` (start/signal), `commands/vacuum.c` (shared
worker-coordination shmem), `pgstat`.
