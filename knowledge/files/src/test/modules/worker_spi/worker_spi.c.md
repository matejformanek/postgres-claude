---
path: src/test/modules/worker_spi/worker_spi.c
anchor_sha: e18b0cb7344
loc: 495
depth: read
---

# src/test/modules/worker_spi/worker_spi.c

## Purpose

Reference / sample background worker. Demonstrates the canonical
patterns: GUC variables that drive worker behavior, both static
registration at `_PG_init` (preload-only) and **dynamic** registration
via a SQL launcher (`worker_spi_launch`), establishing a database
connection (by name or by OID), the signal-handler skeleton
(`SignalHandlerForConfigReload` for SIGHUP, `die` for SIGTERM),
`pgstat_report_activity` for visibility, the SPI-driven transaction
loop, and the `WaitLatch(WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH)`
sleep idiom. `[verified-by-code]` `worker_spi.c:1-22`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:303` | Defines GUCs and statically registers `worker_spi_total_workers` workers (preload only) |
| `worker_spi_main(Datum)` | `:135` | Worker entry point |
| `worker_spi_launch(i int4, dboid oid, roleoid oid, flags text[], interruptible bool) returns int4` | `:393` | Dynamic launcher; returns the PID |
| GUC `worker_spi.naptime` (`PGC_SIGHUP`) | `:313` | Seconds between iterations |
| GUC `worker_spi.database` (`PGC_SIGHUP`) | `:326` | Default DB to connect to |
| GUC `worker_spi.role` (`PGC_SIGHUP`) | `:335` | Default role |
| GUC `worker_spi.total_workers` (`PGC_POSTMASTER`) | `:347` | Number of static workers (preload only) |

## Internal landmarks

- `worker_spi_main` (`:135`):
  - Reads `dboid` / `roleoid` / `flags` from `MyBgworkerEntry->bgw_extra`
    (`:151-157`) — the dynamic-launcher pipe.
  - Installs signal handlers **before** `BackgroundWorkerUnblockSignals`
    (`:160-164`) — required ordering.
  - Connects via OID if `dboid` is valid (set by launcher) else by name
    (from GUCs) (`:166-171`).
  - `initialize_worker_spi` (`:69`) creates the schema + counted table
    on first run if absent.
  - Identifiers are quoted **after** the bootstrap step (`:182-185`)
    because `initialize_worker_spi` builds plain SQL strings.
- Main loop (`:206-291`) — `WaitLatch` with `naptime * 1000` ms timeout
  → reload config on SIGHUP → SPI transaction → repeat. Each iteration
  drains "delta" rows and folds them into the "total" row via a single
  `WITH deleted AS (DELETE ... RETURNING) UPDATE` CTE.
- `_PG_init` (`:303`):
  - GUCs are defined **before** the preload check so SQL launcher
    callers see them (`:308-312`).
  - `MarkGUCPrefixReserved("worker_spi")` and static worker
    registration only when preloaded.
- `worker_spi_launch` (`:393`) — extracts `BGWORKER_INTERRUPTIBLE`,
  `BGWORKER_BYPASS_ALLOWCONN`, `BGWORKER_BYPASS_ROLELOGINCHECK` from the
  text array argument; packs `(dboid, roleoid, flags)` into
  `worker.bgw_extra`; sets `bgw_notify_pid = MyProcPid` so
  `WaitForBackgroundWorkerStartup` can synchronize.

## Invariants & gotchas

- TEST MODULE / REFERENCE — exercises bgworker patterns end-to-end.
- Static registration (`RegisterBackgroundWorker`) is only legal during
  preload (`shared_preload_libraries`); dynamic registration
  (`RegisterDynamicBackgroundWorker`) is callable at any time
  `[verified-by-code]` `:344-345,477`.
- Memory leak intentionally tolerated in `initialize_worker_spi` for
  the schema-name quoting (`[from-comment]` `:177-183`).
- The worker is **not idempotent across crash**: `BGW_NEVER_RESTART`
  means a SIGTERM-driven exit is permanent — the launcher is expected
  to be re-run to bring it back.
- `pgstat_report_stat(true)` at end of each iteration (`:289`) forces
  the pending stats flush, so the test can observe statistics updates
  without waiting for the natural flush cadence.

## Cross-refs

- `knowledge/subsystems/bgworker-and-extensions.md` — bgworker lifecycle
  reference.
- `source/src/include/postmaster/bgworker.h` — `BackgroundWorker`
  struct, `BGWORKER_*` flags, `RegisterBackgroundWorker`,
  `RegisterDynamicBackgroundWorker`, `WaitForBackgroundWorkerStartup`,
  `BackgroundWorkerInitializeConnection{,ByOid}`.
- `source/src/include/postmaster/interrupt.h` —
  `SignalHandlerForConfigReload`, `ConfigReloadPending`.
- `source/src/include/executor/spi.h` — SPI manager API.
