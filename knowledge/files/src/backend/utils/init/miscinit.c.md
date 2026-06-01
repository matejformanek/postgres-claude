# miscinit.c

- **Source path:** `source/src/backend/utils/init/miscinit.c`
- **Lines:** 1902
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/miscadmin.h`, `init/postinit.c` (next-stage init), `utils/pidfile.h` (lockfile format), `libpq/auth.c` (SystemUser construction), `tcop/postgres.c::PostgresMain`

## Purpose

Per-process *miscellaneous* initialization — the things needed by every backend that don't fit anywhere else. Three concrete roles:

1. **Process startup primitives**: `InitPostmasterChild`, `InitStandaloneProcess`, latch initialization, signal mask setup (SIGQUIT unblocked + handler installed centrally), session leader (`setsid()`), postmaster-death pipe.
2. **User identity machinery**: the four-layer user ID concept (`Authenticated` → `Session` → `Outer` → `Current`) and the `SecurityRestrictionContext` flags (`SECURITY_LOCAL_USERID_CHANGE`, `SECURITY_RESTRICTED_OPERATION`, `SECURITY_NOFORCE_RLS`).
3. **Interlock-file management**: `postmaster.pid` and per-socket `.lock` files — creation under O_EXCL with stale-PID detection, retry, fsync, and the `proc_exit` unlink callback.

Also houses `ProcessingMode`, `MyBackendType` storage, `IgnoreSystemIndexes`, and the entry points for `process_shared_preload_libraries` / `process_session_preload_libraries` (the actual loader is in shared-library land but the GUC-state booleans live here). [verified-by-code, miscinit.c:1786-1792]

## Top-of-file comment (verbatim)

> "miscinit.c — miscellaneous initialization support stuff" — bare one-liner. The substantive comments live above each function group ("common process startup code" at 85-87, "database path / name support stuff" at 278-281, "User ID state" at 442-..., "Interlock-file support" at 1107-1119). [from-comment]

## Public surface (selected)

### Process startup
- `InitPostmasterChild()` (96) — first call in any forked child. Sets `IsUnderPostmaster = true`, calls `InitProcessGlobals`, sets stderr to binary on Windows, `on_exit_reset()` (drop postmaster's handlers), inits latches, `setsid()`, installs `SignalHandlerForCrashExit` for SIGQUIT, removes SIGQUIT from `BlockSig`, calls `PostmasterDeathSignalInit`, sets `FD_CLOEXEC` on the postmaster-death pipe.
- `InitStandaloneProcess(argv0)` (175) — no postmaster; sets `MyBackendType = B_STANDALONE_BACKEND`, inits latches, computes `my_exec_path` / `pkglib_path` from argv[0].
- `SwitchToSharedLatch()` (215) / `SwitchBackToLocalLatch()` (242) / `InitProcessLocalLatch()` (235) — toggle `MyLatch` between `LocalLatchData` (pre-PGPROC) and `MyProc->procLatch`. Both `SetLatch(MyLatch)` after the swap, in case a signal arrived during the swap. [from-comment, miscinit.c:227-231]
- `GetBackendTypeDesc(backendType)` (264) — translatable description string; switches on PG_PROCTYPE x-macro from `postmaster/proctypelist.h`.

### Database path / mode
- `SetDatabasePath(path)` (283) — `MemoryContextStrdup(TopMemoryContext, path)`; asserts not-set.
- `checkDataDir()` (296) — stat DataDir; if mode is 0750 set `data_directory_mode = 0750`, otherwise 0700; reject if owned by another user or world-readable.
- `SetDataDir` (389) — canonicalize to absolute path. `ChangeToDataDir` (409) — `chdir(DataDir)`; most backend code then uses relative paths.

### User identity
- `GetUserId()`, `GetOuterUserId()`, `GetSessionUserId()`, `GetSessionUserIsSuperuser()`, `GetSystemUser()`, `GetAuthenticatedUserId()`, `SetAuthenticatedUserId()` (469-565). Four-level: Authenticated (from auth method, can't change), Session (changed by `SET SESSION AUTHORIZATION`), Outer (the "real" effective ID before any local change), Current (what queries see). `SetAuthenticatedUserId` may be called only once and writes `MyProc->roleId` (atomic store, no lock — line 563). [from-comment, miscinit.c:561-564]
- `GetUserIdAndSecContext` / `SetUserIdAndSecContext` (612, 619) — together with the three flag bits, used by `StartTransaction` / `AbortTransaction` to save/restore. **These routines MUST NOT throw**, because they run during abort and may see invalid OIDs. [from-comment, miscinit.c:603-611]
- `InLocalUserIdChange()`, `InSecurityRestrictedOperation()`, `InNoForceRLSOperation()` (630, 639, 648) — flag readers.
- `GetUserIdAndContext` / `SetUserIdAndContext` (661, 668) — obsolete; only kept for pljava bug-compat. [from-comment]
- `has_rolreplication(roleid)` (688) — REPLICATION role check; superuser bypasses.
- `InitializeSessionUserId(rolename, roleid, bypass_login_check)` (710) — the *normal* path: AcceptInvalidationMessages, syscache lookup of pg_authid, check rolcanlogin / rolconnlimit, call `SetAuthenticatedUserId` + `SetSessionUserId` + `SetOuterUserId`. Parallel workers skip the lookup. [verified-by-code]
- `InitializeSessionUserIdStandalone()` (840) — bootstrap / autovac / single-user; sets all four user IDs to `BOOTSTRAP_SUPERUSERID`.
- `InitializeSystemUser(authn_id, auth_method)` (875) — sets `SystemUser = "<auth_method>:<authn_id>"` in TopMemoryContext.
- `SetSessionAuthorization`, `SetCurrentRoleId` (911, 936, 957) — runtime SET SESSION AUTHORIZATION / SET ROLE; refuse to act under `SECURITY_RESTRICTED_OPERATION` (with the same error SET ROLE would throw).
- `GetUserNameFromId(roleid, noerr)` (989) — syscache-backed name resolution.

### Client connection info (parallel-worker serialization)
- `SerializeClientConnectionInfo`, `EstimateClientConnectionInfoSpace`, `RestoreClientConnectionInfo` (1036-1104) — ship `MyClientConnectionInfo` (authn_id, auth_method) to parallel workers.

### Interlock files
- `CreateDataDirLockFile`, `CreateSocketLockFile`, `TouchSocketLockFiles`, `AddToDataDirLockFile`, `RecheckDataDirLockFile` (1455-1719) — public entry points wrapping `CreateLockFile`.
- `CreateLockFile(filename, amPostmaster, socketDir, isDDLock, refName)` (1159) — static; opens O_EXCL, detects stale PIDs against my pid / ppid / `PG_GRANDPARENT_PID`, retry loop bounded at 100 iterations, fsync after write.
- `UnlinkLockFiles` (1125) — `proc_exit` callback; emits the "database system is shut down" log message (LOG normally, NOTICE in standalone). [from-comment, miscinit.c:1138-1148]

### Library preloading
- `process_shared_preload_libraries`, `process_session_preload_libraries`, etc. (1852-1889) — actual library-load logic in `dfmgr.c`; this file owns the state booleans `process_shared_preload_libraries_in_progress`/`_done`, `process_shmem_requests_in_progress`. [verified-by-code, miscinit.c:1786-1792]

## Key invariants

- **`InitProcessLocalLatch` must run before `MyLatch` is dereferenced.** `MyLatch` is set to `&LocalLatchData` (line 238); never NULL once init has happened. [verified-by-code]
- **SIGQUIT is unblocked exactly once, in `InitPostmasterChild`** (line 155). All postmaster children inherit a *blocked* SIGQUIT; this central unblock + crash-exit handler ensures uniform response. Client-facing processes may swap the handler for `quickdie()`. [from-comment, miscinit.c:146-152]
- **The four user IDs follow a strict relationship.** `SetOuterUserId` forces `CurrentUserId = OuterUserId` (line 496) — they only diverge inside `SetUserIdAndSecContext` (local userid change). `SECURITY_RESTRICTED_OPERATION` and `SET ROLE` interact: `SetSessionAuthorization` and `SetCurrentRoleId` refuse to act under it.
- **`SetAuthenticatedUserId` is once-only.** `Assert(!OidIsValid(AuthenticatedUserId))` at 558. Mirrored into `MyProc->roleId` so other backends can see who we are.
- **`Get/SetUserIdAndSecContext` MUST NOT throw**, even with invalid OIDs — they run during abort. [from-comment, miscinit.c:603-611]
- **Lockfile retry loop is bounded** (`ntries > 100` → FATAL); race against concurrent unlink is OK (`ENOENT` → continue). [verified-by-code, miscinit.c:1217-1267]
- **`lock_files` proc_exit callback is registered once on success** so we always clean up our PIDfile and socket lockfiles on a normal exit.
- **`Mode` (ProcessingMode) flows through the lifecycle**: `InitProcessing` → `NormalProcessing` (after `InitPostgres` finishes) or `BootstrapProcessing`. Tested by IsBootstrapProcessingMode() etc. (miscadmin.h).

## Cross-references

- Called by `postmaster.c::PostmasterMain` and every BackendStartup/AuxiliaryProcess entry point (postinit.c references `InitPostmasterChild` and `InitProcessLocalLatch` via the common init prologue).
- User-ID helpers consumed by `commands/variable.c` (SET ROLE/SET SESSION AUTHORIZATION assign hooks), `tcop/utility.c`, every `pg_proc` security-definer call site, and `executor/spi.c`.
- Lockfile interfaces consumed by `postmaster.c` (data-dir lockfile creation) and `libpq/pqcomm.c` (socket lockfiles).
- `process_session_preload_libraries` is called from `postinit.c:1273`.

## Open questions

- The "Windows hasn't got getppid" branch (line 1196-1204) sets `my_p_pid = 0`; in theory a Windows PID of 0 could in principle exist and yield a false "stale lockfile" decision, but the surrounding kill(0)/EPERM logic should still reject it. [unverified]
- Why `MyBackendType` storage lives in miscinit.c (line 65) rather than globals.c — historical artifact. [unverified]

## Confidence tag tally

`[verified-by-code]=11 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
