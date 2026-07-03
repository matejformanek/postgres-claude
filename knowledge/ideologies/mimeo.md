# mimeo — per-table logical replication implemented entirely in userland PL/pgSQL over dblink, years before core had any

> Headline: mimeo is a *pull-based, per-table* replication engine that lives
> wholly inside SQL. There is no C, no `_PG_init`, no background worker, no WAL
> reader and no logical-decoding slot. A destination database reaches across
> `dblink` into each source, and PL/pgSQL functions (the `*_maker` /
> `refresh_*` / `*_destroyer` trios) stand up triggers + queue tables on the
> source and replay changes locally — six replication "shapes" (snapshot,
> inserter, updater, dml, logdel, table) each with its own config table. It is
> the pre-2017 answer to "I need to copy *these* tables, not the whole cluster,"
> written before core logical replication (PG 10) existed.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `omniti-labs/mimeo` @ branch `master` (79★, PL/pgSQL), fetched
> 2026-07-03. All `file:line` cites point into that repo, not `source/`.
> Caveat: fetched via `raw.githubusercontent.com` only — the GitHub API tree
> endpoint, codeload tarballs, and HTML tree views are all 403 in this
> environment, so the file list could not be enumerated; files were probed by
> guessed path. Files read: `README.md`, `mimeo.control`, `doc/mimeo.md`,
> `sql/functions/{dml_maker,refresh_dml,refresh_snap,snapshot_maker,
> refresh_inserter}.sql`, `sql/tables/tables.sql`. Many sibling function files
> (`updater_maker`, `logdel_maker`, `table_maker`, the `*_destroyer`s, the
> maintenance functions) were not fetched; claims about them rest on
> `doc/mimeo.md` and are tagged accordingly.

## Domain & purpose

mimeo "provides specialized, per-table replication between PostgreSQL
instances… snapshot (whole table copy), incremental (based on an incrementing
timestamp or id), and DML (inserts, updates and deletes)" (`README.md:6`)
`[from-README]`. Its niche is the gap core left open for most of Postgres's
history: copying a *chosen subset of tables* from *any number of source
databases* into one destination where mimeo is installed (`doc/mimeo.md:7`)
`[from-README]`, with per-table control over method, column filtering, row
conditions, and batch size. It requires only PostgreSQL 9.1+ and the `dblink`
extension (`README.md:15`; `mimeo.control:3` declares `requires = 'dblink'`)
`[verified-by-code]`, and strongly recommends `pg_jobmon` for an audit trail
(`README.md:8,17`) `[from-README]`. Current `default_version = '1.5.1'`
(`mimeo.control:1`) `[verified-by-code]`.

## How it hooks into PG

It (almost) doesn't — and that is the whole point. mimeo hooks into no backend
extension point:

- **No C at all.** There is no shared library, so no `_PG_init`, no GUCs, no
  `shared_preload_libraries` entry, and no hooks (`ProcessUtility_hook` etc.).
  The `.control` file declares `requires = 'dblink'` and `relocatable = false`
  (`mimeo.control:3-4`) `[verified-by-code]`; everything shipped is PL/pgSQL +
  SQL DDL. Contrast a C extension like `[[pglogical]]` or `[[pgactive]]`, which
  register bgworkers and tap the logical-decoding callback API.
- **No background worker / no scheduler of its own.** Nothing runs on a timer
  inside the server. Refreshes fire only when something calls a `refresh_*`
  function. A bundled Python script `run_refresh.py` is the intended driver,
  reading each job's `period` from its config row and invoking the matching
  refresh (`doc/mimeo.md:31,409-417`) `[from-README]`; in practice that script
  is run from external cron. So the scheduling tier is *outside* Postgres
  entirely — the opposite of `[[pg_partman]]`'s optional in-server bgworker or
  `[[pg_cron]]`'s launcher.
- **`dblink` is the only transport.** Every source interaction — reading source
  rows, creating remote triggers/queue tables, closing the loop — goes through
  `dblink_connect` / `dblink_exec` / `dblink_open` / `dblink_fetch`
  (`sql/functions/dml_maker.sql:105,242-248`;
  `sql/functions/refresh_dml.sql:257-279`) `[verified-by-code]`. mimeo is a
  `dblink` *client program* that happens to be packaged as an extension.
  Cross-ref `[[knowledge/subsystems/contrib-dblink]]`.
- **The only backend machinery it leans on is advisory locks + SPI-implicit
  PL/pgSQL execution.** Refreshes serialize themselves with a transactional
  advisory lock via `concurrent_lock_check` (`refresh_dml.sql:59-60`)
  `[verified-by-code]`, the same primitive core exposes to any SQL user.

## Where it diverges from core idioms

The central divergence: **mimeo reimplements change-data-capture in userland
SQL rather than reading the WAL.** Core's logical replication (PG 10+) decodes
the WAL through a replication slot and an output plugin; mimeo predates that and
instead materializes changes with *ordinary table triggers and a queue table on
the source*. The six methods trade off how much source cooperation they need:

- **Snapshot** — whole-table copy with a **double-buffered view swap**.
  `refresh_snap` keeps two physical tables `<dest>_snap1` / `<dest>_snap2` and a
  view over one of them; each run truncates the *non-active* table
  (`refresh_snap.sql:264-265`), `dblink_fetch`es the full source into it
  (`:314-318`), then `CREATE OR REPLACE VIEW … AS SELECT * FROM <new snap>` to
  flip readers atomically (`:357`), and finally truncates the old table
  (`:405`) `[verified-by-code]`. It can skip the pull entirely when source
  `n_tup_ins/upd/del` stats show no DML since last run (requires
  `track_counts`) (`doc/mimeo.md:9`; `refresh_snap.sql:275-282,111-113`)
  `[verified-by-code]`. This is the only method that auto-replicates column
  add/drop/rename (`doc/mimeo.md:9`) `[from-README]`.
- **Inserter / updater (incremental)** — for tables with a monotonic timestamp
  or serial "control column." Each run pulls rows above the stored `last_value`,
  minus a `boundary` guard interval (default 10 min / 1) so in-flight
  transactions on the source aren't missed (`doc/mimeo.md:11-13`;
  config columns `boundary`/`last_value` in
  `sql/tables/tables.sql:53-54,65-66,81-82`) `[verified-by-code]`. Deletes are
  invisible to these methods (`doc/mimeo.md:11`) `[from-README]`.
- **DML / logdel** — the trigger-based CDC path. `dml_maker` reaches into the
  source over `dblink` and **creates a queue table, a `SECURITY DEFINER`
  trigger function, and an `AFTER INSERT OR UPDATE OR DELETE` trigger** on the
  source table; the trigger writes the changed row's primary-key values into the
  queue (`dml_maker.sql:185-248`) `[verified-by-code]`. `refresh_dml` then reads
  `DISTINCT` keys where `processed = true` from the queue, pulls the current
  rows, `DELETE`s the matching destination rows and re-inserts, then clears the
  processed queue rows on the source (`refresh_dml.sql:256,290,374`)
  `[verified-by-code]`. `logdel` is the same but never deletes on the
  destination — it stamps a `mimeo_source_deleted` timestamp instead, keeping a
  tombstone history (`doc/mimeo.md:16`) `[from-README]`.
- **Table** — brute-force `TRUNCATE` + full repull, no keys/triggers/control
  column needed; positioned as a dev-convenience, "much less efficient"
  (`doc/mimeo.md:18`) `[from-README]`.

Other idiom divergences worth naming:

- **The maker / refresh / destroyer triad is the lifecycle unit, not
  CREATE/ALTER/DROP.** Each method ships `<m>_maker()` (provision source +
  dest + config row), `refresh_<m>()` (one replication pass), and
  `<m>_destroyer()` (tear down, optionally keeping the dest table)
  (`doc/mimeo.md:76-249`) `[from-README]`. The maker even self-heals: on error
  it drops any remote trigger/queue/function it created (`dml_maker.sql:382-395`)
  `[verified-by-code]`.
- **Config lives in an inheritance hierarchy of catalog-like tables, not in
  `pg_catalog`.** `refresh_config` is an abstract parent with a `DO INSTEAD
  NOTHING` rule blocking direct inserts (`tables.sql:18-31`); each method has a
  child table (`refresh_config_snap`, `_inserter_time`, `_updater_serial`,
  `_dml`, `_logdel`, `_table`) added via `INHERITS`
  (`tables.sql:33-130`) `[verified-by-code]`. Every config table is registered
  with `pg_extension_config_dump` so `pg_dump` preserves user config across
  dump/restore (`tables.sql:15,30,34,…`) `[verified-by-code]` — the idiomatic
  way an extension marks its data tables as user data.
- **No WAL, no on-disk format, no AM, no catalog columns.** mimeo adds zero
  storage-engine surface. Its "replication state" is rows in its own config
  tables plus the remote queue tables — all ordinary heap. Contrast
  `[[decoderbufs]]` / `[[wal2json]]`, which are output plugins bound to the WAL
  decoding pipeline.

## Notable design decisions

- **Source-side triggers are `SECURITY DEFINER`** so that any writer to the
  source table (not just the mimeo role) can insert into the queue table
  (`dml_maker.sql:198`; `doc/mimeo.md:81`) `[verified-by-code]`. This is the
  load-bearing trick that lets DML capture work without granting every app role
  write access to the mimeo schema.
- **Queue trigger records only primary-key columns**, and on `UPDATE` records
  the old key too only when a key column actually changed (edge case for
  composite keys) (`dml_maker.sql:201-231`) `[verified-by-code]`. The refresh
  then re-fetches full current rows by key rather than shipping row images
  through the queue — smaller queue, at the cost of a second source read.
- **DML/logdel require a primary key or unique index; it's auto-discovered over
  dblink** via `fetch_replication_key`, or supplied manually with
  `p_pk_name`/`p_pk_type` (needed for views, which have no pk catalog entry)
  (`dml_maker.sql:137-148`; `doc/mimeo.md:25,80`) `[verified-by-code]`.
- **Multi-destination support with a hard 100-destination cap**, implemented by
  suffixing queue-table names `_q00.._q99` and looping to find a free one
  (`dml_maker.sql:168-183`; `doc/mimeo.md:83`) `[verified-by-code]` — each extra
  destination means another trigger firing on the source, an explicit
  write-amplification warning.
- **Advisory-lock self-serialization with configurable wait semantics.** Every
  refresh takes a transactional advisory lock first and exits cleanly (logging a
  WARNING to pg_jobmon) if another run holds it; `p_lock_wait` picks
  fail-fast / bounded-wait / wait-forever (`refresh_dml.sql:59-78`;
  `doc/mimeo.md:29,278-286`) `[verified-by-code]`.
- **Batch limiting + a "75% of limit" backpressure warning** so operators can
  tell replication is falling behind (`refresh_dml.sql:362-367`;
  `doc/mimeo.md:170`) `[verified-by-code]`.
- **DST-aware pause window for time-based incremental.** Non-UTC servers set
  `dst_active` and pause replication 00:30–02:30 on DST-change mornings to avoid
  the ambiguous hour, tunable via `dst_start`/`dst_end`
  (`doc/mimeo.md:12`; `tables.sql:55-57,83-85`) `[verified-by-code]`.
- **`search_path` is pinned then restored** around each function body (set to
  the extension schema + jobmon + dblink + public, restored in the exception
  handler) (`dml_maker.sql:67-68,350,356-360`) `[verified-by-code]` — the
  security-hygiene idiom for `SECURITY`-sensitive PL/pgSQL.
- **Soft dependency on `pg_jobmon`**: if installed, every maker/refresh logs
  step-by-step to it; if absent, jobmon calls are skipped and `v_jobmon` falls
  to false (`dml_maker.sql:89-95`) `[verified-by-code]` — same optional-sibling
  posture `[[pg_partman]]` (same OmniTI / Keith Fiske lineage) takes.
- **Legacy multi-version straddle.** `extras/` ships `*_pre90` / `_81` variants
  of the maker/refresh functions and `array_agg` polyfills so a pre-9.0 / 8.x
  server can be the *source* — mimeo doubling as a cross-major upgrade tool
  (`doc/mimeo.md:419-456`) `[from-README]`.

## Links into corpus

- `[[pg_partman]]` — same author (Keith Fiske) and OmniTI lineage, same
  "automation-as-PL/pgSQL + config tables + optional pg_jobmon" house style; the
  natural sibling. pg_partman adds an in-server bgworker for scheduling, mimeo
  externalizes scheduling to `run_refresh.py`/cron.
- `[[pglogical]]`, `[[pgactive]]` — the C, WAL-decoding, bgworker-driven
  logical-replication frameworks mimeo is the userland antithesis of. Where they
  stream the WAL, mimeo polls tables over dblink and captures DML with triggers.
- `[[decoderbufs]]`, `[[wal2json]]` — logical-decoding output plugins bound to
  core's WAL pipeline; contrast with mimeo's trigger+queue CDC that touches no
  WAL.
- `[[synchdb]]` — another "reach into a foreign source and land changes here"
  CDC extension, but engine-embedded (Debezium/JVM in a bgworker) vs mimeo's
  pure-SQL/dblink pull.
- `[[pg_cron]]` — the in-server scheduler mimeo lacks; a common pairing is
  driving mimeo's `refresh_*` calls from pg_cron instead of external cron.
- `[[knowledge/subsystems/contrib-dblink]]` — the sole transport mimeo is built
  on (`dblink_connect/exec/open/fetch`).
- `[[knowledge/subsystems/replication]]` — core's native logical replication,
  the capability that eventually overlapped mimeo's niche.
- `[[knowledge/idioms/spi]]` — the SPI layer that PL/pgSQL's `EXECUTE` /
  implicit query execution rides on; mimeo's entire engine is SPI-mediated
  dynamic SQL.
- `[[knowledge/idioms/trigger-firing-order]]` — mimeo's source-side
  `AFTER INSERT OR UPDATE OR DELETE` queue trigger is core CDC via ordinary
  triggers.

## Sources

- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/README.md`
  — HTTP 200 (60 lines).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/mimeo.control`
  — HTTP 200 (4 lines; `default_version 1.5.1`, `requires = 'dblink'`).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/doc/mimeo.md`
  — HTTP 200 (457 lines; full reference — methods, functions, config tables).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/dml_maker.sql`
  — HTTP 200 (419 lines; remote trigger/queue provisioning, SECURITY DEFINER).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/refresh_dml.sql`
  — HTTP 200 (438 lines; advisory lock, dblink cursor, queue replay).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/refresh_snap.sql`
  — HTTP 200 (464 lines; double-buffer snap tables + view swap).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/snapshot_maker.sql`
  — HTTP 200 (144 lines).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/refresh_inserter.sql`
  — HTTP 200 (fetched, not deep-read).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/tables/tables.sql`
  — HTTP 200 (131 lines; config inheritance hierarchy + pg_extension_config_dump).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/mimeo.sql`
  — HTTP 404 (no bundled monolithic install script at this path).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/sql/functions/dml_create_objects.sql`
  — HTTP 404 (guessed name; not present).
- `https://raw.githubusercontent.com/omniti-labs/mimeo/master/doc/howto.md`
  — HTTP 404 (quickstart referenced by README but not at this path).

**Gaps:** the file tree could not be listed (API 403), so the SQL function set
was probed by name — `updater_maker`, `logdel_maker`, `table_maker`, all six
`*_destroyer` functions, and the maintenance functions
(`validate_rowcount`, `check_source_columns`, `concurrent_lock_check`,
`snapshot_monitor`) were characterized only from `doc/mimeo.md`, not read. The
`updater`/`logdel` refresh internals are inferred by analogy to the read
`refresh_dml`/`refresh_snap`.
