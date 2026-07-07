---
scenario: add-new-bgworker
when_to_use: A background process you want the postmaster to manage — either static (preloaded at server start) or dynamic (registered at runtime by SQL/extension code).
companion_skills: ["bgworker-and-extensions","parallel-query"]
related_scenarios: ["add-new-extension","add-new-shared-memory-region","add-startup-hook"]
canonical_commit: 090d0f20506
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new background worker

## Scope — what's in / out

**In scope:**
- A new long-running background process forked by the postmaster, registered
  either statically (`RegisterBackgroundWorker` from a `shared_preload_libraries`
  `_PG_init`) or dynamically (`RegisterDynamicBackgroundWorker` from a regular
  backend, returning a `BackgroundWorkerHandle *`).
- Filling in the full `BackgroundWorker` struct: `bgw_name`, `bgw_type`,
  `bgw_flags`, `bgw_start_time`, `bgw_restart_time`, `bgw_library_name`,
  `bgw_function_name`, `bgw_main_arg`, `bgw_extra`, `bgw_notify_pid`
  [verified-by-code](source/src/include/postmaster/bgworker.h:96-108).
- Writing the worker `main` function with signature
  `void worker_main(Datum main_arg)` [verified-by-code](source/src/include/postmaster/bgworker.h:79),
  including signal handler installation, `BackgroundWorkerUnblockSignals()`,
  optional `BackgroundWorkerInitializeConnection[ByOid]()`, and a `WaitLatch`
  main loop.
- Bundling the worker into an extension (`.control` + `.sql` + `_PG_init`) when
  the worker needs an SQL surface to launch / inspect itself.
- Test scaffolding via `src/test/modules/<name>` (TAP test using `Cluster.pm`).

**Out of scope:**
- Parallel-query workers — those go through `RegisterDynamicBackgroundWorker`
  with `BGWORKER_CLASS_PARALLEL` but the parallel-context machinery
  (`ParallelContext`, DSM, error-queue plumbing) is its own change-class; see
  `parallel-query` skill and `parallel-worker-launch-wait-and-errors` idiom.
- Auxiliary postmaster children that are *not* bgworkers (autovacuum launcher,
  checkpointer, walwriter, walsummarizer) — those are in `proctypelist.h`
  and edit the postmaster state machine directly, not via the bgworker API.
- New shared-memory the worker reads / writes — that's
  `add-new-shared-memory-region`. Most worker examples need both; this
  scenario is unioned with #26 in that case.
- Logical-replication apply workers / tablesync workers — those are dispatched
  by `launcher.c` and have their own lifecycle; this scenario doesn't cover
  the launcher contract.

## Pre-flight

- **Companion skills:** load `bgworker-and-extensions` (the registration
  shape and `_PG_init` rules) and `parallel-query` (only if the worker is
  parallel-class — most aren't, but the skill explains the BGWORKER_CLASS_*
  invariants you must NOT trip over).
- **Canonical commit:** `090d0f20506` — *Allow discovery of whether a dynamic
  background worker is running.* The pair `4db3744f1f4` + later worker_spi
  reshapes are the textbook reference (TODO: find the original
  RegisterDynamicBackgroundWorker introduction commit; `090d0f20506` exercises
  the full registration + handle + wait API end-to-end).
- **Common pitfalls (one-line each):**
  - Forgot `BGWORKER_SHMEM_ACCESS` — `SanityCheckBackgroundWorker` rejects
    the registration outright; the flag is mandatory even though it reads
    optional [verified-by-code](source/src/backend/postmaster/bgworker.c:668-676).
  - Static worker with `BgWorkerStart_PostmasterStart` + `BGWORKER_BACKEND_DATABASE_CONNECTION`
    — sanity check rejects: shared catalogs aren't ready that early
    [verified-by-code](source/src/backend/postmaster/bgworker.c:680-688).
  - `RegisterBackgroundWorker` called outside `_PG_init` of a
    `shared_preload_libraries` module — silently noop in EXEC_BACKEND, LOG
    in regular processes; worker never starts
    [verified-by-code](source/src/backend/postmaster/bgworker.c:970-991).
  - Parallel-class worker registered with `bgw_restart_time != BGW_NEVER_RESTART`
    — sanity check rejects (parallel accounting can't survive restart)
    [verified-by-code](source/src/backend/postmaster/bgworker.c:716-724).
  - Static workers can't set `bgw_notify_pid`; rejected at register time
    [verified-by-code](source/src/backend/postmaster/bgworker.c:1007-1014).
  - Forgot to `BackgroundWorkerUnblockSignals()` before entering the main
    loop — worker hangs because postmaster forks it with all signals blocked
    [verified-by-code](source/src/backend/postmaster/bgworker.c:820).
  - Exit code 1 vs 0 vs `proc_exit(0)` — return 0 means "never restart, drop
    the slot"; return 1 means "restart after `bgw_restart_time` seconds";
    `BGW_NEVER_RESTART` forces 0-semantics regardless
    [from-comment](source/src/include/postmaster/bgworker.h:19-22).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/test/modules/<name>/<name>.c` (or `contrib/<name>/<name>.c`) | (NEW) Worker `main` function with signature `void worker_main(Datum main_arg)` [verified-by-code](source/src/include/postmaster/bgworker.h:79). Must install signal handlers (`pqsignal(SIGHUP, SignalHandlerForConfigReload); pqsignal(SIGTERM, die);` — pattern from worker_spi 160-161 [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:160-161)), call `BackgroundWorkerUnblockSignals()` [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:164), optionally `BackgroundWorkerInitializeConnection[ByOid]()`, then loop on `WaitLatch(MyLatch, …)` [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:221). | — | bgworker-and-extensions |
| 2 | `src/test/modules/<name>/<name>.c` `_PG_init` | (NEW) Static-registration path. Build a `BackgroundWorker` struct (memset 0 first), fill `bgw_flags` (`BGWORKER_SHMEM_ACCESS \| BGWORKER_BACKEND_DATABASE_CONNECTION`), `bgw_start_time` (one of `BgWorkerStart_PostmasterStart` / `_ConsistentState` / `_RecoveryFinished` per `bgworker.h:84-89` [verified-by-code](source/src/include/postmaster/bgworker.h:84-89)), `bgw_restart_time` (seconds or `BGW_NEVER_RESTART`), `bgw_library_name`, `bgw_function_name`, `bgw_main_arg`, then call `RegisterBackgroundWorker(&worker)`. Pattern: worker_spi `_PG_init` at 303-387 [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:303-387). | — | bgworker-and-extensions |
| 3 | `src/test/modules/<name>/<name>.c` SQL-launch entrypoint | (NEW, optional) `PG_FUNCTION_INFO_V1(<name>_launch)` for the dynamic-registration path. Build the worker struct same as static, but additionally set `bgw_notify_pid = MyProcPid` and call `RegisterDynamicBackgroundWorker(&worker, &handle)`; on success `WaitForBackgroundWorkerStartup(handle, &pid)` returns once the postmaster has forked. Pattern: worker_spi 477-495 [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:477-495). | — | bgworker-and-extensions |
| 4 | `src/test/modules/<name>/<name>.control` | (NEW) Control file: `comment`, `default_version`, `module_pathname = '$libdir/<name>'`, `relocatable`. Pattern: `worker_spi.control` [verified-by-code](source/src/test/modules/worker_spi/worker_spi.control:1). | — | extension-development |
| 5 | `src/test/modules/<name>/<name>--1.0.sql` | (NEW) SQL surface — the `CREATE FUNCTION <name>_launch(...) RETURNS int AS 'MODULE_PATHNAME' LANGUAGE C STRICT` declaration if you exposed a launch entrypoint in #3. Pattern: `worker_spi--1.0.sql` [verified-by-code](source/src/test/modules/worker_spi/worker_spi--1.0.sql:1). | — | extension-development |
| 6 | `src/test/modules/<name>/Makefile` | (NEW) `MODULE_big = <name>` + `OBJS = $(WIN32RES) <name>.o` + `EXTENSION`/`DATA`/`REGRESS`/`TAP_TESTS` per `PGXS` template. Pattern: `src/test/modules/worker_spi/Makefile`. | — | build-and-run |
| 7 | `src/test/modules/<name>/meson.build` | (NEW) `shared_module('<name>', …, kwargs: pg_test_mod_args)` + `test_install_data` + `tests` block with `tap.tests = [ … ]`. Pattern: `src/test/modules/worker_spi/meson.build` [verified-by-code](source/src/test/modules/worker_spi/meson.build:1-38). | — | build-and-run |
| 8 | `src/test/modules/meson.build` | Add the new subdir entry to the `subdir(...)` list. Without this, meson never sees the new module. | — | build-and-run |
| 9 | `src/test/modules/Makefile` | Add the new subdir to the `SUBDIRS` list. Without this, `make check-world` skips it. | — | build-and-run |
| 10 | `src/test/modules/<name>/t/001_<name>.pl` | (NEW) TAP test: spin up a `PostgreSQL::Test::Cluster`, set `shared_preload_libraries = '<name>'` in postgresql.conf (for the static path), restart, then `CREATE EXTENSION` and exercise the launch entrypoint. Pattern: `worker_spi/t/001_worker_spi.pl` [verified-by-code](source/src/test/modules/worker_spi/t/001_worker_spi.pl:1). | — | testing |
| 11 | `src/test/modules/<name>/t/002_<name>_terminate.pl` (optional) | (NEW) TAP test for `TerminateBackgroundWorker()` + `WaitForBackgroundWorkerShutdown()` paths if the worker exposes a terminate API. Pattern: `worker_spi/t/002_worker_terminate.pl`. | — | testing |
| 12 | `src/include/postmaster/bgworker.h` | Read-only reference for this scenario — declares the registration ABI, the `BackgroundWorker` struct, the `BgWorkerStartTime` enum, the `BGWORKER_*` flags, `BGW_NEVER_RESTART`/`BGW_DEFAULT_RESTART_INTERVAL`, and the wait/terminate API. Do NOT modify unless you're adding a brand-new flag or start-time enum value (those are bgworker-core changes, not "add a worker") [verified-by-code](source/src/include/postmaster/bgworker.h:50-174). | [bgworker.h.md](../files/src/include/postmaster/bgworker.h.md) | bgworker-and-extensions |
| 13 | `src/backend/postmaster/bgworker.c` | Read-only reference — `RegisterBackgroundWorker` 962, `RegisterDynamicBackgroundWorker` 1068, `BackgroundWorkerMain` 741 (the trampoline that calls `LookupBackgroundWorkerFunction` then your `bgw_function_name`), `SanityCheckBackgroundWorker` 658, `BackgroundWorkerInitializeConnection[ByOid]` 875/909 [verified-by-code](source/src/backend/postmaster/bgworker.c:962-1206). | [bgworker.c.md](../files/src/backend/postmaster/bgworker.c.md) | bgworker-and-extensions |
| 14 | `src/backend/postmaster/postmaster.c` | Read-only reference — `StartBackgroundWorker` 4173 (fork+launch), `bgworker_should_start_now` 4234 (gate by `pmState`), `maybe_start_bgworkers` 4280 (the polling driver). Read these so you understand the start-time semantics; do NOT modify unless you're changing pmState rules [verified-by-code](source/src/backend/postmaster/postmaster.c:4173-4380). | [postmaster.c.md](../files/src/backend/postmaster/postmaster.c.md) | — |
| 15 | `doc/src/sgml/bgworker.sgml` | If your worker uses a flag, start-time, or pattern not already documented (rare), update the chapter. The header `<chapter id="bgworker">` is canonical reference docs [verified-by-code](source/doc/src/sgml/bgworker.sgml:1-30). For a one-off contrib/test worker, no edit needed. | — | — |
| 16 | `src/backend/utils/misc/guc_parameters.dat` (optional, READ ONLY) | `max_worker_processes` defines the upper bound on registered workers — postmaster scope, restart required [verified-by-code](source/src/backend/utils/misc/guc_parameters.dat:2196-2198). Do NOT bump the default unless your worker is in core; document the requirement in your extension's README instead. | — | gucs-config |
| 17 | `src/backend/utils/misc/postgresql.conf.sample` (optional) | If your worker is in core (not contrib/test), and you added a new tunable GUC for it (naptime, batch-size, …), add the sample-conf line. Worker_spi uses `DefineCustomIntVariable(…, "worker_spi.naptime", …)` from `_PG_init` and does NOT touch sample-conf because it's a test module [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:313-325). | — | gucs-config |

(`src/include/postmaster/bgworker_internals.h` declares `BackgroundWorkerMain`, `RegisteredBgWorker`, and `BackgroundWorkerList` — never edited by user code; the postmaster owns it [verified-by-code](source/src/include/postmaster/bgworker_internals.h:1).)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Worker skeleton + static registration.** Files: [1, 2, 4, 5, 6, 7, 8, 9]. Edits: write `worker_main` with signal handlers, `BackgroundWorkerUnblockSignals`, `BackgroundWorkerInitializeConnection` if needed, and a `WaitLatch` loop that does nothing yet; write `_PG_init` registering one static worker with `BgWorkerStart_RecoveryFinished` + `BGW_NEVER_RESTART`. Phase-end check: `meson setup` + `ninja` builds the shared module; `meson test -C dev/build-debug --suite setup` passes (install layout sane).
2. **Phase 2 — Real work + dynamic launch.** Files: [1, 3, 5]. Edits: put the actual workload in `worker_main` (SPI calls, etc.); add `<name>_launch` SQL function via `RegisterDynamicBackgroundWorker` + `WaitForBackgroundWorkerStartup`. Phase-end check: build still green; manually `psql -c "CREATE EXTENSION <name>; SELECT <name>_launch();"` returns a pid; `pg_stat_activity` shows the worker.
3. **Phase 3 — Tests + docs.** Files: [10, 11, 15 if needed, 17 if needed]. Edits: TAP test that loads the module via `shared_preload_libraries`, verifies the static worker started, calls the dynamic launcher, exercises terminate path. Phase-end check: `meson test -C dev/build-debug --suite <name>` passes; `make check-world` green.
4. **Phase 4 (optional) — Shmem-region piggyback.** If the worker shares state with backends, this is where you union with `add-new-shared-memory-region`. Files: add `shmem_request_hook` + `shmem_startup_hook` registered from `_PG_init`. Phase-end check: regress + TAP still pass; `pg_shmem_allocations` shows the new region.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/postmaster` (+1) |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/backend/postmaster` (+1) |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/test/modules`, `src/backend/utils` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include` |
| [`tom-lane`](../personas/tom-lane.md) | `src/backend/utils` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`background-worker-startup`](../idioms/background-worker-startup.md) | direct reference |
| [`bgworker-and-parallel`](../idioms/bgworker-and-parallel.md) | direct reference |
| [`guc-variables`](../idioms/guc-variables.md) | shares files: `src/test/modules/worker_spi/worker_spi.c` |
| [`parallel-worker-launch-wait-and-errors`](../idioms/parallel-worker-launch-wait-and-errors.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`bgw_library_name = "postgres"` for in-tree workers.** When the worker
  main lives in the backend itself (not a loadable module), `bgw_library_name`
  must be the literal string `"postgres"` — `LookupBackgroundWorkerFunction`
  treats it specially. For loadable modules, use the bare module name (no
  `$libdir` prefix, no `.so` suffix); worker_spi uses `sprintf(worker.bgw_library_name, "worker_spi")` [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:368).
- **`bgw_function_name` is looked up by `load_external_function` at worker
  start, not at register time.** Typos in the function name are not caught
  until the postmaster forks the worker; you see an exit with a "could not
  find function" error in the postmaster log. Always exercise the worker
  end-to-end before considering the change done.
- **`BGW_MAXLEN = 96` for `bgw_name` / `bgw_type` / `bgw_function_name`;
  `BGW_EXTRALEN = 128` for `bgw_extra`; `MAXPGPATH` for `bgw_library_name`**
  [verified-by-code](source/src/include/postmaster/bgworker.h:93-106). `snprintf`-and-truncate is fine for the name fields, but `bgw_extra` is opaque memory — if you put a struct in it, `sizeof(struct) <= BGW_EXTRALEN` must hold or you corrupt the next slot. Worker_spi packs `Oid + Oid + uint32` into bgw_extra exactly [verified-by-code](source/src/test/modules/worker_spi/worker_spi.c:155-170).
- **`bgw_notify_pid` is only legal on dynamic workers.** Static registration
  with a non-zero `bgw_notify_pid` is silently downgraded to a LOG and the
  worker is not added [verified-by-code](source/src/backend/postmaster/bgworker.c:1007-1014). Use it for "I want SIGUSR1 when the worker starts/stops" — the typical caller pattern is `MyProcPid` so the calling backend's latch wakes.
- **`max_worker_processes` is postmaster-scoped.** Registering more workers
  than the slot count succeeds for `RegisterBackgroundWorker` only up to the
  limit; further static registrations LOG and drop (no error)
  [verified-by-code](source/src/backend/postmaster/bgworker.c:1020-1034). Dynamic registrations return `false` from `RegisterDynamicBackgroundWorker` with no message — the caller MUST check the return value and surface a useful error.
- **Synchronization traps:**
  - If you add a new `bgw_flags` value, you MUST also update
    `SanityCheckBackgroundWorker` in `bgworker.c` AND consider the
    `BGWORKER_CLASS_PARALLEL` accounting in `parallel.c`. This scenario
    assumes you're using existing flags only.
  - If you add a new `BgWorkerStartTime` enum value, you MUST also update
    `bgworker_should_start_now` in `postmaster.c:4234` or the postmaster
    will never start your worker.
  - If the worker calls `BackgroundWorkerInitializeConnection`, you MUST NOT
    use `BgWorkerStart_PostmasterStart` — `SanityCheckBackgroundWorker`
    rejects it at register time [verified-by-code](source/src/backend/postmaster/bgworker.c:680-688).

## Verification (exact test invocations)

```bash
# Build the module
meson compile -C dev/build-debug

# Run the new TAP suite (after wiring meson.build)
meson test -C dev/build-debug --suite <name>

# Existing bgworker smoke tests (always run these alongside)
meson test -C dev/build-debug --suite worker_spi
meson test -C dev/build-debug --suite test_shm_mq

# Full check-world to catch postmaster regressions
meson test -C dev/build-debug
```

If the change adds a brand-new test, name it explicitly here:
`src/test/modules/<name>/t/001_<name>.pl` (TAP, drives the static-load +
`CREATE EXTENSION` + launch path) and optionally `002_<name>_terminate.pl`
(if you exercise `TerminateBackgroundWorker`).

## Cross-refs

- Companion skills: `.claude/skills/bgworker-and-extensions/SKILL.md`,
  `.claude/skills/parallel-query/SKILL.md`.
- Related scenarios: `scenarios/add-new-extension.md` (the `.control` + `.sql`
  + `_PG_init` packaging that wraps the worker for SQL access),
  `scenarios/add-new-shared-memory-region.md` (the `shmem_request_hook` +
  `shmem_startup_hook` pair workers usually need),
  `scenarios/add-startup-hook.md` (where in the postmaster lifecycle your
  worker actually starts — `BgWorkerStart_*` is the user-facing slice of
  that question).
- Idioms: `knowledge/idioms/background-worker-startup.md`,
  `knowledge/idioms/bgworker-and-parallel.md`,
  `knowledge/idioms/parallel-worker-launch-wait-and-errors.md` (for the
  dynamic-registration handle / wait / error semantics).
- Subsystems: `knowledge/subsystems/main.md` (postmaster main loop),
  `knowledge/subsystems/storage-ipc.md` (shmem area the worker attaches to).
- Issues: `knowledge/issues/postmaster.md`,
  `knowledge/issues/include-postmaster.md`.
- Reference patch (canonical_commit): `git -C source show 090d0f20506`.
  Also read `git -C source show 4db3744f1f4` (the worker_spi test module
  introduction) and worker_spi.c end-to-end before starting.
