# globals.c

- **Source path:** `source/src/backend/utils/init/globals.c`
- **Lines:** 170
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/miscadmin.h` (matching `extern` decls for almost every symbol here)

## Purpose

Single translation unit that *defines* (allocates storage and gives initial value for) the globals that the rest of the backend declares `extern` in `miscadmin.h`. Includes interrupt flags, identity (`MyProcPid`, `MyDatabaseId`, `MyProcNumber`), data-dir paths, the latch pointer, and the default values for a small set of GUCs (work_mem, NBuffers, MaxConnections, ...). [from-comment, globals.c:11-15: "Globals used all over the place should be declared here and not in other modules."]

## Top-of-file comment (verbatim)

> "globals.c — global variable declarations / NOTES: Globals used all over the place should be declared here and not in other modules." [from-comment, globals.c:3-15]

## Public surface (defined-here variables, grouped)

- **Signal-handler flags** (volatile sig_atomic_t): `InterruptPending`, `QueryCancelPending`, `ProcDiePending`, `CheckClientConnectionPending`, `ClientConnectionLost`, `IdleInTransactionSessionTimeoutPending`, `TransactionTimeoutPending`, `IdleSessionTimeoutPending`, `ProcSignalBarrierPending`, `LogMemoryContextPending`, `IdleStatsUpdateTimeoutPending`. [globals.c:32-42]
- **Holdoff counters**: `InterruptHoldoffCount`, `QueryCancelHoldoffCount`, `CritSectionCount` (volatile uint32). `CritSectionCount > 0` causes `errstart` to promote ERROR to PANIC (elog.c:372). [globals.c:43-45]
- **Identity**: `MyProcPid`, `MyStartTime`, `MyStartTimestamp`, `MyClientSocket`, `MyProcPort`, `MyCancelKey[MAX_CANCEL_KEY_LENGTH]`, `MyCancelKeyLength`, `MyPMChildSlot`, `MyProcNumber = INVALID_PROC_NUMBER`, `ParallelLeaderProcNumber`, `MyDatabaseId = InvalidOid`, `MyDatabaseTableSpace`, `MyDatabaseHasLoginEventTriggers`, `MyBackendType` (defined in miscinit.c despite living conceptually here). [globals.c:49-100]
- **Latch**: `struct Latch *MyLatch` — *pointer* to either `LocalLatchData` (process-local, before `MyProc` exists) or `MyProc->procLatch` (after we have a PGPROC). Always non-NULL once `InitProcessLocalLatch` (miscinit.c:235) has run. [from-comment, globals.c:58-65]
- **Paths**: `DataDir`, `data_directory_mode = PG_DIR_MODE_OWNER (0700)`, `OutputFileName[MAXPGPATH]`, `my_exec_path[MAXPGPATH]`, `pkglib_path[MAXPGPATH]`, `DatabasePath`. `data_directory_mode` may be changed to `0750` by `checkDataDir` (miscinit.c). [from-comment, globals.c:67-79]
- **EXEC_BACKEND only**: `postgres_exec_path[MAXPGPATH]`. [globals.c:86-90]
- **Postmaster state**: `PostmasterPid`, `IsPostmasterEnvironment = false`, `IsUnderPostmaster = false`, `IsBinaryUpgrade = false`, `ExitOnAnyError = false`. Comment at lines 110-120 emphasizes these must be set early or error handling will go wrong. [from-comment]
- **Datetime defaults**: `DateStyle = USE_ISO_DATES`, `DateOrder = DATEORDER_MDY`, `IntervalStyle = INTSTYLE_POSTGRES`.
- **GUC defaults** (the value compiled in before postgresql.conf is read): `enableFsync = true`, `allowSystemTableMods = false`, `work_mem = 4096` (kB), `hash_mem_multiplier = 2.0`, `maintenance_work_mem = 65536`, `max_parallel_maintenance_workers = 2`, `NBuffers = 16384` (8KB pages → 128 MB), `MaxConnections = 100`, `max_worker_processes = 8`, `max_parallel_workers = 8`, `autovacuum_max_parallel_workers = 0`, `MaxBackends = 0` (computed after preload libs register bg workers — see comment at 141-143).
- **VACUUM costing**: `VacuumBufferUsageLimit = 2048`, `VacuumCostPageHit = 1`, `VacuumCostPageMiss = 2`, `VacuumCostPageDirty = 20`, `VacuumCostLimit = 200`, `VacuumCostDelay = 0`, `VacuumCostBalance`, `VacuumCostActive`.
- **SLRU buffer-count GUCs**: `commit_timestamp_buffers = 0`, `multixact_member_buffers = 32`, `multixact_offset_buffers = 16`, `notify_buffers = 16`, `serializable_buffers = 32`, `subtransaction_buffers = 0`, `transaction_buffers = 0`. Zero means "auto-size from shared_buffers".

## Key invariants

- **No code logic.** This file is pure storage definition; the only header includes are for the types referenced (`Latch *`, `ProcNumber`, `BackendType` enums, etc.).
- **`MyLatch` is always non-NULL when used from signal handlers.** Comment at lines 58-65: it is set to a process-local latch (`LocalLatchData` in miscinit.c) before `MyProc` exists, and swapped to `MyProc->procLatch` by `SwitchToSharedLatch` after `InitProcess`. The pointer hop ensures handlers don't need to test `MyProc != NULL`. [from-comment]
- **`data_directory_mode` may legitimately be one of {0700, 0750}.** Set by `checkDataDir` (miscinit.c:297) based on the actual mode bits the data directory was found with. [from-comment, globals.c:75-79]
- **`MaxBackends` is computed, not configured directly.** Comment at 138-143: "computed by PostmasterMain after modules have had a chance to register background workers." Default 0 here is a sentinel.

## Cross-references

- Every `extern` for these symbols lives in `src/include/miscadmin.h` (the postgres-wide "miscellaneous admin" header).
- `volatile sig_atomic_t` flags are written from signal handlers (in `tcop/postgres.c::HandleStartupProcInterrupts`, `postmaster/interrupt.c`, etc.) and tested by `CHECK_FOR_INTERRUPTS()` (miscadmin.h).
- `CritSectionCount` is incremented by `START_CRIT_SECTION()`/`END_CRIT_SECTION()` macros (xact.h) and read by `errstart` (elog.c:372) to force PANIC promotion.
- GUC values here are *defaults*; `guc_tables.c` references the same storage via pointer.

## Open questions

- None — this file is mechanical. Any behavior change goes through the consumer files.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=6 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
