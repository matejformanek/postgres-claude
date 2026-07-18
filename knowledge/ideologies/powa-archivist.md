# powa-archivist — a bgworker that turns core cumulative-stats counters into a queryable in-database time series by periodic SPI snapshots

> Ideology note characterizing an *external* extension's divergence from core
> PG idioms. Repo: `powa-team/powa-archivist` @ branch `master`. All `file:line`
> cites point into that repo (fetched files listed in the Sources footer), NOT
> into `source/`. C cites are to `powa.c`; SQL cites are to the install script
> `powa--5.0.0.sql`. Cites verified against files fetched 2026-07-17.

## Domain & purpose

PoWA (PostgreSQL Workload Analyzer) is a two-part system: a UI/collector web app
(`powa-web`, out of scope here) and this extension, **powa-archivist — the
collector half**. `powa.control` describes it as "PostgreSQL Workload
Analyser-core" `[verified-by-code]` (`powa.control:2`). Its job is *not* to
produce metrics of its own. The metrics already exist — `pg_stat_statements`,
`pg_qualstats`, `pg_stat_kcache`, `pg_wait_sampling`, and the core
`pg_stat_all_tables`/`pg_stat_all_indexes`/`pg_stat_user_functions` views all
expose **cumulative counters since last reset**. powa-archivist periodically
*snapshots* those counters into history tables so that later you can subtract two
snapshots and get a per-interval delta — a workload time series. It is,
concretely, an in-database time-series ETL daemon: a background worker that wakes
on a timer and runs one SQL function, `powa_take_snapshot()`, over SPI. The
extension `requires = 'plpgsql, pg_stat_statements, btree_gist'` (`powa.control:4`)
— btree_gist because the history tables are range-indexed by GiST (see below).

## How it hooks into PG

**Single-file C, single bgworker.** The Makefile builds one module,
`MODULES = powa` (`Makefile:11`), so all C lives in `powa.c`; there is no
`powa.h` (it is genuinely absent upstream, a 404). `PG_MODULE_MAGIC` is declared
at `powa.c:56` `[verified-by-code]`.

`_PG_init` (`powa.c:239-328`) registers **one static background worker**
(`powa.c:310-327`): `bgw_flags = BGWORKER_SHMEM_ACCESS |
BGWORKER_BACKEND_DATABASE_CONNECTION` (`powa.c:311-312`), `bgw_start_time =
BgWorkerStart_RecoveryFinished` — commented "Must write to the database"
(`powa.c:313`) — `bgw_library_name = "powa"`, `bgw_function_name = "powa_main"`
(`powa.c:316-317`), `bgw_restart_time = 10` seconds (`powa.c:322`). Because it is
a *static* worker via `RegisterBackgroundWorker` (`powa.c:327`), it only starts
when powa is in `shared_preload_libraries`: the whole registration block is
guarded by `if (!process_shared_preload_libraries_in_progress) return;`
(`powa.c:298-299`) `[verified-by-code]`.

**GUCs** are defined in `_PG_init` before the guard. Two are always defined
because they are also used by the SQL datasource functions when a *remote*
collector calls `powa_take_snapshot()` by hand: `powa.ignored_users`
(`PGC_SIGHUP`, `powa.c:248-252`) and `powa.debug` (`PGC_USERSET`,
`powa.c:254-258`). Then `powa.frequency` (ms between snapshots, default 300000,
`PGC_SUSET`, `GUC_UNIT_MS`, `powa.c:265-275`), `powa.coalesce` (records grouped
per aggregate row, default 100, `powa.c:277-281`), and `powa.retention` (purge
horizon in minutes, default one day, `GUC_UNIT_MIN`, `powa.c:283-290`). A GUC
check hook enforces a floor: `powa.frequency` must be `>= MIN_POWA_FREQUENCY`
(5000 ms) or the sentinel `-1` (`powa.c:60`, `powa.c:112-119`). `powa.database`
(the workload-repository DB, default `"powa"`, `PGC_POSTMASTER`) is defined only
inside the preload guard (`powa.c:301-305`).

**The snapshot loop.** `powa_main` (`powa.c:331-505`) is the worker entry point,
marked `pg_noreturn`/`pg_attribute_noreturn` per PG version (`powa.c:87-93`). It
exits immediately under binary upgrade (`IsBinaryUpgrade`, `powa.c:338-342`),
installs a SIGHUP handler (`powa.c:350`), then connects with
`BackgroundWorkerInitializeConnection(powa_database, NULL, 0)` (`powa.c:388-392`)
`[verified-by-code]`. It sets `application_name = 'PoWA - collector'` via an SPI
`SET` (`powa.c:66`, `powa.c:405-406`). Before the loop it resolves the powa
schema once (`powa_get_snapshot_query`, `powa.c:179-231`) and builds the literal
statement it will run every tick: `SET search_path TO pg_catalog; SELECT
<nsp>.powa_take_snapshot()` (`powa.c:228-229`). The main loop (`powa.c:426-504`)
each pass: opens a transaction, `SPI_connect`, `PushActiveSnapshot`, then
`SPI_execute(query_snapshot.data, false, 0)` — i.e. calls the SQL snapshot
driver over SPI (`powa.c:438-448`) `[verified-by-code]` — commits, then sleeps in
an inner loop on `WaitLatch(&MyProc->procLatch, WL_LATCH_SET | WL_TIMEOUT |
WL_POSTMASTER_DEATH, us_to_wait/1000, PG_WAIT_EXTENSION)` (`powa.c:489-495`),
recomputing the remaining wait each pass (`compute_next_wakeup`, `powa.c:148-173`)
and calling `CHECK_FOR_INTERRUPTS()` (`powa.c:470`). SIGHUP is handled
cooperatively: the handler sets a flag and the latch (`powa.c:513-524`);
`powa_process_sighup` re-reads config and, if `powa.frequency` flipped from `-1`
back to a real value, forces an immediate snapshot (`powa.c:532-553`). When
`powa.frequency == -1` the worker treats PoWA as deactivated and parks on a
one-hour latch wait (`powa.c:132-133`, `powa.c:365-382`).

## Where it diverges from core idioms

### 1. It is a meta-observer: it produces no metrics, it snapshots *other* extensions' cumulative views on a timer

This is the central divergence. Core stats extensions each own a counter and a
view. powa-archivist owns *neither*; it is a scheduler + ETL that reads everyone
else's views. The set of things it snapshots is **data, not code** — a registry
table `powa_extension_functions` maps each source extension to the SQL functions
that snapshot / aggregate / purge / reset it (`powa--5.0.0.sql:154-191`)
`[verified-by-code]`. The rows literally enumerate the siblings it collects from:
`pg_stat_statements`, `pg_qualstats`, `pg_stat_kcache`, `pg_wait_sampling`, plus
`pg_track_settings` (`powa--5.0.0.sql:170-191`). A parallel `powa_modules` /
`powa_module_functions` registry (`powa--5.0.0.sql:212-255`) covers cluster-wide
core catalogs (`pg_database`, `pg_role`), and `powa_db_modules` covers the
per-database core views `pg_stat_all_tables` / `pg_stat_all_indexes` /
`pg_stat_user_functions` (`powa--5.0.0.sql:271-323`). A driver need only iterate
the registry; adding a new source extension is an INSERT, not a recompile.

### 2. The snapshot logic lives in SQL/PL-pgSQL, not C

`powa.c` is ~774 lines and does almost no analytics: it schedules, connects, and
runs one SQL call. The actual work — reading source views, computing rows,
inserting history, coalescing, purging — is thousands of lines of PL/pgSQL in
`powa--5.0.0.sql` (7369 lines). The driver `powa_take_snapshot(_srvid integer =
0)` (`powa--5.0.0.sql:3333-3592`) is pure PL/pgSQL: it bumps a sequence
(`coalesce_seq`, `powa--5.0.0.sql:3373-3378`), then loops over the registry
selecting all enabled `operation='snapshot'` functions ordered by `priority, name`
and `EXECUTE format('SELECT %s.%I(%s)', r.schema, r.funcname, _srvid)` on each
(`powa--5.0.0.sql:3392-3430`) `[verified-by-code]`. Each call is wrapped in its
own `BEGIN … EXCEPTION WHEN OTHERS` block that captures `GET STACKED DIAGNOSTICS`
and appends to an error array rather than aborting the whole snapshot
(`powa--5.0.0.sql:3406-3429`) — one flaky source view must not lose everyone
else's snapshot. The C worker never sees these errors as failures; the count is
returned as the function result (`powa--5.0.0.sql:3578-3589`). Compared to the
core idiom of C stats hooks, this is a deliberate inversion: dispatch and the
entire ETL are late-bound SQL.

### 3. Cumulative "counters since reset" become a two-tier time series

Each source has a `_src` function that shapes the foreign view into a row type,
a `_snapshot` function that appends one sample to a `*_history_current` staging
table, an `_aggregate` function that rolls `powa.coalesce` samples into one
array-valued `*_history` row, and a `_purge` function that deletes rows past
retention. For `pg_stat_statements`: `powa_statements_src` reads
`<nsp>.pg_stat_statements` directly with version-branched column lists
(`powa--5.0.0.sql:3680-3886`, note the `v_pgss` extension-version array driving
which columns exist, `powa--5.0.0.sql:3729-3799`); `powa_statements_snapshot`
INSERTs one `powa_statements_history_record` per (queryid,dbid,userid) into
`powa_statements_history_current` and a per-database roll-up into
`..._current_db`, all in a single CTE (`powa--5.0.0.sql:3888-3990`). The staging
row is the *raw cumulative counter value at snapshot time*, not a delta — deltas
are computed downstream by the UI over the stored series.

The **history record is a composite type**, and history rows store an *array* of
them plus the per-range min/max: `powa_statements_history` has `records
powa_statements_history_record[]`, `mins_in_range`, `maxs_in_range`, and a
`coalesce_range tstzrange` (`powa--5.0.0.sql:2055-2069`), GiST-indexed on `(srvid,
queryid, coalesce_range)` (`powa--5.0.0.sql:2071`) — which is why `btree_gist` is
a hard requirement. `powa_statements_aggregate` builds these rows with
`array_agg(record)` and `tstzrange(min((record).ts), max((record).ts),'[]')`,
then deletes the staging rows it consumed (`powa--5.0.0.sql:5606-5671`)
`[verified-by-code]`. Storing a variable-length array of composites in one heap
row is itself un-core-like; the extension even forces `SET STORAGE MAIN` on the
min/max columns to keep them off TOAST (`powa--5.0.0.sql:2068-2069`).

### 4. Coalesce + purge are phase-offset by one snapshot, driven by a modular counter

Rather than a separate timer, aggregation and purge piggyback on the snapshot
tick using the monotonic `coalesce_seq` in `powa_snapshot_metas`
(`powa--5.0.0.sql:902-912`). Aggregate runs when `purge_seq % v_coalesce = 0`
(`powa--5.0.0.sql:3433-3487`); purge runs on the *next* tick, `purge_seq %
v_coalesce = 1` (`powa--5.0.0.sql:3490-3543`) — "we also purge, at the pass after
the coalesce" (`powa--5.0.0.sql:3489`) `[from-comment]`. Purge deletes history
whose `upper(coalesce_range) < now() - retention`
(`powa--5.0.0.sql:5476-5497`), retention coming from the `powa.retention` GUC (or
the per-server column in remote mode). So the three ETL phases are a single
PL/pgSQL function multiplexed by one integer counter, not three schedulers.

### 5. Concurrency control is one advisory `SELECT … FOR UPDATE NOWAIT` row-lock

There is no LWLock or shmem state guarding a snapshot. `powa_take_snapshot` first
calls `powa_prevent_concurrent_snapshot`, which does `SELECT 1 FROM
powa_snapshot_metas WHERE srvid=_srvid FOR UPDATE NOWAIT` and turns
`lock_not_available` into "a concurrent snapshot is probably running"
(`powa--5.0.0.sql:3296-3331`, called at `powa--5.0.0.sql:3371` and again inside
every `_snapshot`/`_aggregate`/`_purge` function, e.g.
`powa--5.0.0.sql:3901`, `:4026`, `:5474`, `:5615`) `[verified-by-code]`. Mutual
exclusion is a plain row lock on a metadata table — appropriate because all the
state is ordinary tables, but unlike the shmem-latch coordination a core
subsystem would use.

### 6. Nested / remote-server mode: the same SQL, two data paths

powa-archivist can act as a *central repository* for many remote PG servers whose
stats are shipped in by an external Python collector (`powa-collector`). The
schema is keyed by `srvid` throughout, with `powa_servers` holding remote
connection info and per-server `frequency`/`powa_coalesce`/`retention`
(`powa--5.0.0.sql:120-136`); the local server is the reserved row `id = 0`
(`powa--5.0.0.sql:136`). Every `_src` function branches on `_srvid`: `_srvid = 0`
reads the live foreign view in-process, `_srvid != 0` reads from an **UNLOGGED**
`*_src_tmp` staging table the remote collector has filled (e.g.
`powa_statements_src_tmp`, `powa--5.0.0.sql:1928`; branch at
`powa--5.0.0.sql:3729` vs the remote path that DELETEs `_src_tmp` after
consuming, `powa--5.0.0.sql:3984-3986`). The C bgworker only ever drives `_srvid
= 0` (`powa.c:229` hard-codes the no-arg call); remote srvids are driven by the
external daemon calling the same `powa_take_snapshot(srvid)` — which is exactly
why the comment at `powa.c:233-238` explains the extension can now be loaded
*outside* `shared_preload_libraries` so the daemon can reach the datasource
functions.

## Notable design decisions (cited)

- **The C worker fools pgstat on old PG.** For PG < 15, `powa_stat_common`
  temporarily overwrites the global `MyDatabaseId`, calls
  `pgstat_fetch_stat_dbentry(dbid)` to pull another database's table/function
  stats, then restores it inside a `PG_TRY/PG_CATCH` and re-clears the snapshot
  cache (`powa.c:607-771`, comment at `powa.c:608-644`: "The stat collector isn't
  suppose to act this way … we need to fool it") `[from-comment]`. This whole
  SRF-in-C path (`powa_stat_user_functions` / `powa_stat_all_rel`,
  `powa.c:555-565`) exists only because pre-15 pgstat refused cross-database
  reads; PG 15+ compiles it out (`#if PG_VERSION_NUM < 150000`, `powa.c:575`,
  `:607`, `:771`).
- **Version-drift resilience is table-driven.** `powa_db_module_src_queries`
  stores multiple `query_source` strings keyed by `min_version`, and
  `powa_db_functions` picks the highest `min_version <= server_version_num`
  (`powa--5.0.0.sql:325-420`). The same pattern appears inline in
  `powa_statements_src` (pgss 1.8 / 1.10 / 1.11 column branches,
  `powa--5.0.0.sql:3736-3799`). The collector adapts to whatever version of the
  source extension is installed, at runtime, from data.
- **Reset-after-read for non-cumulative sources.** `pg_qualstats` counters are
  not cumulative, so `powa_qualstats_snapshot` resets the source after each
  local snapshot; the registry carries the reset as a `query_cleanup` string
  `'SELECT {pg_qualstats}.pg_qualstats_reset()'` for the remote path
  (`powa--5.0.0.sql:176`), while the local path resets inline (comment
  `powa--5.0.0.sql:6792-6794`, `powa--5.0.0.sql:6795-6801`). (Note the local
  reset is written `PERFORM format('%I.pg_qualstats_reset()', v_schema)` at
  `powa--5.0.0.sql:6800`, which evaluates the formatted string but does not
  `EXECUTE` it — an apparent latent bug `[verified-by-code]`.)
- **Snapshot tables are marked for dump selectively.** History tables are
  registered with `pg_extension_config_dump` so `pg_dump` preserves collected
  data (`powa--5.0.0.sql:1412`), and `powa_snapshot_metas` is dumped only for
  remote servers, `WHERE srvid > 0` (`powa--5.0.0.sql:3147`) — the local repo
  rebuilds its own row 0.
- **Frequency drift correction.** The worker advances its ideal wakeup reference
  by exactly `time_powa_frequency` each cycle rather than resetting to `now()`,
  "so errors don't add up" (`powa.c:499-503`) `[from-comment]`.
- **`superuser = true`, `relocatable = false`** in the control file
  (`powa.control:5-6`) — the schema is chosen at `CREATE EXTENSION` time and
  every function pins `SET search_path = pg_catalog` (e.g.
  `powa--5.0.0.sql:3592`), a hardening idiom against search-path attacks on a
  superuser-owned extension.

## Links into corpus

- `[[pg_qualstats]]` — a PoWA sibling; powa-archivist snapshots its
  (non-cumulative) qual stats and resets it after each read
  (`powa--5.0.0.sql:176`, `:6792-6801`).
- `[[pg_wait_sampling]]` / `[[pg_stat_kcache]]` — the other external cumulative
  sources in the snapshot registry (`powa--5.0.0.sql:180-191`).
- `[[pg_cron]]` — architectural cousin: also a static bgworker on a WaitLatch
  timer running SQL, but pg_cron opens libpq client connections and runs
  arbitrary user SQL; powa-archivist stays in-process over SPI and runs one
  fixed ETL function.
- `.claude/skills/bgworker-and-extensions/SKILL.md` — `RegisterBackgroundWorker`,
  `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `BgWorkerStart_RecoveryFinished`, `bgw_restart_time`,
  `BackgroundWorkerInitializeConnection`, and the SIGHUP-flag + WaitLatch loop
  powa.c implements (`powa.c:310-505`).
- `[[knowledge/idioms/spi]]` — the worker's whole job is one SPI call per tick
  (`powa.c:438-448`); every registry-driven ETL function is SPI-reachable SQL.
- `.claude/skills/pgstat-framework/SKILL.md` — the core cumulative-stats system
  (counters-since-reset, `pg_stat_*` views, `pgstat_fetch_stat_dbentry`) that
  powa-archivist snapshots on top of, and directly pokes at in
  `powa_stat_common` on PG < 15 (`powa.c:607-771`).
- `.claude/skills/gucs-config/SKILL.md` — `DefineCustom*Variable`, unit flags
  (`GUC_UNIT_MS`, `GUC_UNIT_MIN`), a check hook, and `PGC_POSTMASTER`/`PGC_SUSET`
  contexts (`powa.c:248-305`).

## Sources

Fetched 2026-07-17 (branch `master`, via
`https://raw.githubusercontent.com/powa-team/powa-archivist/master/<path>`):

- `powa.c` → HTTP 200 (774 lines). All C cites `[verified-by-code]` against this
  file: bgworker registration, the WaitLatch snapshot loop, SPI dispatch, the
  GUC set, and the pre-15 `MyDatabaseId`-fooling SRF path.
- `powa--5.0.0.sql` → HTTP 200 (7369 lines). All SQL cites verified against this
  install script: the registry tables, `powa_take_snapshot`, the
  `_src`/`_snapshot`/`_aggregate`/`_purge` families, history composite types +
  GiST tables, coalesce/purge phase-offset logic, concurrency lock, and remote
  `_src_tmp` staging.
- `powa.control` → HTTP 200 (7 lines): `requires`, `superuser`, `relocatable`,
  `default_version = '5.2.0'`.
- `Makefile` → HTTP 200: `MODULES = powa` (single C module), `DATA = *--*.sql`,
  PGXS wiring.
- `README.md` → HTTP 200 (16 lines): points at readthedocs; confirms this is the
  "core extension of the PoWA project"; no code detail beyond that.

Gaps / 404s: `powa.h` (does not exist — powa.c is self-contained), `init.sql`
(does not exist). The install script fetched is `powa--5.0.0.sql`; the control
file's `default_version` is `5.2.0`, so 5.0.0→5.2.0 upgrade scripts exist but
were not fetched — the divergence-carrying structures (registry, snapshot driver,
history model, bgworker) are established in the base script and cited from it.
The external `powa-collector` Python daemon that drives remote `srvid != 0`
snapshots is a separate project and is described here only as `[inferred]` from
the SQL's remote-mode branches and the `powa.c:233-238` comment.
