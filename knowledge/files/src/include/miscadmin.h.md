# `src/include/miscadmin.h`

- **Last verified commit:** `f0a4f280b4d3` (2026-06-25; clean re-pin — all major cites hold ±2: InterruptPending :90, CHECK_FOR_INTERRUPTS :125, SECURITY_* :321-323, BackendType :340, ProcessingMode :477, INIT_PG flags :508-510, shmem_request_hook :546)
- **Lines:** 555
- **Source:** `source/src/include/miscadmin.h`

The process-wide globals + signal handlers + initialization API
collation header. The opening comment is candid: this used to be
multiple files (`globals.h`, `pdir.h`, `pinit.h`, `pmod.h`); they got
merged and then "this has also become the preferred place for widely
known resource-limitation stuff, such as work_mem and
check_stack_depth()" (`miscadmin.h:5-11`). [from-comment]

The file pulls in `<signal.h>`, `datatype/timestamp.h`, and `pgtime.h`,
then declares dozens of process-globals. Six logical sections marked
by banner comments: (1) interrupt/critical-section handling, (2)
globals.h (the big PGDLLIMPORT block), (3) pdir.h (data dir + user
ID), (4) pmod.h (ProcessingMode), (5) pinit.h (InitPostgres etc.).

## API / declarations

### Interrupt / critical-section machinery (`miscadmin.h:35-158`)

The signal-cooperation contract: signal handlers set `volatile
sig_atomic_t` flags; CHECK_FOR_INTERRUPTS() drains them at safe
points. The volatile flags:

- `InterruptPending` (`miscadmin.h:90`) — master flag set whenever
  any cancel/die/timeout signal arrives.
- `QueryCancelPending`, `ProcDiePending`, `ProcDieSenderPid`,
  `ProcDieSenderUid` — set by SIGINT/SIGTERM handlers.
- `IdleInTransactionSessionTimeoutPending`, `TransactionTimeoutPending`,
  `IdleSessionTimeoutPending` — timeout subsystem.
- `ProcSignalBarrierPending`, `LogMemoryContextPending`,
  `IdleStatsUpdateTimeoutPending` — per-process custom signals.
- `CheckClientConnectionPending`, `ClientConnectionLost`.
- Counts: `InterruptHoldoffCount`, `QueryCancelHoldoffCount`,
  `CritSectionCount`.

Macros:
- `INTERRUPTS_PENDING_CONDITION()` (`miscadmin.h:115`) — bare
  `unlikely(InterruptPending)` on Unix; Win32 also drains the queued
  signal queue first.
- `CHECK_FOR_INTERRUPTS()` (`miscadmin.h:125-129`) — drain via
  `ProcessInterrupts()`.
- `INTERRUPTS_CAN_BE_PROCESSED()` (`miscadmin.h:132-134`) — all three
  hold counts are zero.
- `HOLD_INTERRUPTS()` / `RESUME_INTERRUPTS()` — bump/decrement
  `InterruptHoldoffCount`.
- `HOLD_CANCEL_INTERRUPTS()` / `RESUME_CANCEL_INTERRUPTS()` — affects
  only cancel, not die.
- `START_CRIT_SECTION()` / `END_CRIT_SECTION()` — within a crit
  section, any `ereport(ERROR)` becomes `ereport(PANIC)`
  (`miscadmin.h:79-84`). XLOG insertion is the only in-tree user.
- `ProcessInterrupts(void)` (`miscadmin.h:111`) — the actual drain
  routine, defined in `tcop/postgres.c`.

### Globals (`miscadmin.h:161-292`)

Process-identity:
- `PostmasterPid`, `IsPostmasterEnvironment`, `IsUnderPostmaster`,
  `IsBinaryUpgrade`, `ExitOnAnyError`.
- `DataDir`, `data_directory_mode`.
- `NBuffers`, `MaxBackends`, `MaxConnections`, `max_worker_processes`,
  `max_parallel_workers`, `autovacuum_max_parallel_workers`.
- SLRU buffer counts: `commit_timestamp_buffers`,
  `multixact_member_buffers`, `multixact_offset_buffers`,
  `notify_buffers`, `serializable_buffers`, `subtransaction_buffers`,
  `transaction_buffers`.
- `MyProcPid`, `MyStartTime`, `MyStartTimestamp`, `MyProcPort`,
  `MyLatch`, `MyCancelKey[]`, `MyCancelKeyLength`, `MyPMChildSlot`.
- `OutputFileName[]`, `my_exec_path[]`, `pkglib_path[]`,
  `postgres_exec_path[]` (EXEC_BACKEND only).
- `MyDatabaseId`, `MyDatabaseTableSpace`,
  `MyDatabaseHasLoginEventTriggers`.

DateStyle/Order (`miscadmin.h:216-251`):
- `USE_POSTGRES_DATES`, `USE_ISO_DATES`, `USE_SQL_DATES`,
  `USE_GERMAN_DATES`, `USE_XSD_DATES`.
- `DATEORDER_YMD`, `DATEORDER_DMY`, `DATEORDER_MDY`.
- `DateStyle`, `DateOrder` globals.

IntervalStyle:
- `INTSTYLE_POSTGRES`, `INTSTYLE_POSTGRES_VERBOSE`,
  `INTSTYLE_SQL_STANDARD`, `INTSTYLE_ISO_8601`.

`MAXTZLEN = 10`.

Resource limits:
- `enableFsync`, `allowSystemTableMods`, `work_mem`,
  `hash_mem_multiplier`, `maintenance_work_mem`,
  `max_parallel_maintenance_workers`.
- `MIN_BAS_VAC_RING_SIZE_KB = 128`, `MAX_BAS_VAC_RING_SIZE_KB = 16 GB`.
- `VacuumBufferUsageLimit`, `VacuumCostPageHit/Miss/Dirty`,
  `VacuumCostLimit`, `VacuumCostDelay`, `VacuumCostBalance`,
  `VacuumCostActive`.

Stack-depth (`miscadmin.h:295-308`):
- `max_stack_depth` GUC.
- `STACK_DEPTH_SLOP = 512 KB`.
- `pg_stack_base_t set_stack_base(void)`, `restore_stack_base`,
  `check_stack_depth`, `stack_is_too_deep`, `get_stack_depth_rlimit`.

`PreventCommandIfReadOnly/IfParallelMode/DuringRecovery` (`miscadmin.h:310-313`).

### Security-context flags (`miscadmin.h:319-323`)

- `SECURITY_LOCAL_USERID_CHANGE = 0x0001`
- `SECURITY_RESTRICTED_OPERATION = 0x0002`
- `SECURITY_NOFORCE_RLS = 0x0004`

`DatabasePath` global.

### Init API (`miscadmin.h:325-332`)

- `InitPostmasterChild`, `InitStandaloneProcess(argv0)`,
  `InitProcessLocalLatch`, `SwitchToSharedLatch`,
  `SwitchBackToLocalLatch`.

### BackendType enum (`miscadmin.h:340-381`)

- `B_INVALID=0`, `B_BACKEND`, `B_DEAD_END_BACKEND`,
  `B_AUTOVAC_LAUNCHER`, `B_AUTOVAC_WORKER`, `B_BG_WORKER`,
  `B_WAL_SENDER`, `B_SLOTSYNC_WORKER`, `B_STANDALONE_BACKEND`.
- Auxiliary: `B_ARCHIVER`, `B_BG_WRITER`, `B_CHECKPOINTER`,
  `B_IO_WORKER`, `B_STARTUP`, `B_WAL_RECEIVER`, `B_WAL_SUMMARIZER`,
  `B_WAL_WRITER`.
- `B_DATACHECKSUMSWORKER_LAUNCHER`, `B_DATACHECKSUMSWORKER_WORKER`.
- `B_LOGGER` — no shared mem, no PGPROC.
- `BACKEND_NUM_TYPES = B_LOGGER + 1`.
- `MyBackendType` global; `Am{...}Process()` predicate macros
  (`miscadmin.h:387-403`).
- `IsExternalConnectionBackend(bt)` — true for `B_BACKEND` or
  `B_WAL_SENDER` (`miscadmin.h:414-415`).
- `GetBackendTypeDesc(bt)` — human-readable name.

### User ID / auth API (`miscadmin.h:424-450`)

- `GetUserNameFromId(roleid, noerr)`.
- `GetUserId`, `GetOuterUserId`, `GetSessionUserId`,
  `GetSessionUserIsSuperuser`, `GetAuthenticatedUserId`,
  `SetAuthenticatedUserId`.
- `GetUserIdAndSecContext(&userid, &sec_context)`,
  `SetUserIdAndSecContext(userid, sec_context)`.
- `InLocalUserIdChange`, `InSecurityRestrictedOperation`,
  `InNoForceRLSOperation`.
- `GetUserIdAndContext` / `SetUserIdAndContext` (legacy bool variant).
- `InitializeSessionUserId(rolename, roleid, bypass_login_check)`.
- `InitializeSessionUserIdStandalone()`.
- `SetSessionAuthorization(userid, is_superuser)`.
- `GetCurrentRoleId` / `SetCurrentRoleId`.
- `InitializeSystemUser(authn_id, auth_method)` / `GetSystemUser`.
- `superuser()` / `superuser_arg(roleid)`.

### Processing mode (`miscadmin.h:477-498`)

- `ProcessingMode { BootstrapProcessing, InitProcessing,
  NormalProcessing }` + `Mode` global.
- `IsBootstrapProcessingMode()`, `IsInitProcessingMode()`,
  `IsNormalProcessingMode()`, `SetProcessingMode(mode)`.

### Full init (`miscadmin.h:506-549`)

- `InitPostgres(in_dbname, dboid, username, useroid, flags,
  out_dbname)` with flags:
  - `INIT_PG_LOAD_SESSION_LIBS = 0x0001`
  - `INIT_PG_OVERRIDE_ALLOW_CONNS = 0x0002`
  - `INIT_PG_OVERRIDE_ROLE_LOGIN = 0x0004`
- `InitializeMaxBackends`, `InitializeFastPathLocks`, `BaseInit`.
- `StoreConnectionWarning(msg, detail)`.
- `pg_split_opts(argv, argcp, optstr)`.
- `IgnoreSystemIndexes`, `process_shared_preload_libraries_in_progress/done`,
  `process_shmem_requests_in_progress`,
  `session_preload_libraries_string`, `shared_preload_libraries_string`,
  `local_preload_libraries_string`.
- `CreateDataDirLockFile(amPostmaster)`,
  `CreateSocketLockFile(socketfile, amPostmaster, socketDir)`,
  `TouchSocketLockFiles`, `AddToDataDirLockFile(target_line, str)`,
  `RecheckDataDirLockFile`, `ValidatePgVersion(path)`.
- `process_shared_preload_libraries`, `process_session_preload_libraries`,
  `process_shmem_requests`.
- `pg_bindtextdomain`, `has_rolreplication(roleid)`.
- `shmem_request_hook_type shmem_request_hook` global hook.
- `EstimateClientConnectionInfoSpace`, `SerializeClientConnectionInfo`,
  `RestoreClientConnectionInfo` — parallel-worker handoff.
- `get_hash_memory_limit()` (from `executor/nodeHash.c`).

## Notable invariants / details

- All interrupt-pending flags are `volatile sig_atomic_t` — the only
  type C guarantees can be atomically set in a signal handler. New
  per-process flags MUST follow this pattern (`miscadmin.h:89`).
  [from-comment]
- `CHECK_FOR_INTERRUPTS()` is the cooperation point. Long loops in
  user-facing code (sort, scan, JSON parse, regex) MUST call it
  every N iterations. There's no central registry of "places that
  need CFI"; new long loops can silently make queries
  uncancellable. [inferred]
- A critical section converts ERROR→PANIC. **Only XLOG insertion uses
  it currently** (`miscadmin.h:81-84`). Adding new crit sections is
  a major decision — a recoverable error inside one crashes the
  cluster. [from-comment]
  [ISSUE-defense-in-depth: no header-level guidance for "should this
  be a crit section?" — answer is almost always no (likely)]
- `HOLD_CANCEL_INTERRUPTS()` vs `HOLD_INTERRUPTS()` — the former
  blocks query cancel but still allows process die. Code that wants
  cleanup-on-die-only uses HOLD_CANCEL_INTERRUPTS. [from-comment]
- `MyDatabaseHasLoginEventTriggers` is a per-backend cached flag —
  set during InitPostgres. Modifying login event triggers requires a
  connection-restart to see the change. [inferred]
  [ISSUE-undocumented-invariant: `MyDatabaseHasLoginEventTriggers` is
  per-session, stale across CREATE EVENT TRIGGER (maybe)]
- `MyCancelKey` is the legacy 4-byte cancel key used in the wire
  protocol. Modern code uses 256-byte keys (length in
  `MyCancelKeyLength`). [verified-by-code]
- `STACK_DEPTH_SLOP = 512 KB` — the headroom between `max_stack_depth`
  GUC and actual kernel limit. Recursive code that exhausts this margin
  hits SIGSEGV instead of the friendly `check_stack_depth` ereport.
  [from-comment]
- `SECURITY_*` flags are bitfield ORed into `sec_context`. New flags
  must use unused bits; documented none. [verified-by-code]
  [ISSUE-undocumented-invariant: SECURITY_* bit allocation policy is
  comment-only (nit)]
- `ProcessingMode` controls many subtle behaviors —
  `IsBootstrapProcessingMode` skips ACL checks, uses XID 1, etc.
  Modifying it via `SetProcessingMode` outside postinit.c is a
  recipe for corruption. The macro has an Assert
  (`miscadmin.h:493-498`).
- `BackendType` enum — new entries MUST update `child_process_kinds`
  in `launch_backend.c` AND `NUM_AUXILIARY_PROCS` (`miscadmin.h:336-338`).
  Header comment is explicit. [from-comment]
- `shared_preload_libraries_string` is the parsed-once string;
  callbacks fire from `process_shared_preload_libraries()`. After
  `process_shared_preload_libraries_done` is true, late-loading is
  not equivalent. [inferred]
- `shmem_request_hook` is a single-global hook; multi-extension
  installations must chain. No header-level hook-chain idiom.
  [ISSUE-defense-in-depth: shmem_request_hook chaining is
  extension-author's responsibility, not enforced (likely)]

## Potential issues

- `miscadmin.h:198-199` — `MyCancelKey[]` is the cancel key buffer;
  fixed size is in the implementation. Header gives no size hint.
  [ISSUE-doc-drift: MyCancelKey array size opaque at header (nit)]
- `miscadmin.h:269-273` — `work_mem` etc. exposed as mutable
  PGDLLIMPORT `int`. An extension can scribble on these mid-query
  with no protection. [ISSUE-defense-in-depth: tuning GUCs mutable
  via direct symbol access (nit)]
- `miscadmin.h:319-323` — `SECURITY_*` flags are 3 bits used out of
  presumably 32. No `SECURITY_MAX_BIT` constant, no comment about
  reserved bits. [ISSUE-style: SECURITY_* allocation discipline not
  documented (nit)]
- `miscadmin.h:340-381` — BackendType enum is a hard-coded list;
  pluggable extension worker types (logical replication apply
  workers) lump into `B_BG_WORKER`. [ISSUE-api-shape: BackendType
  not extensible (likely)]
- `miscadmin.h:438-440` —
  `InitializeSessionUserId(..., bypass_login_check)` is a bare
  bool. Calls with `true` bypass NOLOGIN checks — a security-sensitive
  flag with no enum naming. [ISSUE-security: bypass_login_check is
  bare bool; misuse silently bypasses NOLOGIN (likely)]
- `miscadmin.h:506-510` — `INIT_PG_OVERRIDE_ROLE_LOGIN = 0x0004`
  flag bypasses LOGIN check; pg_upgrade uses it. New callers must
  not. No "INTERNAL USE ONLY" marker. [ISSUE-security:
  INIT_PG_OVERRIDE_ROLE_LOGIN is dangerous, no header marker
  (likely)]
- `miscadmin.h:544` — `shmem_request_hook` exported as mutable
  PGDLLIMPORT — extension that overwrites instead of chaining loses
  prior subscriber. [ISSUE-defense-in-depth: shmem_request_hook
  single-global chaining hazard (likely)]
- `miscadmin.h:128` — `CHECK_FOR_INTERRUPTS()` is a do/while macro;
  if a caller writes `if (cond) CHECK_FOR_INTERRUPTS(); else ...`
  the semicolon hazard is real but caught by Wempty-body.
  [ISSUE-style: trivial — already mitigated by do/while pattern (nit)]
- `miscadmin.h:108` — `CritSectionCount` is `volatile uint32`. A
  buggy mis-paired `END_CRIT_SECTION` without `START` underflows
  to 0xFFFFFFFF, silently enabling crit-section semantics globally.
  Assert in macro catches under cassert (`miscadmin.h:154-156`) but
  release builds wrap. [ISSUE-correctness: CritSectionCount
  underflow on mis-pairing silent in release (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
