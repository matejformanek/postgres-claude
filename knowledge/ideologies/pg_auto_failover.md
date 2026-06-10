# pg_auto_failover — an in-backend HA control plane that polls the cluster with libpq from a bgworker

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `hapostgres/pg_auto_failover` @ branch `main`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-10 (see Sources footer). Read alongside
> `[[knowledge/ideologies/pg_cron]]` and `[[knowledge/ideologies/pg_squeeze]]`
> (the other scheduler/bgworker extensions in the corpus) and
> `[[knowledge/subsystems/replication]]`.

## Domain & purpose

pg_auto_failover "monitors and manages automated failover for a Postgres
cluster … optimized for simplicity and correctness" (`README.md:5-7`)
`[from-README]`. It is a three-part system: (1) a Postgres extension named
`pgautofailover` that runs *inside* a dedicated "monitor" Postgres instance;
(2) the monitor service itself; (3) an out-of-process `pg_autoctl` keeper that
operates each managed data node (`README.md:24-28`) `[from-README]`. The
monitor implements a **replication state machine** and "relies on in-core
PostgreSQL facilities to deliver HA" — e.g. when a secondary is detected
unhealthy or lagging, the monitor rewrites `synchronous_standby_names` on the
primary to keep failover safe (`README.md:16-22`) `[from-README]`. The piece
worth documenting is the monitor extension: it turns a Postgres backend into
the brain of a *distributed* control plane, which forces several patterns core
extensions rarely combine.

## How it hooks into PG

`pgautofailover` is `relocatable = false`, `requires = 'btree_gist'`, and ships
at `default_version = '2.2'` (`src/monitor/pgautofailover.control:1-5`)
`[verified-by-code]` — the `btree_gist` dependency is for exclusion-constraint
style guarantees on its catalog tables. It uses the classic `PG_MODULE_MAGIC`
(`src/monitor/pg_auto_failover.c:69`).

The surface installed from `_PG_init` (`pg_auto_failover.c:75-92`)
`[verified-by-code]`:

- **Hard preload requirement.** `_PG_init` *errors out* unless
  `process_shared_preload_libraries_in_progress` is true
  (`pg_auto_failover.c:78-84`) — a deliberately stricter stance than most
  hook extensions, which merely warn or silently no-op.
- **`shmem_request_hook`** (`pgautofailover_shmem_request`,
  `pg_auto_failover.c:101-110`) reserves `HealthCheckWorkerShmemSize()` for the
  monitor's shared hash table.
- **A static `BackgroundWorker`** registered with `RegisterBackgroundWorker`
  whose entry point is `HealthCheckWorkerLauncherMain`
  (`pg_auto_failover.c:189-200`) `[verified-by-code]`. `bgw_restart_time = 1`
  means a crashed launcher restarts after one second.
- **`ProcessUtility_hook`** (`pgautofailover_ProcessUtility`,
  `pg_auto_failover.c:184-185, 210-269`) — installed for one narrow purpose:
  intercept `DROP DATABASE` so the per-database health-check worker is
  SIGTERM'd first, otherwise the connected bgworker would block the drop
  (`pg_auto_failover.c:233-247`) `[verified-by-code]`.
- **Eleven `DefineCustomIntVariable`/`BoolVariable` GUCs**, all `PGC_SIGHUP`
  and flagged `GUC_NO_SHOW_ALL | GUC_NOT_IN_SAMPLE`
  (`pg_auto_failover.c:124-182`) — health-check period/timeout/retries, WAL
  lag thresholds for promotion, drain timeout, startup grace period.

Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`.claude/skills/extension-development/SKILL.md`,
`.claude/skills/gucs-bgworker-parallel/SKILL.md`,
`.claude/skills/replication-overview/SKILL.md`.

## Where it diverges from core idioms

### 1. A bgworker that is a libpq *client* of every other node — a non-blocking PQconnectPoll event loop inside the backend

Core's background workers connect to *their own* database via
`BackgroundWorkerInitializeConnection` and use SPI. pg_auto_failover's health
checker does that for catalog access, but its actual job is to open **outbound
libpq connections to remote Postgres nodes** and time the handshake. The whole
of `health_check_worker.c` is a hand-rolled async state machine
(`HEALTH_CHECK_INITIAL → CONNECTING → OK | RETRY → DEAD`,
`health_check_worker.c:61-79`) `[verified-by-code]` that drives
`PQconnectStart` + `PQsetnonblocking` + `PQconnectPoll`
(`health_check_worker.c:879-905, 941-957`) and multiplexes all in-flight
connections through a single `poll(2)` over `PQsocket(connection)`
(`WaitForEvent`, `health_check_worker.c:709-796`) `[verified-by-code]`. So a
Postgres backend is running a libpq connection-pool poller — libpq is normally
a *client*-side library; here it lives in the server, calling out to peers. The
connection string hardcodes `user=pgautofailover_monitor
password=pgautofailover_monitor … connect_timeout`
(`health_check_worker.c:54-58`) and the comment is explicit that auth is
irrelevant: it only checks whether a TCP+startup handshake completes, sending
no secrets (`health_check_worker.c:47-53`) `[from-comment]`. This is the
single most unusual thing in the doc-set: an in-server health prober that
treats every cluster member as a libpq endpoint. Cross-ref
`[[knowledge/subsystems/replication]]` (the thing it is indirectly managing),
`[[knowledge/idioms/bgworker-and-parallel]]`.

### 2. A launcher → per-database worker hierarchy with its own shmem hash, mirroring autovacuum but in extension code

A single bgworker can only ever connect to one database for its lifetime, so
pg_auto_failover replicates core's autovacuum-launcher pattern *by hand*:
`HealthCheckWorkerLauncherMain` scans `pg_database` each round
(`BuildDatabaseList`, `health_check_worker.c:442-484`), and for every
non-template, connectable DB it `RegisterDynamicBackgroundWorker`s a
`HealthCheckWorkerMain` (`health_check_worker.c:396-435`) `[verified-by-code]`.
Liveness is tracked in a shmem `HTAB` keyed by database OID
(`HealthCheckWorkerDBHash`, `health_check_worker.c:119, 1139-1142`), guarded by
a custom LWLock tranche allocated at startup via `LWLockNewTrancheId` +
`LWLockRegisterTranche` in the `shmem_startup_hook`
(`HealthCheckWorkerShmemInit`, `health_check_worker.c:1103-1150`)
`[verified-by-code]`. The launcher takes the lock `LW_EXCLUSIVE` to insert,
*releases it before* `WaitForBackgroundWorkerStartup` so the child can take it
`LW_SHARED` to write its own PID into its hash entry
(`health_check_worker.c:264-352, 500-528`) `[verified-by-code]` — a careful
lock-handoff dance the comments call out (`:324-329`). This is core's
launcher/worker architecture rebuilt outside core, with the same shmem +
tranche + dynamic-bgworker primitives. Cross-ref
`[[knowledge/idioms/locking-overview]]`, `.claude/skills/locking/SKILL.md`,
`[[knowledge/subsystems/storage-ipc]]` (ShmemInitHash / AddinShmemInitLock).

### 3. The cluster's authoritative state lives in ordinary heap tables, addressed by hand-built SQL with hardcoded attnums

The monitor's model — formations, groups, nodes, replication states — is just
a set of regular tables created by the extension SQL. `node_metadata.h` pins
the `pgautofailover.node` table to **21 columns** with `Anum_*` macros that the
header *warns* "must match with the columns given in the following definition"
(`node_metadata.h:25-50`) `[from-comment]`, and builds `SELECT … FROM node`
strings by macro concatenation (`AUTO_FAILOVER_NODE_TABLE_ALL_COLUMNS`,
`SELECT_ALL_FROM_AUTO_FAILOVER_NODE_TABLE`, `node_metadata.h:52-77`)
`[verified-by-code]`. There is no `pg_proc.dat`/bootstrap-catalog involvement —
this is application schema, but accessed from C with the same
attnum-discipline core uses for *system* catalogs, which means an out-of-order
column in the install SQL silently corrupts every read. The C side mirrors each
row into an `AutoFailoverNode` struct via `TupleToAutoFailoverNode`
(`node_metadata.h:113-136, 185-186`). Cross-ref
`[[knowledge/idioms/catalog-conventions]]` (the attnum-must-match discipline,
here applied to user tables), `.claude/skills/catalog-conventions/SKILL.md`.

### 4. Promotion policy is encoded as WAL-LSN thresholds in GUCs, not in core replication

`promote_wal_log_threshold` and `enable_sync_wal_log_threshold` (both default
`DEFAULT_XLOG_SEG_SIZE`, `pg_auto_failover.c:156-166`) `[verified-by-code]`
gate when the monitor will add a node to the replication quorum or pick it as a
promotion candidate, comparing reported `reportedLSN`/`reportedTLI`
(`node_metadata.h:131-132`) against the primary. So the *correctness* knob of
failover — "don't promote a standby more than N bytes behind" — is an extension
GUC layered on top of the LSNs that nodes self-report, not anything core
enforces. The candidate-selection bias is similarly hand-coded:
`candidatePriority` is user-facing 0..100 but the monitor internally adds
`CANDIDATE_PRIORITY_INCREMENT (= 101)` to force a chosen candidate
(`node_metadata.h:90-97`) `[verified-by-code]`. Cross-ref
`[[knowledge/architecture/wal]]`, `[[knowledge/subsystems/replication]]`.

## Notable design decisions (cited)

- **`heap_open`/`heap_close`/`heap_getnext` spelling** (`health_check_worker.c:451,
  455, 477-478`) `[verified-by-code]` — the pre-12 relation-open API names, kept
  behind `version_compat.h` shims so one source tree builds against PG 13–18
  (`README.md:7`). A recurring extension tax: the code is written to the *oldest*
  supported API and adapts upward.
- **`BackgroundWorkerInitializeConnection(NULL, NULL, 0)`** for the launcher
  (`health_check_worker.c:233`) connects to shared catalogs only, so it can read
  `pg_database` without committing to one DB — the same trick the autovacuum
  launcher uses. `[verified-by-code]`
- **Crash-recovery of shmem state is explicit**: if a restarted worker finds no
  entry in `HealthCheckWorkerDBHash` (lost on a crash that reset shmem), it
  `proc_exit(0)`s and lets the launcher re-register it
  (`health_check_worker.c:506-514`) `[from-comment]`.
- **`WaitLatch` with `WL_POSTMASTER_DEATH`** and an immediate `proc_exit(1)` on
  postmaster death (`LatchWait`, `health_check_worker.c:802-832`)
  `[verified-by-code]` — textbook bgworker latch discipline; the comment quotes
  the "background workers mustn't call usleep()" rule verbatim (`:807-812`).
- **Per-round memory hygiene**: each scan runs in a child `AllocSetContext` that
  is `MemoryContextReset` every loop (`health_check_worker.c:540-581`)
  `[verified-by-code]`, the standard long-lived-backend leak-scoping idiom.

## Links into corpus

- `[[knowledge/ideologies/pg_cron]]` — sibling launcher/bgworker extension;
  pg_cron schedules SQL jobs, pg_auto_failover schedules *health probes* and a
  failover state machine. Both rebuild the autovacuum launcher pattern.
- `[[knowledge/ideologies/pg_squeeze]]` — another extension whose bgworker pair
  + `shmem_request_hook` reproduces core launcher infrastructure.
- `[[knowledge/subsystems/replication]]` — the monitor manages
  `synchronous_standby_names`, replication quorum, and promotion by LSN, all
  from outside the replication subsystem proper.
- `[[knowledge/idioms/bgworker-and-parallel]]` — `RegisterBackgroundWorker` +
  `RegisterDynamicBackgroundWorker`, BGWORKER_BACKEND_DATABASE_CONNECTION,
  `bgw_restart_time`.
- `[[knowledge/idioms/locking-overview]]` — custom LWLock tranche
  (`LWLockNewTrancheId`/`RegisterTranche`) protecting a shmem `HTAB`, with a
  deliberate exclusive-insert / shared-self-update lock handoff.
- `[[knowledge/idioms/catalog-conventions]]` — `Anum_*`/attnum discipline applied
  to the extension's own `node` table.

## Anthropology takeaway

pg_auto_failover is the corpus's clearest example of a Postgres backend used as
a **distributed-systems control plane** rather than a data engine. Two patterns
stand out for Phase-D and idiom mining: (a) **libpq-as-a-server-library** — a
bgworker running a non-blocking `PQconnectPoll` + `poll(2)` event loop to probe
peers is a reusable "in-backend outbound connection poller" idiom worth a
`knowledge/idioms` note, and a surface area no core code exercises (server
code linking the client connection state machine). (b) **The autovacuum
launcher pattern reimplemented in extension space** keeps recurring
(pg_cron, pg_squeeze, here) — the fact that core's launcher/per-database-worker
+ shmem-hash + custom-tranche scaffolding is *not* exposed as a reusable helper
is a concrete "core internals aren't exported" finding, parallel to the
`swap_relation_files`-copied-from-core observation in
`[[knowledge/ideologies/pg_squeeze]]`. (c) The hardcoded `Anum_*` table contract
shows the system-catalog attnum discipline leaking into application schema —
fragile, and a candidate cautionary entry in `knowledge/issues`.

## Sources

Fetched 2026-06-10 (branch `main`):

- `https://api.github.com/repos/hapostgres/pg_auto_failover/git/trees/main?recursive=1`
  @ 2026-06-10 → HTTP 200 (tree listing; manifest `src/monitor/health_check.c`
  does not exist → the worker file is `src/monitor/health_check_worker.c`,
  substituted; added `src/monitor/pg_auto_failover.c` for the `_PG_init` story).
- `https://raw.githubusercontent.com/hapostgres/pg_auto_failover/main/README.md`
  @ 2026-06-10 → HTTP 200 (6446 bytes).
- `.../main/src/monitor/pgautofailover.control` @ 2026-06-10 → HTTP 200 (140 bytes).
- `.../main/src/monitor/health_check.c` @ 2026-06-10 → HTTP 404 (does not exist).
- `.../main/src/monitor/health_check_worker.c` @ 2026-06-10 → HTTP 200 (30117 bytes;
  deep-read — state machine, launcher/worker hierarchy, shmem hash, poll loop).
- `.../main/src/monitor/pg_auto_failover.c` @ 2026-06-10 → HTTP 200 (8338 bytes;
  deep-read — `_PG_init`, GUCs, bgworker registration, ProcessUtility hook).
- `.../main/src/monitor/node_metadata.h` @ 2026-06-10 → HTTP 200 (8924 bytes;
  read — node table contract, AutoFailoverNode, candidate-priority, replication
  state accessors).

All cites are `[verified-by-code]` against the fetched `.c`/`.h`/`.control`
except the three-part-architecture framing, the state-machine narrative, and the
multi-version support claim, which are `[from-README]`, and the auth-irrelevance
and crash-recovery rationales, which are `[from-comment]`. The group state
machine (`group_state_machine.c`), `node_metadata.c` (tuple-to-struct + SQL
execution bodies), and `notifications.c` were not fetched; claims about *how* the
monitor rewrites `synchronous_standby_names` and runs the state transitions rest
on the README + header declarations, tagged accordingly.
