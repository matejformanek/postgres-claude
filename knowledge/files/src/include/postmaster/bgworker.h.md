# bgworker.h

- **Source:** `source/src/include/postmaster/bgworker.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim

## Public API for extensions

- `BackgroundWorker` struct: `bgw_name`, `bgw_type`, `bgw_flags`,
  `bgw_start_time` (`BgWorkerStart_*`), `bgw_restart_time`,
  `bgw_library_name`, `bgw_function_name`, `bgw_main_arg`,
  `bgw_extra`, `bgw_notify_pid`.
- Start-time enum: `BgWorkerStart_PostmasterStart`, `_ConsistentState`,
  `_RecoveryFinished`.
- Flags: `BGWORKER_SHMEM_ACCESS`, `BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `BGWORKER_CLASS_PARALLEL`.
- Registration:
  - `RegisterBackgroundWorker(BackgroundWorker *)` — for `_PG_init` of
    shared_preload_libraries.
  - `RegisterDynamicBackgroundWorker(BackgroundWorker *, BackgroundWorkerHandle **)`
    — at runtime.
- Worker-side helpers: `BackgroundWorkerInitializeConnection[ByOid]`,
  `BackgroundWorkerBlockSignals`, `BackgroundWorkerUnblockSignals`.
- Status APIs: `GetBackgroundWorkerPid`, `WaitForBackgroundWorkerStartup`,
  `WaitForBackgroundWorkerShutdown`, `TerminateBackgroundWorker`.

## See also

`postmaster/bgworker_internals.h` (postmaster-side state) and the canonical
bgworker skill.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/bgworker-and-parallel.md](../../../../idioms/bgworker-and-parallel.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new background worker](../../../../scenarios/add-new-bgworker.md)

<!-- scenarios:auto:end -->
