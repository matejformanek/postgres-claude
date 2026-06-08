# pgmq — a message queue built entirely from SQL objects, no C and no background worker

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgmq/pgmq` @ branch `main`. All `file:line` cites below point into that
> repo (not `source/`), since this doc characterizes an *external* extension's
> divergence from core idioms. Cites verified against the files fetched on
> 2026-06-08 (see Sources footer). The shipped artifact is a single
> `pgmq-extension/sql/pgmq.sql` (2159 lines of SQL + plpgsql); the separate
> `pgmq-rs/` tree is a Rust *client* library, not part of the backend extension,
> and is out of scope here.

## Domain & purpose

pgmq is "a lightweight message queue. Like AWS SQS and RSMQ but on Postgres"
(`pgmq-extension/pgmq.control:1`) `[verified-by-code]`. It gives SQL-level
`send` / `read` / `pop` / `archive` / `delete` queue semantics with SQS-style
visibility timeouts, FIFO message-group ordering, and topic/wildcard routing —
**"No background worker or external dependencies, just Postgres SQL objects"**
(`pgmq-extension/README.md:15`) `[from-README]`. That self-description is the
whole ideology: where most ambitious extensions reach for C, a `.so`,
`_PG_init`, hooks, or a bgworker, pgmq deliberately implements an entire
broker as schema-qualified tables, composite types, and `plpgsql`/`sql`
functions. It is the inverse of the "host a foreign engine through a pluggable
PG API" extensions (`[[knowledge/ideologies/zombodb]]`,
`[[knowledge/ideologies/pg_duckdb]]`, `[[knowledge/ideologies/cstore_fdw]]`):
pgmq adds **zero** new C surface and rests entirely on existing SQL-engine
guarantees (MVCC, `SKIP LOCKED`, advisory locks, `LISTEN/NOTIFY`).

## How it hooks into PG

It barely "hooks" at all — and that is the point. There is no `.c`, no
`PG_MODULE_MAGIC`, no `_PG_init`, no `module_pathname`-backed shared library
actually loaded; the control file's `module_pathname = '$libdir/pgmq'`
(`pgmq-extension/pgmq.control:3`) is vestigial because no SQL function is
`LANGUAGE C` — every routine is `LANGUAGE plpgsql` or `LANGUAGE sql`. The
control file pins the extension to schema `pgmq`, `relocatable = false`, and
crucially **`superuser = false`** (`pgmq-extension/pgmq.control:4-6`)
`[verified-by-code]`: a non-superuser with `CREATE` on the database can install
it, because nothing it does requires elevated privilege. The build is plain
PGXS — `DATA = $(wildcard sql/*--*.sql)` with the version scraped from the
control file (`pgmq-extension/Makefile:1-3`) `[verified-by-code]`, see the
`extension-development` skill §2.

The runtime "API" is a family of overloaded SQL functions over a fixed
metadata schema:

- `pgmq.meta` — registry row per queue: `queue_name`, `is_partitioned`,
  `is_unlogged`, `created_at` (`pgmq.sql:17-22`).
- `pgmq.message_record` / `pgmq.queue_record` composite types are the return
  shapes (`pgmq.sql:89-104`).
- Each queue is its own dynamically-created table `pgmq.q_<name>` (live) plus
  `pgmq.a_<name>` (archive), created by `pgmq.create_non_partitioned`
  (`pgmq.sql:1172-1238`) `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]` (the C calling convention pgmq
never touches), the `extension-development` skill (the file set it
trims to control + SQL only).

## Where it diverges from core idioms

### 1. The queue *is* a table, manufactured at runtime by `EXECUTE FORMAT(...)`

A queue is not an in-memory ring or a custom storage AM — it is an ordinary
heap table built on demand. `pgmq.create_non_partitioned` runs
`EXECUTE FORMAT('CREATE TABLE IF NOT EXISTS pgmq.%I (...)', qtable)` with
columns `msg_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY, read_ct,
enqueued_at, last_read_at, vt TIMESTAMPTZ, message JSONB, headers JSONB`, then
a matching `pgmq.a_<name>` archive table with an extra `archived_at`, plus a
`(vt ASC)` index on the live table and an `(archived_at)` index on the archive
(`pgmq.sql:1182-1225`) `[verified-by-code]`. Every queue operation is
string-built SQL with `%I`/`%L` placeholders (`pgmq.format_table_name`,
`pgmq.sql:321-331`) executed via `EXECUTE ... USING`. So pgmq's "schema" grows
one pair of real relations per `create()` call — DDL-as-data-plane, where core
subsystems would reach for a fixed catalog and a C storage path. Cross-ref
`[[knowledge/subsystems/access-heap]]` (the heap pgmq stores messages in),
`[[knowledge/idioms/catalog-conventions]]`.

### 2. "Exactly-once within a visibility timeout" is `FOR UPDATE SKIP LOCKED` + an `UPDATE ... RETURNING`, not a lock manager

The central trick: `pgmq.read` selects up to `qty` message ids
`WHERE vt <= clock_timestamp() ... ORDER BY msg_id ASC LIMIT $1 FOR UPDATE SKIP
LOCKED` inside a CTE, then in the same statement `UPDATE`s those rows to push
`vt = clock_timestamp() + <vt interval>`, bump `read_ct`, set `last_read_at`,
and `RETURNING` the message (`pgmq.sql:345-370`) `[verified-by-code]`. `SKIP
LOCKED` lets N concurrent consumers each grab disjoint batches with no explicit
coordination, and the visibility-timeout bump makes a read invisible to others
until it expires — re-implementing SQS semantics purely on row-level locking +
MVCC visibility of the `vt` column. There is no heavyweight queue lock, no
shared-memory state; concurrency safety is delegated wholesale to the executor's
locking. Cross-ref `[[knowledge/idioms/locking-overview]]` (the `SKIP LOCKED` /
row-lock path it leans on), `[[knowledge/architecture/mvcc]]`.

### 3. Queue-creation races are handled with a *transaction* advisory lock, not a catalog lock

Two sessions calling `create()` for the same name race on the `CREATE TABLE`s
and the `pgmq.meta` insert. pgmq guards this with
`pgmq.acquire_queue_lock(queue_name)` (`pgmq.sql:113-120`, called first in
`create_non_partitioned` at `pgmq.sql:1180`) `[verified-by-code]`, a
transaction-scoped advisory lock held to commit — the comment notes "a race
condition would still exist if lock was released before commit"
(`pgmq.sql:110-112`). Using `pg_advisory_xact_lock` keyed on the queue name
rather than relying on `CREATE TABLE IF NOT EXISTS` + `ON CONFLICT DO NOTHING`
alone is a userspace concurrency-control choice on top of the SQL engine.
Cross-ref `[[knowledge/idioms/locking-overview]]` (advisory locks).

### 4. Partitioned queues are outsourced to another extension (pg_partman), discovered dynamically

For high-volume queues pgmq does not implement its own retention/partition
rotation — it defers to `[[knowledge/ideologies/pg_partman]]`.
`create_partitioned` first `PERFORM pgmq._ensure_pg_partman_installed()` (raises
if absent, `pgmq.sql:1333-1340`), builds a `PARTITION BY RANGE` table, then
`EXECUTE FORMAT('SELECT %I.create_parent(...)', pgmq._get_pg_partman_schema())`
and writes retention policy into `<partman>.part_config`
(`pgmq.sql:1371-1426`) `[verified-by-code]`. It even branches on partman's
*major version* — `p_type := case when major_version = 5 then 'range' else
'native' end` (`pgmq.sql:1394-1397`) — and looks the partman schema up at
runtime via `pg_extension` (`pgmq._get_pg_partman_schema`, `pgmq.sql:1045-1053`)
rather than assuming `public`. This is extension-composing-extension: one SQL
extension reaching into another's catalog tables and version-gating its API.
Cross-ref `[[knowledge/ideologies/pg_partman]]`, `[[knowledge/idioms/catalog-conventions]]`.

### 5. `UNLOGGED` queues trade durability for throughput — a per-queue WAL decision exposed in SQL

`pgmq.create_unlogged` is identical to the non-partitioned path except the live
table is `CREATE UNLOGGED TABLE` (`pgmq.sql:1240-1295`, `is_unlogged = true`
recorded in `meta`) `[verified-by-code]`. That lets a caller opt a whole queue
out of WAL (faster sends, but messages vanish on crash) per-queue, at SQL
level. Core's own `pgmq.notify_insert_throttle` bookkeeping table is likewise
`UNLOGGED` (`pgmq.sql:35-42`) because throttle timestamps are
reconstructable. Cross-ref `[[knowledge/architecture/wal]]` (the WAL pgmq
selectively skips), `[[knowledge/subsystems/access-heap]]`.

### 6. Push notifications via a `DEFERRABLE` constraint trigger over `LISTEN/NOTIFY`, with a throttle table

Beyond polling, `enable_notify_insert` attaches a per-queue
`CREATE CONSTRAINT TRIGGER trigger_notify_queue_insert_listeners AFTER INSERT
... DEFERRABLE FOR EACH ROW EXECUTE PROCEDURE pgmq.notify_queue_listeners()`
(`pgmq.sql:1703-1709`) `[verified-by-code]`. The trigger derives the queue name
from `substring(TG_TABLE_NAME from 3)` (stripping the `q_` prefix), and only
fires `PG_NOTIFY('pgmq.'||TG_TABLE_NAME||'.'||TG_OP, NULL)` if a rate-limit
`UPDATE` against the `UNLOGGED` `notify_insert_throttle` table actually changed
a row (`GET DIAGNOSTICS updated_count = ROW_COUNT`, `pgmq.sql:1656-1672`). So
the "do I notify?" decision is itself a throttled SQL `UPDATE`, and consumers
`LISTEN` on a channel named after the queue table. Building backpressure-aware
pub/sub out of constraint triggers + `LISTEN/NOTIFY` + an unlogged counter
table is a pure-SQL substitute for what a C extension would do with a bgworker
or `WaitLatch`. Cross-ref `PG's `LISTEN/NOTIFY` machinery (`commands/async.c`)` (the
`LISTEN/NOTIFY` machinery), `[[knowledge/idioms/error-handling]]`.

### 7. Topic routing implemented with a `GENERATED ... STORED` regex column

`send_topic(routing_key, msg, ...)` (`pgmq.sql:1961+`) routes to queues bound in
`pgmq.topic_bindings`, whose `compiled_regex` column is
`GENERATED ALWAYS AS (... regexp_replace(pattern, ...) ...) STORED`
(`pgmq.sql:48-69`) — wildcard patterns (`*` = one segment, `#` = zero-or-more)
are precompiled to a regex at write time "to avoid runtime compilation on every
send_topic call" (`pgmq.sql:56-58`), with a covering index
`(pattern) INCLUDE (queue_name, compiled_regex)` for index-only scans
(`pgmq.sql:71-73`) `[verified-by-code]`. AMQP-style topic exchange, expressed as
a generated column + covering index instead of any C matching engine. Cross-ref
`[[knowledge/idioms/catalog-conventions]]`, `[[knowledge/subsystems/access-heap]]`.

## Notable design decisions (cited)

- **`send` returns the `msg_id` and is a thin `INSERT ... RETURNING`** over the
  dynamically-named `q_<name>` table; all the delay/headers/batch overloads
  funnel into one 4-arg base via `LANGUAGE sql` wrappers
  (`pgmq.sql:684-750`) `[verified-by-code]` — overload-and-delegate keeps one
  source of truth for the actual INSERT.
- **Messages are `JSONB`, with a separate `JSONB headers` column**
  (`pgmq.sql:89-97`, `1190-1191`) — payloads are schemaless; `read`'s optional
  `conditional JSONB` filter uses the `@>` containment operator inline
  (`pgmq.sql:351-354`), so content-based filtering rides the JSONB operator set
  rather than a custom predicate.
- **`pg_extension_config_dump` marks `meta`, `notify_insert_throttle`, and
  `topic_bindings` as dumpable extension config** (`pgmq.sql:75-85`) — so a
  `pg_dump` of an extension install still captures user-created queue metadata,
  a subtlety many SQL extensions forget. Per-queue `q_*`/`a_*` tables are *not*
  owned by the extension (they're created by function calls, not the install
  script), so they dump as ordinary tables.
- **`pg_monitor` is granted `SELECT` on all pgmq tables + default privileges**
  up front (`pgmq.sql:28-32`), and the comment explains the placement is
  deliberate so a fresh-install `pg_dump` matches the upgrade-path `pg_dump`
  (`pgmq.sql:24-27`) — install-script ordering chosen for dump determinism.
- **FIFO / message-group ordering (`read_grouped*`) is layered on the same
  `SKIP LOCKED` core**, computing the absolute head id per group regardless of
  visibility before locking (`pgmq.sql:122-320`) `[verified-by-code]` — SQS FIFO
  semantics without leaving SQL.
- **Versioning is a long linear chain of `pgmq--X--Y.sql` upgrade scripts**
  (dozens, from `0.7.3` to `1.11.2`; `default_version = '1.11.2'`,
  `pgmq.control:2`) `[verified-by-code]` — textbook `ALTER EXTENSION UPDATE`
  discipline (`extension-development` skill §6), notable only for how
  disciplined a pure-SQL extension stays about it.

## Links into corpus

- `.claude/skills/extension-development/SKILL.md` — pgmq is the minimal-surface
  end of the spectrum: control file + SQL scripts,
  no `.so`, no `_PG_init`, `superuser = false`. A useful counter-example to the
  hook/bgworker-heavy extensions.
- `[[knowledge/idioms/locking-overview]]` — `FOR UPDATE SKIP LOCKED` as the
  exactly-once-within-VT mechanism, plus `pg_advisory_xact_lock` for
  create races. The single most important cross-reference.
- `[[knowledge/architecture/mvcc]]` + `[[knowledge/subsystems/access-heap]]` —
  visibility-timeout reads ride MVCC + the `vt` column; queues are heap tables.
- `[[knowledge/architecture/wal]]` — per-queue `UNLOGGED` opt-out of WAL.
- `PG's `LISTEN/NOTIFY` machinery (`commands/async.c`)` — `LISTEN/NOTIFY` + `DEFERRABLE`
  constraint trigger + throttle table for push delivery.
- `[[knowledge/ideologies/pg_partman]]` — partitioned queues are delegated to
  pg_partman, discovered and version-gated at runtime via `pg_extension`.
- `[[knowledge/idioms/catalog-conventions]]` — `pg_extension_config_dump`,
  reaching into another extension's `part_config`, generated-column topic regex.
- `[[knowledge/ideologies/zombodb]]` + `[[knowledge/ideologies/pg_duckdb]]` +
  `[[knowledge/ideologies/cstore_fdw]]` — the opposite design pole (heavy C /
  foreign-engine embedding); pgmq shows how much can be done with *no* new C.

## Sources

Fetched 2026-06-08 (branch `main`):

- `https://api.github.com/repos/pgmq/pgmq/git/trees/main?recursive=1`
  @ 2026-06-08 → HTTP 200 (tree listing; manifest paths corrected — the
  extension lives under `pgmq-extension/`, `pgmq-rs/` is a separate Rust client).
- `https://raw.githubusercontent.com/pgmq/pgmq/main/README.md`
  @ 2026-06-08 → HTTP 200 (symlink → `pgmq-extension/README.md`).
- `https://raw.githubusercontent.com/pgmq/pgmq/main/pgmq-extension/README.md`
  @ 2026-06-08 → HTTP 200 (366 lines).
- `https://raw.githubusercontent.com/pgmq/pgmq/main/pgmq-extension/pgmq.control`
  @ 2026-06-08 → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/pgmq/pgmq/main/pgmq-extension/sql/pgmq.sql`
  @ 2026-06-08 → HTTP 200 (2159 lines; the full install script).
- `https://raw.githubusercontent.com/pgmq/pgmq/main/pgmq-extension/Makefile`
  @ 2026-06-08 → HTTP 200 (55 lines).

All cites are `[verified-by-code]` against the fetched `pgmq.sql`/`.control`/
`Makefile` (table layout, `SKIP LOCKED` read, advisory create-lock, dynamic
DDL, partman delegation, unlogged path, notify trigger, topic generated column)
except the "no background worker / just SQL objects" framing, which is
`[from-README]` and corroborated by the absence of any `.c` / `LANGUAGE C` in
the install script. The dozens of `pgmq--X--Y.sql` upgrade scripts, the
`pgmq-rs/` Rust client, the test suite, and the docs site were not deep-read.
