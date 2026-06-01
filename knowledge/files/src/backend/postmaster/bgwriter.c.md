# bgwriter.c

- **Source:** `source/src/backend/postmaster/bgwriter.c` (344 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Background writer — singleton aux process. Trickles dirty shared buffers
to disk so regular backends rarely need to write before evicting. As of
PG 9.2 it does **not** handle checkpoints (that's `checkpointer.c`).
[from-comment] `:5-13`

## Lifecycle

- Singleton, postmaster-spawned, `main_fn = BackgroundWriterMain`.
- Normal exit: SIGTERM. Emergency: SIGQUIT (`_exit(2)`).
- Unexpected exit → postmaster treats as a backend crash; full crash-restart.
  [from-comment] `:19-21`

## `BackgroundWriterMain` (`:88-344`)

1. `AuxiliaryProcessMainCommon()` — standard aux init.
2. Install signal handlers — `SIGHUP→SignalHandlerForConfigReload`,
   `SIGTERM→SignalHandlerForShutdownRequest`, `SIGUSR1→procsignal_sigusr1_handler`.
3. Create `bgwriter_context` child of `TopMemoryContext` for per-iteration
   allocations; on error we `MemoryContextReset` it rather than resetting
   `TopMemoryContext`. `:124-132`
4. `sigsetjmp` at the bottom of the exception stack — same idiom as
   `PostgresMain`. On longjmp: release lwlocks, AIO, buffers, smgr; reset
   `bgwriter_context`; `pg_usleep(1s)` so error storms don't spin. `:136-205`
5. Main loop (`:223-343`):
   - `ResetLatch` → `ProcessMainLoopInterrupts` → `BgBufferSync(&wb_context)`.
   - `pgstat_report_bgwriter` / `pgstat_report_wal(true)`.
   - After every checkpoint (`FirstCallSinceLastCheckpoint`), call
     `smgrdestroyall()` to release smgr refs for dropped relations (bgwriter
     does not process sinval messages). `:242-251`
   - On non-recovery, `XLogStandbyInfoActive`: every ~15s emit a fresh
     `xl_running_xacts` via `LogStandbySnapshot` (only bgwriter is regular
     enough to do this reliably). `:253-295`
   - `WaitLatch(BgWriterDelay)`; if idle for two consecutive cycles, ask
     the buffer strategy to wake us via `StrategyNotifyBgWriter(MyProcNumber)`
     and sleep `BgWriterDelay * HIBERNATE_FACTOR` (= 200ms × 50 = 10s).
     `:297-340`

## GUCs

- `bgwriter_delay` (default 200ms) — `BgWriterDelay` global. `:59`
- `bgwriter_flush_after`, `bgwriter_lru_*` — consumed inside `BgBufferSync`
  (in `bufmgr.c`).

## Interactions

- Calls `BgBufferSync` (`storage/buffer/bufmgr.c`).
- Calls `LogStandbySnapshot` (`storage/ipc/standby.c`).
- Consumed by: `pg_stat_bgwriter` reads the same stats this process writes.
- Header: `postmaster/bgwriter.h`.
