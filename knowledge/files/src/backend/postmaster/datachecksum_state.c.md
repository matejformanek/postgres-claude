# `src/backend/postmaster/datachecksum_state.c`

- **Last verified commit:** `4abf411e2328`
- **Lines:** 1789
- **Source:** `source/src/backend/postmaster/datachecksum_state.c`

PG18 feature: online enable / disable of data checksums (without
having to shut down the cluster and run `pg_checksums`). This file
contains BOTH the state-transition logic (called from any backend
absorbing a procsignalbarrier) AND the launcher / worker background
processes that rewrite every page in the cluster while the database
is online. Header has an unusually long English-prose proof of the
synchronization model (sets `Bd`, `Bi`, `Be`, `Bo`, `Bg` of backends
in different states, and per-direction barrier sequencing).
[verified-by-code §datachecksum_state.c:1-176]

The four runtime states (in `data_checksums`):
- `off` — neither write nor verify
- `inprogress-on` — write, don't verify
- `on` — write and verify (the steady-state "enabled")
- `inprogress-off` — write, don't verify (transitioning down)

Direction:
- enable: `off → inprogress-on` (barrier) → rewrite all pages →
  `on` (barrier).
- disable: `on → inprogress-off` (barrier) → `off` (barrier).

## API / entry points

- **SQL-callable:**
  - `Datum enable_data_checksums(PG_FUNCTION_ARGS)` — checks role,
    parses cost_delay / cost_limit, calls
    `StartDataChecksumsWorkerLauncher(ENABLE_DATACHECKSUMS, ...)`.
    [verified-by-code §datachecksum_state.c:563-587]
  - `Datum disable_data_checksums(PG_FUNCTION_ARGS)` — same shape
    for DISABLE. [verified-by-code §datachecksum_state.c:544-561]
- **Barrier plumbing:**
  - `void EmitAndWaitDataChecksumsBarrier(uint32 state)` — wraps
    `EmitProcSignalBarrier` + `WaitForProcSignalBarrier` for the four
    barrier types. [verified-by-code §datachecksum_state.c:426-465]
  - `bool AbsorbDataChecksumsBarrier(ProcSignalBarrierType barrier)`
    — called by `ProcessProcSignalBarrier` in every backend. Looks
    up `(from, to)` in the static `checksum_barriers[9]` array; if
    the transition isn't valid, `ereport(ERROR)` so the procsignal
    machinery retries. Recovery skips validation (`RecoveryInProgress()`)
    since redo is trusted. [verified-by-code §datachecksum_state.c:467-540]
- **Launcher entry:**
  - `void StartDataChecksumsWorkerLauncher(op, cost_delay, cost_limit)`
    — under `DataChecksumsWorkerLock`, stores the desired
    operation/costs, then `RegisterDynamicBackgroundWorker` if
    not already running. The launcher is a
    `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`
    bgworker with `bgw_restart_time = BGW_NEVER_RESTART`. Idempotent:
    second call while a launcher is running does nothing (the
    launcher will pick up the new target state when it finishes its
    current iteration). [verified-by-code §datachecksum_state.c:603-665]
- **Launcher / worker mains:**
  - `void DataChecksumsWorkerLauncherMain(Datum arg)` — top-level
    launcher loop with a `goto again` for the "user changed mind
    mid-run" case. On enable, sets `inprogress-on`, calls
    `ProcessAllDatabases`, sets `on`. On disable, just sets `off`
    (no page rewrite needed). Reports progress via
    `pgstat_progress_*`. [verified-by-code §datachecksum_state.c:1093-1240]
  - `void DataChecksumsWorkerMain(Datum arg)` — per-database
    worker; opens the named DB, calls `BuildRelationList`, processes
    each relation. Reads cost params from shared state **under
    `DataChecksumsWorkerLock` EXCLUSIVE** (`:1569-1576`), and during
    processing periodically re-checks whether new cost settings were
    requested (`launch_cost_delay/limit != cost_delay/limit`), copying
    them across and resetting `VacuumCostDelay/Limit` under the same
    lock (`:1663-1681`). [verified-by-code §datachecksum_state.c:1544+ context]
- **Per-relation / per-database helpers (`static`):**
  - `ProcessSingleRelationFork(reln, forkNum, strategy)` — the inner
    loop. For each block: `ReadBufferExtended` + `LockBuffer
    EXCLUSIVE`, `START_CRIT_SECTION`, `MarkBufferDirty`, and
    `log_newpage_buffer` if `RelationNeedsWAL(reln) || forkNum ==
    INIT_FORKNUM`. Honours `vacuum_delay_point` between blocks.
    Checks abort flag every block. [verified-by-code §datachecksum_state.c:689-770]
  - `ProcessSingleRelationByOid(oid, strategy)` — wraps the above
    with `try_relation_open(AccessShareLock)`; if relation has been
    dropped, treats as success (no pages to checksum).
    [verified-by-code §datachecksum_state.c:775-...]
  - `ProcessDatabase(db)` — wraps a transaction around per-relation
    processing.
  - `ProcessAllDatabases()` — top-level loop. Sets
    `process_shared_catalogs = true` for the first DB (so shared
    catalogs are only processed once); falls back to per-DB
    relations after. On failure of ANY db, calls `SetDataChecksumsOff()`
    and ERRORs — "all or nothing". [verified-by-code §datachecksum_state.c:1248-1340]
  - `BuildDatabaseList()` / `BuildRelationList(temp, shared)` /
    `FreeDatabaseList(list)` — list-of-DB / list-of-rel constructors.
  - `WaitForAllTransactionsToFinish()` — used before snapshotting
    the DB list, to make sure new DBs that started concurrently are
    visible.
  - `DataChecksumsShmemRequest` / `launcher_exit` /
    `launcher_cancel_handler`.
- **Abort-request macros** — check `launch_operation` vs `operation`
  under shared lock; set `abort_requested` if they diverge. Called
  from inside the per-page loop. The cleanup cluster (window
  `419ce13b7019..4abf411e2328`) **split the single
  `CHECK_FOR_ABORT_REQUEST()` into two** —
  `CHECK_FOR_LAUNCHER_ABORT_REQUEST()` (`:401-408`) and
  `CHECK_FOR_WORKER_ABORT_REQUEST()` (`:410-417`) — to distinguish
  launcher vs worker invocations (`a4f02cab4b97`). The shared
  `abort_requested` flag is at `:369`.
  [verified-by-code §datachecksum_state.c:401-417]

## Notable invariants / details

- **Procsignal-barrier transition table.** `checksum_barriers[9]`
  enumerates the LEGAL `(from, to)` pairs. Any
  `AbsorbDataChecksumsBarrier` call with an unlisted pair raises
  ERROR (which procsignal turns into a retry). The table is the
  authoritative source for which transitions are valid; it's
  explicitly documented with prose blocks above each entry.
  [verified-by-code §datachecksum_state.c:238-277]
- **Full-page WAL for every dirtied buffer.** The reason is the
  primary may have valid checksums while a replica has different
  hint-bit content (due to FPI of an unlogged hint-bit change).
  Comment is explicit: only when checksums-on, then off, then on
  again does this hazard apply, but rewriting every page closes
  it. [from-comment §datachecksum_state.c:718-728]
- **INIT_FORKNUM exception.** Init forks of unlogged tables ARE
  logged — the standby may promote and copy that init fork to main
  fork; an unchecksummed init fork there would then fail
  verification. [from-comment §datachecksum_state.c:737-741]
- **Recovery trust:** `AbsorbDataChecksumsBarrier` shortcuts the
  validation check during `RecoveryInProgress()` — replay is
  authoritative. [verified-by-code §datachecksum_state.c:505-512]
- **No restartability across crash.** If the launcher is killed
  mid-run, the controlfile state is reverted to `off` on next
  startup (state `inprogress-on` observed → reset to `off`); the
  operator must re-run `pg_enable_data_checksums()`. The header
  prose lists this as a future improvement. [from-comment §datachecksum_state.c:39-41, 157-162]
- **"All-or-nothing".** A single database failure causes the worker
  to call `SetDataChecksumsOff()` and ERROR — no partial enable.
  [verified-by-code §datachecksum_state.c:1312-1320]
- **Cost-delay reuses vacuum cost machinery.**
  `vacuum_delay_point(false)` between blocks. Comment: "Processing
  is re-using the vacuum cost delay for process throttling, hence
  why we call vacuum APIs here." [from-comment §datachecksum_state.c:757-760]

## Potential issues

- **File-line `datachecksum_state.c:723-728`.** "TODO: investigate if
  this could be avoided if the checksum is calculated to be correct
  and wal_level is set to 'minimal'." Documented optimisation.
  [ISSUE-stale-todo: avoid WAL when checksum already matches (likely)]
- **File-line `datachecksum_state.c:149-176`.** The "Future
  opportunities for optimizations" comment lists 5+ items — restart
  from startup process, skip dirtying when checksum matches,
  pg_checksums resume, restartability, skip DBs created during
  inprogress-on, CREATE DATABASE inheriting from template. None
  scheduled. [ISSUE-stale-todo: post-v1 enhancements parking lot (nit)]
- **File-line `datachecksum_state.c:299-320` (RESOLVED as of `8d22f5232458`).**
  The old comment claimed the cost fields were "set when the launcher
  starts, and are only accessed read-only by the single worker. Thus, we
  can access these without a lock." Commit `8d22f5232458` ("Fix comments
  on data checksum cost settings") rewrote that comment to match the
  actual code: the worker reads cost params **under
  `DataChecksumsWorkerLock`** (`:1569-1576`) and periodically copies in
  newly-requested `launch_cost_*` values under the same lock
  (`:1663-1681`) — i.e. dynamic cost parameters ARE supported, with
  locking. The prior `[ISSUE-undocumented-invariant: lock-free reads only
  valid for single-worker]` no longer holds; the lock-free claim was the
  stale-comment bug this commit fixed. [verified-by-code]
- **File-line `datachecksum_state.c:748`.** `Assert(operation ==
  ENABLE_DATACHECKSUMS)` inside `ProcessSingleRelationFork`. If a
  future caller invokes this from a disable path, the assert fires
  in debug but the code silently does the right-ish thing in
  release. Better as a hard runtime check. [ISSUE-style: assert vs hard check on operation (nit)]
- **File-line `datachecksum_state.c:1218-1228`.** When the target state
  changes during processing, the launcher returns false, but the
  outer loop treats that as "ABORTED" and re-enters via `goto
  again` (`:1228`). The double-meaning of "false" (genuine failure vs
  re-target) is teased apart by re-acquiring the lock and checking
  `launch_operation != operation` (`:1221`) — that's three reads of the
  same pair under three different lock acquisitions. Worth a helper.
  [ISSUE-style: triple-check of launch_operation==operation pattern (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `postmaster`](../../../../issues/postmaster.md)
<!-- issues:auto:end -->
