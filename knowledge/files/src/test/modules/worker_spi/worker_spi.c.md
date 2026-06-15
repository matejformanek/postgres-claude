# src/test/modules/worker_spi/worker_spi.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 495
**Verification depth:** full read

## Role

Canonical sample/test module demonstrating the full background-worker + SPI coding pattern: establishing a database connection, running transactions, using GUCs, heeding SIGHUP to reload config, reporting to pg_stat_activity, and sleeping on the process latch with exit-on-postmaster-death. [from-comment] `source/src/test/modules/worker_spi/worker_spi.c:4-8`. The worker connects to a database, lazily creates a schema + `counted` table, and on each wakeup aggregates `'delta'` rows into the `'total'` row. [from-comment] `source/src/test/modules/worker_spi/worker_spi.c:10-14`. It registers static workers at `shared_preload_libraries` time and also exposes a SQL function to launch dynamic workers at runtime. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:379-386,392-495`

## Public API

- `worker_spi_main(Datum main_arg)` — `pg_noreturn PGDLLEXPORT` worker entrypoint; named in `bgw_function_name`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:48,134-135`
- `worker_spi_launch(PG_FUNCTION_ARGS)` — SQL-callable function (`PG_FUNCTION_INFO_V1`) launching a dynamic bgworker; args: index, dboid, roleoid, flags text[], interruptible bool; returns the started worker PID or NULL. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:46,392-495`
- `_PG_init(void)` — module init; defines GUCs and registers static workers. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:302-387`
- GUCs: `worker_spi.naptime` (int, PGC_SIGHUP), `worker_spi.database` (string, PGC_SIGHUP), `worker_spi.role` (string, PGC_SIGHUP), `worker_spi.total_workers` (int, PGC_POSTMASTER, only when preloaded). [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:313-358`

## Invariants

- INV-1: `worker_spi.naptime`/`.database`/`.role` are defined unconditionally so `worker_spi_launch()` works even without preloading; `.total_workers` and static registration require `process_shared_preload_libraries_in_progress`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:309-345`
- INV-2: `bgw_extra` layout is exactly `Oid dboid` + `Oid roleoid` + `uint32 flags`, packed by the launcher and unpacked identically by the worker. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:151-157,470-475`
- INV-3: Signal handlers (`SignalHandlerForConfigReload` on SIGHUP, `die` on SIGTERM) must be installed before `BackgroundWorkerUnblockSignals()`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:159-164`
- INV-4: `initialize_worker_spi` assumes schema/table names are unquoted; `quote_identifier` must only be applied after it returns. [from-comment] `source/src/test/modules/worker_spi/worker_spi.c:177-185`
- INV-5: Each `StartTransactionCommand()` is preceded by `SetCurrentStatementStartTimestamp()`. [from-comment] `source/src/test/modules/worker_spi/worker_spi.c:238-245,254-255`

## Notable internals

- Main loop sleeps via `WaitLatch(MyLatch, WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH, naptime*1000, wait_event)` then `ResetLatch` + `CHECK_FOR_INTERRUPTS()`; never `usleep`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:221-227`
- Custom wait event lazily allocated once via `WaitEventExtensionNew("WorkerSpiMain")`, cached in `worker_spi_wait_event_main`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:57,211-213`
- Per-iteration SPI transaction skeleton: `SetCurrentStatementStartTimestamp` → `StartTransactionCommand` → `SPI_connect` → `PushActiveSnapshot(GetTransactionSnapshot())` → `SPI_execute` → `SPI_finish` → `PopActiveSnapshot` → `CommitTransactionCommand`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:254-290`
- `_PG_init` calls `MarkGUCPrefixReserved("worker_spi")` and registers N static workers with `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`, `BgWorkerStart_RecoveryFinished`, `BGW_NEVER_RESTART`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:360-386`
- Dynamic launch: parses a text[] of flag names (`ALLOWCONN`→`BGWORKER_BYPASS_ALLOWCONN`, `ROLELOGINCHECK`→`BGWORKER_BYPASS_ROLELOGINCHECK`), optional `BGWORKER_INTERRUPTIBLE`, sets `bgw_notify_pid = MyProcPid`, then `RegisterDynamicBackgroundWorker` + `WaitForBackgroundWorkerStartup`. [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:404-492`
- Worker connects via `BackgroundWorkerInitializeConnectionByOid` (dynamic, OID supplied) or `BackgroundWorkerInitializeConnection` (falls back to GUCs). [verified-by-code] `source/src/test/modules/worker_spi/worker_spi.c:166-172`

## Cross-refs

- `source/src/include/postmaster/bgworker.h` — BackgroundWorker struct, bgw_flags, Register*BackgroundWorker, WaitForBackgroundWorkerStartup.
- `source/src/backend/postmaster/bgworker.c` — bgworker registration/launch implementation.
- `source/src/backend/executor/spi.c` — SPI_connect/SPI_execute/SPI_finish.
- `source/src/backend/postmaster/interrupt.c` — SignalHandlerForConfigReload, ConfigReloadPending.
- `source/src/backend/utils/activity/wait_event.c` — WaitEventExtensionNew.
- `source/src/test/modules/worker_spi/worker_spi--1.0.sql` — SQL wrappers for worker_spi_launch.

## Potential issues

- **[ISSUE-leak: acknowledged memory leak]** `worker_spi.c:184` — `quote_identifier` results overwrite the prior `pstrdup`'d pointers; the comment at :182 explicitly says "some memory might be leaked here." Benign in a long-lived worker (one-time at startup), and documented. Severity: nit.
- **[ISSUE-stale: open XXX]** `worker_spi.c:83` — `XXX could we use CREATE SCHEMA IF NOT EXISTS?` — long-standing open question; the count-then-create approach has a TOCTOU window but is acceptable for a single worker. Severity: nit.
