# postinit.c

- **Source path:** `source/src/backend/utils/init/postinit.c`
- **Lines:** 1553
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/miscadmin.h` (InitPostgres flags, ProcessingMode), `tcop/postgres.c::PostgresMain` (caller), `postmaster/postmaster.c` (forks the child that ends up here), `init/miscinit.c` (Init{PostmasterChild,StandaloneProcess}), `storage/lmgr/proc.c::InitProcess[Phase2]`

## Purpose

Per-backend initialization. After `postmaster.c` has forked the child and `InitPostmasterChild()` / `InitProcess()` have set up the basic environment + a `PGPROC`, this file finishes the job: opens XLOG (in standalone/bootstrap), wires the proc into the ProcArray, performs authentication, looks up the target database in `pg_database` under a `RowExclusiveLock`, sets `MyDatabaseId`, validates the cluster files, runs `process_settings` to apply `pg_db_role_setting`, fires session preloads, and finally returns to `PostgresMain` ready to accept queries. [from-comment, postinit.c:707-714 ("Be very careful with the order of calls")]

## Top-of-file comment (verbatim)

> "postinit.c — postgres initialization utilities" — terse one-liner; the substantive prose lives at `InitPostgres`'s function header (lines 673-714). [from-comment, postinit.c:1-15, 673-714]

## Public surface

- `pg_split_opts(argv, argcp, optstr)` (501) — tokenize a `-c key=value` style command-line option string into argv (used by backend launchers and EXEC_BACKEND path).
- `PostgresSingleUserMain` — actually defined in `tcop/postgres.c`, but the typical caller graph routes through `BaseInit` + `InitPostgres` here.
- `InitializeMaxBackends` (558) and `InitializeFastPathLocks` (583) — must be called after shared_preload_libraries have run but before shared memory sizing. [from-comment, postinit.c:578-582]
- `BaseInit(void)` (615) — early backend init (also used by auxiliary processes that don't call `InitPostgres`); brings up `DebugFileOpen`, `InitFileAccess`, `pgstat_initialize`, `pgaio_init_backend`, `InitSync`, `smgrinit`, `InitBufferManagerAccess`, `InitTemporaryFileAccess`, `InitXLogInsert`, `InitLockManagerAccess`, `ReplicationSlotInitialize`. [verified-by-code, postinit.c:615-670]
- `InitPostgres(in_dbname, dboid, username, useroid, flags, out_dbname)` (715) — the main per-connection init. Flags include `INIT_PG_LOAD_SESSION_LIBS`, `INIT_PG_OVERRIDE_ALLOW_CONNS`, `INIT_PG_OVERRIDE_ROLE_LOGIN`. Returns to caller with everything ready for query processing.
- `EnterParallelMode` / `ExitParallelMode` are NOT here — they live in `access/transam/parallel.c`.

## Static helpers

- `GetDatabaseTuple` (113), `GetDatabaseTupleByOid` — minimal pg_database lookups that work without a full relcache (hardwired descriptor fallback). [from-comment, postinit.c:102-112]
- `PerformAuthentication` — runs ClientAuthentication, sets `MyClientConnectionInfo.authn_id`.
- `CheckMyDatabase` (84) — datistemplate / datallowconn / datconnlimit checks; runs after we hold the DB lock and have re-read `pg_database`.
- `ShutdownPostgres` (85) — `before_shmem_exit` callback that runs `AbortOutOfAnyTransaction` and `LockReleaseAll` on backend exit.
- Timeout handlers: `StatementTimeoutHandler` etc. (86-92).
- `process_startup_options` (94, 1292) — parse `-c name=value` GUC options from the startup packet.
- `process_settings` (95, 1357) — apply `pg_db_role_setting` rows in DB / role / DB+role order.
- `EmitConnectionWarnings` (96) — replays warnings accumulated during init once the client connection is up.

## The InitPostgres pipeline (ordering matters!)

The comment at line 712 says: *"Be very careful with the order of calls in the InitPostgres function."* Critical observed sequence (postinit.c:715-1290):

1. `InitProcessPhase2` (734) — adds our PGPROC to the ProcArray. **"Once I have done this, I am visible to other backends!"** [from-comment, postinit.c:732]
2. `pgstat_beinit` + `pgstat_bestart_initial` (737, 746) — preliminary stats entry, before auth.
3. `SharedInvalBackendInit` (754) — sinval slot.
4. `HOLD_INTERRUPTS` → `ProcSignalInit(MyCancelKey, MyCancelKeyLength)` (762-764) → `InitLocalDataChecksumState` (782) → `RESUME_INTERRUPTS` (784). Interrupts held so the local checksum state is set before any procsignal barrier could change it. [from-comment, postinit.c:755-781]
5. `RegisterTimeout(...)` x7 (792-801) — DEADLOCK, STATEMENT, LOCK, IDLE_IN_TRANSACTION, TRANSACTION, IDLE_SESSION, CLIENT_CONNECTION_CHECK, IDLE_STATS_UPDATE.
6. If `!IsUnderPostmaster`: `CreateAuxProcessResourceOwner` → `StartupXLOG` → `before_shmem_exit(ShutdownXLOG, 0)` (810-831).
7. `InitializeProcessXLogLogicalInfo` (841) — must follow `ProcSignalInit` (to receive barriers) and (in standalone) `StartupXLOG` (to have shared state).
8. `RelationCacheInitialize` → `InitCatalogCache` → `InitPlanCache` (849-851) — set up hashes only, no catalog access yet ("we must do this before starting a transaction because transaction abort would try to touch these hashtables").
9. `EnablePortalManager` (854).
10. `RelationCacheInitializePhase2` (860) — load relcache entries for *shared* catalogs (pg_database, pg_authid).
11. `before_shmem_exit(ShutdownPostgres, 0)` (871) — must be registered before first xact so abort path is clean.
12. If `AmAutoVacuumLauncherProcess()` → finalize beentry and return (autovac launcher needs nothing more) (874-880).
13. `StartTransactionCommand` (889) — first real xact, downgraded to READ COMMITTED in hot standby.
14. **Authentication branch** (908-949):
    - bootstrap / autovacuum worker / slotsync worker → `InitializeSessionUserIdStandalone`, `am_superuser = true`.
    - `!IsUnderPostmaster` (single-user) → standalone, superuser; warn if no roles defined.
    - background worker / data-checksums worker → either standalone or `InitializeSessionUserId(username, useroid, INIT_PG_OVERRIDE_ROLE_LOGIN?)`.
    - Otherwise (normal client connection) → `PerformAuthentication(MyProcPort)` → `InitializeSessionUserId` → `InitializeSystemUser`.
15. Binary-upgrade superuser check (962-967); reserved connection slot check (979-994); walsender replication-role check (997-1007).
16. **Walsender-only fast exit** (1015-1038): physical walsender doesn't bind to a DB; process startup options, commit xact, return.
17. **Database resolution** (1041-1148): `GetDatabaseTuple(in_dbname)` (or by oid); `LockSharedObject(DatabaseRelationId, dboid, 0, RowExclusiveLock)` (1103) **— blocks against concurrent DROP DATABASE**; recheck `pg_database` after the lock (1115-1131); set `MyDatabaseTableSpace`, `MyDatabaseHasLoginEventTriggers`.
18. `MyDatabaseId = dboid` (1161) and `MyProc->databaseId = MyDatabaseId` (1175). **Ordering note:** id is set only after we hold the lock that prevents drop/rename, so pgstat etc. can't create entries for a doomed DB. [from-comment, postinit.c:1153-1160]
19. `InvalidateCatalogSnapshot` (1183) — the catalog snapshot taken during pg_authid / pg_database reads is now suspect (we weren't reacting to sinval for unshared catalogs yet).
20. `GetDatabasePath` + `access()` check + `ValidatePgVersion` (1189-1212); `SetDatabasePath`.
21. `RelationCacheInitializePhase3` (1221) — load *unshared* nailed relcache entries.
22. `initialize_acl` (1224); `CheckMyDatabase` (1232-1234) — datallowconn, datconnlimit, locale.
23. `process_startup_options` (1242), `process_settings` (1245), `PostAuthDelay` (1248), `InitializeSearchPath`, `InitializeClientEncoding`, `InitializeSession` (1257-1263).
24. `process_session_preload_libraries` if `INIT_PG_LOAD_SESSION_LIBS` (1272-1273).
25. `pgstat_bestart_final` and `CommitTransactionCommand` (1277, 1280) — close the init xact. `EmitConnectionWarnings` deferred until first real query so warnings are seen on a live wire protocol.

## Key invariants

- **`MyProc` must already exist before `InitPostgres` runs.** Asserted at `BaseInit` (line 618: `Assert(MyProc != NULL)`). InitProcess (proc.c) is called from `AuxiliaryProcessMainCommon` / `BackgroundWorkerInitializeConnection` / `BackendStartup` before reaching here. [verified-by-code]
- **ProcArray insertion (`InitProcessPhase2`) is irrevocable visibility.** All later FATAL paths must reach `ProcArrayEndTransaction` via the `ShutdownPostgres` `before_shmem_exit` to remove us. [from-comment, postinit.c:730-733]
- **`MyDatabaseId` must not be set until the database is locked with `RowExclusiveLock`.** A concurrent `DROP DATABASE` would otherwise see us in the ProcArray with a stale id; pgstat would create dangling entries. [from-comment, postinit.c:1081-1101, 1153-1174]
- **Catalog snapshot taken before `MyDatabaseId` is set is unsafe** and must be invalidated explicitly (line 1183).
- **Timeout handlers cannot run in bootstrap mode** (the `if (!bootstrap)` guard at 790).
- **Standalone backend / bootstrap drives XLOG itself** (StartupXLOG inline at line 819); under postmaster the startup process and checkpointer handle XLOG lifecycle. [from-comment, postinit.c:804-810]

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
