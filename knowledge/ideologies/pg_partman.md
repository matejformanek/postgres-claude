# pg_partman — partition automation as plpgsql + a self-scheduling bgworker swarm

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgpartman/pg_partman` @ branch `development`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-03 (see Sources footer).

## Domain & purpose

pg_partman automates time- and number-based table partitioning. As of 5.0.1 it
builds *entirely* on PostgreSQL's native declarative partitioning — the old
trigger-based method is gone — and adds the lifecycle automation core lacks:
creating new child tables ahead of time, dropping or detaching old ones per a
retention policy, and converting existing tables to/from partitioned form
(`README.md:6-8`) `[from-README]`. The headline divergence from "an extension
is C that hooks the backend" is that pg_partman is **mostly plpgsql** — the
partition logic lives in SQL functions (`requires = 'plpgsql'`,
`pg_partman.control:1-5`) — and its only C is a **background worker** whose sole
job is to periodically call `run_maintenance()` so no external cron is needed
(`README.md:10`). It answers: *how does an extension run recurring maintenance
across every database without an external scheduler?*

## How it hooks into PG

The SQL half is a plain plpgsql extension (`relocatable = false`, `superuser =
false`, `requires = 'plpgsql'`, `pg_partman.control:1-5`) — no hooks, just
functions and config tables. The interesting half is `pg_partman_bgw`, a
*separate* shared library that must be in `shared_preload_libraries`
(`README.md:58-60`), and which can be omitted entirely with `make NO_BGW=1` if
you'd rather drive `run_maintenance()` from external cron (`README.md:47-51`).

`_PG_init` (`pg_partman_bgw.c:101-202`) `[verified-by-code]`:

1. Defines GUCs: `pg_partman_bgw.interval` (seconds between runs, default 3600),
   `.maintenance_wait`, `.analyze`, `.dbname`, `.jobmon`, `.role` (default
   `postgres`), `.maintenance_db` (`pg_partman_bgw.c:105-186`).
2. Guards on `process_shared_preload_libraries_in_progress`
   (`pg_partman_bgw.c:188`).
3. Registers a **static** `BackgroundWorker` (the "master") with
   `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
   `bgw_start_time = BgWorkerStart_RecoveryFinished`, `bgw_restart_time = 600`,
   entry `pg_partman_bgw_main` (`pg_partman_bgw.c:192-202`).

Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/idioms/guc-variables]]`.

## Where it diverges from core idioms

### 1. A two-tier worker model: one static master spawns N dynamic per-database workers each cycle

This is the architectural signature. The master worker (`pg_partman_bgw_main`,
`pg_partman_bgw.c:206-357`) loops forever; on each tick it parses the
comma-separated `pg_partman_bgw.dbname` GUC into a list and, *for each database*,
**registers a fresh dynamic background worker** via
`RegisterDynamicBackgroundWorker` with entry `pg_partman_bgw_run_maint`
(`pg_partman_bgw.c:283-325`). Each dynamic worker has `bgw_restart_time =
BGW_NEVER_RESTART` (`pg_partman_bgw.c:286`) — it does one maintenance pass and
exits — while the master synchronously waits for it via
`WaitForBackgroundWorkerStartup` and handles `BGWH_STOPPED` /
`BGWH_POSTMASTER_DIED` (`pg_partman_bgw.c:308-324`). So instead of one
long-lived connection per database, pg_partman uses a **disposable
worker-per-database-per-cycle** swarm spawned from a single restartable master.
The master itself restarts every 600 s if it dies (`pg_partman_bgw.c:197`), but
the dynamic workers are deliberately never auto-restarted — the master is the
sole scheduler. Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/subsystems/storage-ipc]]`.

### 2. The C worker is a thin SPI shim — all real work is plpgsql `run_maintenance()`

The dynamic worker (`pg_partman_bgw_run_maint`, `pg_partman_bgw.c:364+`) does
`BackgroundWorkerInitializeConnection(dbname, pg_partman_bgw_role, 0)`
(`pg_partman_bgw.c:409`), opens SPI, and first checks whether the extension is
even installed: `SELECT extname FROM pg_catalog.pg_extension WHERE extname =
'pg_partman'` — if absent it "exits gracefully" (`pg_partman_bgw.c:432-444`).
Only then does it call the plpgsql `run_maintenance()`. The C layer carries
*no* partitioning logic; it is purely "connect to the right db as the right
role and invoke the SQL entry point." This inverts the usual extension balance
(C core + thin SQL wrappers): here SQL is the core and C is the scheduler.
Cross-ref `[[knowledge/idioms/spi]]`.

### 3. It hand-builds a Portal + transaction inside the worker for non-atomic SPI

To let `run_maintenance()` use procedures with internal `COMMIT`s, the worker
connects with `SPI_connect_ext(SPI_OPT_NONATOMIC)` and, when there's no active
portal, manually constructs one: `CreateNewPortal()`, sets `portal->visible =
false`, wires `portal->resowner` / `PortalContext`, then
`StartTransactionCommand()` + `EnsurePortalSnapshotExists()`
(`pg_partman_bgw.c:417-427`). Standard backends get this scaffolding from the
top-level executor; a bgworker driving non-atomic SPI must assemble it by hand.
This portal/transaction bring-up is a divergence forced by running
transaction-controlling plpgsql outside a normal client session. Cross-ref
`[[knowledge/idioms/spi]]`, `[[knowledge/architecture/executor]]` (portals),
`[[knowledge/architecture/mvcc]]` (snapshot management).

### 4. Latch-driven sleep with full SIGHUP/SIGTERM hygiene, not `pg_sleep`

The master uses the canonical latch pattern from `latch.h`: `ResetLatch(&MyProc->procLatch)`,
`CHECK_FOR_INTERRUPTS()`, then `WaitLatch` with a timeout instead of sleeping
(`pg_partman_bgw.c:243-247`), so a `SIGTERM` produces a clean shutdown mid-cycle
(`pg_partman_bgw.c:256-260`) and `SIGHUP` triggers `ProcessConfigFile(PGC_SIGHUP)`
to reload GUCs live (`pg_partman_bgw.c:249-253`). Custom `pg_partman_bgw_sigterm`
/ `pg_partman_bgw_sighup` handlers set `volatile sig_atomic_t` flags and set the
latch (`pg_partman_bgw.c:69-99`). This is core's own recommended bgworker
signal/latch discipline applied faithfully — notable because it's the part of
the extension that most resembles core backend code.

### 5. GUC string-as-boolean (`'on'`/`'off'`) instead of bool GUCs

`pg_partman_bgw.analyze` and `.jobmon` are **string** GUCs documented as "Set
to 'on' to send TRUE (default). Set to 'off' to send FALSE"
(`pg_partman_bgw.c:131-162`) rather than `DefineCustomBoolVariable`. The reason
is that these values are forwarded as SQL arguments into the plpgsql
`run_maintenance()` call, so the worker passes the string through to SQL rather
than round-tripping a C bool. A small but real divergence from the idiomatic
"use a bool GUC for a boolean."

## Notable design decisions (cited)

- **Built strictly on declarative partitioning.** Since 5.0.1 the
  trigger-based engine is removed; pg_partman "uses the built-in declarative
  features that PostgreSQL provides and builds upon those"
  (`README.md:6-8`). It is automation *around* core partitioning, not a
  reimplementation. Cross-ref `[[knowledge/subsystems/partitioning]]`.
- **BGW is optional and replaceable by cron.** `make NO_BGW=1` ships only the
  plpgsql, for shops that prefer an external scheduler (`README.md:47-51`) — the
  C worker is a convenience, not a dependency.
- **Per-database opt-in via existence check.** A dynamic worker that finds
  pg_partman not installed in its target database exits with no error
  (`pg_partman_bgw.c:439-444`), so listing many DBs in `.dbname` is safe even
  if only some have the extension.
- **`superuser = false` + role indirection.** The extension installs as
  non-superuser (`pg_partman.control:4`) and the worker runs maintenance as a
  configurable `pg_partman_bgw.role` that need only have execute on
  `run_maintenance()` (`pg_partman_bgw.c:164-166`) — least-privilege by design.
- **Optional pg_jobmon integration.** If `pg_jobmon` is installed, maintenance
  runs are logged to it automatically, gated by the `.jobmon` GUC
  (`README.md:38`, `pg_partman_bgw.c:153-162`) — soft dependency on a sibling
  extension.
- **Portable list-split via a function pointer.** `(*split_function_ptr)(...)`
  (`pg_partman_bgw.c:267`, `:390`) indirects the GUC-list splitter to stay
  compatible across PG majors where `SplitIdentifierString`/`SplitGUCList`
  signatures shifted — the out-of-tree multi-version straddle again.

## Links into corpus

- `[[knowledge/subsystems/partitioning]]` — the native declarative partitioning
  pg_partman automates (child creation, attach/detach, retention).
- `[[knowledge/idioms/bgworker-and-parallel]]` — static master +
  `RegisterDynamicBackgroundWorker` per-database swarm; `BGWORKER_SHMEM_ACCESS`
  / `BGWORKER_BACKEND_DATABASE_CONNECTION`; `BgWorkerStart_RecoveryFinished`.
- `[[knowledge/idioms/spi]]` — the worker's SPI shim, the extension-presence
  probe, and the non-atomic `SPI_OPT_NONATOMIC` path.
- `[[knowledge/architecture/executor]]` + `[[knowledge/architecture/mvcc]]` —
  the hand-built Portal + `StartTransactionCommand` + snapshot scaffolding for
  procedure-with-COMMIT maintenance.
- `[[knowledge/idioms/guc-variables]]` — the seven `pg_partman_bgw.*` GUCs,
  including the string-as-boolean choice and `PGC_SIGHUP` live reload.
- `.claude/skills/gucs-bgworker-parallel/SKILL.md` — `RegisterBackgroundWorker`
  vs `RegisterDynamicBackgroundWorker`, latch loops, signal handlers; pg_partman
  is a clean two-tier worked example.
- `.claude/skills/extension-development/SKILL.md` — plpgsql-heavy extension with
  a separate preload bgworker library and a `NO_BGW` build switch.

## Sources

Fetched 2026-06-03 (branch `development`; queue manifest said `master`, the
repo's default branch is `development` — fetched accordingly. The queue also
named `doc/pg_partman.md` and `sql/types/types.sql`; this run focused on the
C bgworker + README to characterize the *architectural* divergence, which is
where pg_partman departs from core idioms — the plpgsql reference doc is
end-user surface, noted as a gap below):

- `https://raw.githubusercontent.com/pgpartman/pg_partman/development/README.md`
  @ 2026-06-03T23:08Z → HTTP 200 (131 lines).
- `https://raw.githubusercontent.com/pgpartman/pg_partman/development/src/pg_partman_bgw.c`
  @ 2026-06-03T23:08Z → HTTP 200 (537 lines).
- `https://raw.githubusercontent.com/pgpartman/pg_partman/development/pg_partman.control`
  @ 2026-06-03T23:08Z → HTTP 200 (5 lines).
- Tree listing
  `https://api.github.com/repos/pgpartman/pg_partman/git/trees/development?recursive=1`
  @ 2026-06-03T23:08Z → HTTP 200 (265 entries).

All bgworker cites are `[verified-by-code]` against the fetched
`pg_partman_bgw.c` (the two-tier worker model, the SPI shim, the Portal/txn
bring-up, the latch loop). Domain/declarative-partitioning framing is
`[from-README]`. **Gap:** `doc/pg_partman.md` and `sql/types/types.sql` from
the queue manifest were not fetched this run — the plpgsql maintenance logic
and config-table schema are therefore characterized only via the C worker's
call sites, not read directly; a follow-up pass should cover the SQL side.
</content>
