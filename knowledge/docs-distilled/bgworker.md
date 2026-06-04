---
source_url: https://www.postgresql.org/docs/current/bgworker.html
fetched_at: 2026-06-03T19:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 48: Background Worker Processes

The extension-author contract for spawning a managed backend process. The
non-obvious parts are the static-vs-dynamic registration split, the start-time
state gating, and the EXEC_BACKEND/Windows Datum-passing hazard.

## The `BackgroundWorker` struct (what you fill in)

`bgw_name` / `bgw_type` (log + `pg_stat_activity` labels; `bgw_type` groups
workers) · `bgw_flags` (capability mask) · `bgw_start_time` · `bgw_restart_time`
(seconds, or `BGW_NEVER_RESTART`) · `bgw_library_name` (`"postgres"` for core
code) · `bgw_function_name` (entry point — must be `PGDLLEXPORT`, **not
`static`**) · `bgw_main_arg` (single `Datum`) · `bgw_extra` (reached via
`MyBgworkerEntry`, not an argument) · `bgw_notify_pid` (gets `SIGUSR1` on
start/exit; 0 for postmaster-time registration). [from-docs]
[verified-by-code, source/src/include/postmaster/bgworker.h, via
knowledge/files/src/include/postmaster/bgworker.h.md]

## Two registration paths — the key fork

- **`RegisterBackgroundWorker()`** — callable **only from `_PG_init()`** of a
  `shared_preload_libraries` module, i.e. at postmaster start. Returns no handle.
  Use for always-on workers known at boot. [from-docs]
- **`RegisterDynamicBackgroundWorker()`** — callable from a *running* backend or
  another worker (**not** the postmaster). Returns a `BackgroundWorkerHandle *`
  for polling/termination. Use for on-demand workers (e.g. a parallel-query
  leader spawning helpers). [from-docs]
  [verified-by-code, via knowledge/files/src/backend/postmaster/bgworker.c.md]

## Capability flags

- **`BGWORKER_SHMEM_ACCESS`** — shared-memory access (needed for almost
  anything).
- **`BGWORKER_BACKEND_DATABASE_CONNECTION`** — may attach to a database;
  **requires** `BGWORKER_SHMEM_ACCESS` or startup fails. [from-docs]

## Start-time gating (`bgw_start_time`)

- `BgWorkerStart_PostmasterStart` — earliest; no DB connections possible yet.
- `BgWorkerStart_ConsistentState` — after a standby reaches a consistent state
  (read-only queries OK).
- `BgWorkerStart_RecoveryFinished` — after full read-write; on a non-standby
  this is equivalent to ConsistentState. **A worker is not stopped when a later
  state is reached** — start-time only gates *when it may start*. [from-docs]

## Restart & lifecycle

- Worker is **auto-unregistered** (not restarted) if `bgw_restart_time =
  BGW_NEVER_RESTART`, OR it exits with code **0**, OR
  `TerminateBackgroundWorker()` was called. Otherwise it is restarted after
  `bgw_restart_time` seconds (immediately on a postmaster re-init). [from-docs]
- **`TerminateBackgroundWorker()`** sends `SIGTERM` and unregisters once stopped.
- Status: `GetBackgroundWorkerPid()` →
  `BGWH_NOT_YET_STARTED` / `BGWH_STARTED` (with pid) / `BGWH_STOPPED`.
  `WaitForBackgroundWorkerStartup()` / `…Shutdown()` block (require
  `bgw_notify_pid = MyProcPid`) and can return `BGWH_POSTMASTER_DIED`. [from-docs]
  [verified-by-code, via knowledge/files/src/backend/postmaster/bgworker.c.md]

## Connecting & running code

- **`BackgroundWorkerInitializeConnection(dbname, username, flags)`** /
  **`…ByOid(dboid, useroid, flags)`** — call **exactly one, exactly once**;
  cannot switch DBs after. NULL dbname → no specific DB (shared catalogs only);
  NULL username → **superuser**. Bypass flags: `BGWORKER_BYPASS_ALLOWCONN`,
  `BGWORKER_BYPASS_ROLELOGINCHECK`. [from-docs]
- **Signals start *blocked*;** unblock with `BackgroundWorkerUnblockSignals()`
  after installing handlers. To idle, use `WaitLatch()` with
  `WL_POSTMASTER_DEATH` rather than exiting. [from-docs]
- **`MyBgworkerEntry`** (global) points at the worker's copy of its registered
  struct — the channel for `bgw_extra`. [from-docs]

## The portability hazard (read before shipping)

- **Do not pass a by-reference `Datum` in `bgw_main_arg` for dynamic workers or
  under `EXEC_BACKEND`/Windows** — pointers (cstring/text) are invalid in the new
  process's address space. Pass a small `int32` index into a shared-memory array
  instead. This is the most common cross-platform bgworker bug. [from-docs]
- Workers should **not `LISTEN`** (no infrastructure consumes the notifications);
  they *can* `NOTIFY` (via SPI / `Async_Notify()`, delivered at commit). [from-docs]

## Limits

- **`max_worker_processes`** caps total registered workers cluster-wide — shared
  with parallel query, so an over-subscribed parallel workload can starve a
  custom worker (and vice-versa). [from-docs]
  [verified-by-code, via knowledge/idioms/bgworker-and-parallel.md]

## Links into corpus

- [[knowledge/idioms/bgworker-and-parallel.md]] — the idiom-level walkthrough
  (registration, DSM, parallel-query reuse of the same slot pool).
- [[knowledge/files/src/backend/postmaster/bgworker.c.md]] — postmaster-side
  registration, restart, and slot management.
- [[knowledge/files/src/include/postmaster/bgworker.h.md]] — the public struct +
  flag/constant definitions.
- [[knowledge/files/src/include/postmaster/bgworker_internals.h.md]] — the
  internal `RegisteredBgWorker` slot view.
- [[knowledge/docs-distilled/parallel-query.md]] — parallel workers draw from the
  same `max_worker_processes` pool.
- Skill: `gucs-bgworker-parallel` — registering workers + custom GUCs in C.

## Gaps / follow-ups

- The chapter's `worker_spi` contrib example (the canonical end-to-end bgworker)
  is referenced but not mined here; it is a good `pg-extension-anthropologist`
  target.
</content>
