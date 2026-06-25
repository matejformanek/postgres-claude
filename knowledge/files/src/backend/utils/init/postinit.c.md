# postinit.c

- **Source path:** `source/src/backend/utils/init/postinit.c`
- **Lines:** 1567
- **Last verified commit:** `f0a4f280b4d3` (2026-06-25; anchor-bump re-pin, cites shifted +6/+7)
- **Companion files:** `source/src/include/miscadmin.h` (InitPostgres flags, ProcessingMode), `tcop/postgres.c::PostgresMain` (caller), `postmaster/postmaster.c` (forks the child that ends up here), `init/miscinit.c` (Init{PostmasterChild,StandaloneProcess}), `storage/lmgr/proc.c::InitProcess[Phase2]`

## Purpose

Per-backend initialization. After `postmaster.c` has forked the child and `InitPostmasterChild()` / `InitProcess()` have set up the basic environment + a `PGPROC`, this file finishes the job: opens XLOG (in standalone/bootstrap), wires the proc into the ProcArray, performs authentication, looks up the target database in `pg_database` under a `RowExclusiveLock`, sets `MyDatabaseId`, validates the cluster files, runs `process_settings` to apply `pg_db_role_setting`, fires session preloads, and finally returns to `PostgresMain` ready to accept queries. [from-comment, postinit.c:713-720 ("Be very careful with the order of calls")]

## Top-of-file comment (verbatim)

> "postinit.c — postgres initialization utilities" — terse one-liner; the substantive prose lives at `InitPostgres`'s function header (lines 679-720). [from-comment, postinit.c:1-15, 679-720]

## Public surface

- `pg_split_opts(argv, argcp, optstr)` (507) — tokenize a `-c key=value` style command-line option string into argv (used by backend launchers and EXEC_BACKEND path).
- `PostgresSingleUserMain` — actually defined in `tcop/postgres.c`, but the typical caller graph routes through `BaseInit` + `InitPostgres` here.
- `InitializeMaxBackends` (565) and `InitializeFastPathLocks` (590) — must be called after shared_preload_libraries have run but before shared memory sizing. [from-comment, postinit.c:585-589]
- `BaseInit(void)` (622) — early backend init (also used by auxiliary processes that don't call `InitPostgres`); brings up `DebugFileOpen`, `InitFileAccess`, `pgstat_initialize`, `pgaio_init_backend`, `InitSync`, `smgrinit`, `InitBufferManagerAccess`, `InitTemporaryFileAccess`, `InitXLogInsert`, `InitLockManagerAccess`, `ReplicationSlotInitialize`. [verified-by-code, postinit.c:622-677]
- `InitPostgres(in_dbname, dboid, username, useroid, flags, out_dbname)` (722) — the main per-connection init. Flags include `INIT_PG_LOAD_SESSION_LIBS`, `INIT_PG_OVERRIDE_ALLOW_CONNS`, `INIT_PG_OVERRIDE_ROLE_LOGIN`. Returns to caller with everything ready for query processing.
- `EnterParallelMode` / `ExitParallelMode` are NOT here — they live in `access/transam/parallel.c`.

## Static helpers

- `GetDatabaseTuple` (120), `GetDatabaseTupleByOid` — minimal pg_database lookups that work without a full relcache (hardwired descriptor fallback). [from-comment, postinit.c:109-119]
- `PerformAuthentication` (decl 89, def 209) — runs ClientAuthentication, sets `MyClientConnectionInfo.authn_id`.
- `CheckMyDatabase` (decl 90, def 338) — datistemplate / datallowconn / datconnlimit checks; runs after we hold the DB lock and have re-read `pg_database`.
- `ShutdownPostgres` (91) — `before_shmem_exit` callback that runs `AbortOutOfAnyTransaction` and `LockReleaseAll` on backend exit.
- Timeout handlers: `StatementTimeoutHandler` etc. (92-98).
- `process_startup_options` (decl 100, def 1298) — parse `-c name=value` GUC options from the startup packet.
- `process_settings` (decl 101, def 1363) — apply `pg_db_role_setting` rows in DB / role / DB+role order.
- `EmitConnectionWarnings` (102) — replays warnings accumulated during init once the client connection is up.

## The InitPostgres pipeline (ordering matters!)

The comment at line 718 says: *"Be very careful with the order of calls in the InitPostgres function."* Critical observed sequence (postinit.c:722-1295):

1. `InitProcessPhase2` (740) — adds our PGPROC to the ProcArray. **"Once I have done this, I am visible to other backends!"** [from-comment, postinit.c:738]
2. `pgstat_beinit` + `pgstat_bestart_initial` (743, 752) — preliminary stats entry, before auth.
3. `SharedInvalBackendInit` (760) — sinval slot.
4. `HOLD_INTERRUPTS` → `ProcSignalInit(MyCancelKey, MyCancelKeyLength)` (770) → `InitLocalDataChecksumState` (788) → `RESUME_INTERRUPTS` (790). Interrupts held so the local checksum state is set before any procsignal barrier could change it. [from-comment, postinit.c:761-787]
5. `RegisterTimeout(...)` x7 (798-806) — DEADLOCK, STATEMENT, LOCK, IDLE_IN_TRANSACTION, TRANSACTION, IDLE_SESSION, CLIENT_CONNECTION_CHECK, IDLE_STATS_UPDATE.
6. If `!IsUnderPostmaster`: `CreateAuxProcessResourceOwner` (823) → `StartupXLOG` (825) → `before_shmem_exit(ShutdownXLOG, 0)` (836).
7. `InitializeProcessXLogLogicalInfo` (847) — must follow `ProcSignalInit` (to receive barriers) and (in standalone) `StartupXLOG` (to have shared state).
8. `RelationCacheInitialize` → `InitCatalogCache` → `InitPlanCache` (855-857) — set up hashes only, no catalog access yet ("we must do this before starting a transaction because transaction abort would try to touch these hashtables").
9. `EnablePortalManager` (860).
10. `RelationCacheInitializePhase2` (866) — load relcache entries for *shared* catalogs (pg_database, pg_authid).
11. `before_shmem_exit(ShutdownPostgres, 0)` (877) — must be registered before first xact so abort path is clean.
12. If `AmAutoVacuumLauncherProcess()` → finalize beentry and return (autovac launcher needs nothing more) (880-886).
13. `StartTransactionCommand` (895) — first real xact, downgraded to READ COMMITTED in hot standby.
14. **Authentication branch** (914-955):
    - bootstrap / autovacuum worker / slotsync worker → `InitializeSessionUserIdStandalone`, `am_superuser = true`.
    - `!IsUnderPostmaster` (single-user) → standalone, superuser; warn if no roles defined.
    - background worker / data-checksums worker → either standalone or `InitializeSessionUserId(username, useroid, INIT_PG_OVERRIDE_ROLE_LOGIN?)`.
    - Otherwise (normal client connection) → `PerformAuthentication(MyProcPort)` (948) → `InitializeSessionUserId` → `InitializeSystemUser`.
15. Binary-upgrade superuser check (`IsBinaryUpgrade && !am_superuser`, 968); reserved connection slot check; walsender replication-role check.
16. **Walsender-only fast exit** (~1021-1044): physical walsender doesn't bind to a DB; `process_startup_options` (1025), `pgstat_bestart_final` (1035), `CommitTransactionCommand` (1038), return.
17. **Database resolution** (~1047-1154): `GetDatabaseTuple(in_dbname)` (1063, or by oid); `LockSharedObject(DatabaseRelationId, dboid, 0, RowExclusiveLock)` (1109) **— blocks against concurrent DROP DATABASE**; recheck `pg_database` after the lock (comment at 1112); set `MyDatabaseTableSpace` (1149), `MyDatabaseHasLoginEventTriggers`.
18. `MyDatabaseId = dboid` (1167) and `MyProc->databaseId = MyDatabaseId` (1181). **Ordering note:** id is set only after we hold the lock that prevents drop/rename, so pgstat etc. can't create entries for a doomed DB. [from-comment, postinit.c:1159-1166]
19. `InvalidateCatalogSnapshot` (1189) — the catalog snapshot taken during pg_authid / pg_database reads is now suspect (we weren't reacting to sinval for unshared catalogs yet).
20. `GetDatabasePath` (1195) + `access()` check + `ValidatePgVersion` (1215); `SetDatabasePath` (1218).
21. `RelationCacheInitializePhase3` (1227) — load *unshared* nailed relcache entries.
22. `initialize_acl` (1230); `CheckMyDatabase` call (1239) — datallowconn, datconnlimit, locale.
23. `process_startup_options` (1248), `process_settings` (1251), `PostAuthDelay` (1254), `InitializeSearchPath` (1263), `InitializeClientEncoding` (1266), `InitializeSession`.
24. `process_session_preload_libraries` if `INIT_PG_LOAD_SESSION_LIBS` (1279).
25. `pgstat_bestart_final` (1283) and `CommitTransactionCommand` (1287) — close the init xact. `EmitConnectionWarnings` deferred until first real query so warnings are seen on a live wire protocol.

## Key invariants

- **`MyProc` must already exist before `InitPostgres` runs.** Asserted at `BaseInit` (line 624: `Assert(MyProc != NULL)`). InitProcess (proc.c) is called from `AuxiliaryProcessMainCommon` / `BackgroundWorkerInitializeConnection` / `BackendStartup` before reaching here. [verified-by-code]
- **ProcArray insertion (`InitProcessPhase2`) is irrevocable visibility.** All later FATAL paths must reach `ProcArrayEndTransaction` via the `ShutdownPostgres` `before_shmem_exit` to remove us. [from-comment, postinit.c:736-739]
- **`MyDatabaseId` must not be set until the database is locked with `RowExclusiveLock`.** A concurrent `DROP DATABASE` would otherwise see us in the ProcArray with a stale id; pgstat would create dangling entries. [from-comment, postinit.c:1087-1107, 1159-1180]
- **Catalog snapshot taken before `MyDatabaseId` is set is unsafe** and must be invalidated explicitly (line 1189).
- **Timeout handlers cannot run in bootstrap mode** (the `if (!bootstrap)` guard at 796).
- **Standalone backend / bootstrap drives XLOG itself** (StartupXLOG inline at line 825); under postmaster the startup process and checkpointer handle XLOG lifecycle. [from-comment, postinit.c:810-816]

## Cross-references

- Called by `PostgresMain` (tcop/postgres.c) for normal client connections, by `AutoVacWorkerMain` / `AutoVacLauncherMain`, by `BackgroundWorkerInitializeConnection*` (bgworker.c), by walsender startup, by `BootstrapModeMain`.
- `BaseInit` also called by auxiliary processes (checkpointer, bgwriter, walwriter, archiver) via `AuxiliaryProcessMainCommon`.
- Calls `StartupXLOG` (access/transam/xlog.c) in single-user case; `ProcessLocalLatch` setup happens earlier in miscinit.c.
- Hard cross-link to `knowledge/files/src/backend/storage/lmgr/proc.c.md` for the PGPROC side of InitProcess[Phase2].

## Open questions

- Exact failure cascade if `PerformAuthentication` errors after `InitProcessPhase2` but before `MyDatabaseId` is set — `ShutdownPostgres` is registered earlier (line 871) so AbortTransaction should run, but pg_authid reads happen *before* it under bootstrap-only branch. [unverified]
- Whether `INIT_PG_OVERRIDE_ALLOW_CONNS` is a security boundary or operational convenience — only `pg_dumpall`-style tooling appears to use it. [unverified]

## Confidence tag tally

`[verified-by-code]=14 [from-comment]=9 [from-readme]=0 [inferred]=0 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
